"""After a Start that worked, podium checks where the new session opened (PLAN.md, "podium shows each live
session in detail", 4; Settled 175). It compares what conduct status --json says is alive with the Starts it
remembers; it stops and archives nothing. Every name and folder here is invented."""

import datetime
import json
import subprocess

import pytest
from test_podium_live import LIVE, a_row
from test_podium_view import NOW

from bernstein import podium

SENT = NOW - datetime.timedelta(minutes=2)          # when the Start was sent: 09:38:05 UTC
WAITING = "No new session in this project's folder yet: in the app, confirm the folder and send the first line."
NONE = "No session has appeared: was the first line sent?"
WRONG = ("A session that started after this Start is alive in {}, which is no project's folder, and none is in "
         "this project's folder: it may have opened in the wrong folder. If so, stop that session in the app, press "
         "Start again, and before you send the first line change the form's folder to another and back.")


def started(seconds_after, **more):
    """A live session that started so long after the Start was sent."""
    when = SENT + datetime.timedelta(seconds=seconds_after)
    return dict(LIVE, started=f"{when:%Y-%m-%dT%H:%M:%SZ}", **more)


def away(folder, seconds_after, name="a stray"):
    when = SENT + datetime.timedelta(seconds=seconds_after)
    return {"folder": folder, "name": name, "status": "idle", "kind": "interactive",
            "started": f"{when:%Y-%m-%dT%H:%M:%SZ}", "pid": 7}


def top(*elsewhere, read=True):
    return {"live_listing": {"read": read, "why": None if read else "x"},
            "live_elsewhere": list(elsewhere) if read else None}


def sent(project="soups-tools", entry=0, at=SENT):
    return {project: {"at": at, "entry": entry, "right": None}}


def check(starts, rows, told, now=NOW):
    return podium.start_checks(starts, rows, told, now)


def one(starts, rows, told, now=NOW):
    (found,) = check(starts, rows, told, now)
    return found


def later(minutes):
    return SENT + datetime.timedelta(minutes=minutes)


# --- what happened ---

def test_a_new_session_in_the_project_s_folder_is_started_in_the_right_folder_with_its_name_and_model():
    rows = [a_row("off", None, live=started(40, model="claude-fable-5-2", effort="xhigh"))]
    assert one(sent(), rows, top()) == {
        "project": "soups-tools", "entry": 0, "state": "right", "line": True,
        "said": "Started, in the right folder: soups-tools · 18 October. It is running on claude-fable-5-2, xhigh."}
    assert one(sent(), [a_row("off", None, live=started(0, model="invented", name=None))], top())["said"] == (
        "Started, in the right folder: a session with no name. It is running on invented.")
    assert one(sent(), [a_row("off", None, live=started(1))], top())["said"] == (
        "Started, in the right folder: soups-tools · 18 October.")


def test_a_session_that_began_before_the_start_is_not_taken_for_the_new_one():
    rows = [a_row("off", None, live=started(-1))]
    assert one(sent(), rows, top())["state"] == "waiting"
    assert one(sent(), rows, top(), now=later(11))["state"] == "none"


def test_nothing_new_is_waited_for_for_ten_minutes_and_then_said_not_to_have_appeared():
    rows = [a_row("off", None)]
    assert one(sent(), rows, top()) == {"project": "soups-tools", "entry": 0, "state": "waiting", "line": True,
                                        "said": WAITING}
    assert one(sent(), rows, top(), now=later(10))["state"] == "waiting"
    late = one(sent(), rows, top(), now=later(10) + datetime.timedelta(seconds=1))
    assert (late["state"], late["said"], late["line"]) == ("none", NONE, True)


def test_a_new_session_in_no_project_s_folder_and_none_in_the_project_s_is_a_warning_naming_the_folder():
    rows = [a_row("off", None)]
    found = one(sent(), rows, top(away("/Users/sq", 30)))
    assert (found["state"], found["line"], found["said"]) == ("wrong", True, WRONG.format("/Users/sq"))
    both = one(sent(), rows, top(away("/Users/sq", 30), away("/tmp/x y", 50)))
    assert both["said"] == WRONG.format("/Users/sq and /tmp/x y")
    same = one(sent(), rows, top(away("/Users/sq", 30), away("/Users/sq", 50)))
    assert same["said"] == WRONG.format("/Users/sq")


def test_a_session_elsewhere_that_began_before_the_start_or_has_no_start_is_not_a_new_one():
    rows = [a_row("off", None)]
    old = away("/Users/sq", -5)
    unknown = dict(away("/Users/sq", 5), started=None)
    assert one(sent(), rows, top(old, unknown, "not a session", {"folder": 7, "started": "2026-10-18T09:39:00Z"})
               )["state"] == "waiting"


def test_a_new_session_in_each_is_the_right_folder():
    rows = [a_row("off", None, live=started(40))]
    assert one(sent(), rows, top(away("/Users/sq", 30)))["state"] == "right"


def test_the_warning_stands_while_the_stray_session_is_alive_and_gives_way_when_it_is_gone():
    rows = [a_row("off", None)]
    assert one(sent(), rows, top(away("/Users/sq", 30)), now=later(45))["state"] == "wrong"
    assert one(sent(), rows, top(), now=later(45))["state"] == "none"


