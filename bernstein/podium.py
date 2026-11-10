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
import shlex
import subprocess
import tempfile
import threading
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


LABELS = {"start": "Start", "stop": "Stop", "dormant": "Dormant", "dream": "Dream", "wake": "Wake"}
ASLEEP = ("dormant", "quiet", "stale")


def buttons(row):
    """The verbs a row offers, from its state. conduct still decides when one is pressed."""
    if row["mailbox"] == "bernstein" or row.get("missing"):
        return []
    state = row["state"]
    if state == "running":
        return ["stop", "dormant", "dream"]
    if state in ASLEEP:
        return ["wake"]
    return ["start"] if row["kind"] is not None and not row["refused"] else []


def buttons_for_all(rows):
    """The verbs offered for every session at once: bernstein's own is never among them."""
    states = {r["state"] for r in rows if r["mailbox"] != "bernstein"}
    return (["stop", "dormant", "dream"] if "running" in states else []) + (
        ["wake"] if states.intersection(ASLEEP) else [])


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
    acts = "".join(f'<button type="button" class="act" data-verb="{verb}" data-project="{e(row["mailbox"])}">'
                   f"{LABELS[verb]}</button>" for verb in buttons(row))
    acts = f'<div class="acts">{acts}</div>' if acts else ""
    return (f'{start}{who}<span class="badge {tone}">{e(words)}</span>'
            f'<ul class="facts">{"".join(facts)}</ul>{acts}{refused}</div>')


def activity(entries):
    """What podium has run since it started, newest first; nothing when it has run nothing."""
    if not entries:
        return ""
    runs = []
    for entry in reversed(entries):
        done = entry["exit"] is not None
        mark = f'exit {e(entry["exit"])}' if done else "not run"
        tone = "ok" if entry["exit"] == 0 else "alert"
        when = stamp(entry["time"])
        time = f"{when:%H:%M:%S} UTC" if when else e(entry["time"])
        trouble = f'<p class="refused">{e(entry["log_error"])}</p>' if entry.get("log_error") else ""
        runs.append(f'<div class="run"><p class="what"><span class="time">{time}</span> '
                    f'<code>{e(entry["command"])}</code> <span class="badge {tone}">{mark}</span></p>'
                    f'<pre>{e(entry["output"])}{e(entry["error"])}</pre>{trouble}</div>')
    return '<h2>Activity</h2><section class="card log">' + "".join(runs) + "</section>"


def view(rows, now, error=None, entries=()):
    """The part of the page that is made again at every refresh: when, then the cards or the error, then
    what podium has run."""
    parts = [f'<p class="asof">As of {now:%H:%M:%S} UTC</p>']
    if error:
        return parts[0] + f'<p class="error">{e(error)}</p>' + activity(entries)
    if not rows:
        return parts[0] + '<p class="empty">No mailboxes.</p>' + activity(entries)
    for_all = "".join(f'<button type="button" class="act" data-verb="{verb}" data-all="1">{LABELS[verb]} all</button>'
                      for verb in buttons_for_all(rows))
    if for_all:
        parts.append(f'<div class="all">{for_all}</div>')
    found = groups(rows)
    for head, claws in found["cards"]:
        parts.append('<section class="card">' + row_html(head, now)
                     + "".join(row_html(c, now, label, claw=True) for c, label in claws) + "</section>")
    for title, members in (("Lone claws", found["lone"]), ("Cannot be started", found["unstartable"]),
                           ("bernstein", [found["bernstein"]] if found["bernstein"] else [])):
        if members:
            parts.append(f'<h2>{title}</h2><section class="card">'
                         + "".join(row_html(r, now) for r in members) + "</section>")
    return "".join(parts) + activity(entries)


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
.row { display: grid; grid-template-columns: minmax(10rem, 1.2fr) 9.5rem minmax(0, 2fr) 13rem;
  gap: 4px 16px; align-items: center; padding: 12px 16px; }
