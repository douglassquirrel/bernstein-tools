import datetime
import os
from urllib.parse import quote as urlquote

import pytest

from bernstein.conduct import (
    ProjectRefused,
    find_project,
    link_for,
    name_refusal,
    session_name,
    start_message,
    stop_message,
)

DAY = datetime.date(2026, 10, 18)


def quote(text):
    return urlquote(text, safe="")


def test_a_session_is_named_for_its_project_and_the_day_unless_a_name_is_given():
    assert session_name("recipes-tools", DAY) == "recipes-tools · 18 October"
    assert session_name("recipes", DAY, "  Sunday's menu  ") == "Sunday's menu"


@pytest.mark.parametrize("given, why", [
    ("", "the name is empty"),
    ("   ", "the name is empty"),
    ("one\ntwo", "the name must be one line"),
    ("x" * 61, "the name is longer than 60 characters"),
])
def test_a_name_that_is_empty_has_two_lines_or_is_too_long_is_refused(given, why):
    assert name_refusal(given) == why


def test_a_name_of_sixty_characters_with_quotes_and_accents_is_accepted():
    assert name_refusal("é\"$'<" + "x" * 55) is None


def test_the_start_message_points_to_start_here_names_the_session_and_waits_without_a_brief():
    assert start_message(None, DAY, "recipes · 18 October") == (
        "Start (from bernstein, 18 October 2026).\n\n"
        "Squirrel has started this session through bernstein. Follow START-HERE.txt in this\n"
        "project's folder from the top: step 0 (the model and effort question) first, then the\n"
        "mail and the rest. If lobster-mail start says a status is being reported for this mailbox, an\n"
        "earlier session left it: clear it with the command start prints.\n\n"
        "This session's name is \"recipes · 18 October\". If you have a tool that names or renames a\n"
        "session, give this session (\"self\") exactly that title now, so Squirrel can find it in his list;\n"
        "if you have no such tool, say so in your reply to this message.\n\n"
        "Then wait for Squirrel.\n")


def test_the_start_message_carries_the_brief_word_for_word():
    text = start_message("Draft the menu for Sunday.\nKeep it vegetarian.\n", DAY, "recipes · 18 October")
    assert text.endswith("Then this brief, from Squirrel:\n\nDraft the menu for Sunday.\nKeep it vegetarian.\n")


def test_the_stop_message_asks_for_a_handover_at_a_safe_point():
    assert stop_message(DAY) == (
        "Stop (from bernstein, 18 October 2026).\n\n"
        "Squirrel has asked this session to hand over and stop. At the next safe point (nothing\n"
        "half-edited, nothing half-committed): bring the record up to date, send the handover with\n"
        "lobster-mail handover, stop watching mail and stop the check-in chain, tell Squirrel in\n"
        "chat that bernstein asked you to hand over, and do nothing more unless he says.\n\n"
        "Then, as the very last thing, after your reply to this message: archive this session, so it\n"
        "leaves his list of sessions. In Claude Code in the desktop app that is the archive tool with\n"
        "the session \"self\", which he approves on the card the app shows; nothing may still be\n"
        "running in the background when you call it. If you have no tool that archives a session, say\n"
        "so in your last line to him instead.\n")


def make(tmp_path, rel, kind, sister):
    folder = tmp_path / rel
    folder.mkdir(parents=True)
    (folder / "lobster.conf").write_text(f"KIND={kind}\nSISTER={sister}\nMODEL=opus\nEFFORT=high\n")
    (folder / "START-HERE.txt").write_text("Start.\n")
    return str(folder)


