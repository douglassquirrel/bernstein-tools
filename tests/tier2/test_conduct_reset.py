"""conduct reset: tidy the mailbox of a session that ended without handing over (PLAN.md, Settled 144)."""

import pytest
from conftest import NOW

from bernstein.conduct import reset_note

STALE = {"mailbox": "recipes", "holder": "mac", "since": "2026-10-18T09:00:00Z",
         "last_beat": "2026-10-18T09:30:00Z", "stale": True, "minutes": 3}


def mail(world):
    """Every lobster-mail call, as its arguments."""
    return [c["args"] for c in world.calls() if c["prog"] == "lobster-mail"]


def writes(world):
    """The lobster-mail calls that change a mailbox: everything but the listings a reset reads."""
    return [args for args in mail(world) if args[0] not in ("list",) and args[:2] != ["duty", "status"]]


def test_reset_refuses_an_unknown_mailbox_and_a_session_fresh_on_duty_with_exit_3_and_changes_nothing(world):
    world.duty({"recipes": "fresh"})
    code, out, err = world.conduct("reset", "menus")
    assert (code, out, err) == (3, "", f"conduct: there is no mailbox menus in {world.mail}\n")
    for argv in (("reset", "recipes"), ("reset", "recipes", "--dry-run")):
        code, out, err = world.conduct(*argv)
        assert (code, out) == (3, "")
        assert err == ("conduct: a session is on duty for recipes (mac, last beat 2026-10-18T09:30:00Z): reset is "
                       "for a session that is gone. Use conduct stop; or, if that session has just died, run "
                       "reset again once its duty has gone stale\n")
    assert writes(world) == []


WAITING = [("m-stop", "bernstein", "Stop: hand over"),
           ("m-notice", "bernstein", "Notice: the folder around your checkout now has a local git history"),
           ("m-request", "recipes-tools", "Request 4: Start: a new tool"),
           ("m-own", "recipes", "Handover 2026-10-17 18:00Z"),
           ("m-wake", "bernstein", "Wake: watch mail again"),
           ("m-start", "bernstein", "Start: recipes")]
CLAIMED = [("m-dream", "bernstein", "Dream: until 17:00Z"),
           ("m-reply", "bernstein", "Re: Request 2: the oven"),
           ("m-dormant", "bernstein", "Dormant: stop watching mail until Squirrel is back"),
           ("m-finish", "bernstein", "Finish: write up and hand over")]
CLOSED = [("m-stop", "Stop: hand over"), ("m-wake", "Wake: watch mail again"), ("m-start", "Start: recipes"),
          ("m-dream", "Dream: until 17:00Z"), ("m-dormant", "Dormant: stop watching mail until Squirrel is back"),
          ("m-finish", "Finish: write up and hand over")]


def lost(world):
    """A mailbox whose session is gone: a stale duty, and mail of every kind unread and claimed."""
    world.duty({"recipes": "stale", "recipes-tools": None})
    world.boxed("new", WAITING)
    world.boxed("open", CLAIMED)


def test_reset_closes_only_conducts_messages_then_gives_up_the_stale_duty_with_a_note_for_the_next_session(world):
    lost(world)
    code, out, err = world.conduct("reset", "recipes")
    assert (code, err) == (0, "")
    root = ["--root", world.mail]
    assert mail(world) == [
        ["duty", "status", "--all", "--json"] + root,
        ["list", "--as", "recipes", "--new", "--json"] + root,
        ["list", "--as", "recipes", "--open", "--json"] + root,
    ] + [["done", "--as", "recipes", ident] + root for ident, _subject in CLOSED] + [
        ["handover", "--as", "recipes", "--session", "mac"] + root + ["-"]]
    (handover,) = [c for c in world.calls() if c["args"][:1] == ["handover"]]
    assert handover["stdin"] == reset_note(NOW, CLOSED, STALE, None)
    assert out == ("recipes: mac is on duty but stale (last beat 2026-10-18T09:30:00Z).\n"
                   "Closed in recipes's mailbox: m-stop (\"Stop: hand over\")\n"
                   "Closed in recipes's mailbox: m-wake (\"Wake: watch mail again\")\n"
                   "Closed in recipes's mailbox: m-start (\"Start: recipes\")\n"
                   "Closed in recipes's mailbox: m-dream (\"Dream: until 17:00Z\")\n"
                   "Closed in recipes's mailbox: m-dormant (\"Dormant: stop watching mail until Squirrel is back\")\n"
                   "Closed in recipes's mailbox: m-finish (\"Finish: write up and hand over\")\n"
                   "Left a note for recipes's next session and gave up the duty of mac "
                   "(last beat 2026-10-18T09:30:00Z).\n"
                   "recipes is reset: conduct start recipes will start it afresh.\n")


