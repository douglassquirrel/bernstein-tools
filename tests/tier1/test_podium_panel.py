import datetime
import json
import os
import subprocess

import pytest

from bernstein import podium

NOW = datetime.datetime(2026, 10, 18, 9, 40, 5, tzinfo=datetime.timezone.utc)
ROWS = [{"mailbox": name, "state": "running"} for name in ("bernstein", "recipes", "recipes-tools")]
RAW = json.dumps({"root": "/m", "mailboxes": ROWS, "skipped": []})


class Conduct:
    """Stands in for running conduct: records each call (and the brief file's text while it exists)."""

    def __init__(self):
        self.calls, self.briefs, self.during = [], [], None
        self.answer = (0, "done\n", "")

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if argv[1:] == ["status", "--json"]:
            return subprocess.CompletedProcess(argv, 0, RAW, "")
        if "--brief" in argv:
            path = argv[argv.index("--brief") + 1]
            with open(path, encoding="utf-8") as f:
                self.briefs.append((path, f.read()))
        if self.during:
            self.during()
        if isinstance(self.answer, Exception):
            raise self.answer
        code, out, err = self.answer
        return subprocess.CompletedProcess(argv, code, out, err)

    def actions(self):
        return [argv[1:] for argv, _ in self.calls if argv[1:] != ["status", "--json"]]


@pytest.fixture
def conduct():
    return Conduct()


@pytest.fixture
def panel(conduct, tmp_path):
    return podium.Panel("/x/conduct", {"HOME": "/h"}, lambda: NOW, str(tmp_path / "logs" / "podium.log"), run=conduct)


def test_an_action_is_run_for_real_at_once_and_recorded(panel, conduct):
    conduct.answer = (0, "Sent the Dream message to recipes.\n", "")
    code, entry = panel.send({"verb": "dream", "all": True, "minutes": 30, "then": "stop"})
    assert code == 200 and entry == {
        "time": "2026-10-18T09:40:05Z", "command": "conduct dream --all --minutes 30 --then stop", "exit": 0,
        "output": "Sent the Dream message to recipes.\n", "error": "", "reminder": None, "log_error": None}
    assert conduct.actions() == [["dream", "--all", "--minutes", "30", "--then", "stop"]]
    argv, kwargs = conduct.calls[-1]
    assert argv[0] == "/x/conduct"
    assert kwargs == {"env": {"HOME": "/h"}, "capture_output": True, "text": True, "check": False, "timeout": 60}
    assert panel.entries == [entry]


def test_podium_has_no_preview_and_never_runs_conduct_with_dry_run(panel, conduct):
    assert not hasattr(panel, "preview") and not hasattr(podium, "GONE")
    for action in ({"verb": "start", "project": "recipes", "brief": "x", "pace": "eager", "name": "n"},
                   {"verb": "stop", "project": "recipes", "wait": 5}, {"verb": "stop", "all": True},
                   {"verb": "dormant", "project": "recipes"}, {"verb": "wake", "all": True},
                   {"verb": "dream", "project": "recipes", "minutes": 5, "then": "dormant"}):
        assert panel.send(action)[0] == 200
    assert len(conduct.actions()) == 6
    assert not [argv for argv in conduct.actions() if "--dry-run" in argv]
    assert not [entry for entry in panel.entries if "--dry-run" in entry["command"]]


def test_the_same_action_sent_twice_is_run_twice(panel, conduct):
    for _ in range(2):
        assert panel.send({"verb": "wake", "project": "recipes"})[0] == 200
    assert conduct.actions() == [["wake", "recipes"], ["wake", "recipes"]] and len(panel.entries) == 2


def test_an_action_conduct_refuses_is_recorded_with_its_message(panel, conduct):
    conduct.answer = (3, "", "conduct: a session is already running for recipes\n")
    code, entry = panel.send({"verb": "start", "project": "recipes"})
    assert code == 200 and (entry["command"], entry["exit"], entry["output"], entry["reminder"]) == (
        "conduct start recipes", 3, "", None)
    assert entry["error"] == "conduct: a session is already running for recipes\n"
    assert panel.entries == [entry]


@pytest.mark.parametrize("action, why", [
    ({"verb": "stop", "project": "nope"}, "'nope' is not a mailbox in the listing podium last showed"),
    ({"verb": "rm"}, "podium does not offer the verb 'rm'"),
    ({"verb": "stop", "project": "recipes", "dry_run": True}, "stop does not take dry_run"),
    ({"verb": "dream", "project": "recipes", "minutes": 4}, "the minutes must be a whole number from 5 to 240"),
    (None, "an action must be a JSON object"),
    ("ticket-1", "an action must be a JSON object"),
    (["stop", "recipes"], "an action must be a JSON object"),
])
def test_an_action_podium_does_not_offer_is_400_and_conduct_is_not_run(panel, conduct, tmp_path, action, why):
    assert panel.send(action) == (400, {"error": why})
    assert conduct.actions() == [] and panel.entries == [] and not (tmp_path / "logs").exists()


def test_the_names_come_from_the_last_listing_asked_for_once_if_there_has_been_none(panel, conduct):
    panel.send({"verb": "stop", "project": "recipes"})
    panel.send({"verb": "stop", "project": "recipes-tools"})
    assert [argv[1:] for argv, _ in conduct.calls].count(["status", "--json"]) == 1
    panel.listing()
    assert [argv[1:] for argv, _ in conduct.calls].count(["status", "--json"]) == 2