def test_find_project_for_each_kind_and_layout(tmp_path):
    nc = make(tmp_path, "non-code/recipes", "non-code", "recipes-tools")
    tools = make(tmp_path, "code/recipes-tools", "code", "recipes")
    p = find_project("recipes", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert (p.name, p.kind, p.folder, p.sister, p.claws) == ("recipes", "non-code", nc, "recipes-tools", [(tools, None)])
    q = find_project("recipes-tools", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert (q.kind, q.folder, q.checkout) == ("code", tools, tools)


def test_find_project_for_a_public_tools_project(tmp_path):
    outer = make(tmp_path, "code/pub-tools-code", "code", "pub")
    os.makedirs(os.path.join(outer, "pub-tools"))
    make(tmp_path, "non-code/pub", "non-code", "pub-tools")
    q = find_project("pub-tools", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert (q.folder, q.checkout) == (outer, os.path.join(outer, "pub-tools"))
    p = find_project("pub", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert p.claws == [(os.path.join(outer, "pub-tools"), None)]


def test_find_project_refuses_a_project_with_no_folder_or_no_settings(tmp_path):
    with pytest.raises(ProjectRefused) as refused:
        find_project("nope", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert str(refused.value) == (f"no project nope in {tmp_path / 'non-code'} or {tmp_path / 'code'}, or a folder "
                                  "directly inside either")
    os.makedirs(tmp_path / "non-code" / "bare")
    with pytest.raises(ProjectRefused) as refused:
        find_project("bare", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert str(refused.value) == "%s has no lobster.conf: is it a lobster project?" % (tmp_path / "non-code" / "bare")


def test_the_link_for_a_non_code_project_connects_its_four_folders(tmp_path):
    make(tmp_path, "non-code/recipes", "non-code", "recipes-tools")
    make(tmp_path, "code/recipes-tools", "code", "recipes")
    p = find_project("recipes", str(tmp_path / "non-code"), str(tmp_path / "code"))
    link = link_for(p, "/m/mail", "/l/lobster-tools", "recipes · 18 October")
    enc = lambda s: s.replace("/", "%2F")
    assert link == ("claude://cowork/new?folder=" + enc(p.folder) + "&folder=%2Fm%2Fmail"
                    "&folder=" + enc(p.claws[0][0]) + "&folder=%2Fl%2Flobster-tools"
                    "&q=" + quote("Session title: recipes · 18 October. Read START-HERE.txt in the recipes folder (mounted at ~/mnt/recipes) and do "
                                  "what it says, starting with its step 0 before anything else. If ~/mnt/recipes "
                                  "is not there, say \"the app opened me without the recipes folder\" and stop."))


def test_the_link_for_a_tools_project_opens_claude_code_in_its_folder(tmp_path):
    make(tmp_path, "code/recipes-tools", "code", "recipes")
    q = find_project("recipes-tools", str(tmp_path / "non-code"), str(tmp_path / "code"))
    assert link_for(q, "/m/mail", "/l/lobster-tools", "Fix the \"oven\" & more") == (
        "claude://code/new?folder=" + quote(q.folder) + "&q=" + quote(
            "Session title: Fix the \"oven\" & more. This session must work in " + q.folder + ". If your working folder is anything else, say \"the app "
            "opened me in the wrong folder\" and stop. Otherwise read START-HERE.txt there and do what it says, "
            "starting with its step 0 before anything else."))


def test_the_dormant_message_says_keep_running_stop_watching_and_how_to_wake():
    from bernstein.conduct import dormant_message
    assert dormant_message("recipes", DAY) == (
        "Dormant (from bernstein, 18 October 2026).\n\n"
        "Squirrel has asked this session to go dormant until he comes back: keep running, keep\n"
        "everything as it is, and do not hand over. First say so: run lobster-mail status --as recipes\n"
        "--session <your session> dormant. Then stop watching mail (stop the background wait, or the\n"
        "check-in chain) and run no mail checks; this mailbox's pace is being set to relaxed, so\n"
        "lobster-mail pace --as recipes shows it. Ask Squirrel nothing until he next speaks to you: no\n"
        "question, no offer, no reminder. When he does, run lobster-mail status --as recipes --session\n"
        "<your session> --clear and lobster-mail pace --as recipes normal, start watching again as that\n"
        "prints, read the mail that arrived meanwhile, and tell him you are back.\n"
        "Nothing else changes.\n")


def test_the_wake_message_says_to_watch_again():
    from bernstein.conduct import wake_message
    assert wake_message("recipes", DAY) == (
        "Wake (from bernstein, 18 October 2026).\n\n"
        "Squirrel is back: this mailbox's pace is normal again. Run lobster-mail status --as recipes\n"
        "--session <your session> --clear, so you no longer report dormant; then lobster-mail pace --as\n"
        "recipes, and do what it prints (start the background wait, or the check-in chain), read the\n"
        "mail that arrived while you were dormant, report it, and carry on.\n")


MORNING = datetime.datetime(2026, 10, 18, 9, 40, tzinfo=datetime.timezone.utc)

DREAM_DORMANT = (
    "Dream (from bernstein, 18 October 2026).\n\n"
    "Squirrel has asked this session to dream until 10:40 UTC (60 minutes): to look back over its recent work\n"
    "and write down proposals for him to review. Proposals only: change nothing else.\n\n"
    "1. Say so, then mail while dreaming. Run lobster-mail status --as recipes --session <your session>\n"
    "   dreaming --until 2026-10-18T10:40:00Z. Stop the background wait or the check-in chain, and watch for\n"
    "   bernstein only:\n"
    "   lobster-mail wait --as recipes --session <your session> --from bernstein in the background, or\n"
    "   lobster-mail checkin --as recipes --session <your session> --from bernstein between steps where a\n"
    "   background command cannot run. Claim and act on bernstein's mail only; leave every other message\n"
    "   unclaimed and unread until the dream is over. A Stop from bernstein ends the dream early: write what\n"
    "   you have, then do the Stop.\n"
    "2. Read what has happened since your last dream (the newest file in dreams/, dreams/done/ or\n"
    "   dreams/discarded/), or in the last seven days if there is none: the diary's log, your handovers and\n"
    "   finished mail, the git log, inbox/done/, and your own rules (CLAUDE.md, START-HERE.txt, PLAN.md's\n"
    "   decisions).\n"
    "3. Look for anything that would make this project work better or faster: rules to merge (one concise rule\n"
    "   is better than two or more verbose ones, and shorter reading at startup is a main aim), repeated\n"
    "   actions to make into tools, corrections Squirrel has given more than once, surprises that keep coming\n"
    "   back, and anything else. Be expansive and creative: a few silly ideas are better than filtering out a\n"
    "   good one that seems extravagant at first. In a non-code project, draft each tool idea as a request to\n"
    "   its tools project or a claw, in the usual form (the need, the ask, test ideas), but do not send it.\n"
    "4. Write one file per topic in dreams/ in this project's folder, named 2026-10-18-<topic>.md: what you\n"
    "   propose, why (with evidence: diary dates, message ids), the exact change (the full text of a new or\n"
    "   merged rule, the request as it would be sent), and how many words it adds to or takes off what a\n"
    "   session reads at startup. A file holds everything that belongs together, such as a tool request and\n"
    "   the startup step that would use it. Write nothing else: no change to CLAUDE.md, START-HERE.txt,\n"
    "   PLAN.md or any other rule, no request sent, no ticket, no commit; dreams/ stays out of git.\n"
    "5. Check the time (date -u) between steps and stop by 10:40 UTC, sooner if you run out of ideas.\n"
    "6. At the end, reply to this message with the files written and a line on each, and tell Squirrel in\n"
    "   chat, in a line, with no question. Then go dormant: run lobster-mail status --as recipes --session\n"
    "   <your session> dormant (it replaces dreaming) and lobster-mail pace --as recipes relaxed, run no\n"
    "   watch or check-in, do not hand over, and ask Squirrel nothing until he next speaks to you: no\n"
    "   question, no offer, no reminder. When he does, run lobster-mail status --as recipes --session\n"
    "   <your session> --clear and lobster-mail pace --as recipes normal, start watching again as that\n"
    "   prints, read the mail that arrived meanwhile, and offer to go through the dreams.\n")


def test_the_dream_message_gives_the_finish_time_the_routine_and_dormant_afterwards():
    from bernstein.conduct import dream_message
    assert dream_message("recipes", MORNING, 60, "dormant") == DREAM_DORMANT


def test_the_dream_message_with_then_stop_hands_over_at_the_end_instead():
    from bernstein.conduct import dream_message
    text = dream_message("recipes", MORNING, 60, "stop")
    assert text.startswith(DREAM_DORMANT.split("6. At the end")[0])
    assert "ask Squirrel nothing" not in text
    assert text.endswith(
        "6. At the end, reply to this message with the files written and a line on each, and tell Squirrel in\n"
        "   chat, in a line, with no question. Then hand over and stop: bring the record up to date, send the handover with lobster-mail\n"
        "   handover (it ends the dreaming status with the duty), stop watching mail, and tell Squirrel you\n"
        "   have stopped. Last of all, archive this session, so it leaves his list (in Claude Code in the\n"
        "   desktop app, the archive tool with the session \"self\", which he approves on the card it shows;\n"
        "   if you have no such tool, say so in your last line to him).\n")


def test_a_dream_past_midnight_names_the_day_it_ends_and_its_own_length():
    from bernstein.conduct import dream_message
    late = datetime.datetime(2026, 10, 18, 23, 30, tzinfo=datetime.timezone.utc)
    text = dream_message("recipes", late, 90, "dormant")
    assert "dream until 01:00 UTC on 19 October 2026 (90 minutes)" in text
    assert "stop by 01:00 UTC on 19 October 2026, sooner" in text
    assert "named 2026-10-18-<topic>.md" in text
    assert "dreaming --until 2026-10-19T01:00:00Z." in text


def test_the_dreaming_status_s_finish_time_is_a_whole_utc_stamp_whatever_the_clock_s_fraction():
    from bernstein.conduct import dream_message
    odd = datetime.datetime(2026, 10, 18, 9, 40, 7, 123456, tzinfo=datetime.timezone.utc)
    assert "dreaming --until 2026-10-18T10:10:07Z." in dream_message("recipes", odd, 30, "stop")


def test_the_dream_subject_names_the_finish_time():
    from bernstein.conduct import dream_subject
    assert dream_subject(MORNING, 60) == "Dream: until 10:40 UTC"
    assert dream_subject(datetime.datetime(2026, 10, 18, 23, 30, tzinfo=datetime.timezone.utc), 90) == \
        "Dream: until 01:00 UTC on 19 October 2026"


def test_a_dream_that_ends_dormant_does_not_archive_the_session():
    from bernstein.conduct import dream_message
    assert "archive" not in dream_message("recipes", MORNING, 60, "dormant")


def test_a_session_that_cannot_rename_itself_is_told_its_name_and_asked_for_nothing():
    text = start_message(None, DAY, "recipes · 18 October", can_rename=False)
    assert text == (
        "Start (from bernstein, 18 October 2026).\n\n"
        "Squirrel has started this session through bernstein. Follow START-HERE.txt in this\n"
        "project's folder from the top: step 0 (the model and effort question) first, then the\n"
        "mail and the rest. If lobster-mail start says a status is being reported for this mailbox, an\n"
        "earlier session left it: clear it with the command start prints.\n\n"
        "This session's name is \"recipes · 18 October\": the first line Squirrel sent begins with it, so\n"
        "that the app titles the session from it. A Claude Cowork session has no tool for naming a session,\n"
        "so there is nothing to do or to report about the name.\n\n"
        "Then wait for Squirrel.\n")


CLOSED = [("2026-10-18-0812-bernstein-stop-hand-over", "Stop: hand over"),
          ("2026-10-18-0930-bernstein-start-recipes", "Start: recipes")]
DUTY = {"holder": "device", "since": "2026-10-18T07:00:00Z", "last_beat": "2026-10-18T08:05:00Z", "stale": True}


def test_the_reset_note_says_who_reset_the_mailbox_what_was_closed_whose_duty_went_and_gives_the_lost_note():
    from bernstein.conduct import reset_note
    assert reset_note(DAY, CLOSED, DUTY, "Where I stopped: the menu.\nNext: the shopping list.\n") == (
        "Reset by bernstein (conduct reset, 18 October 2026), at Squirrel's word: the session that was working\n"
        "here ended without handing over. This note stands in for its handover.\n\n"
        "- Closed, so that nobody acts on them now: 2 messages from bernstein to that session, moved to done/:\n"
        "  2026-10-18-0812-bernstein-stop-hand-over (\"Stop: hand over\")\n"
        "  2026-10-18-0930-bernstein-start-recipes (\"Start: recipes\")\n"
        "- Given up with this note: the duty of device, whose last beat was 2026-10-18T08:05:00Z.\n"
        "- What that session left for you follows the line below, as it was given to bernstein.\n"
        "- Say in your diary that the mailbox was reset, and check DIARY.md against what you find: its last\n"
        "  entries may be missing.\n\n"
        "---\n\n"
        "Where I stopped: the menu.\nNext: the shopping list.\n")


def test_the_reset_note_says_so_when_nothing_was_closed_nobody_was_on_duty_or_no_note_was_given():
    from bernstein.conduct import reset_note
    assert reset_note(DAY, CLOSED[:1], None, None) == (
        "Reset by bernstein (conduct reset, 18 October 2026), at Squirrel's word: the session that was working\n"
        "here ended without handing over. This note stands in for its handover.\n\n"
        "- Closed, so that nobody acts on them now: 1 message from bernstein to that session, moved to done/:\n"
        "  2026-10-18-0812-bernstein-stop-hand-over (\"Stop: hand over\")\n"
        "- Nobody was on duty: no duty was given up.\n"
        "- That session left no note: go by DIARY.md and the project's own files.\n"
        "- Say in your diary that the mailbox was reset, and check DIARY.md against what you find: its last\n"
        "  entries may be missing.\n")
    text = reset_note(DAY, [], DUTY, "é “quoted” $HOME </script> \\n {{NAME}}")
    assert "- Closed: nothing. No message from bernstein to that session was waiting.\n" in text
    assert text.endswith("---\n\né “quoted” $HOME </script> \\n {{NAME}}\n")


WATCH = "/l/lobster-mail wait --as recipes-tools --session mac --root /m --from bernstein --timeout 0"


def test_the_quiet_watch_is_one_line_to_type_that_counts_only_bernstein_s_mail_and_never_gives_up():
    from bernstein.conduct import quiet_watch
    assert quiet_watch("recipes-tools", "/l/lobster-mail", "/m") == WATCH


def test_the_quiet_watch_quotes_awkward_paths_so_the_shell_reads_each_as_one_word():
    import shlex

    from bernstein.conduct import quiet_watch
    tool = "/Users/sq/My Tools/it's/lobster-mail"
    root = '/m/"mail" $HOME `x` \\ café </script>\n;rm'
    line = quiet_watch("recipes-tools", tool, root)
    assert shlex.split(line) == [tool, "wait", "--as", "recipes-tools", "--session", "mac", "--root", root,
                                 "--from", "bernstein", "--timeout", "0"]
    assert "$HOME" not in line.replace("'/m/\"mail\" $HOME", "")       # the $ is inside single quotes


DORMANT_ON_THE_MAC = (
    "Dormant (from bernstein, 18 October 2026).\n\n"
    "Squirrel has asked this session to go dormant until he comes back: keep running, keep\n"
    "everything as it is, and do not hand over. First say so: run lobster-mail status --as recipes-tools\n"
    "--session mac dormant. Then stop your ordinary watch of the mail (the background wait) and start one\n"
    "quiet watch in its place, as a background command, word for word:\n\n"
    "    /l/lobster-mail wait --as recipes-tools --session mac --root /m --from bernstein --timeout 0\n\n"
    "It counts only bernstein's mail and never gives up, so it returns only when bernstein writes. Run no\n"
    "other mail check, and leave this mailbox's pace as it is. Ask Squirrel nothing until he next speaks\n"
    "to you: no question, no offer, no reminder.\n\n"
    "When the quiet watch returns, claim what it lists with ack, and:\n"
    "- a Wake: do as it says, and you are awake;\n"
    "- a Stop: hand over, as it says;\n"
    "- anything else from bernstein: deal with it as your rules say, then start the quiet watch again,\n"
    "  word for word as above, and stay dormant.\n"
    "Mail from other projects stays unread until you wake. If the quiet watch ends in any other way (an\n"
    "error, or exit 6 because the pace changed), start it again.\n\n"
    "When Squirrel next speaks to you, you are awake too: stop the quiet watch, run lobster-mail status --as\n"
    "recipes-tools --session mac --clear, start watching again as lobster-mail pace --as recipes-tools\n"
    "prints, read the mail that arrived meanwhile, and tell him you are back.\n"
    "Nothing else changes.\n")


def test_the_dormant_message_for_a_session_on_the_mac_names_the_quiet_watch_word_for_word():
    from bernstein.conduct import dormant_message
    assert dormant_message("recipes-tools", DAY, watch=WATCH) == DORMANT_ON_THE_MAC


def test_the_dormant_message_for_any_other_session_is_word_for_word_what_it_was():
    from bernstein.conduct import dormant_message
    plain = dormant_message("recipes", DAY)
    assert plain == dormant_message("recipes", DAY, watch=None)
    assert "quiet watch" not in plain and "--timeout 0" not in plain and "pace is being set to relaxed" in plain


DREAM_ENDS_DORMANT_ON_THE_MAC = (
    "6. At the end, reply to this message with the files written and a line on each, and tell Squirrel in\n"
    "   chat, in a line, with no question. Then go dormant: run lobster-mail status --as recipes-tools --session\n"
    "   mac dormant (it replaces dreaming), stop the watch the dream used, and start one quiet watch in its\n"
    "   place, as a background command, word for word:\n\n"
    "       /l/lobster-mail wait --as recipes-tools --session mac --root /m --from bernstein --timeout 0\n\n"
    "   It counts only bernstein's mail and never gives up. Leave this mailbox's pace as it is, run no other\n"
    "   mail check, do not hand over, and ask Squirrel nothing until he next speaks to you: no question, no\n"
    "   offer, no reminder. When the quiet watch returns, claim what it lists with ack: a Wake, do as it\n"
    "   says; a Stop, hand over; anything else from bernstein, deal with it as your rules say and start the\n"
    "   quiet watch again. If it ends in any other way, start it again. When you wake, by a Wake or because\n"
    "   Squirrel speaks to you, stop the quiet watch, run lobster-mail status --as recipes-tools --session mac\n"
    "   --clear, start watching again as lobster-mail pace --as recipes-tools prints, read the mail that\n"
    "   arrived meanwhile, and offer to go through the dreams.\n")


def test_a_dream_that_ends_dormant_on_the_mac_ends_with_the_quiet_watch_and_sets_no_pace():
    from bernstein.conduct import dream_message
    text = dream_message("recipes-tools", MORNING, 60, "dormant", watch=WATCH)
    plain = dream_message("recipes-tools", MORNING, 60, "dormant")
    assert text.split("6. At the end")[0] == plain.split("6. At the end")[0]       # the routine is the same
    assert text.endswith(DREAM_ENDS_DORMANT_ON_THE_MAC)
    assert "relaxed" not in text and "archive" not in text
    assert "pace --as recipes-tools relaxed" in plain and "quiet watch" not in plain


def test_a_dream_that_ends_in_a_handover_is_the_same_on_the_mac_as_anywhere():
    from bernstein.conduct import dream_message
    assert dream_message("recipes-tools", MORNING, 60, "stop", watch=WATCH) == \
        dream_message("recipes-tools", MORNING, 60, "stop")