NASTY = "Where I stopped: “the menu”.\nIt's $HOME `id` $(id) </script> \\n {{NAME}} — naïve ünïcode\n\n- next: the list\n"


def test_reset_passes_on_the_lost_sessions_own_note_as_data_under_its_own_lines(world, tmp_path):
    lost(world)
    note = tmp_path / "the note's file.md"
    note.write_text(NASTY, encoding="utf-8")
    code, out, err = world.conduct("reset", "recipes", "--handover", str(note))
    assert (code, err) == (0, "")
    (handover,) = [c for c in world.calls() if c["args"][:1] == ["handover"]]
    assert handover["stdin"] == reset_note(NOW, CLOSED, STALE, NASTY)
    assert handover["stdin"].endswith("\n---\n\n" + NASTY)
    assert handover["args"] == ["handover", "--as", "recipes", "--session", "mac", "--root", world.mail, "-"]
    assert note.read_text(encoding="utf-8") == NASTY
    assert "Left a note for recipes's next session, with the note from " + str(note) + ", and gave up" in out


@pytest.mark.parametrize("content, why", [
    (None, "cannot be read"), (b"", "is empty"), (b" \n\t\n", "is empty"), (b"caf\xe9\n", "is not plain UTF-8 text"),
])
def test_reset_with_a_note_that_is_missing_empty_or_not_text_is_exit_2_and_changes_nothing(world, tmp_path, content, why):
    lost(world)
    note = tmp_path / "note.md"
    if content is not None:
        note.write_bytes(content)
    code, out, err = world.conduct("reset", "recipes", "--handover", str(note))
    assert (code, out, err) == (2, "", f"conduct: the handover note {note} {why}\n")
    assert mail(world) == []


def test_reset_dry_run_shows_what_it_would_close_give_up_and_leave_and_changes_nothing(world, tmp_path):
    lost(world)
    note = tmp_path / "note.md"
    note.write_text("Where I stopped.\n", encoding="utf-8")
    code, out, err = world.conduct("reset", "recipes", "--handover", str(note), "--dry-run")
    assert (code, err) == (0, "")
    assert writes(world) == []
    assert out == (
        "recipes: mac is on duty but stale (last beat 2026-10-18T09:30:00Z).\n"
        "Would close in recipes's mailbox, as recipes:\n"
        "  m-stop (\"Stop: hand over\")\n  m-wake (\"Wake: watch mail again\")\n  m-start (\"Start: recipes\")\n"
        "  m-dream (\"Dream: until 17:00Z\")\n  m-dormant (\"Dormant: stop watching mail until Squirrel is back\")\n"
        "  m-finish (\"Finish: write up and hand over\")\n"
        "Would give up the duty of mac and leave this note for recipes's next session, as its handover:\n\n"
        + reset_note(NOW, CLOSED, STALE, "Where I stopped.\n") +
        "\nDry run: nothing was closed, given up or sent.\n")


@pytest.mark.parametrize("entry, says", [
    ({"mailbox": "recipes", "duty": STALE, "pace": "relaxed", "reported": {"status": "Dormant"}},
     ("recipes: mac is on duty but stale (last beat 2026-10-18T09:30:00Z). It reported itself dormant: a dormant "
      "session is still open in the app, so reset it only if that session is gone.\n")),
    ({"mailbox": "recipes", "duty": STALE, "pace": "relaxed"},
     ("recipes: mac is on duty but stale (last beat 2026-10-18T09:30:00Z). Its mail pace is relaxed, at which a "
      "live session's duty is stale between turns, so reset it only if that session is gone.\n")),
    ({"mailbox": "recipes", "duty": None, "handover_waiting": True}, "recipes: nobody is on duty.\n"),
])
def test_reset_says_first_what_state_the_mailbox_is_in_and_warns_when_a_stale_duty_may_be_a_live_session(world, entry, says):
    world.listing([entry])
    world.boxed("new", WAITING[:1])
    for argv in (("reset", "recipes", "--dry-run"), ("reset", "recipes")):
        code, out, _err = world.conduct(*argv)
        assert code == 0 and out.startswith(says + ("Would close" if "--dry-run" in argv else "Closed"))


def test_reset_with_nobody_on_duty_and_nothing_from_conduct_waiting_does_nothing_and_says_so(world):
    world.duty({"recipes": "handed over"})
    world.boxed("new", [m for m in WAITING if m[1] != "bernstein" or m[2].startswith("Notice")])
    world.boxed("open", CLAIMED[1:2])
    for argv in (("reset", "recipes"), ("reset", "recipes", "--dry-run")):
        code, out, err = world.conduct(*argv)
        assert (code, err) == (0, "")
        assert out == ("recipes: nobody is on duty.\nNothing to reset for recipes: no message from conduct waits "
                       "in its mailbox, and no note was given to pass on.\n")
    assert writes(world) == []