def test_right_once_seen_stays_right_after_that_session_has_gone():
    starts = sent()
    assert one(starts, [a_row("off", None, live=started(40))], top())["state"] == "right"
    gone = one(starts, [a_row("off", None)], top(away("/Users/sq", 50)), now=later(20))
    assert (gone["state"], gone["said"], gone["line"]) == (
        "right", "Started, in the right folder: soups-tools · 18 October.", False)


# --- where it is said, and for how long ---

@pytest.mark.parametrize("state_rows, elsewhere, minutes, state, on_line", [
    ("new", (), 9, "right", True), ("new", (), 11, "right", False),
    ("none", (), 9, "waiting", True),
    ("none", (), 11, "none", True), ("none", (), 30, "none", True), ("none", (), 31, "none", False),
    ("none", ("/Users/sq",), 9, "wrong", True), ("none", ("/Users/sq",), 600, "wrong", True),
])
def test_the_line_says_it_while_it_is_news_and_a_warning_for_as_long_as_it_is_so(state_rows, elsewhere, minutes,
                                                                                state, on_line):
    rows = [a_row("off", None, live=started(40) if state_rows == "new" else None)]
    found = one(sent(), rows, top(*[away(folder, 30) for folder in elsewhere]), now=later(minutes))
    assert (found["state"], found["line"]) == (state, on_line)


# --- several Starts, and the ones that are not checked ---

def test_with_two_starts_waited_for_a_stray_session_may_be_either_s():
    rows = [a_row("off", None), dict(a_row("off", None), mailbox="stews-tools", folder="/p/stews-tools")]
    starts = dict(sent("soups-tools", 0), **sent("stews-tools", 1))
    first, second = check(starts, rows, top(away("/Users/sq", 30)))
    assert first["said"] == WRONG.format("/Users/sq") + " A Start of stews-tools is waited for too: it may be that one's."
    assert second["said"] == WRONG.format("/Users/sq") + " A Start of soups-tools is waited for too: it may be that one's."
    rows[1] = dict(rows[1], live=started(20))
    first, second = check(starts, rows, top(away("/Users/sq", 30)))
    assert (first["said"], second["state"]) == (WRONG.format("/Users/sq"), "right")


@pytest.mark.parametrize("rows, told", [
    ([a_row("off", None)], top(read=False)),                            # the listing was not read
    ([a_row("off", None)], None),
    ([a_row("off", None)], {}),
    ([a_row("off", None)], {"live_listing": "odd", "live_elsewhere": []}),
    ([dict(a_row("off", None), runs_in="cowork")], top()),              # a Cowork project: the listing cannot see it
    ([dict(a_row("off", None), runs_in=None)], top()),
    ([dict(a_row("off", None), mailbox="another")], top()),             # the project is no longer listed
    ([], top()),
])
def test_a_start_that_cannot_be_checked_says_nothing_and_is_not_forgotten(rows, told):
    starts = sent()
    assert check(starts, rows, told) == []
    assert starts == sent()
    assert one(starts, [a_row("off", None, live=started(40))], top())["state"] == "right"


def test_checks_come_in_the_order_the_starts_were_sent_and_no_starts_give_none():
    rows = [dict(a_row("off", None), mailbox=name) for name in ("a-tools", "b-tools")]
    starts = dict(sent("b-tools", 0), **sent("a-tools", 3))
    assert [(c["project"], c["entry"]) for c in check(starts, rows, top())] == [("b-tools", 0), ("a-tools", 3)]
    assert check({}, rows, top()) == []


# --- the panel remembers the Starts it sent ---

RAW = json.dumps({"root": "/m", "mailboxes": [a_row("off", None)], "skipped": [], **top()})


class Conduct:
    def __init__(self, code=0):
        self.code, self.raw = code, RAW

    def __call__(self, argv, **kwargs):
        if argv[1:] == ["status", "--json"]:
            return subprocess.CompletedProcess(argv, 0, self.raw, "")
        return subprocess.CompletedProcess(argv, self.code, "started\n", "")


class Clock:
    """A clock that moves a second each time it is read."""

    def __init__(self):
        self.now = SENT

    def __call__(self):
        self.now += datetime.timedelta(seconds=1)
        return self.now


def a_panel(tmp_path, code=0):
    return podium.Panel("/x/conduct", {"HOME": "/h"}, Clock(), str(tmp_path / "podium.log"), run=Conduct(code))


def test_a_start_that_worked_is_remembered_from_before_conduct_ran_with_its_place_in_the_activity(tmp_path):
    panel = a_panel(tmp_path)
    panel.send({"verb": "wake", "project": "soups-tools"})
    panel.send({"verb": "start", "project": "soups-tools"})
    assert panel.starts == {"soups-tools": {"at": SENT + datetime.timedelta(seconds=2), "entry": 1, "right": None}}
    assert panel.entries[1]["time"] == f"{SENT + datetime.timedelta(seconds=3):%Y-%m-%dT%H:%M:%SZ}"
    assert sorted(panel.entries[1]) == ["command", "error", "exit", "log_error", "output", "reminder", "time"]


