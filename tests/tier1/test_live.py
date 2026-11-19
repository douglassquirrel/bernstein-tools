"""bernstein/live.py: which Claude Code sessions are alive on the Mac, from `claude agents --json`."""

import json
import os
import subprocess

import pytest

from bernstein import live


def listed(cwd, name="soups-tools · 18 October", status="idle", started=1792051200000, pid=4242,
           kind="interactive", sid="00000000-0000-4000-8000-000000000000"):
    """One session as `claude agents --json` prints it (every value here is invented)."""
    return {"pid": pid, "cwd": cwd, "kind": kind, "startedAt": started, "sessionId": sid, "name": name,
            "status": status}


def a_session(**changed):
    session = {"name": "soups-tools · 18 October", "status": "idle", "kind": "interactive", "pid": 4242,
               "started": "2026-10-15T08:00:00Z", "id": "00000000-0000-4000-8000-000000000000"}
    session.update(changed)
    return session


# --- the listing as text ---

def test_an_empty_listing_has_no_sessions():
    assert live.sessions("[]") == {}


def test_a_session_is_filed_under_its_folder_with_its_facts(tmp_path):
    folder = str(tmp_path)
    assert live.sessions(json.dumps([listed(folder)])) == {os.path.realpath(folder): [a_session()]}


def test_a_folder_is_made_a_real_path_so_a_link_and_a_trailing_slash_match(tmp_path):
    real = tmp_path / "soups tools"
    real.mkdir()
    (tmp_path / "link").symlink_to(real)
    found = live.sessions(json.dumps([listed(str(tmp_path / "link") + "/"), listed(str(real) + "/", name="b")]))
    assert list(found) == [os.path.realpath(str(real))]
    assert [s["name"] for s in found[os.path.realpath(str(real))]] == ["soups-tools · 18 October", "b"]


def test_sessions_in_one_folder_are_oldest_first_and_one_with_no_start_before_them(tmp_path):
    folder = str(tmp_path)
    text = json.dumps([listed(folder, name="late", started=1792315260000), listed(folder, name="none", started=None),
                       listed(folder, name="early", started=1792315200000)])
    assert [s["name"] for s in live.sessions(text)[os.path.realpath(folder)]] == ["none", "early", "late"]


@pytest.mark.parametrize("entry", [None, 7, "text", [], {}, {"name": "no folder"}, {"cwd": 7}, {"cwd": None},
                                   {"cwd": ["/a"]}, {"cwd": ""}])
def test_an_entry_that_is_not_a_session_with_a_folder_is_passed_over(entry, tmp_path):
    text = json.dumps([entry, listed(str(tmp_path))])
    assert live.sessions(text) == {os.path.realpath(str(tmp_path)): [a_session()]}


@pytest.mark.parametrize("key, value, fact", [
    ("name", 7, "name"), ("name", None, "name"), ("name", ["a"], "name"),
    ("status", {"busy": True}, "status"), ("kind", 3, "kind"),
    ("pid", "4242", "pid"), ("pid", True, "pid"), ("pid", 1.5, "pid"),
    ("startedAt", "yesterday", "started"), ("startedAt", True, "started"), ("startedAt", 10 ** 30, "started"),
    ("startedAt", -(10 ** 30), "started"), ("startedAt", 1.5, "started"), ("sessionId", 12, "id"),
])
def test_a_fact_that_is_not_the_type_expected_is_not_known(key, value, fact, tmp_path):
    entry = listed(str(tmp_path))
    entry[key] = value
    (session,) = live.sessions(json.dumps([entry]))[os.path.realpath(str(tmp_path))]
    assert session == a_session(**{fact: None})


def test_a_listing_from_a_later_claude_with_keys_missing_and_keys_added_is_still_read(tmp_path):
    text = json.dumps([{"cwd": str(tmp_path), "somethingNew": {"a": 1}}])
    assert live.sessions(text) == {os.path.realpath(str(tmp_path)): [
        {"name": None, "status": None, "kind": None, "pid": None, "started": None, "id": None}]}


def test_a_name_is_data_whatever_is_in_it(tmp_path):
    name = "a \"quoted\" \\ name\nwith $HOME, </script> and é ü 漢"
    (session,) = live.sessions(json.dumps([listed(str(tmp_path), name=name)]))[os.path.realpath(str(tmp_path))]
    assert session["name"] == name