def test_reset_with_nobody_on_duty_still_closes_what_waits_and_passes_on_a_note(world, tmp_path):
    world.duty({"recipes": None})
    world.boxed("new", WAITING[:1])
    code, out, err = world.conduct("reset", "recipes", "--dry-run")
    assert (code, err) == (0, "") and writes(world) == []
    assert ("Would leave this note for recipes's next session, as its handover (nobody is on duty, so no duty is "
            "given up):\n\n" + reset_note(NOW, CLOSED[:1], None, None)) in out
    code, out, err = world.conduct("reset", "recipes")
    assert (code, err) == (0, "")
    assert writes(world) == [["done", "--as", "recipes", "m-stop", "--root", world.mail],
                             ["handover", "--as", "recipes", "--session", "conduct-reset", "--root", world.mail, "-"]]
    assert world.calls()[-1]["stdin"] == reset_note(NOW, CLOSED[:1], None, None)
    assert out.endswith("Left a note for recipes's next session.\n"
                        "recipes is reset: conduct start recipes will start it afresh.\n")
    world.boxed("new", [])
    note = tmp_path / "n.md"
    note.write_text("The lost note.\n", encoding="utf-8")
    code, out, err = world.conduct("reset", "recipes", "--handover", str(note), "--dry-run")
    assert code == 0 and "Would close nothing: no message from conduct waits in recipes's mailbox.\n" in out
    code, out, err = world.conduct("reset", "recipes", "--handover", str(note))
    assert (code, err) == (0, "")
    assert world.calls()[-1]["stdin"] == reset_note(NOW, [], None, "The lost note.\n")
    assert out == ("recipes: nobody is on duty.\n"
                   f"Left a note for recipes's next session, with the note from {note}.\n"
                   "recipes is reset: conduct start recipes will start it afresh.\n")


@pytest.mark.parametrize("box, printed", [
    ("new", ""), ("new", "not json"), ("new", "{}"), ("new", '[{"id": "m0", "from": "bernstein"}]'),
    ("new", '["text"]'), ("new", "[3]"), ("new", '[{"id": 7, "from": "bernstein", "subject": "Stop: hand over"}]'),
    ("new", '[{"id": "m0", "from": "bernstein", "subject": 9}]'), ("open", "not json"), ("open", "{}"),
])
def test_reset_with_a_mailbox_listing_that_cannot_be_read_is_exit_4_and_changes_nothing(world, box, printed):
    lost(world)
    world.boxed(box, printed)
    code, out, err = world.conduct("reset", "recipes")
    assert (code, out) == (4, "")
    assert err == f"conduct: lobster-mail list --{box} --json did not print the expected JSON for recipes\n"
    assert writes(world) == []


def test_reset_that_fails_part_way_says_what_was_closed_and_which_step_failed_and_leaves_no_note(world):
    lost(world)
    world.fail("lobster-mail:done:3")
    code, out, err = world.conduct("reset", "recipes")
    assert code == 4
    assert out == "recipes: mac is on duty but stale (last beat 2026-10-18T09:30:00Z).\n"
    assert err == ("conduct: lobster-mail done m-stop for recipes failed (exit 3)\n  lobster-mail: stub failure\n"
                   "  Nothing was closed and no note was left; the duty of mac stands. Run conduct reset recipes "
                   "again when the cause is mended\n")
    assert [args[0] for args in writes(world)] == ["done"]


def test_reset_whose_note_cannot_be_left_says_what_was_closed_and_that_the_duty_stands(world):
    lost(world)
    world.fail("lobster-mail:handover")
    code, out, err = world.conduct("reset", "recipes")
    assert code == 4 and out.count("Closed in recipes's mailbox: ") == 6 and "Left a note" not in out
    assert err == ("conduct: lobster-mail handover for recipes failed (exit 1)\n  lobster-mail: stub failure\n"
                   "  6 messages were closed, but no note was left; the duty of mac stands. Run conduct reset "
                   "recipes again when the cause is mended\n")


def test_help_names_reset_and_its_options(world):
    code, out, _err = world.conduct("--help")
    assert code == 0 and "conduct reset <project> [--handover FILE] [--dry-run]\n" in out
    code, out, _err = world.conduct("reset", "--help")
    assert code == 0 and "--handover FILE" in out and "--dry-run" in out
