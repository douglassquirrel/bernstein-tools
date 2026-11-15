import json
import os
import re
import socket
import threading
import urllib.error
import urllib.request

from conftest import NOW, tree

from bernstein import podium

ROWS = [{"mailbox": "lone-tools", "state": "running", "kind": "code", "folder": "/p/lone-tools", "model": "opus",
         "effort": "high", "sister": "", "claws": [], "serves": [], "refused": None,
         "duty": {"mailbox": "lone-tools", "holder": "mac", "since": "2026-10-18T09:00:00Z",
                  "last_beat": "2026-10-18T09:37:00Z", "stale": False, "minutes": 3},
         "pace": "normal", "new": 1, "open": 0, "handover_waiting": False, "reported": None}]
RAW = json.dumps({"root": "/m", "mailboxes": ROWS, "skipped": []}, indent=1) + "\n"


def opened(world):
    return [c["args"] for c in world.calls() if c["prog"] == "open"]


def conducted(world):
    return [c["args"] for c in world.calls() if c["prog"] == "conduct"]


def test_help_shows_the_form_and_exits_0_serving_nothing(world):
    served = []
    code, out, err = world.podium("--help", serve=served.append)
    assert (code, err, served) == (0, "", [])
    assert "podium [--port N] [--no-open]" in out and world.calls() == []


def test_podium_serves_on_this_machine_only_says_where_and_opens_the_link(world):
    served = []
    code, out, err = world.podium("--port", "0", serve=served.append)
    assert (code, err) == (0, "")
    (server,) = served
    host, port = server.server_address[:2]
    assert host == "127.0.0.1" and port > 0
    link = f"http://127.0.0.1:{port}/?t=tok-en"
    assert out == (f"podium is serving at {link}\n"
                   "It runs only while this command runs: stop it with Ctrl-C.\n"
                   "podium stopped.\n")
    assert opened(world) == [[link]]
    assert conducted(world) == []           # conduct is asked only when the page is


def test_no_open_serves_without_opening_the_browser(world):
    served = []
    code, out, _err = world.podium("--port", "0", "--no-open", serve=served.append)
    assert code == 0 and len(served) == 1 and out.startswith("podium is serving at http://127.0.0.1:")
    assert world.calls() == []


def test_when_the_browser_cannot_be_opened_podium_says_so_and_serves_all_the_same(world):
    world.fail("open")
    served = []
    code, out, err = world.podium("--port", "0", serve=served.append)
    assert code == 0 and len(served) == 1 and out.endswith("podium stopped.\n")
    assert err == "podium: the page could not be opened in the browser (open: stub failure); open the link above yourself\n"


def test_the_listening_socket_is_closed_when_serving_ends_even_by_ctrl_c(world):
    seen = []

    def interrupted(server):
        seen.append(server)
        raise KeyboardInterrupt

    code, out, err = world.podium("--port", "0", "--no-open", serve=interrupted)
    assert (code, err) == (0, "") and out.endswith("podium stopped.\n")
    assert seen[0].socket.fileno() == -1


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_the_port_comes_from_the_flag_then_the_setting(world):
    served = []
    wanted = free_port()
    world.write_conf(f"PODIUM_PORT={wanted}\n")
    assert world.podium("--no-open", serve=served.append)[0] == 0
    assert served[0].server_address[1] == wanted
    other = free_port()
    assert world.podium("--no-open", "--port", str(other), serve=served.append)[0] == 0
    assert served[1].server_address[1] == other


def test_a_port_already_in_use_falls_back_to_a_free_one_and_says_so(world):
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen(1)
        busy = taken.getsockname()[1]
        served = []
        code, out, err = world.podium("--no-open", "--port", str(busy), serve=served.append)
    port = served[0].server_address[1]
    assert (code, err) == (0, "") and port not in (0, busy)
    assert out.startswith(f"Port {busy} is in use: using {port} instead.\n"
                          f"podium is serving at http://127.0.0.1:{port}/?t=tok-en\n")


