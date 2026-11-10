"""podium: a control panel for lobster sessions, a local web page that only ever calls conduct.

PLAN.md ("The control panel, podium") is the specification. It serves on 127.0.0.1 only, only while
its Terminal command runs, and every request needs the token in the link it prints. Exit codes: 0
stopped, 2 bad arguments or settings, 4 it could not start serving.
"""

import argparse
import datetime
import errno
import hmac
import html
import http.server
import json
import os
import secrets
import subprocess
import urllib.parse

from bernstein.conduct import day
from bernstein.settings import SettingsRefused, check_port, read_settings

TONES = {"running": "ok", "dormant": "sleep", "quiet": "warn", "stale": "alert", "handed-over": "off", "off": "off"}


def ago(minutes):
    """How long ago a session last checked in, from the listing's whole minutes."""
    if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 0:
        return "at an unknown time"
    if minutes == 0:
        return "just now"
    if minutes < 60:
        return f"{minutes} min ago"
    if minutes < 1440:
        hours, rest = divmod(minutes, 60)
        return f"{hours} h {rest} min ago" if rest else f"{hours} h ago"
    return f"{minutes // 1440} d ago"


def stamp(text):
    """lobster-mail's UTC stamp as a time, or None when the text is not one."""
    try:
        when = datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        return None
    return when.replace(tzinfo=datetime.timezone.utc)


def clock(when, now):
    """A time of day in UTC, with the day when it is not today's."""
    text = f"{when:%H:%M} UTC"
    return text if when.date() == now.date() else f"{text} on {day(when)}"


def badge(row, now):
    """(words, tone) for a row's state. A running session's own report takes the badge, until its
    finish time passes: after that it is overdue, not trusted."""
    state = row["state"]
    said = row.get("reported")
    if state != "running" or not said:
        return state.replace("-", " "), TONES.get(state, "off")
    status = str(said.get("status", ""))
    until = said.get("until")
    if not until:
        return status, "busy"
    when = stamp(until)
    if when is None:
        return f"{status} until {until}", "busy"
    if when < now:
        return f"{status}, overdue since {clock(when, now)}", "warn"
    return f"{status} until {clock(when, now)}", "busy"


def groups(rows):
    """The rows as the page lays them out: a card per non-code project with its claws under it (its
    sister first, as the home claw), then claws that serve nobody, then mailboxes whose project
    cannot be read, then bernstein's own."""
    by_name = {r["mailbox"]: r for r in rows}
    cards, lone, unstartable, bernstein = [], [], [], None
    for r in rows:
        if r["mailbox"] == "bernstein":
            bernstein = r
        elif r["kind"] == "non-code":
            claws = [(by_name.get(name, {"mailbox": name, "missing": True}),
                      "home claw" if name == r["sister"] else "claw") for name in r["claws"]]
            cards.append((r, claws))
        elif r["kind"] is None:
            unstartable.append(r)
        elif not r["serves"]:
            lone.append(r)
    return {"cards": cards, "lone": lone, "unstartable": unstartable, "bernstein": bernstein}


def e(text):
    """Anything from outside, as text for the page: never markup."""
    return html.escape(str(text), quote=True)


def row_html(row, now, label=None, claw=False):
    """One mailbox's line on the page. label is what the row is to the card it sits in."""
    start = '<div class="row claw">' if claw else '<div class="row">'
    kind = label or row.get("kind")
    who = f'<div class="who"><span class="name">{e(row["mailbox"])}</span>'
    who += f' <span class="kind">{e(kind)}</span></div>' if kind else "</div>"
    if row.get("missing"):
        return f'{start}{who}<span class="badge off">no mailbox</span></div>'
    words, tone = badge(row, now)
    duty = row.get("duty")
    facts = [f"<li>{e(duty.get('holder'))}, checked in {ago(duty.get('minutes'))}</li>" if duty
             else "<li>nobody on duty</li>",
             f"<li>pace {e(row['pace'])}</li>",
             f'<li class="new">{e(row["new"])} new</li>' if row["new"] else "<li>0 new</li>",
             f"<li>{e(row['open'])} open</li>"]
    if row.get("model"):
        facts.append(f"<li>{e(row['model'])}, {e(row['effort'])}</li>")
    said = row.get("reported")
    if said and row["state"] != "running":
        facts.append("<li>reporting " + e('"' + str(said.get("status", "")) + '"') + "</li>")
    refused = ""
    if row.get("refused") and row["mailbox"] != "bernstein":   # conduct never starts bernstein's own session
        refused = f'<p class="refused">Cannot start: {e(row["refused"])}</p>'
    return (f'{start}{who}<span class="badge {tone}">{e(words)}</span>'
            f'<ul class="facts">{"".join(facts)}</ul>{refused}</div>')


