import datetime
import json
import subprocess

import pytest

from bernstein import podium

NOW = datetime.datetime(2026, 10, 18, 9, 40, 5, tzinfo=datetime.timezone.utc)
ROWS = [{"mailbox": "lone-tools", "state": "off", "kind": "code", "folder": "/p/lone-tools", "model": "opus",
         "effort": "high", "sister": "", "claws": [], "serves": [], "refused": None, "duty": None,
         "pace": "normal", "new": 0, "open": 0, "handover_waiting": False, "reported": None}]
RAW = json.dumps({"root": "/m", "mailboxes": ROWS, "skipped": []}, indent=1) + "\n"


class Fetch:
    """Stands in for asking conduct: counts the calls and gives one canned answer."""

    def __init__(self, rows=ROWS, raw=RAW, error=None):
        self.answer, self.calls = (rows, raw, error), 0

    def __call__(self):
        self.calls += 1
        return self.answer


@pytest.mark.parametrize("target", [
    "/", "/?t=", "/?t=wrong", "/?t=secre", "/?t=secret1", "/?token=secret", "/view", "/status?t=nope",
    "/?t=secret&t=secret", "/?t=wrong&t=secret", "/nowhere", "/?T=secret",
])
def test_a_request_without_exactly_the_token_is_refused_403_and_conduct_is_not_asked(target):
    fetch = Fetch()
    code, kind, body = podium.respond("GET", target, "secret", fetch, NOW)
    assert (code, kind) == (403, "text/plain")
    assert body == "podium: this address needs the token: open the link podium printed when it started\n"
    assert fetch.calls == 0


def test_the_page_is_the_view_inside_the_page():
    fetch = Fetch()
    assert podium.respond("GET", "/?t=secret", "secret", fetch, NOW) == \
        (200, "text/html", podium.page(podium.view(ROWS, NOW)))
    assert fetch.calls == 1


def test_view_is_the_fragment_alone_for_the_page_s_refresh():
    assert podium.respond("GET", "/view?t=secret", "secret", Fetch(), NOW) == (200, "text/html", podium.view(ROWS, NOW))


def test_status_is_what_conduct_printed_passed_through_unchanged():
    assert podium.respond("GET", "/status?t=secret", "secret", Fetch(), NOW) == (200, "application/json", RAW)


def test_when_conduct_fails_the_page_shows_why_and_status_is_502_with_the_reason():
    failed = Fetch(rows=[], raw=None, error="conduct status failed (exit 4)\n  conduct: lobster-mail is gone")
    code, kind, body = podium.respond("GET", "/?t=secret", "secret", failed, NOW)
    assert (code, kind) == (200, "text/html") and '<p class="error">conduct status failed (exit 4)' in body
    code, kind, body = podium.respond("GET", "/view?t=secret", "secret", failed, NOW)
    assert (code, kind) == (200, "text/html") and body == podium.view([], NOW, error=failed.answer[2])
    code, kind, body = podium.respond("GET", "/status?t=secret", "secret", failed, NOW)
    assert (code, kind) == (502, "application/json")
    assert json.loads(body) == {"error": "conduct status failed (exit 4)\n  conduct: lobster-mail is gone"}


@pytest.mark.parametrize("target", ["/nowhere?t=secret", "/view/?t=secret", "/status/x?t=secret", "//?t=secret",
                                    "/../etc/passwd?t=secret", "/VIEW?t=secret"])
def test_an_address_podium_does_not_have_is_404_and_conduct_is_not_asked(target):
    fetch = Fetch()
    assert podium.respond("GET", target, "secret", fetch, NOW) == \
        (404, "text/plain", "podium: there is nothing at this address\n")
    assert fetch.calls == 0


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "HEAD", "OPTIONS", "PATCH"])
def test_anything_but_get_is_405_and_conduct_is_not_asked(method):
    fetch = Fetch()
    assert podium.respond(method, "/?t=secret", "secret", fetch, NOW) == \
        (405, "text/plain", "podium: this page is read only: it answers GET and nothing else\n")
    assert fetch.calls == 0


def test_a_token_with_awkward_characters_is_matched_as_data():
    token = "a b&c=d%/é"
    from urllib.parse import quote
    assert podium.respond("GET", "/view?t=" + quote(token, safe=""), token, Fetch(), NOW)[0] == 200
    assert podium.respond("GET", "/view?t=a", token, Fetch(), NOW)[0] == 403


def test_a_fault_inside_podium_is_a_plain_500_never_a_traceback():
    def broken():
        raise RuntimeError("boom")
    assert podium.answer("GET", "/?t=secret", "secret", broken, NOW) == \
        (500, "text/plain", "podium: something went wrong inside podium (RuntimeError: boom); try Refresh\n")
    assert podium.answer("GET", "/view?t=secret", "secret", Fetch(), NOW) == (200, "text/html", podium.view(ROWS, NOW))


def ran(returncode=0, stdout="", stderr=""):
    def run(argv, **kwargs):
        run.seen = (argv, kwargs)
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)
    return run


def test_asking_conduct_runs_status_json_as_an_argument_list_and_reads_the_rows():
    run = ran(stdout=RAW)
    assert podium.ask_conduct("/x y/conduct", {"HOME": "/h"}, run) == (ROWS, RAW, None)
    argv, kwargs = run.seen
    assert argv == ["/x y/conduct", "status", "--json"]
    assert kwargs == {"env": {"HOME": "/h"}, "capture_output": True, "text": True, "check": False, "timeout": 30}


def test_asking_conduct_gives_its_own_message_when_it_fails():
    run = ran(returncode=4, stderr="conduct: lobster-mail duty status --all failed (exit 1)\n  boom\n")
    assert podium.ask_conduct("/c", {}, run) == (
        [], None, "conduct status failed (exit 4)\n  conduct: lobster-mail duty status --all failed (exit 1)\n  boom")
    assert podium.ask_conduct("/c", {}, ran(returncode=2)) == ([], None, "conduct status failed (exit 2)")


@pytest.mark.parametrize("printed", ["", "not json", "[]", '{"mailboxes": 3}', '{"rows": []}', '{"mailboxes": [3]}',
                                     '{"mailboxes": [{"state": "off"}]}',
                                     '{"mailboxes": [{"mailbox": 3, "state": "off"}]}'])
def test_asking_conduct_refuses_output_that_is_not_its_json(printed):
    assert podium.ask_conduct("/c", {}, ran(stdout=printed)) == (
        [], None, "conduct status --json did not print the expected JSON")


def test_asking_conduct_says_so_when_it_cannot_be_run_or_does_not_answer():
    def missing(argv, **kwargs):
        raise FileNotFoundError(2, "No such file or directory")

    def hangs(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    assert podium.ask_conduct("/gone/conduct", {}, missing) == (
        [], None, "/gone/conduct could not be run (No such file or directory)")
    assert podium.ask_conduct("/c", {}, hangs) == ([], None, "conduct status did not answer within 30 seconds")


def test_when_open_is_not_there_to_run_podium_says_so_and_carries_on(monkeypatch):
    import io

    def missing(argv, **kwargs):
        raise FileNotFoundError(2, "No such file or directory")

    monkeypatch.setattr(podium.subprocess, "run", missing)
    err = io.StringIO()
    podium.open_in_browser("http://127.0.0.1:1/?t=x", {}, err)
    assert err.getvalue() == ("podium: the page could not be opened in the browser (No such file or directory); "
                              "open the link above yourself\n")