def test_bad_arguments_are_refused_with_exit_2_and_nothing_is_served(world):
    for argv, why in (
            (("--port", "web"), "--port must be a whole number from 0 to 65535, not web"),
            (("--port", "65536"), "--port must be a whole number from 0 to 65535, not 65536"),
            (("--port", "-1"), "--port must be a whole number from 0 to 65535, not -1"),
            (("--dry-run",), "unrecognized arguments: --dry-run"),
            (("recipes",), "unrecognized arguments: recipes")):
        served = []
        code, out, err = world.podium(*argv, serve=served.append)
        assert (code, out, served) == (2, "", [])
        assert err == f"podium: {why} (podium --help shows the form)\n"
    assert world.calls() == []


def test_a_bad_settings_file_is_refused_with_exit_2(world):
    world.write_conf("PODIUM_PORT=web\n")
    served = []
    code, out, err = world.podium(serve=served.append)
    assert (code, out, served) == (2, "", [])
    assert err == f"podium: {world.conf}: line 7: PODIUM_PORT must be a whole number from 0 to 65535\n"


def test_with_no_settings_file_the_defaults_are_used(world):
    os.remove(world.conf)
    served = []
    assert world.podium("--port", "0", "--no-open", serve=served.append)[0] == 0 and len(served) == 1


def test_when_it_cannot_listen_at_all_podium_says_why_with_exit_4(world):
    def refuses(address, handler):
        raise PermissionError(13, "Permission denied")

    served = []
    code, out, err = world.podium("--port", "80", serve=served.append, make_server=refuses)
    assert (code, out, served) == (4, "", [])
    assert err == "podium: could not start serving on 127.0.0.1 port 80 (Permission denied)\n"
    assert world.calls() == []


def test_a_token_is_made_fresh_for_each_run_and_is_safe_in_a_link(world):
    links = []
    for _ in range(2):
        _code, out, _err = world.podium("--port", "0", "--no-open", token=None)
        links.append(re.search(r"\?t=(\S+)\n", out).group(1))
    assert links[0] != links[1]
    assert all(re.fullmatch(r"[A-Za-z0-9_-]{32,}", t) for t in links)


def test_conduct_is_the_one_beside_podium_unless_another_is_given():
    path = podium.conduct_beside()
    assert os.path.basename(path) == "conduct" and os.path.isfile(path)
    assert os.path.dirname(path) == os.path.dirname(os.path.dirname(os.path.abspath(podium.__file__)))


def get(url, method="GET"):
    """(status, headers, body) from the real loopback server."""
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            return answer.status, dict(answer.headers), answer.read().decode("utf-8")
    except urllib.error.HTTPError as refused:
        return refused.code, dict(refused.headers), refused.read().decode("utf-8")


def raw(port, request):
    """Everything the server sends back for one request written by hand, headers and body."""
    with socket.create_connection(("127.0.0.1", port), timeout=10) as s:
        s.sendall(request.encode("ascii"))
        chunks = []
        while True:
            chunk = s.recv(65536)
            if not chunk:
                return b"".join(chunks).decode("utf-8")
            chunks.append(chunk)


def test_over_a_real_loopback_socket_the_page_view_and_status_need_the_token(world):
    world.status(RAW)
    before = tree(os.path.join(world.home, "projects"))
    got = {}

    def serve(server):
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            for name, path, method in (("page", "/?t=tok-en", "GET"), ("view", "/view?t=tok-en", "GET"),
                                       ("status", "/status?t=tok-en", "GET"), ("no token", "/", "GET"),
                                       ("wrong token", "/status?t=tok", "GET"), ("nowhere", "/x?t=tok-en", "GET"),
                                       ("post", "/?t=tok-en", "POST"), ("head", "/?t=tok-en", "HEAD"),
                                       ("put", "/?t=tok-en", "PUT")):
                got[name] = get(base + path, method)
            got["raw head"] = raw(server.server_address[1], "HEAD /?t=tok-en HTTP/1.0\r\n\r\n")
        finally:
            server.shutdown()
            thread.join()

    code, _out, err = world.podium("--port", "0", "--no-open", serve=serve)
    assert (code, err) == (0, "")
    made = podium.view(ROWS, NOW)
    assert got["page"][0] == 200 and got["page"][2] == podium.page(made)
    assert got["view"][0] == 200 and got["view"][2] == made and '<span class="name">lone-tools</span>' in made
    assert got["status"][0] == 200 and got["status"][2] == RAW
    assert [got[k][0] for k in ("no token", "wrong token", "nowhere", "put")] == [403, 403, 404, 405]
    assert got["post"][0] == 403            # a POST's token is in its body, and this one had none
    assert "lone-tools" not in got["no token"][2] + got["wrong token"][2]
    assert got["head"][0] == 405
    assert got["raw head"].startswith("HTTP/1.0 405 ") and got["raw head"].endswith("\r\n\r\n")   # no body
    headers = got["page"][1]
    assert headers["Content-Type"] == "text/html; charset=utf-8" and headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Content-Security-Policy"] == ("default-src 'none'; style-src 'unsafe-inline'; "
                                                  "script-src 'unsafe-inline'; connect-src 'self'; "
                                                  "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
    assert got["status"][1]["Content-Type"] == "application/json; charset=utf-8"
    assert got["no token"][1]["Content-Type"] == "text/plain; charset=utf-8"
    assert conducted(world) == [["status", "--json"]] * 3       # the page, the view, the status: nothing else
    assert [c["prog"] for c in world.calls()] == ["conduct"] * 3
    assert tree(os.path.join(world.home, "projects")) == before