def view(rows, now, error=None):
    """The part of the page that is made again at every refresh: when, then the cards or the error."""
    parts = [f'<p class="asof">As of {now:%H:%M:%S} UTC</p>']
    if error:
        return parts[0] + f'<p class="error">{e(error)}</p>'
    if not rows:
        return parts[0] + '<p class="empty">No mailboxes.</p>'
    found = groups(rows)
    for head, claws in found["cards"]:
        parts.append('<section class="card">' + row_html(head, now)
                     + "".join(row_html(c, now, label, claw=True) for c, label in claws) + "</section>")
    for title, members in (("Lone claws", found["lone"]), ("Cannot be started", found["unstartable"]),
                           ("bernstein", [found["bernstein"]] if found["bernstein"] else [])):
        if members:
            parts.append(f'<h2>{title}</h2><section class="card">'
                         + "".join(row_html(r, now) for r in members) + "</section>")
    return "".join(parts)


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>podium</title>
<style>
:root {
  --bg: #f6f5f1; --card: #ffffff; --ink: #1d1d1b; --muted: #6b6a65; --line: #e3e1da;
  --ok: #1f7a4d; --ok-bg: #e3f3ea; --busy: #5b3fb0; --busy-bg: #ece8fa; --sleep: #44566c; --sleep-bg: #e6ebf1;
  --warn: #8a5a00; --warn-bg: #fbefd3; --alert: #a32020; --alert-bg: #fbe3e3; --off: #6b6a65; --off-bg: #eeede8;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161615; --card: #1f1f1d; --ink: #ecebe6; --muted: #9c9b95; --line: #33322f;
    --ok: #7fd3a5; --ok-bg: #173526; --busy: #b9a6f5; --busy-bg: #2a2247; --sleep: #a9bdd4; --sleep-bg: #232d39;
    --warn: #f0c36a; --warn-bg: #3a2c0c; --alert: #ff9a9a; --alert-bg: #451a1a; --off: #9c9b95; --off-bg: #2a2a27;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif; }
.page { max-width: 62rem; margin: 0 auto; padding: 20px 16px 48px; }
.top { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-bottom: 4px; }
h1 { font-size: 22px; margin: 0; letter-spacing: -0.01em; }
h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: var(--muted);
  margin: 26px 0 8px; font-weight: 600; }
button { font: inherit; color: var(--ink); background: var(--card); border: 1px solid var(--line);
  border-radius: 8px; padding: 6px 14px; cursor: pointer; }
button:hover { border-color: var(--muted); }
button:focus-visible { outline: 2px solid var(--busy); outline-offset: 2px; }
.asof { color: var(--muted); margin: 0 0 14px; font-variant-numeric: tabular-nums; }
.lost, .error { background: var(--alert-bg); color: var(--alert); border-radius: 10px; padding: 12px 14px;
  margin: 0 0 14px; white-space: pre-wrap; }
.empty { color: var(--muted); }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; margin: 0 0 12px;
  overflow: hidden; }
.row { display: grid; grid-template-columns: minmax(11rem, 1.1fr) minmax(8rem, auto) 2.4fr;
  gap: 4px 16px; align-items: center; padding: 12px 16px; }
.row + .row { border-top: 1px solid var(--line); }
.row.claw { background: color-mix(in srgb, var(--bg) 45%, var(--card)); }
.row.claw .who { padding-left: 18px; }
.who { min-width: 0; }
.name { font-weight: 600; overflow-wrap: anywhere; }
.kind { color: var(--muted); font-size: 13px; white-space: nowrap; }
.badge { justify-self: start; font-size: 13px; font-weight: 600; border-radius: 999px; padding: 2px 10px;
  color: var(--off); background: var(--off-bg); }