@pytest.mark.parametrize("text", ["", "\n", "not json", "{}", '{"cwd": "/a"}', "7", '"[]"', "null", "[1, 2"])
def test_text_that_is_not_a_json_array_is_not_a_listing(text):
    with pytest.raises(ValueError):
        live.sessions(text)


# --- running the command ---

class Ran:
    """A stand-in for subprocess.run that records the call and answers as told."""

    def __init__(self, stdout="[]", code=0, raises=None):
        self.stdout, self.code, self.raises, self.calls = stdout, code, raises, []

    def __call__(self, argv, **how):
        self.calls.append((argv, how))
        if self.raises:
            raise self.raises
        return subprocess.CompletedProcess(argv, self.code, self.stdout, "claude: some words of its own\n")


def test_read_runs_agents_json_and_nothing_else_with_a_limit_of_five_seconds(tmp_path):
    ran = Ran(json.dumps([listed(str(tmp_path))]))
    env = {"PATH": "/somewhere", "HOME": "/home/sq"}
    assert live.read("claude", env, run=ran) == ({os.path.realpath(str(tmp_path)): [a_session()]}, None)
    assert ran.calls == [(["claude", "agents", "--json"],
                          {"env": env, "capture_output": True, "text": True, "check": False, "timeout": 5,
                           "stdin": subprocess.DEVNULL})]


def test_read_runs_the_command_it_is_given_as_one_argument():
    ran = Ran()
    assert live.read("/odd path/cl aude; rm -rf $HOME", {}, run=ran) == ({}, None)
    assert ran.calls[0][0] == ["/odd path/cl aude; rm -rf $HOME", "agents", "--json"]


@pytest.mark.parametrize("ran, why", [
    (Ran(raises=FileNotFoundError(2, "No such file or directory")), "claude was not found"),
    (Ran(raises=PermissionError(13, "Permission denied")), "claude could not be run (Permission denied)"),
    (Ran(code=3), "claude agents --json failed (exit 3)"),
    (Ran(raises=subprocess.TimeoutExpired(["claude"], 5)), "claude agents --json gave no answer in 5 seconds"),
    (Ran(stdout=""), "claude agents --json did not print the expected JSON"),
    (Ran(stdout="Please sign in.\n"), "claude agents --json did not print the expected JSON"),
    (Ran(stdout="{}"), "claude agents --json did not print the expected JSON"),
])
def test_a_listing_that_cannot_be_read_gives_the_reason_and_no_sessions(ran, why):
    assert live.read("claude", {}, run=ran) == (None, why)
    assert len(ran.calls) == 1          # never tried again


def test_the_reason_names_the_command_by_its_last_part_when_it_is_a_path():
    ran = Ran(raises=FileNotFoundError(2, "No such file or directory"))
    assert live.read("/opt/tools/bin/claude", {}, run=ran) == (None, "/opt/tools/bin/claude was not found")


# --- the sessions of one project ---

def test_a_folder_with_no_session_has_none():
    assert live.of({"/p/soups": [a_session()]}, "/p/stews") is None
    assert live.of({}, "/p/stews") is None


def test_one_session_is_given_with_a_count_of_one(tmp_path):
    folder = os.path.realpath(str(tmp_path))
    assert live.of({folder: [a_session()]}, folder) == {
        "name": "soups-tools · 18 October", "status": "idle", "kind": "interactive",
        "started": "2026-10-15T08:00:00Z", "pid": 4242, "count": 1}


def test_the_newest_of_several_is_given_with_every_name_oldest_first(tmp_path):
    folder = os.path.realpath(str(tmp_path))
    found = {folder: [a_session(name="first", started="2026-10-15T08:00:00Z", status="idle", pid=1),
                      a_session(name="second", started="2026-10-15T09:00:00Z", status="busy", pid=2)]}
    assert live.of(found, folder) == {
        "name": "second", "status": "busy", "kind": "interactive", "started": "2026-10-15T09:00:00Z", "pid": 2,
        "count": 2, "names": ["first", "second"]}


def test_the_newest_interactive_session_is_the_one_given_before_a_newer_one_of_another_kind(tmp_path):
    folder = os.path.realpath(str(tmp_path))
    found = {folder: [a_session(name="the session", started="2026-10-15T08:00:00Z", pid=1),
                      a_session(name="an agent", kind="background", started="2026-10-15T09:00:00Z", pid=2)]}
    assert live.of(found, folder) == {
        "name": "the session", "status": "idle", "kind": "interactive", "started": "2026-10-15T08:00:00Z", "pid": 1,
        "count": 2, "names": ["the session", "an agent (background)"]}
    only = {folder: [a_session(name="older", kind=None, started="2026-10-14T08:00:00Z"),
                     a_session(name="an agent", kind="background")]}
    assert live.of(only, folder)["name"] == "an agent"      # none interactive: the newest of them