def test_over_the_socket_a_failing_conduct_is_shown_on_the_page_and_502_for_status(world):
    world.fail("conduct:status:4")
    got = {}

    def serve(server):
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            got["page"] = get(base + "/?t=tok-en")
            got["status"] = get(base + "/status?t=tok-en")
        finally:
            server.shutdown()
            thread.join()

    assert world.podium("--port", "0", "--no-open", serve=serve)[0] == 0
    assert got["page"][0] == 200
    assert '<p class="error">conduct status failed (exit 4)\n  conduct: stub failure</p>' in got["page"][2]
    assert got["status"][0] == 502
    assert json.loads(got["status"][2]) == {"error": "conduct status failed (exit 4)\n  conduct: stub failure"}


def test_the_link_is_written_out_before_serving_starts_even_when_output_is_not_a_terminal(world):
    import io

    class Out(io.StringIO):
        flushed = ""

        def flush(self):
            Out.flushed = self.getvalue()

    out, at_serve = Out(), []
    env = {"PATH": world.bin + os.pathsep + "/usr/bin:/bin", "HOME": world.home, "BERNSTEIN_CONF": world.conf}
    code = podium.main(["--port", "0", "--no-open"], env=env, out=out, err=io.StringIO(), token="tok-en",
                       serve=lambda server: at_serve.append(Out.flushed))
    assert code == 0 and "podium is serving at http://127.0.0.1:" in at_serve[0]
    assert at_serve[0].endswith("stop it with Ctrl-C.\n")