.badge.ok { color: var(--ok); background: var(--ok-bg); }
.badge.busy { color: var(--busy); background: var(--busy-bg); }
.badge.sleep { color: var(--sleep); background: var(--sleep-bg); }
.badge.warn { color: var(--warn); background: var(--warn-bg); }
.badge.alert { color: var(--alert); background: var(--alert-bg); }
.facts { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 2px 14px;
  color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
.facts .new { color: var(--ink); font-weight: 600; }
.refused { grid-column: 1 / -1; margin: 2px 0 0; color: var(--alert); font-size: 13px; overflow-wrap: anywhere; }
@media (max-width: 640px) {
  .row { grid-template-columns: 1fr auto; }
  .facts { grid-column: 1 / -1; }
  .row.claw .who { padding-left: 12px; }
}
</style>
</head>
<body>
<div class="page">
<header class="top"><h1>podium</h1><button id="refresh" type="button">Refresh</button></header>
<p id="lost" class="lost" hidden></p>
<main id="view">%%VIEW%%</main>
</div>
<script>
(function () {
  var token = new URLSearchParams(location.search).get("t") || "";
  var lost = document.getElementById("lost");
  function refresh() {
    return fetch("/view?t=" + encodeURIComponent(token), {cache: "no-store"}).then(function (answer) {
      if (!answer.ok) { throw new Error("it answered " + answer.status); }
      return answer.text();
    }).then(function (made) {
      document.getElementById("view").innerHTML = made;
      lost.hidden = true;
    }).catch(function (why) {
      lost.textContent = "podium is not answering (" + why.message + "). Is its Terminal command still running?";
      lost.hidden = false;
    });
  }
  document.getElementById("refresh").addEventListener("click", refresh);
  setInterval(refresh, 15000);
})();
</script>
</body>
</html>
"""


def page(made):
    """The whole page around a view. The view is made here, in Python; the page's script only fetches
    a new one and puts it in place."""
    return PAGE.replace("%%VIEW%%", made)


CONDUCT_SECONDS = 30


def ask_conduct(conduct, env, run=subprocess.run):
    """conduct status --json, as (rows, the text it printed, None), or ([], None, why it failed).
    conduct is run as an argument list, never through a shell."""
    try:
        done = run([conduct, "status", "--json"], env=env, capture_output=True, text=True, check=False,
                   timeout=CONDUCT_SECONDS)
    except subprocess.TimeoutExpired:
        return [], None, f"conduct status did not answer within {CONDUCT_SECONDS} seconds"
    except OSError as why:
        return [], None, f"{conduct} could not be run ({why.strerror})"
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip()
        return [], None, f"conduct status failed (exit {done.returncode})" + ("\n  " + detail if detail else "")
    try:
        rows = json.loads(done.stdout)["mailboxes"]
        if not all(isinstance(r["mailbox"], str) and isinstance(r["state"], str) for r in rows):
            raise TypeError("not rows")
    except (ValueError, KeyError, TypeError):
        return [], None, "conduct status --json did not print the expected JSON"
    return rows, done.stdout, None


def respond(method, target, token, fetch, now):
    """(status, content type, body) for one request. Nothing is answered without the token; fetch,
    which asks conduct, is called only for an address that shows the listing."""
    parts = urllib.parse.urlsplit(target)
    given = urllib.parse.parse_qs(parts.query, keep_blank_values=True).get("t", [])
    if len(given) != 1 or not hmac.compare_digest(given[0].encode("utf-8"), token.encode("utf-8")):
        return 403, "text/plain", ("podium: this address needs the token: open the link podium printed when "
                                   "it started\n")
    if method != "GET":
        return 405, "text/plain", "podium: this page is read only: it answers GET and nothing else\n"
    if parts.path not in ("/", "/view", "/status"):
        return 404, "text/plain", "podium: there is nothing at this address\n"
    rows, raw, error = fetch()
    if parts.path == "/status":
        if error:
            return 502, "application/json", json.dumps({"error": error}) + "\n"
        return 200, "application/json", raw
    made = view(rows, now, error)
    return 200, "text/html", page(made) if parts.path == "/" else made


def answer(method, target, token, fetch, now):
    """respond, with any fault of podium's own turned into a plain 500 instead of a traceback."""
    try:
        return respond(method, target, token, fetch, now)
    except Exception as fault:  # noqa: BLE001 - the last line of defence for a page someone is looking at
        return 500, "text/plain", (f"podium: something went wrong inside podium ({type(fault).__name__}: {fault}); "
                                   "try Refresh\n")


CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def handler_for(token, fetch, clock):
    """The request handler: every method goes through answer, and nothing is logged to the terminal."""
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "podium"
        sys_version = ""
        timeout = 30

        def reply(self):
            code, kind, body = answer(self.command, self.path, token, fetch, clock())
            data = body.encode("utf-8")
            self.send_response(code)
            for name, value in (("Content-Type", kind + "; charset=utf-8"), ("Content-Length", str(len(data))),
                                ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"),
                                ("Referrer-Policy", "no-referrer"), ("Content-Security-Policy", CSP)):
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(data)

        do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_OPTIONS = do_PATCH = reply

        def log_message(self, format, *args):
            pass

    return Handler


class Server(http.server.ThreadingHTTPServer):
    """One thread per request, so a browser's idle connection cannot hold the page up."""
    daemon_threads = True


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SettingsRefused(message)


def parser():
    p = Parser(prog="podium", description="A control panel for lobster sessions: a page on this machine only, "
               "served while this command runs, showing what conduct status shows.",
               epilog="podium [--port N] [--no-open]", formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", metavar="N", help="the port to serve on, 0 for any free one (setting PODIUM_PORT, "
                   "8417 unless set); if it is in use, a free one is used instead")
    p.add_argument("--no-open", action="store_true", help="do not open the page in the browser")
    return p


def conduct_beside():
    """The conduct command in the checkout this module is in."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "conduct")


def listen(port, handler, make_server):
    """(server, the port asked for if it was in use and another was taken). 127.0.0.1 only."""
    try:
        return make_server(("127.0.0.1", port), handler), None
    except OSError as why:
        if why.errno != errno.EADDRINUSE or port == 0:
            raise
    return make_server(("127.0.0.1", 0), handler), port


def main(argv, env, out, err, conduct=None, token=None, serve=None, clock=None, make_server=Server):
    """Run podium; return its exit code. conduct is the command to ask, token the secret in the link,
    serve what runs the server until it is stopped, clock the time in UTC: all for tests to supply."""
    if argv[:1] in (["-h"], ["--help"]):
        out.write(parser().format_help())
        return 0
    try:
        path = env.get("BERNSTEIN_CONF") or os.path.join(env["HOME"], ".bernstein.conf")
        text = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
        try:
            s = read_settings(text, env["HOME"])
        except SettingsRefused as why:
            raise Stop(2, f"{path}: {why}")
        try:
            a = parser().parse_args(argv)
            if a.port is not None:
                check_port(a.port, "--port", shown=True)
        except SettingsRefused as why:
            raise Stop(2, f"{why} (podium --help shows the form)")
        port = int(a.port if a.port is not None else s["PODIUM_PORT"])
        token = token or secrets.token_urlsafe(32)
        conduct = conduct or conduct_beside()
        clock = clock or (lambda: datetime.datetime.now(datetime.timezone.utc))
        handler = handler_for(token, lambda: ask_conduct(conduct, env), clock)
        try:
            server, busy = listen(port, handler, make_server)
        except OSError as why:
            raise Stop(4, f"could not start serving on 127.0.0.1 port {port} ({why.strerror})")
    except Stop as stopped:
        err.write(f"podium: {stopped.message}\n")
        return stopped.code
    try:
        serving = server.server_address[1]
        if busy is not None:
            out.write(f"Port {busy} is in use: using {serving} instead.\n")
        link = f"http://127.0.0.1:{serving}/?t={urllib.parse.quote(token, safe='')}"
        out.write(f"podium is serving at {link}\nIt runs only while this command runs: stop it with Ctrl-C.\n")
        out.flush()   # the link must be readable now, also when the output is a file or a pipe
        if not a.no_open:
            open_in_browser(link, env, err)
        try:
            (serve or (lambda running: running.serve_forever()))(server)
        except KeyboardInterrupt:
            pass
        out.write("podium stopped.\n")
    finally:
        server.server_close()
    return 0


def open_in_browser(link, env, err):
    """Open the page with macOS's open. If that fails the page is still served: say so and carry on."""
    try:
        done = subprocess.run(["open", link], env=env, capture_output=True, text=True, check=False)
        why = None if done.returncode == 0 else (done.stderr or done.stdout).strip() or f"exit {done.returncode}"
    except OSError as failed:
        why = failed.strerror
    if why:
        err.write(f"podium: the page could not be opened in the browser ({why}); open the link above yourself\n")