def test_a_brief_goes_to_conduct_as_a_file_that_is_gone_afterwards(panel, conduct):
    brief = 'Line one.\n"quotes" \\ $HOME `id` </script> café\n'
    code, entry = panel.send({"verb": "start", "project": "recipes", "pace": "eager", "brief": brief})
    assert code == 200
    assert [text for _, text in conduct.briefs] == [brief]
    assert conduct.actions()[0][:5] == ["start", "recipes", "--pace", "eager", "--brief"]
    assert len(conduct.actions()) == 1 and len(conduct.actions()[0]) == 6
    assert all(not os.path.exists(path) for path, _ in conduct.briefs)
    assert entry["command"] == ("conduct start recipes --pace eager --brief <the brief typed in podium, "
                                f"{len(brief)} characters>")


def test_the_brief_file_is_removed_even_when_conduct_cannot_be_run(panel, conduct):
    conduct.answer = FileNotFoundError(2, "No such file or directory")
    code, entry = panel.send({"verb": "start", "project": "recipes", "brief": "x"})
    assert (code, entry["exit"], entry["reminder"]) == (200, None, None)
    assert entry["error"] == "/x/conduct could not be run (No such file or directory)"
    assert all(not os.path.exists(path) for path, _ in conduct.briefs) and len(conduct.briefs) == 1


def test_a_run_that_does_not_finish_in_time_says_some_of_it_may_have_been_done(panel, conduct):
    conduct.answer = subprocess.TimeoutExpired(["conduct"], 660)
    code, entry = panel.send({"verb": "stop", "project": "recipes", "wait": 600})
    assert conduct.calls[-1][1]["timeout"] == 660          # the wait, and a minute
    assert code == 200 and entry["exit"] is None and entry["output"] == ""
    assert entry["error"] == ("conduct was stopped after 660 seconds without finishing; some of it may have been "
                              "done: look at the page before trying again")


def test_a_second_action_while_one_runs_is_409_busy_and_is_not_run(panel, conduct):
    seen = []
    conduct.during = lambda: seen.append(panel.send({"verb": "wake", "project": "recipes"}))
    assert panel.send({"verb": "stop", "project": "recipes"})[0] == 200
    assert seen == [(409, {"error": "podium is busy with another action: try again when it has finished"})]
    assert conduct.actions() == [["stop", "recipes"]]
    conduct.during = None
    assert panel.send({"verb": "wake", "project": "recipes"})[0] == 200       # free again afterwards


def test_each_run_is_appended_to_the_log_file_whose_folder_is_made(panel, conduct, tmp_path):
    for verb, answer in (("stop", (0, "Sent the Stop message to recipes.\n", "")),
                         ("start", (3, "", "conduct: a session is already running for recipes\n  mac since 09:00\n"))):
        conduct.answer = answer
        assert panel.send({"verb": verb, "project": "recipes"})[1]["log_error"] is None
    assert (tmp_path / "logs" / "podium.log").read_text(encoding="utf-8") == (
        "2026-10-18T09:40:05Z  conduct stop recipes  (exit 0)\n"
        "  Sent the Stop message to recipes.\n"
        "2026-10-18T09:40:05Z  conduct start recipes  (exit 3)\n"
        "  conduct: a session is already running for recipes\n"
        "    mac since 09:00\n")


def test_the_log_is_added_to_never_written_over(panel, conduct, tmp_path):
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "podium.log").write_text("earlier line\n", encoding="utf-8")
    panel.send({"verb": "wake", "all": True})
    text = (tmp_path / "logs" / "podium.log").read_text(encoding="utf-8")
    assert text.startswith("earlier line\n2026-10-18T09:40:05Z  conduct wake --all  (exit 0)\n")


def test_when_the_log_cannot_be_written_the_run_still_counts_and_says_so(conduct, tmp_path):
    (tmp_path / "file").write_text("x")
    path = str(tmp_path / "file" / "podium.log")            # its folder is a file: it cannot be made
    panel = podium.Panel("/x/conduct", {}, lambda: NOW, path, run=conduct)
    code, entry = panel.send({"verb": "wake", "all": True})
    assert code == 200 and entry["exit"] == 0
    assert entry["log_error"].startswith(f"the log {path} could not be written (")
    assert panel.entries == [entry]


def test_a_start_that_worked_reminds_him_what_only_he_can_do_in_the_app(panel, conduct):
    entry = panel.send({"verb": "start", "project": "recipes"})[1]
    assert entry["reminder"] == (
        "Now in the desktop app: confirm the folder or folders it shows, then send the first line. If it is a "
        "Claude Code session, check its folder is the project's before anything else (the app has dropped it "
        "before), and ask a bernstein session to set its model and effort.")
    assert panel.send({"verb": "stop", "project": "recipes"})[1]["reminder"] is None


def test_a_start_that_failed_has_no_reminder(panel, conduct):
    conduct.answer = (4, "", "conduct: open failed\n")
    assert panel.send({"verb": "start", "project": "recipes"})[1]["reminder"] is None


def test_the_listing_is_what_ask_conduct_gives_and_a_failed_one_keeps_the_earlier_names(panel, conduct):
    assert panel.listing() == (ROWS, RAW, None)
    panel.run = lambda argv, **kw: subprocess.CompletedProcess(argv, 4, "", "conduct: gone\n")
    assert panel.listing() == ([], None, "conduct status failed (exit 4)\n  conduct: gone")
    panel.run = conduct
    assert panel.send({"verb": "stop", "project": "recipes"})[0] == 200