def post(url, **fields):
    """(status, the JSON answer or the text) from a POST of these fields as JSON to the real loopback server."""
    request = urllib.request.Request(url, data=json.dumps(fields).encode("utf-8"), method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            return answer.status, json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as refused:
        text = refused.read().decode("utf-8")
        return refused.code, json.loads(text) if text.startswith("{") else text


def serving(world, talk, *argv):
    """Run podium on a real loopback socket while talk(base address) runs; podium's exit code and stderr."""
    def serve(server):
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            talk(f"http://127.0.0.1:{server.server_address[1]}")
        finally:
            server.shutdown()
            thread.join()

    code, _out, err = world.podium("--port", "0", "--no-open", *argv, serve=serve)
    return code, err


def acted(world):
    return [c["args"] for c in world.calls() if c["prog"] == "conduct" and c["args"][:1] != ["status"]]


def test_an_action_is_sent_at_once_with_no_dry_run_and_logged(world):
    world.status(RAW)
    log = os.path.join(world.home, ".bernstein", "podium.log")      # the default place, under HOME
    got = {}

    def talk(base):
        got["preview"] = post(base + "/preview", t="tok-en", action={"verb": "stop", "project": "lone-tools"})
        got["log after that"] = os.path.exists(log)
        got["old way"] = post(base + "/run", t="tok-en", ticket="a ticket from an older page")
        got["run"] = post(base + "/run", t="tok-en", action={"verb": "stop", "project": "lone-tools"})
        got["view"] = get(base + "/view?t=tok-en")

    assert serving(world, talk) == (0, "")
    assert got["preview"][0] == 404 and got["log after that"] is False       # there is no preview to ask for
    assert got["old way"] == (400, {"error": "an action must be a JSON object"})
    code, entry = got["run"]
    assert code == 200 and entry == {"time": "2026-10-18T09:40:00Z", "command": "conduct stop lone-tools", "exit": 0,
                                     "output": "conduct stub: stop lone-tools\n", "error": "", "reminder": None,
                                     "log_error": None}
    assert acted(world) == [["stop", "lone-tools"]]
    with open(log, encoding="utf-8") as f:
        assert f.read() == ("2026-10-18T09:40:00Z  conduct stop lone-tools  (exit 0)\n"
                            "  conduct stub: stop lone-tools\n")
    assert "<h2>Activity</h2>" in got["view"][2] and "<code>conduct stop lone-tools</code>" in got["view"][2]


def test_the_log_goes_where_the_setting_says(world, tmp_path):
    world.status(RAW)
    log = str(tmp_path / "my logs" / "podium é.log")
    world.write_conf(f"PODIUM_LOG={log}\n")

    def talk(base):
        post(base + "/run", t="tok-en", action={"verb": "wake", "all": True})

    assert serving(world, talk) == (0, "")
    with open(log, encoding="utf-8") as f:
        assert f.read() == "2026-10-18T09:40:00Z  conduct wake --all  (exit 0)\n  conduct stub: wake --all\n"
    assert not os.path.exists(os.path.join(world.home, ".bernstein"))


def test_a_brief_typed_in_the_page_reaches_conduct_as_a_file_word_for_word_and_is_then_removed(world):
    world.status(RAW)
    brief = 'Line one.\n"quotes" \\ $HOME `id` $(id) ; rm -rf / </script> café 日本\n'
    got = {}

    def talk(base):
        got["run"] = post(base + "/run", t="tok-en",
                          action={"verb": "start", "project": "lone-tools", "pace": "relaxed", "brief": brief})

    assert serving(world, talk) == (0, "")
    calls = [c for c in world.calls() if c["prog"] == "conduct" and c["args"][:1] == ["start"]]
    assert [c["brief"] for c in calls] == [brief]
    assert calls[0]["args"][:5] == ["start", "lone-tools", "--pace", "relaxed", "--brief"]
    assert len(calls[0]["args"]) == 6 and not os.path.exists(calls[0]["args"][5])
    assert got["run"][1]["reminder"].startswith("Now in the desktop app: confirm the folder")
    assert got["run"][1]["command"] == ("conduct start lone-tools --pace relaxed --brief <the brief typed in podium, "
                                        f"{len(brief)} characters>")


def test_nothing_is_run_without_the_token_or_for_a_project_not_in_the_listing(world):
    world.status(RAW)
    got = {}

    def talk(base):
        got["no token"] = post(base + "/run", action={"verb": "stop", "project": "lone-tools"})
        got["wrong token"] = post(base + "/run", t="tok", action={"verb": "stop", "project": "lone-tools"})
        got["token in the address only"] = post(base + "/run?t=tok-en",
                                                action={"verb": "stop", "project": "lone-tools"})
        got["stranger"] = post(base + "/run", t="tok-en", action={"verb": "stop", "project": "elsewhere"})
        got["all for start"] = post(base + "/run", t="tok-en", action={"verb": "start", "all": True})

    assert serving(world, talk) == (0, "")
    assert [got[k][0] for k in ("no token", "wrong token", "token in the address only")] == [403, 403, 403]
    assert got["stranger"] == (400, {"error": "'elsewhere' is not a mailbox in the listing podium last showed"})
    assert got["all for start"] == (400, {"error": "start is for one project at a time"})
    assert acted(world) == []
    assert not os.path.exists(os.path.join(world.home, ".bernstein"))


def test_a_post_whose_length_is_not_a_number_is_read_as_empty_and_refused_403(world):
    got = {}

    def serve(server):
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()
        try:
            got["reply"] = raw(server.server_address[1],
                               "POST /run HTTP/1.0\r\nContent-Length: lots\r\n\r\n")
        finally:
            server.shutdown()
            thread.join()

    assert world.podium("--port", "0", "--no-open", serve=serve)[0] == 0
    assert got["reply"].startswith("HTTP/1.0 403 ") and got["reply"].endswith("when it started\n")
    assert world.calls() == []