.row + .row { border-top: 1px solid var(--line); }
.row.claw { background: color-mix(in srgb, var(--bg) 45%, var(--card)); }
.row.claw .who { padding-left: 18px; }
.who { min-width: 0; }
.name { font-weight: 600; overflow-wrap: anywhere; }
.kind { color: var(--muted); font-size: 13px; white-space: nowrap; }
.badge { justify-self: start; font-size: 13px; font-weight: 600; border-radius: 12px; padding: 2px 10px;
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
.acts, .all { display: flex; flex-wrap: wrap; gap: 6px; }
.acts { grid-column: 4; justify-content: flex-end; }
.all { margin: 0 0 14px; }
.act { font-size: 13px; padding: 4px 11px; }
.log .run { padding: 12px 16px; }
.log .run + .run { border-top: 1px solid var(--line); }
.what { margin: 0 0 6px; display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: center; }
.time { color: var(--muted); font-size: 13px; font-variant-numeric: tabular-nums; }
code, pre { font: 12.5px/1.5 ui-monospace, SFMono-Regular, Menlo, monospace; }
code { overflow-wrap: anywhere; }
pre { margin: 0; white-space: pre-wrap; overflow-wrap: anywhere; color: var(--muted); }
dialog { width: min(44rem, calc(100% - 32px)); max-height: calc(100% - 32px); overflow: auto; color: var(--ink);
  background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 20px; }
dialog::backdrop { background: rgba(0, 0, 0, 0.45); }
dialog h2 { font-size: 18px; text-transform: none; letter-spacing: 0; color: var(--ink); margin: 0 0 14px; }
dialog label, dialog legend { display: block; font-size: 13px; color: var(--muted); margin: 0 0 4px; }
dialog fieldset { border: 0; padding: 0; margin: 0 0 12px; }
dialog .choice { display: flex; gap: 8px; align-items: baseline; color: var(--ink); font-size: 15px; margin: 0 0 4px; }
dialog .field { margin: 0 0 12px; }
textarea, select, input[type="number"] { font: inherit; color: var(--ink); background: var(--bg);
  border: 1px solid var(--line); border-radius: 8px; padding: 6px 8px; }
textarea { width: 100%; min-height: 7rem; resize: vertical; }
input[type="number"] { width: 6rem; }
.shown { background: var(--bg); border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px;
  margin: 0 0 12px; }
.shown code { display: block; color: var(--ink); margin: 0 0 6px; }
.note { margin: 0 0 12px; }
.progress { display: flex; align-items: center; gap: 10px; margin: 0 0 12px; font-variant-numeric: tabular-nums; }
.spin { flex: none; width: 16px; height: 16px; border-radius: 50%; border: 2px solid var(--line);
  border-top-color: var(--ink); animation: spin 0.9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .spin { animation: none; border-top-color: var(--muted); } }
.buttons { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
#act-go { background: var(--ink); color: var(--card); border-color: var(--ink); }
button:disabled { opacity: 0.5; cursor: default; }
@media (max-width: 640px) {
  .row { grid-template-columns: 1fr auto; }
  .facts, .acts { grid-column: 1 / -1; }
  .acts { justify-content: flex-start; }
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
<dialog id="act" aria-labelledby="act-title">
<h2 id="act-title"></h2>
<div id="act-options"></div>
<div id="act-shown" class="shown" hidden><code id="act-command"></code><pre id="act-output"></pre></div>
<p id="act-progress" class="progress" role="status" hidden><span class="spin"></span><span id="act-progress-text"></span></p>
<p id="act-note" class="note" hidden></p>
<p id="act-problem" class="error" hidden></p>
<div class="buttons"><button type="button" id="act-cancel">Cancel</button><button type="button" id="act-go">Preview</button></div>
</dialog>
<script>
(function () {
  var token = new URLSearchParams(location.search).get("t") || "";
  var lost = document.getElementById("lost");
  var dialog = document.getElementById("act");
  var title = document.getElementById("act-title");
  var options = document.getElementById("act-options");
  var shown = document.getElementById("act-shown");
  var command = document.getElementById("act-command");
  var output = document.getElementById("act-output");
  var note = document.getElementById("act-note");
  var progress = document.getElementById("act-progress");
  var progressText = document.getElementById("act-progress-text");
  var ticking = null;    // the timer that counts the seconds while conduct runs
  var problem = document.getElementById("act-problem");
  var cancel = document.getElementById("act-cancel");
  var go = document.getElementById("act-go");
  var names = {start: "Start", stop: "Stop", dormant: "Dormant", wake: "Wake", dream: "Dream"};
  var asked = null;      // {verb, project} or {verb, all: true}: what the open dialog is about
  var ticket = null;     // what the last preview gave, to send it
  var step = "options";  // options, then preview, then done

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

  function post(path, body) {
    body.t = token;
    return fetch(path, {method: "POST", cache: "no-store", headers: {"Content-Type": "application/json"},
                        body: JSON.stringify(body)}).then(function (answer) {
      return answer.text().then(function (text) {
        var said;
        try { said = JSON.parse(text); } catch (notJson) { said = {error: text.trim() || "podium answered " + answer.status}; }
        return {ok: answer.ok, said: said};
      });
    }, function (why) {
      return {ok: false, said: {error: "podium is not answering (" + why.message + "). Is its Terminal command still running?"}};
    });
  }

  function add(parent, tag, text, attributes) {
    var made = document.createElement(tag);
    if (text) { made.textContent = text; }
    Object.keys(attributes || {}).forEach(function (name) { made.setAttribute(name, attributes[name]); });
    parent.appendChild(made);
    return made;
  }

  function field(labelText, id) {
    var holder = add(options, "div", "", {"class": "field"});
    add(holder, "label", labelText, {"for": id});
    return holder;
  }

  function choice(parent, name, value, text, checked) {
    var line = add(parent, "label", "", {"class": "choice"});
    var radio = add(line, "input", "", {type: "radio", name: name, value: value});
    radio.checked = checked;
    add(line, "span", text);
    return radio;
  }

  function minutesField(labelText) {
    return add(field(labelText, "act-minutes"), "input", "",
               {type: "number", id: "act-minutes", min: "5", max: "240", value: "60"});
  }

  function build(verb) {
    options.textContent = "";
    if (verb === "start") {
      add(field("A brief for the session (optional). It is sent word for word.", "act-brief"), "textarea", "",
          {id: "act-brief"});
      var pace = add(field("Mail pace", "act-pace"), "select", "", {id: "act-pace"});
      add(pace, "option", "Leave as it is", {value: ""});
      ["eager", "normal", "relaxed"].forEach(function (level) { add(pace, "option", level, {value: level}); });
    } else if (verb === "stop") {
      var first = add(options, "fieldset", "");
      add(first, "legend", "Dream first?");
      choice(first, "act-dream", "no", "No: hand over and stop now", true);
      choice(first, "act-dream", "yes", "Yes: dream first, then hand over and stop", false);
      minutesField("Minutes to dream, if dreaming first (5 to 240)");
      add(field("Seconds to wait for the handover, if stopping now (optional, 1 to 600)", "act-wait"), "input", "",
          {type: "number", id: "act-wait", min: "1", max: "600"});
    } else if (verb === "dream") {
      minutesField("Minutes to dream (5 to 240)");
      var then = add(field("Afterwards", "act-then"), "select", "", {id: "act-then"});
      add(then, "option", "Go dormant", {value: "dormant"});
      add(then, "option", "Hand over and stop", {value: "stop"});
    }
  }

  function number(id) {
    var box = document.getElementById(id);
    if (!box || box.value.trim() === "") { return null; }
    return /^[0-9]+$/.test(box.value.trim()) ? parseInt(box.value.trim(), 10) : box.value;
  }

  function actionNow() {
    var action = {verb: asked.verb};
    if (asked.all) { action.all = true; } else { action.project = asked.project; }
    if (asked.verb === "start") {
      if (document.getElementById("act-brief").value !== "") { action.brief = document.getElementById("act-brief").value; }
      if (document.getElementById("act-pace").value !== "") { action.pace = document.getElementById("act-pace").value; }
    } else if (asked.verb === "stop") {
      if (document.querySelector('input[name="act-dream"]:checked').value === "yes") {
        action.verb = "dream";
        action.then = "stop";
        action.minutes = number("act-minutes");
      } else if (number("act-wait") !== null) {
        action.wait = number("act-wait");
      }
    } else if (asked.verb === "dream") {
      action.minutes = number("act-minutes");
      action.then = document.getElementById("act-then").value;
    }
    if (action.minutes === null) { delete action.minutes; }
    return action;
  }

  function show(said) {
    command.textContent = said.command || "";
    output.textContent = (said.output || "") + (said.error || "");
    shown.hidden = false;
  }

  function trouble(text) {
    problem.textContent = text;
    problem.hidden = !text;
  }

  function working(what) {
    // what: words for what conduct is doing now, shown with the seconds so far; nothing when it has finished
    var began = Date.now();
    function tick() {
      var seconds = Math.floor((Date.now() - began) / 1000);
      progressText.textContent = what + "\u2026 " + seconds + " s";
    }
    if (ticking !== null) { clearInterval(ticking); ticking = null; }
    go.disabled = Boolean(what);
    cancel.disabled = Boolean(what);
    progress.hidden = !what;
    if (what) {
      tick();
      ticking = setInterval(tick, 1000);
    }
  }

  function preview() {
    var action = actionNow();
    working("Asking conduct what it would do");
    trouble("");
    post("/preview", {action: action}).then(function (got) {
      working("");
      if (!got.ok) {
        go.textContent = "Preview";
        trouble(got.said.error || "podium refused that");
        return;
      }
      show(got.said);
      options.hidden = true;
      ticket = got.said.ticket;
      if (ticket) {
        step = "preview";
        go.textContent = "Send";
        note.textContent = "Nothing has been sent. This is what conduct would do: read it, then Send or Cancel.";
        note.hidden = false;
      } else {
        step = "done";
        go.hidden = true;
        cancel.textContent = "Close";
        trouble("conduct would not do this" + (got.said.exit === null ? "" : " (exit " + got.said.exit + ")") +
                ", so there is nothing to send.");
      }
    });
  }

  function send() {
    var sending = command.textContent.replace(/ --dry-run$/, "");
    var waits = /--wait ([0-9]+)/.exec(sending);
    command.textContent = sending;       // what is running now, in place of the dry run just read
    output.textContent = "";
    note.hidden = true;
    working("Sending: " + sending + (waits ? " (it waits up to " + waits[1] + " s for the handover)" : ""));
    post("/run", {ticket: ticket}).then(function (got) {
      working("");
      step = "done";
      go.hidden = true;
      cancel.textContent = "Close";
      note.hidden = true;
      if (!got.ok) {
        trouble(got.said.error || "podium refused that");
        return;
      }
      show(got.said);
      if (got.said.exit === 0) {
        note.textContent = "Done." + (got.said.reminder ? " " + got.said.reminder : "");
        note.hidden = false;
      } else {
        trouble(got.said.exit === null ? "conduct did not finish." : "conduct failed (exit " + got.said.exit + ").");
      }
      if (got.said.log_error) { trouble((problem.textContent ? problem.textContent + " " : "") + got.said.log_error); }
    });
  }

  function open(verb, project, all) {
    asked = all ? {verb: verb, all: true} : {verb: verb, project: project};
    ticket = null;
    step = "options";
    title.textContent = names[verb] + " " + (all ? "every session but bernstein's" : project);
    build(verb);
    options.hidden = false;
    command.textContent = "";
    output.textContent = "";
    shown.hidden = true;
    note.hidden = true;
    trouble("");
    working("");
    go.hidden = false;
    go.textContent = "Preview";
    cancel.textContent = "Cancel";
    dialog.showModal();
    if (verb === "dormant" || verb === "wake") { preview(); }
  }

  document.getElementById("view").addEventListener("click", function (event) {
    var pressed = event.target.closest("button.act");
    if (pressed) { open(pressed.dataset.verb, pressed.dataset.project, pressed.dataset.all === "1"); }
  });
  go.addEventListener("click", function () { if (step === "options") { preview(); } else if (step === "preview") { send(); } });
  cancel.addEventListener("click", function () { dialog.close(); });
  dialog.addEventListener("close", function () { refresh(); });
  document.getElementById("refresh").addEventListener("click", refresh);
  setInterval(function () { if (!dialog.open) { refresh(); } }, 15000);
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


NO_TOKEN = (403, "text/plain",
            "podium: this address needs the token: open the link podium printed when it started\n")
BODY_LIMIT = 200000


def respond(method, target, token, fetch, now, entries=()):
    """(status, content type, body) for a request to look. Nothing is answered without the token; fetch,
    which asks conduct, is called only for an address that shows the listing."""
    parts = urllib.parse.urlsplit(target)
    given = urllib.parse.parse_qs(parts.query, keep_blank_values=True).get("t", [])
    if len(given) != 1 or not hmac.compare_digest(given[0].encode("utf-8"), token.encode("utf-8")):
        return NO_TOKEN
    if method != "GET":
        return 405, "text/plain", "podium: this address answers GET and nothing else\n"
    if parts.path not in ("/", "/view", "/status"):
        return 404, "text/plain", "podium: there is nothing at this address\n"
    rows, raw, error = fetch()
    if parts.path == "/status":
        if error:
            return 502, "application/json", json.dumps({"error": error}) + "\n"
        return 200, "application/json", raw
    made = view(rows, now, error, entries)
    return 200, "text/html", page(made) if parts.path == "/" else made


def act(target, body, token, panel):
    """(status, content type, body) for a request to act: POST /preview with an action, then POST /run
    with the ticket the preview gave. The token is in the body, and nothing is done without it."""
    if len(body) > BODY_LIMIT:
        return 413, "text/plain", "podium: that is more than podium takes in one request\n"
    try:
        sent = json.loads(body.decode("utf-8"))
    except ValueError:
        sent = None
    given = sent.get("t") if isinstance(sent, dict) else None
    if not isinstance(given, str) or not hmac.compare_digest(given.encode("utf-8"), token.encode("utf-8")):
        return NO_TOKEN
    path = urllib.parse.urlsplit(target).path
    if path == "/preview":
        code, said = panel.preview(sent.get("action"))
    elif path == "/run":
        code, said = panel.send(sent.get("ticket"))
    else:
        return 404, "text/plain", "podium: there is nothing to send to at this address\n"
    return code, "application/json", json.dumps(said) + "\n"


def answer(method, target, body, token, panel, now):
    """The answer to any request: a POST acts, anything else looks. A fault of podium's own becomes a
    plain 500 instead of a traceback."""
    try:
        if method == "POST":
            return act(target, body, token, panel)
        return respond(method, target, token, panel.listing, now, panel.entries)
    except Exception as fault:  # noqa: BLE001 - the last line of defence for a page someone is looking at
        return 500, "text/plain", (f"podium: something went wrong inside podium ({type(fault).__name__}: {fault}); "
                                   "try Refresh\n")


CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")


def handler_for(token, panel, clock):
    """The request handler: every method goes through answer, and nothing is logged to the terminal."""
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "podium"
        sys_version = ""
        timeout = 30

        def reply(self):
            try:
                length = max(0, int(self.headers.get("Content-Length") or 0))
            except ValueError:
                length = 0
            sent = self.rfile.read(min(length, BODY_LIMIT + 1)) if length else b""
            code, kind, body = answer(self.command, self.path, sent, token, panel, clock())
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

    def handle_error(self, request, client_address):
        """A connection the browser dropped is nothing to tell the terminal about."""


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
        handler = handler_for(token, Panel(conduct, env, clock, s["PODIUM_LOG"]), clock)
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


class Refused(ValueError):
    """An action the page asked for that podium does not offer; the message says why."""


PACES = ("eager", "normal", "relaxed")
BRIEF_LIMIT = 20000
OPTIONS = {"start": ("pace", "brief"), "stop": ("wait",), "dormant": (), "wake": (), "dream": ("minutes", "then")}


def whole(value, low, high):
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def command_for(action, names):
    """(conduct's arguments, the brief's text or None) for an action the page sent. Only the verbs and
    options podium offers, and only a project in the listing it last showed: anything else is Refused."""
    if not isinstance(action, dict):
        raise Refused("an action must be a JSON object")
    verb = action.get("verb")
    if not isinstance(verb, str) or verb not in OPTIONS:
        raise Refused(f"podium does not offer the verb {verb!r}")
    for key in action:
        if key not in ("verb", "project", "all") + OPTIONS[verb]:
            raise Refused(f"{verb} does not take {key}")
    project, everything = action.get("project"), action.get("all", False)
    if not isinstance(everything, bool) or everything == (project is not None):
        raise Refused("name one project, or everything at once")
    if everything:
        if verb == "start":
            raise Refused("start is for one project at a time")
        argv = [verb, "--all"]
    else:
        if not isinstance(project, str) or project not in names:
            raise Refused(f"{project!r} is not a mailbox in the listing podium last showed")
        if project == "bernstein":
            raise Refused("podium does not act on bernstein's own session")
        if project.startswith("-"):
            raise Refused(f"{project!r} cannot be given to conduct as a project: it starts with a dash")
        argv = [verb, project]
    brief = None
    if verb == "start":
        if action.get("pace") is not None:
            if action["pace"] not in PACES:
                raise Refused("the pace must be eager, normal or relaxed")
            argv += ["--pace", action["pace"]]
        brief = action.get("brief")
        if brief is not None and not isinstance(brief, str):
            raise Refused("the brief must be text")
        if brief is not None and len(brief) > BRIEF_LIMIT:
            raise Refused(f"the brief is longer than {BRIEF_LIMIT} characters")
        brief = brief or None
    if verb == "stop" and action.get("wait") is not None:
        if not whole(action["wait"], 1, 600):
            raise Refused("the wait must be a whole number of seconds from 1 to 600")
        argv += ["--wait", str(action["wait"])]
    if verb == "dream":
        minutes, then = action.get("minutes", 60), action.get("then", "dormant")
        if not whole(minutes, 5, 240):
            raise Refused("the minutes must be a whole number from 5 to 240")
        if then not in ("dormant", "stop"):
            raise Refused("then must be dormant or stop")
        argv += ["--minutes", str(minutes), "--then", then]
    return argv, brief


def shown(argv, brief, dry_run=False):
    """The command as it could be typed, for the preview and the log. A brief is shown by its length."""
    text = "conduct " + " ".join(shlex.quote(a) for a in argv)
    if brief:
        text += f" --brief <the brief typed in podium, {len(brief)} characters>"
    return text + (" --dry-run" if dry_run else "")


BUSY = (409, {"error": "podium is busy with another action: try again when it has finished"})
GONE = (409, {"error": "that preview is no longer the latest one: preview again, then send"})
REMINDER = ("Now in the desktop app: confirm the folder or folders it shows, then send the first line. If it is a "
            "Claude Code session, check its folder is the project's before anything else (the app has dropped it "
            "before), and ask a bernstein session to set its model and effort.")


def log_text(entry):
    """One run as the log file keeps it: a line saying when, what and how it ended, then what it printed."""
    ended = f"exit {entry['exit']}" if entry["exit"] is not None else "not run"
    printed = "".join("  " + line + "\n" for line in (entry["output"] + entry["error"]).splitlines())
    return f"{entry['time']}  {entry['command']}  ({ended})\n{printed}"


class Panel:
    """What podium knows and does between requests: the names in the last listing, the one preview
    that may be sent, what it has run, and the one action that may run at a time. It runs conduct and
    nothing else, and writes only the brief's temporary file and the log."""

    def __init__(self, conduct, env, clock, log_path, run=subprocess.run, ticket=None):
        self.conduct, self.env, self.clock, self.log_path, self.run = conduct, env, clock, log_path, run
        self.ticket = ticket or (lambda: secrets.token_urlsafe(16))
        self.names, self.pending, self.entries = None, None, []
        self.lock = threading.Lock()

    def listing(self):
        """conduct status --json, remembering the mailboxes it names for the actions that follow."""
        rows, raw, error = ask_conduct(self.conduct, self.env, self.run)
        if not error:
            self.names = {r["mailbox"] for r in rows}
        return rows, raw, error

    def call(self, argv, brief, dry_run):
        """Run conduct with these arguments: (exit code or None if it did not run to the end, what it
        printed, what it said on standard error or why it did not run). The brief is a file while it runs."""
        seconds = 60 + (int(argv[argv.index("--wait") + 1]) if "--wait" in argv else 0)
        full, path = [self.conduct, *argv], None
        try:
            if brief:
                handle, path = tempfile.mkstemp(prefix="podium-brief-", suffix=".txt")
                with os.fdopen(handle, "w", encoding="utf-8") as f:
                    f.write(brief)
                full += ["--brief", path]
            if dry_run:
                full.append("--dry-run")
            try:
                done = self.run(full, env=self.env, capture_output=True, text=True, check=False, timeout=seconds)
            except subprocess.TimeoutExpired:
                if dry_run:
                    return None, "", f"conduct did not answer within {seconds} seconds"
                return None, "", (f"conduct was stopped after {seconds} seconds without finishing; some of it may "
                                  "have been done: look at the page before trying again")
            except OSError as why:
                return None, "", f"{self.conduct} could not be run ({why.strerror})"
            return done.returncode, done.stdout, done.stderr
        finally:
            if path:
                os.remove(path)

    def preview(self, action):
        """(status, answer) for a preview: the verb run with --dry-run, and a ticket to send it if
        conduct was content."""
        if not self.lock.acquire(blocking=False):
            return BUSY
        try:
            if self.names is None:
                self.listing()
            try:
                argv, brief = command_for(action, self.names or set())
            except Refused as why:
                return 400, {"error": str(why)}
            self.pending = None
            code, output, error = self.call(argv, brief, True)
            ticket = None
            if code == 0:
                ticket = self.ticket()
                self.pending = (ticket, argv, brief)
            return 200, {"command": shown(argv, brief, dry_run=True), "exit": code, "output": output,
                         "error": error, "ticket": ticket}
        finally:
            self.lock.release()

    def send(self, ticket):
        """(status, the run as recorded) for sending the latest preview, once."""
        if not self.lock.acquire(blocking=False):
            return BUSY
        try:
            if (self.pending is None or not isinstance(ticket, str)
                    or not hmac.compare_digest(ticket.encode("utf-8"), self.pending[0].encode("utf-8"))):
                return GONE
            _ticket, argv, brief = self.pending
            self.pending = None
            code, output, error = self.call(argv, brief, False)
            entry = {"time": f"{self.clock():%Y-%m-%dT%H:%M:%SZ}", "command": shown(argv, brief), "exit": code,
                     "output": output, "error": error,
                     "reminder": REMINDER if argv[0] == "start" and code == 0 else None, "log_error": None}
            try:
                os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8") as log:
                    log.write(log_text(entry))
            except OSError as why:
                entry["log_error"] = f"the log {self.log_path} could not be written ({why.strerror})"
            self.entries.append(entry)
            return 200, entry
        finally:
            self.lock.release()