def test_a_start_that_failed_and_any_other_verb_are_not_remembered(tmp_path):
    panel = a_panel(tmp_path, code=3)
    panel.send({"verb": "start", "project": "soups-tools"})
    assert panel.starts == {}
    panel = a_panel(tmp_path)
    for verb in ("stop", "dormant", "wake", "dream"):
        panel.send({"verb": verb, "project": "soups-tools"})
    assert panel.starts == {}


def test_a_later_start_of_the_same_project_takes_the_place_of_the_earlier(tmp_path):
    panel = a_panel(tmp_path)
    panel.send({"verb": "start", "project": "soups-tools"})
    panel.send({"verb": "start", "project": "soups-tools"})
    assert list(panel.starts) == ["soups-tools"] and panel.starts["soups-tools"]["entry"] == 1


def test_the_panel_s_checks_are_start_checks_of_what_it_remembers(tmp_path):
    panel = a_panel(tmp_path)
    panel.send({"verb": "start", "project": "soups-tools"})
    rows = [a_row("off", None, live=started(40))]
    assert panel.checks(rows, top(), NOW) == podium.start_checks(dict(panel.starts), rows, top(), NOW)
    assert panel.starts["soups-tools"]["right"] is not None             # and what it saw is kept


# --- on the page ---

RUN = {"time": "2026-10-18T09:38:06Z", "command": "conduct start soups-tools", "exit": 0, "output": "started\n",
       "error": "", "reminder": podium.REMINDER, "log_error": None}


def a_check(state, said, line=True, project="soups-tools", entry=0):
    return {"project": project, "entry": entry, "state": state, "said": said, "line": line}


@pytest.mark.parametrize("state, mark", [("right", "started right"), ("waiting", "started"),
                                         ("wrong", "started wrong"), ("none", "started wrong")])
def test_the_check_is_said_on_the_project_s_line_and_under_its_start_in_the_activity(state, mark):
    html = podium.view([a_row("off", None)], NOW, entries=[RUN], checks=[a_check(state, "What happened & <where>.")])
    said = f'<p class="{mark}">What happened &amp; &lt;where&gt;.</p>'
    assert html.count(said) == 2
    line, log = html.split("<h2>Activity</h2>")
    assert said in line and said in log
    assert log.index(said) > log.index('<p class="remind">')


def test_a_check_that_is_no_longer_news_is_said_in_the_activity_only():
    html = podium.view([a_row("off", None)], NOW, entries=[RUN], checks=[a_check("right", "Started.", line=False)])
    line, log = html.split("<h2>Activity</h2>")
    assert "Started." not in line and '<p class="started right">Started.</p>' in log


def test_a_check_goes_to_its_own_line_and_its_own_run():
    rows = [a_row("off", None), dict(a_row("off", None), mailbox="stews-tools")]
    other = dict(RUN, command="conduct start stews-tools")
    html = podium.view(rows, NOW, entries=[RUN, other], checks=[a_check("wrong", "Wrong folder.", project="stews-tools",
                                                                        entry=1)])
    line, log = html.split("<h2>Activity</h2>")
    assert line.index("Wrong folder.") > line.index("stews-tools")
    newest, older = log.split('<div class="run">')[1:]                  # the Activity is newest first
    assert "Wrong folder." in newest and "conduct start stews-tools" in newest and "Wrong folder." not in older


def test_with_no_checks_the_page_is_the_page_of_before():
    assert podium.view([a_row("off", None)], NOW, entries=[RUN], checks=[]) == podium.view(
        [a_row("off", None)], NOW, entries=[RUN])
    assert 'class="started' not in podium.view([a_row("off", None)], NOW, entries=[RUN])


def test_the_page_asked_for_is_made_with_the_panel_s_checks(tmp_path):
    panel = a_panel(tmp_path)
    panel.send({"verb": "start", "project": "soups-tools"})
    panel.run.raw = json.dumps({"root": "/m", "mailboxes": [a_row("off", None)], "skipped": [],
                                **top(away("/Users/sq <x>", 30))})
    code, _kind, body = podium.answer("GET", "/view?t=secret", b"", "secret", panel, NOW)
    assert code == 200
    assert body.count('<p class="started wrong">' + podium.e(WRONG.format("/Users/sq <x>")) + "</p>") == 2
    assert "<x>" not in body


def test_the_start_is_timed_before_conduct_runs_so_a_session_opened_while_it_ran_counts_as_new(tmp_path):
    panel = a_panel(tmp_path)
    plain = panel.run

    def slow(argv, **kwargs):
        if argv[1:2] == ["start"]:
            panel.clock.now += datetime.timedelta(seconds=20)       # conduct start takes its time
        return plain(argv, **kwargs)

    panel.run = slow
    panel.send({"verb": "start", "project": "soups-tools"})
    assert panel.starts["soups-tools"]["at"] == SENT + datetime.timedelta(seconds=1)
    rows = [a_row("off", None, live=started(10))]                   # opened ten seconds in, while conduct ran
    assert panel.checks(rows, top(), NOW)[0]["state"] == "right"