def test_a_session_that_is_not_interactive_is_named_with_its_kind_and_one_with_no_name_is_said_so(tmp_path):
    folder = os.path.realpath(str(tmp_path))
    found = {folder: [a_session(name="a", kind="background"), a_session(name=None), a_session(name="c", kind=None)]}
    assert live.of(found, folder)["names"] == ["a (background)", "a session with no name", "c"]


def test_the_project_s_folder_matches_through_a_link_and_a_trailing_slash_but_not_a_folder_inside(tmp_path):
    real = tmp_path / "soups-tools-code"
    (real / "soups-tools").mkdir(parents=True)
    (tmp_path / "link").symlink_to(real)
    found = {os.path.realpath(str(real)): [a_session()]}
    assert live.of(found, str(tmp_path / "link") + "/")["count"] == 1
    assert live.of(found, str(real) + "/")["count"] == 1
    assert live.of(found, str(real / "soups-tools")) is None
    assert live.of({os.path.realpath(str(real / "soups-tools")): [a_session()]}, str(real)) is None


# --- where the duty and the listing disagree ---

FRESH = {"holder": "mac", "stale": False}
STALE = {"holder": "mac", "stale": True}


@pytest.mark.parametrize("state, duty, handover, count, note", [
    ("running", FRESH, False, 1, None),
    ("dormant", FRESH, False, 1, None),
    ("running", FRESH, False, 0,
     "no session alive, though its duty is fresh: a watch has outlived its session"),
    ("dormant", FRESH, False, 0,
     "no session alive, though its duty is fresh: a watch has outlived its session"),
    ("quiet", STALE, False, 1, None),
    ("quiet", STALE, False, 0, "no session alive: it ended without a handover"),
    ("stale", STALE, False, 1, "alive, not watching mail"),
    ("dormant", STALE, False, 1, "alive, not watching mail"),
    ("stale", STALE, False, 0, "no session alive: it ended without a handover"),
    ("dormant", STALE, False, 0, "no session alive: it ended without a handover"),
    ("handed-over", None, True, 1, "alive after its handover: not archived"),
    ("off", None, False, 1, "alive, not on duty"),
    ("handed-over", None, True, 0, None),
    ("off", None, False, 0, None),
    ("running", FRESH, False, 2, "2 sessions alive in its folder"),
    ("quiet", STALE, False, 3, "3 sessions alive in its folder"),
    ("stale", STALE, False, 2, "alive, not watching mail; 2 sessions alive in its folder"),
    ("handed-over", None, True, 2, "alive after its handover: not archived; 2 sessions alive in its folder"),
    ("off", None, False, 2, "alive, not on duty; 2 sessions alive in its folder"),
])
def test_the_note_follows_the_table(state, duty, handover, count, note):
    assert live.note(state, duty, handover, count) == note


# --- the field in conduct status's text ---

def test_the_text_of_a_project_with_no_session_and_no_note():
    assert live.text(None, None, []) == "no session alive"


def test_the_text_of_a_session_with_no_note_is_alive_and_the_session_in_brackets():
    assert live.text({"count": 1}, None, [a_session()]) == 'alive ("soups-tools · 18 October", idle)'


def test_the_text_leads_with_the_note():
    assert live.text(None, "no session alive: it ended without a handover", []) == (
        "no session alive: it ended without a handover")
    assert live.text({"count": 1}, "alive, not watching mail", [a_session(status="busy")]) == (
        'alive, not watching mail ("soups-tools · 18 October", busy)')


def test_the_text_names_every_session_of_several():
    both = [a_session(name="first"), a_session(name="second", status="busy", kind="background")]
    assert live.text({"count": 2}, "2 sessions alive in its folder", both) == (
        '2 sessions alive in its folder ("first", idle; "second", busy, background)')


def test_the_text_keeps_a_name_as_data_and_says_what_is_not_known():
    odd = a_session(name="a \"b\"\n$HOME é", status=None)
    assert live.text({"count": 1}, None, [odd]) == 'alive ("a \\"b\\"\\n$HOME é", status not known)'
    assert live.text({"count": 1}, None, [a_session(name=None)]) == "alive (a session with no name, idle)"
