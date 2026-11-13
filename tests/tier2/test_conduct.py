import os

import pytest
from conftest import NOW

from bernstein.conduct import dream_message


def sent(world):
    return [c for c in world.calls() if c["prog"] == "lobster-mail" and c["args"][:1] == ["send"]]


def opened(world):
    return [c["args"] for c in world.calls() if c["prog"] == "open"]


def test_help_names_both_verbs_and_exits_0(world):
    code, out, _err = world.conduct("--help")
    assert code == 0 and "conduct start" in out and "conduct stop" in out


def test_no_verb_or_an_unknown_verb_is_refused_with_exit_2(world):
    assert world.conduct()[0] == 2
    code, _out, err = world.conduct("pause", "recipes")
    assert code == 2 and err.startswith("conduct: ")


def test_start_refuses_an_unknown_project_with_exit_3(world):
    world.duty({})
    code, _out, err = world.conduct("start", "recipes")
    assert code == 3
    assert err == f"conduct: no project recipes in {world.non_code} or {world.code}, or a folder directly inside either\n"


def test_start_refuses_a_project_without_a_mailbox_with_exit_3(world):
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({})
    code, _out, err = world.conduct("start", "recipes")
    assert code == 3 and err == f"conduct: there is no mailbox recipes in {world.mail}\n"


def test_start_refuses_when_a_session_is_already_on_duty_and_sends_nothing(world):
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({"recipes": "fresh"})
    code, _out, err = world.conduct("start", "recipes")
    assert code == 3
    assert err == ("conduct: a session is already running for recipes: mac has been on duty since "
                   "2026-10-18T09:00:00Z, last beat 2026-10-18T09:30:00Z\n")
    assert sent(world) == [] and opened(world) == []


def test_start_sends_the_start_message_as_bernstein_then_opens_the_session(world):
    nc = world.project("recipes", "non-code")
    tools = world.project("recipes-tools", "code")
    world.duty({"recipes": "stale", "recipes-tools": None})
    code, out, err = world.conduct("start", "recipes")
    assert code == 0, err
    (mail,) = sent(world)
    assert mail["args"] == ["send", "--as", "bernstein", "--to", "recipes", "--subject", "Start: recipes",
                            "--root", world.mail, "-"]
    assert mail["stdin"].startswith("Start (from bernstein, 18 October 2026).")
    (link,) = opened(world)
    assert link[0].startswith("claude://cowork/new?folder=" + nc.replace("/", "%2F").replace(" ", "%20"))
    assert tools.replace("/", "%2F").replace(" ", "%20") in link[0]
    assert "Sent the Start message to recipes" in out and "Opened a Claude session" in out
    progs = [c["prog"] for c in world.calls()]
    assert progs == ["lobster-mail", "lobster-mail", "open"]


def test_start_of_a_tools_project_says_who_sets_its_model_and_effort(world):
    world.project("recipes-tools", "code")
    world.duty({"recipes-tools": None})
    code, out, _err = world.conduct("start", "recipes-tools")
    assert code == 0
    assert opened(world)[0][0].startswith("claude://code/new?folder=")
    assert ("Ask a bernstein session in the desktop app to set its model and effort to opus, high." in out)


def test_start_sets_the_pace_first_and_carries_a_brief(world, tmp_path):
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({"recipes": None})
    brief = tmp_path / "brief.md"
    brief.write_text("Plan Sunday's menu.\n", encoding="utf-8")
    code, _out, err = world.conduct("start", "recipes", "--pace", "relaxed", "--brief", str(brief))
    assert code == 0, err
    lm = [c["args"] for c in world.calls() if c["prog"] == "lobster-mail"]
    assert lm[1] == ["pace", "--as", "recipes", "relaxed", "--root", world.mail]
    assert sent(world)[0]["stdin"].endswith("Then this brief, from Squirrel:\n\nPlan Sunday's menu.\n")


def test_start_refuses_a_bad_pace_and_a_missing_brief_with_exit_2(world):
    assert world.conduct("start", "recipes", "--pace", "frantic")[0] == 2
    code, _out, err = world.conduct("start", "recipes", "--brief", "/nowhere/brief.md")
    assert code == 2 and err == "conduct: the brief /nowhere/brief.md cannot be read\n"


def test_start_dry_run_shows_the_message_and_link_and_sends_and_opens_nothing(world):
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({"recipes": None})
    code, out, _err = world.conduct("start", "--dry-run", "recipes")
    assert code == 0
    assert "Start (from bernstein, 18 October 2026)." in out and "claude://cowork/new?" in out
    assert "Dry run: nothing was sent or opened." in out
    assert sent(world) == [] and opened(world) == []


def test_a_duty_caught_changing_is_looked_at_again_then_refused_with_exit_4(world):
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({"recipes": "changing"})
    waits = []
    code, _out, err = world.conduct("start", "recipes", sleep=waits.append)
    assert code == 4 and waits == [1, 1, 1]
    assert err == "conduct: the duty of recipes kept changing while it was read; run conduct again\n"


def test_a_failing_send_or_open_is_exit_4(world):
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({"recipes": None})
    world.fail("open")
    code, _out, err = world.conduct("start", "recipes")
    assert code == 4 and err.startswith("conduct: open failed (exit 1)")
    assert len(sent(world)) == 1


def test_stop_with_nobody_on_duty_sends_nothing_and_exits_0(world):
    world.duty({"recipes": None})
    code, out, _err = world.conduct("stop", "recipes")
    assert code == 0 and out == "Nobody is on duty for recipes: nothing to stop.\n"
    assert sent(world) == []


def test_stop_sends_the_stop_message_as_bernstein(world):
    world.duty({"recipes": "fresh"})
    code, out, _err = world.conduct("stop", "recipes")
    assert code == 0
    (mail,) = sent(world)
    assert mail["args"] == ["send", "--as", "bernstein", "--to", "recipes", "--subject", "Stop: hand over",
                            "--root", world.mail, "-"]
    assert mail["stdin"].startswith("Stop (from bernstein, 18 October 2026).")
    assert out == "Sent the Stop message to recipes.\n"


def test_stop_all_asks_every_session_on_duty_except_bernstein(world):
    world.duty({"bernstein": "fresh", "recipes": "fresh", "audio": "stale", "video-tools": "fresh", "old": None})
    code, _out, _err = world.conduct("stop", "--all")
    assert code == 0
    assert [m["args"][4] for m in sent(world)] == ["recipes", "video-tools"]


def test_stop_needs_a_project_or_all_but_not_both(world):
    assert world.conduct("stop")[0] == 2
    assert world.conduct("stop", "--all", "recipes")[0] == 2


def test_stop_wait_reports_the_handover_once_the_duty_is_given_up(world):
    world.duty({"recipes": "fresh"})
    looks = []

    def sleep(seconds):
        looks.append(seconds)
        if len(looks) == 2:
            world.duty({"recipes": "handed over"})

    code, out, _err = world.conduct("stop", "recipes", "--wait", "60", sleep=sleep)
    assert code == 0 and looks == [10, 10]
    assert out.endswith("recipes has handed over.\n")


def test_stop_wait_runs_out_with_exit_5_naming_who_is_still_on_duty(world):
    world.duty({"recipes": "fresh"})
    looks = []
    code, _out, err = world.conduct("stop", "recipes", "--wait", "30", sleep=looks.append)
    assert code == 5 and looks == [10, 10, 10]
    assert err == "conduct: after 30 seconds, still on duty: recipes\n"


def test_the_command_file_runs_as_a_program(tmp_path):
    import subprocess
    import sys
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    done = subprocess.run([sys.executable, os.path.join(here, "conduct"), "--help"], capture_output=True,
                          text=True, check=False, env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr
    assert done.stdout.startswith("usage: conduct")


def test_stop_refuses_an_unknown_mailbox_with_exit_3(world):
    world.duty({})
    code, _out, err = world.conduct("stop", "recipes")
    assert code == 3 and err == f"conduct: there is no mailbox recipes in {world.mail}\n"


def test_stop_dry_run_shows_the_message_and_sends_nothing(world):
    world.duty({"recipes": "fresh"})
    code, out, _err = world.conduct("stop", "--dry-run", "recipes")
    assert code == 0 and "Stop (from bernstein, 18 October 2026)." in out and out.endswith("Dry run: nothing was sent.\n")
    assert sent(world) == []


def test_stop_all_with_nobody_on_duty_says_so(world):
    world.duty({"bernstein": "fresh", "recipes": "stale"})
    code, out, _err = world.conduct("stop", "--all")
    assert (code, out) == (0, "Nobody is on duty anywhere but bernstein: nothing to stop.\n")


def test_a_bad_settings_line_is_exit_2_naming_the_file(world):
    world.write_conf("PACE=fast\n")
    code, _out, err = world.conduct("stop", "--all")
    assert code == 2 and err == f"conduct: {world.conf}: line 7: unknown setting PACE\n"


def test_an_unreadable_listing_or_a_missing_lobster_mail_is_exit_4(world):
    with open(os.path.join(world.bin, "duty.json"), "w") as f:
        f.write("[")
    code, _out, err = world.conduct("stop", "--all")
    assert code == 4 and err == "conduct: lobster-mail duty status --all --json did not print the expected JSON\n"
    os.remove(os.path.join(world.bin, "lobster-mail"))
    code, _out, err = world.conduct("stop", "--all")
    assert code == 4 and err.startswith("conduct: lobster-mail duty status --all could not be run")


def refused(world, project):
    """Run conduct start on a project the duty listing knows; return (code, err) and check nothing went out."""
    world.duty({project: None})
    code, _out, err = world.conduct("start", project)
    assert sent(world) == [] and opened(world) == []
    return code, err


def test_start_refuses_a_lobster_conf_that_is_not_utf8_or_cannot_be_read(world):
    folder = world.project("recipes-tools", "code")
    conf = os.path.join(folder, "lobster.conf")
    with open(conf, "wb") as f:
        f.write(b"KIND=code\nMODEL=opus\xff\nEFFORT=high\n")
    assert refused(world, "recipes-tools") == (3, f"conduct: {conf} is not plain UTF-8 text: save it again as UTF-8\n")
    os.chmod(conf, 0)
    try:
        assert refused(world, "recipes-tools") == (
            3, f"conduct: {conf} cannot be read (Permission denied): check its permissions\n")
    finally:
        os.chmod(conf, 0o644)


def test_start_refuses_a_kind_that_is_neither_code_nor_non_code(world):
    folder = world.project("recipes-tools", "code")
    conf = os.path.join(folder, "lobster.conf")
    with open(conf, "w") as f:
        f.write("KIND=weird\nMODEL=opus\nEFFORT=high\n")
    assert refused(world, "recipes-tools") == (
        3, f"conduct: {conf} says KIND=weird: it must be code, non-code or feeler\n")


def test_start_refuses_a_project_with_no_start_here(world):
    folder = world.project("recipes-tools", "code")
    os.remove(os.path.join(folder, "START-HERE.txt"))
    assert refused(world, "recipes-tools") == (
        3, (f"conduct: {folder} has no START-HERE.txt, which the session is told to follow: "
            "bring the project into line with the lobster template first\n"))


def test_start_refuses_a_project_whose_lobster_conf_lacks_model_or_effort(world):
    tools = world.project("recipes-tools", "code")
    conf = os.path.join(tools, "lobster.conf")
    with open(conf, "w") as f:
        f.write("KIND=code\nSISTER=recipes\nMODEL=\nEFFORT=high\n")
    assert refused(world, "recipes-tools") == (
        3, f"conduct: {conf} has no MODEL, which START-HERE.txt step 0 reads: add a line such as MODEL=opus\n")
    nc = world.project("recipes", "non-code")
    conf = os.path.join(nc, "lobster.conf")
    with open(conf, "w") as f:
        f.write("KIND=non-code\nSISTER=recipes-tools\nMODEL=opus\n")
    assert refused(world, "recipes") == (
        3, f"conduct: {conf} has no EFFORT, which START-HERE.txt step 0 reads: add a line such as EFFORT=high\n")


def test_start_refuses_a_non_code_project_that_names_no_sister(world):
    nc = world.project("recipes", "non-code")
    conf = os.path.join(nc, "lobster.conf")
    with open(conf, "w") as f:
        f.write("KIND=non-code\nMODEL=opus\nEFFORT=high\n")
    assert refused(world, "recipes") == (
        3, (f"conduct: {conf} has no SISTER, the tools project a non-code session works with: "
            "add a line such as SISTER=recipes-tools\n"))


def test_start_refuses_a_non_code_project_whose_sister_checkout_is_missing(world):
    world.project("recipes", "non-code")
    assert refused(world, "recipes") == (
        3, "conduct: the sister tools project recipes-tools is not in {} or a folder directly inside it: "
           "make it, or correct SISTER in {}\n".format(world.code, os.path.join(world.non_code, "recipes", "lobster.conf")))


def link_folder(out):
    """The first folder= in the link a dry run prints."""
    from urllib.parse import parse_qs, urlsplit
    link = next(line.strip() for line in out.splitlines() if line.strip().startswith("claude://"))
    return parse_qs(urlsplit(link).query)["folder"]


def test_start_finds_a_tools_project_in_a_subfolder_of_the_code_folder(world):
    plain = world.project("fish-tools", "code", under="kitchen")
    public = world.project("bread-tools", "code", public=True, under="bakery")
    world.duty({"fish-tools": None, "bread-tools": None})
    code, out, err = world.conduct("start", "--dry-run", "fish-tools")
    assert (code, err) == (0, "") and link_folder(out) == [plain]
    code, out, err = world.conduct("start", "--dry-run", "bread-tools")
    assert (code, err) == (0, "") and link_folder(out) == [public]


def test_start_finds_a_non_code_project_and_its_sister_in_subfolders(world):
    nc = world.project("training", "non-code", under="videos")
    outer = world.project("training-tools", "code", public=True, under="videos")
    world.duty({"training": None})
    code, out, err = world.conduct("start", "--dry-run", "training")
    assert (code, err) == (0, "")
    assert link_folder(out) == [nc, world.mail, os.path.join(outer, "training-tools"),
                                os.path.dirname(os.path.join(world.bin, "lobster-mail"))]


def test_start_refuses_a_name_found_in_two_subfolders_and_prefers_one_directly_in_the_folder(world):
    a = world.project("fish-tools", "code", under="kitchen")
    b = world.project("fish-tools", "code", public=True, under="sea")
    assert refused(world, "fish-tools") == (
        3, f"conduct: fish-tools is in two places, {a} and {b}: keep one, or rename the other\n")
    direct = world.project("fish-tools", "code")
    world.duty({"fish-tools": None})
    code, out, err = world.conduct("start", "--dry-run", "fish-tools")
    assert (code, err) == (0, "") and link_folder(out) == [direct]


def test_a_send_that_delivered_but_kept_no_copy_counts_as_sent_and_is_never_repeated(world):
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({"recipes": None})
    world.fail("lobster-mail:send:7")
    code, out, err = world.conduct("start", "recipes")
    assert code == 0
    assert "Sent the Start message to recipes." in out and len(opened(world)) == 1
    assert err == ("conduct: the Start message reached recipes, but bernstein's own copy of it could not be "
                   "kept (lobster-mail exit 7); it was not sent again\n  lobster-mail: stub failure\n")
    assert len(sent(world)) == 1
    world.duty({"recipes": "fresh"})
    looks = []

    def sleep(seconds):
        looks.append(seconds)
        world.duty({"recipes": "handed over"})

    code, out, err = world.conduct("stop", "recipes", "--wait", "60", sleep=sleep)
    assert code == 0 and out.endswith("recipes has handed over.\n") and looks == [10]
    assert err.startswith("conduct: the Stop message reached recipes, but bernstein's own copy")
    assert len(sent(world)) == 2


def claws_world(world):
    """beyond-ai, home claw book-tools (private), further claws word-tools (public) and google-docs-tools (public, in
    a subfolder); all three claws lone."""
    nc = world.project("beyond-ai", "non-code", sister="book-tools", claws=["word-tools", "google-docs-tools"])
    book = world.project("book-tools", "code", sister="")
    word = world.project("word-tools", "code", public=True, sister="")
    docs = world.project("google-docs-tools", "code", public=True, under="writing", sister="")
    return nc, book, os.path.join(word, "word-tools"), os.path.join(docs, "google-docs-tools")


def test_start_connects_the_home_claw_and_every_further_claw_a_non_code_project_uses(world):
    nc, book, word, docs = claws_world(world)
    world.duty({"beyond-ai": None})
    code, out, err = world.conduct("start", "--dry-run", "beyond-ai")
    assert (code, err) == (0, "")
    assert link_folder(out) == [nc, world.mail, book, word, docs, os.path.dirname(os.path.join(world.bin, "lobster-mail"))]


def test_start_refuses_a_non_code_project_whose_claw_is_missing(world):
    nc = world.project("beyond-ai", "non-code", sister="book-tools", claws=["word-tools"])
    world.project("book-tools", "code", sister="")
    assert refused(world, "beyond-ai") == (
        3, (f"conduct: the claw word-tools is not in {world.code} or a folder directly inside it: make it, or correct "
            f"CLAWS in {os.path.join(nc, 'lobster.conf')}\n"))


def test_start_connects_a_claws_secrets_folder_beside_it_when_it_has_one(world):
    nc, book, word, docs = claws_world(world)
    book_secrets = os.path.join(world.code, "book-tools-secrets")
    docs_secrets = os.path.join(world.code, "writing", "google-docs-tools-secrets")
    os.makedirs(book_secrets)
    os.makedirs(docs_secrets)
    with open(os.path.join(world.code, "word-tools-secrets"), "w") as f:
        f.write("a file, not a folder\n")
    world.duty({"beyond-ai": None})
    code, out, err = world.conduct("start", "--dry-run", "beyond-ai")
    assert (code, err) == (0, "")
    assert link_folder(out) == [nc, world.mail, book, book_secrets, word, docs, docs_secrets,
                                os.path.dirname(os.path.join(world.bin, "lobster-mail"))]


def test_start_finds_a_code_project_by_its_kind_when_its_name_does_not_end_in_tools(world):
    folder = world.project("transcriber", "code", sister="", under="transcribing")
    world.duty({"transcriber": None})
    code, out, err = world.conduct("start", "--dry-run", "transcriber")
    assert (code, err) == (0, "")
    assert "claude://code/new?" in out and link_folder(out) == [folder]
    world.duty({})
    code, _out, err = world.conduct("start", "recipes")
    assert (code, err) == (3, (f"conduct: no project recipes in {world.non_code} or {world.code}, or a folder directly "
                               "inside either\n"))
    twice = world.project("transcriber", "non-code", sister="x-tools")
    assert refused(world, "transcriber") == (
        3, f"conduct: transcriber is in two places, {twice} and {folder}: keep one, or rename the other\n")


def paces(world):
    return [c["args"] for c in world.calls() if c["prog"] == "lobster-mail" and c["args"][:1] == ["pace"]]


def test_dormant_sends_the_dormant_message_then_sets_the_pace_relaxed_for_each_session_on_duty(world):
    world.duty({"bernstein": "fresh", "recipes": "fresh", "audio": "stale", "video-tools": "fresh", "old": None})
    code, out, err = world.conduct("dormant", "--all")
    assert (code, err) == (0, "")
    assert [m["args"][4] for m in sent(world)] == ["recipes", "video-tools"]
    assert sent(world)[0]["args"][6] == "Dormant: stop watching mail until Squirrel is back"
    assert sent(world)[0]["stdin"].startswith("Dormant (from bernstein, 18 October 2026).")
    assert paces(world) == [["pace", "--as", "recipes", "relaxed", "--root", world.mail],
                            ["pace", "--as", "video-tools", "relaxed", "--root", world.mail]]
    lm = [c["args"][:1] + c["args"][2:4] for c in world.calls() if c["prog"] == "lobster-mail"]
    assert lm[1:] == [["send", "bernstein", "--to"], ["pace", "recipes", "relaxed"],
                      ["send", "bernstein", "--to"], ["pace", "video-tools", "relaxed"]]
    assert out == ("Sent the Dormant message to recipes and set its pace to relaxed.\n"
                   "Sent the Dormant message to video-tools and set its pace to relaxed.\n")


def test_dormant_for_one_project_with_nobody_on_duty_sends_nothing(world):
    world.duty({"recipes": "stale"})
    code, out, _err = world.conduct("dormant", "recipes")
    assert (code, out) == (0, "Nobody is on duty for recipes: nothing to make dormant.\n")
    assert sent(world) == [] and paces(world) == []
    code, out, _err = world.conduct("dormant", "--all")
    assert (code, out) == (0, "Nobody is on duty anywhere but bernstein: nothing to make dormant.\n")


def test_dormant_dry_run_shows_the_message_and_changes_nothing(world):
    world.duty({"recipes": "fresh"})
    code, out, _err = world.conduct("dormant", "--dry-run", "recipes")
    assert code == 0
    assert "Would send to recipes, as bernstein, subject \"Dormant: stop watching mail until Squirrel is back\"" in out
    assert "Dormant (from bernstein, 18 October 2026)." in out
    assert out.endswith("Would set the pace of recipes to relaxed.\nDry run: nothing was sent or set.\n")
    assert sent(world) == [] and paces(world) == []


def test_dormant_needs_a_project_or_all_and_refuses_an_unknown_mailbox(world):
    assert world.conduct("dormant")[0] == 2
    world.duty({})
    code, _out, err = world.conduct("dormant", "recipes")
    assert code == 3 and err == f"conduct: there is no mailbox recipes in {world.mail}\n"


def test_wake_sets_the_pace_normal_then_sends_the_wake_message(world):
    world.duty({"recipes": "stale", "video-tools": "fresh", "old": None})
    code, out, err = world.conduct("wake", "recipes")
    assert (code, err) == (0, "")
    assert paces(world) == [["pace", "--as", "recipes", "normal", "--root", world.mail]]
    (mail,) = sent(world)
    assert mail["args"][4:7] == ["recipes", "--subject", "Wake: watch mail again"]
    assert mail["stdin"].startswith("Wake (from bernstein, 18 October 2026).")
    assert out == "Set the pace of recipes to normal and sent the Wake message.\n"
    code, out, _err = world.conduct("wake", "--all")
    assert code == 0 and [m["args"][4] for m in sent(world)[1:]] == ["recipes", "video-tools"]


def test_wake_dry_run_shows_the_message_and_sets_nothing(world):
    world.duty({"recipes": "stale"})
    code, out, _err = world.conduct("wake", "--dry-run", "recipes")
    assert code == 0
    assert "Would set the pace of recipes to normal, then send to it, as bernstein, subject \"Wake: watch mail again\"" in out
    assert "Wake (from bernstein, 18 October 2026)." in out and out.endswith("Dry run: nothing was sent or set.\n")
    assert sent(world) == [] and paces(world) == []
    world.duty({"recipes": None})
    code, out, _err = world.conduct("wake", "recipes")
    assert (code, out) == (0, "Nobody is on duty for recipes: nothing to wake.\n")


def test_help_names_the_dream_verb_and_its_options(world):
    code, out, _err = world.conduct("--help")
    assert code == 0
    assert "conduct dream <project> | --all [--minutes N] [--then dormant|stop] [--dry-run]" in out


def test_dream_sends_the_dream_message_to_each_session_fresh_on_duty_and_sets_no_pace(world):
    world.duty({"bernstein": "fresh", "recipes": "fresh", "audio": "stale", "video-tools": "fresh", "old": None})
    code, out, err = world.conduct("dream", "--all")
    assert (code, err) == (0, "")
    assert [m["args"][4] for m in sent(world)] == ["recipes", "video-tools"]
    assert [m["args"][6] for m in sent(world)] == ["Dream: until 10:40 UTC"] * 2
    assert sent(world)[0]["stdin"] == dream_message("recipes", NOW, 60, "dormant")
    assert sent(world)[1]["stdin"] == dream_message("video-tools", NOW, 60, "dormant")
    assert paces(world) == []
    assert out == ("Sent the Dream message to recipes: until 10:40 UTC, then dormant.\n"
                   "Sent the Dream message to video-tools: until 10:40 UTC, then dormant.\n")


def test_dream_takes_its_length_and_its_ending_from_the_options(world):
    world.duty({"recipes": "fresh"})
    code, out, err = world.conduct("dream", "recipes", "--minutes", "90", "--then", "stop")
    assert (code, err) == (0, "")
    assert sent(world)[0]["args"][6] == "Dream: until 11:10 UTC"
    assert sent(world)[0]["stdin"] == dream_message("recipes", NOW, 90, "stop")
    assert out == "Sent the Dream message to recipes: until 11:10 UTC, then hand over and stop.\n"


@pytest.mark.parametrize("minutes", ["4", "241", "0", "-5"])
def test_dream_refuses_a_length_outside_5_to_240_minutes_with_exit_2_and_sends_nothing(world, minutes):
    world.duty({"recipes": "fresh"})
    code, out, err = world.conduct("dream", "recipes", "--minutes", minutes)
    assert (code, out) == (2, "")
    assert err == f"conduct: --minutes must be from 5 to 240, not {minutes}\n"
    assert sent(world) == []


def test_dream_refuses_a_length_that_is_not_a_whole_number_or_an_unknown_ending(world):
    world.duty({"recipes": "fresh"})
    code, _out, err = world.conduct("dream", "recipes", "--minutes", "an hour")
    assert code == 2 and "--minutes" in err and err.endswith("(conduct --help shows the form)\n")
    code, _out, err = world.conduct("dream", "recipes", "--then", "sleep")
    assert code == 2 and "--then" in err and err.endswith("(conduct --help shows the form)\n")
    assert sent(world) == []


def test_dream_with_nobody_on_duty_sends_nothing(world):
    world.duty({"recipes": "stale"})
    code, out, _err = world.conduct("dream", "recipes")
    assert (code, out) == (0, "Nobody is on duty for recipes: nothing to dream.\n")
    code, out, _err = world.conduct("dream", "--all")
    assert (code, out) == (0, "Nobody is on duty anywhere but bernstein: nothing to dream.\n")
    assert sent(world) == []


def test_dream_dry_run_shows_the_message_and_sends_nothing(world):
    world.duty({"recipes": "fresh"})
    code, out, err = world.conduct("dream", "recipes", "--dry-run")
    assert (code, err) == (0, "")
    assert out == ("Would send to recipes, as bernstein, subject \"Dream: until 10:40 UTC\":\n\n"
                   + dream_message("recipes", NOW, 60, "dormant") + "\nDry run: nothing was sent.\n")
    assert sent(world) == []


def test_dream_needs_a_project_or_all_and_refuses_an_unknown_mailbox(world):
    world.duty({"recipes": "fresh"})
    code, _out, err = world.conduct("dream")
    assert (code, err) == (2, "conduct: name one project, or give --all\n")
    code, _out, err = world.conduct("dream", "recipes", "--all")
    assert (code, err) == (2, "conduct: name one project, or give --all\n")
    code, _out, err = world.conduct("dream", "salads")
    assert (code, err) == (3, f"conduct: there is no mailbox salads in {world.mail}\n")
    assert sent(world) == []


def test_no_verb_names_all_seven_verbs(world):
    code, _out, err = world.conduct()
    assert (code, err) == (2, "conduct: say start, stop, finish, dormant, wake, dream or status (conduct --help shows the form)\n")


def test_start_names_the_session_for_the_project_and_the_day_in_the_message_the_link_and_its_report(world):
    world.project("recipes-tools", "code")
    world.duty({"recipes-tools": None})
    code, out, err = world.conduct("start", "recipes-tools")
    assert code == 0, err
    assert "This session's name is \"recipes-tools · 18 October\"." in sent(world)[0]["stdin"]
    assert "&q=recipes-tools%20%C2%B7%2018%20October.%20This%20session%20must%20work%20in" in opened(world)[0][0]
    assert "The session is to be named: recipes-tools · 18 October\n" in out


def test_start_takes_a_name_as_data_with_quotes_dollars_and_accents(world):
    world.project("recipes-tools", "code")
    world.duty({"recipes-tools": None})
    name = "Fix \"oven\" $HOME </script> é\\"
    code, out, err = world.conduct("start", "recipes-tools", "--name", name)
    assert code == 0, err
    assert f"This session's name is \"{name}\"." in sent(world)[0]["stdin"]
    assert opened(world)[0][0].split("&q=")[1].startswith(
        "Fix%20%22oven%22%20%24HOME%20%3C%2Fscript%3E%20%C3%A9%5C.%20This%20session")
    assert f"The session is to be named: {name}\n" in out


@pytest.mark.parametrize("name, why", [
    ("", "the name is empty"),
    ("one\ntwo", "the name must be one line"),
    ("x" * 61, "the name is longer than 60 characters"),
])
def test_start_refuses_a_bad_name_with_exit_2_and_sends_and_opens_nothing(world, name, why):
    world.project("recipes-tools", "code")
    world.duty({"recipes-tools": None})
    code, out, err = world.conduct("start", "recipes-tools", "--name", name)
    assert (code, out, err) == (2, "", f"conduct: {why}: give --name one line of at most 60 characters\n")
    assert sent(world) == [] and opened(world) == []


def test_start_dry_run_shows_the_name_the_session_would_be_given(world):
    world.project("recipes-tools", "code")
    world.duty({"recipes-tools": None})
    code, out, _err = world.conduct("start", "--dry-run", "recipes-tools", "--name", "Sunday")
    assert code == 0 and "Would name the session: Sunday\n" in out
    assert sent(world) == [] and opened(world) == []


def split_claw(world, rules="Rules v1 for recipes-tools.\n"):
    """A tools project that keeps the template's global files apart, and a template whose rules have moved on."""
    from conftest import write_tree
    folder = world.project("recipes-tools", "code")
    write_tree(world.template, {"common/global-files": "RULES.md\nSTART-HERE.txt\n",
                                "code/RULES.md": "Rules v2 for {{TOOLS}}, serving {{SERVING}}.\n"})
    write_tree(folder, {"RULES.md": rules, "CLAUDE.md": "The project's own.\n"})
    world.duty({"recipes-tools": None})
    return folder


def test_start_brings_a_split_projects_global_files_up_to_date_before_the_session_opens(world):
    from conftest import tree
    folder = split_claw(world)
    code, out, err = world.conduct("start", "recipes-tools")
    assert code == 0, err
    files = tree(folder)
    assert files["RULES.md"] == b"Rules v2 for recipes-tools, serving `recipes`.\n"
    assert files["_to_delete/before-global-update-2026-10-18-0940/RULES.md"] == b"Rules v1 for recipes-tools.\n"
    assert files["CLAUDE.md"] == b"The project's own.\n" and files["START-HERE.txt"] == b"Start recipes-tools.\n"
    assert sorted(files) == ["CLAUDE.md", "RULES.md", "START-HERE.txt",
                             "_to_delete/before-global-update-2026-10-18-0940/RULES.md", "lobster.conf"]
    assert ("bernstein brought this project's global files up to date just before this session started:\n"
            "RULES.md. They are the template's and are never edited here; the copies they replaced are in\n"
            "_to_delete/before-global-update-2026-10-18-0940/. Read them as they are now, say so in the diary,\n"
            "and commit them with your next commit.\n\n") in sent(world)[0]["stdin"]
    assert f"Brought up to date in {folder}: RULES.md (the old copies are in " in out
    assert len(opened(world)) == 1


def test_start_dry_run_says_which_global_files_it_would_replace_and_writes_nothing(world):
    from conftest import tree
    folder = split_claw(world)
    before = tree(folder)
    code, out, _err = world.conduct("start", "--dry-run", "recipes-tools")
    assert code == 0 and f"Would bring up to date in {folder}: RULES.md\n" in out
    assert tree(folder) == before and sent(world) == [] and opened(world) == []


def test_start_leaves_a_project_that_is_not_split_exactly_as_it_is_and_says_so(world):
    from conftest import tree, write_tree
    folder = world.project("recipes-tools", "code")
    write_tree(world.template, {"common/global-files": "RULES.md\nSTART-HERE.txt\n", "code/RULES.md": "Rules v2.\n"})
    world.duty({"recipes-tools": None})
    before = tree(folder)
    code, out, err = world.conduct("start", "recipes-tools")
    assert code == 0, err
    assert tree(folder) == before
    assert "global files" not in sent(world)[0]["stdin"]
    assert ("recipes-tools does not keep the template's global files apart yet: its files are left as they are.\n"
            in out)


def test_start_changes_nothing_when_the_global_files_are_current_or_the_template_has_none(world):
    from conftest import tree, write_tree
    folder = split_claw(world, rules="Rules v2 for recipes-tools, serving `recipes`.\n")
    before = tree(folder)
    code, out, _err = world.conduct("start", "recipes-tools")
    assert code == 0 and tree(folder) == before
    assert "global files" not in sent(world)[0]["stdin"] and "up to date" not in out and "apart" not in out
    os.remove(os.path.join(world.template, "common", "global-files"))
    write_tree(folder, {"RULES.md": "anything\n"})
    code, out, _err = world.conduct("start", "recipes-tools")
    assert code == 0 and tree(folder)["RULES.md"] == b"anything\n" and "apart" not in out


def test_start_that_is_refused_never_touches_the_global_files(world):
    from conftest import tree
    folder = split_claw(world)
    before = tree(folder)
    world.duty({"recipes-tools": "fresh"})
    assert world.conduct("start", "recipes-tools")[0] == 3
    world.duty({"recipes-tools": None})
    world.fail("lobster-mail:send")
    assert world.conduct("start", "recipes-tools", "--name", "")[0] == 2
    assert tree(folder) == before


def test_start_with_a_template_whose_global_file_carries_the_date_is_exit_4_and_nothing_happens(world):
    from conftest import tree, write_tree
    folder = split_claw(world)
    write_tree(world.template, {"code/RULES.md": "Rules of {{DATE}}.\n"})
    before = tree(folder)
    code, out, err = world.conduct("start", "recipes-tools")
    assert (code, out) == (4, "")
    assert err == ("conduct: the template cannot be read: code/RULES.md is a global file and must read the same "
                   "every day: use {{TEMPLATE_VERSION}} in it, not {{DATE}}\n")
    assert tree(folder) == before and sent(world) == [] and opened(world) == []


def test_start_renders_a_non_code_projects_global_files_with_its_own_folder_and_claws(world):
    from conftest import tree, write_tree
    nc = world.project("recipes", "non-code", under="eat", claws=("knives",))
    world.project("recipes-tools", "code", under="eat")
    world.project("knives", "code", sister="")
    write_tree(world.template, {"common/global-files": "RULES.md\n",
                                "non-code/RULES.md": "{{SELF}} at {{NONCODE_PATH}}, tools at {{TOOLS_PATH}}, {{CLAW_NAMES}}.\n"})
    write_tree(nc, {"RULES.md": "old\n"})
    world.duty({"recipes": None})
    code, _out, err = world.conduct("start", "recipes")
    assert code == 0, err
    assert tree(nc)["RULES.md"] == (b"recipes at ~/projects/non-code/eat/recipes, tools at "
                                    b"~/projects/code/eat/recipes-tools, recipes-tools and knives.\n")


def test_start_that_cannot_keep_the_old_copy_replaces_nothing_and_sends_and_opens_nothing(world):
    from conftest import tree, write_tree
    folder = split_claw(world)
    write_tree(folder, {"_to_delete": "a file where the folder should be\n"})
    before = tree(folder)
    code, out, err = world.conduct("start", "recipes-tools")
    assert (code, out) == (4, "")
    assert err.startswith(f"conduct: a global file in {folder} could not be replaced (")
    assert err.endswith("): nothing was sent or opened\n")
    assert tree(folder) == before and sent(world) == [] and opened(world) == []


def feeler(world, name="agents", claws=(), under=""):
    """A feeler's folder as new-lobster --feeler makes it."""
    from conftest import write_tree
    folder = os.path.join(world.non_code, under, name)
    write_tree(folder, {"lobster.conf": f"KIND=feeler\nSELF={name}\nSISTER=\nCLAWS={' '.join(claws)}\nMODEL=opus\nEFFORT=high\n",
                        "START-HERE.txt": f"Start {name}.\n"})
    return folder


def test_start_opens_a_feeler_as_a_claude_session_with_its_folder_the_mail_its_claws_and_lobster_tools(world):
    folder = feeler(world, claws=("knives",), under="one-offs")
    knives = world.project("knives", "code", sister="")
    world.duty({"agents": None})
    code, out, err = world.conduct("start", "agents")
    assert code == 0, err
    enc = lambda s: s.replace("/", "%2F").replace(" ", "%20")
    link = opened(world)[0][0]
    assert link.startswith("claude://cowork/new?folder=" + enc(folder) + "&folder=" + enc(world.mail)
                           + "&folder=" + enc(knives) + "&folder=" + enc(world.bin) + "&q=agents%20%C2%B7%2018%20October.%20Read%20START-HERE.txt")
    assert sent(world)[0]["args"][:7] == ["send", "--as", "bernstein", "--to", "agents", "--subject", "Start: agents"]
    assert "Opened a Claude session for agents: confirm its folders, then send its first line.\n" in out


def test_start_opens_a_feeler_that_uses_no_claw(world):
    folder = feeler(world)
    world.duty({"agents": None})
    code, _out, err = world.conduct("start", "agents")
    assert code == 0, err
    enc = lambda s: s.replace("/", "%2F").replace(" ", "%20")
    assert opened(world)[0][0].startswith("claude://cowork/new?folder=" + enc(folder) + "&folder=" + enc(world.mail)
                                          + "&folder=" + enc(world.bin) + "&q=")


def test_start_refuses_a_feeler_whose_claw_is_missing_or_that_names_a_sister(world):
    feeler(world, claws=("knives",))
    world.duty({"agents": None})
    code, _out, err = world.conduct("start", "agents")
    assert code == 3 and "knives" in err and "CLAWS" in err
    folder = feeler(world, name="letters")
    with open(os.path.join(folder, "lobster.conf"), "a") as f:
        f.write("SISTER=letters-tools\n")
    world.duty({"letters": None})
    code, _out, err = world.conduct("start", "letters")
    assert code == 3
    assert err == (f"conduct: {os.path.join(folder, 'lobster.conf')} says KIND=feeler and SISTER=letters-tools: a feeler "
                   "has no home claw; name the tools projects it uses in CLAWS\n")
    assert sent(world) == [] and opened(world) == []


def test_a_kind_that_is_not_code_non_code_or_feeler_is_still_refused(world):
    folder = feeler(world)
    with open(os.path.join(folder, "lobster.conf"), "a") as f:
        f.write("KIND=tentacle\n")
    world.duty({"agents": None})
    code, _out, err = world.conduct("start", "agents")
    assert code == 3 and err.endswith("says KIND=tentacle: it must be code, non-code or feeler\n")


def test_start_brings_a_feelers_global_files_up_to_date_from_the_feeler_half(world):
    from conftest import tree, write_tree
    folder = feeler(world, claws=("knives",))
    world.project("knives", "code", sister="")
    write_tree(world.template, {"common/global-files": "RULES.md\ninbox/README.md\n",
                                "feeler/RULES.md": "Feeler rules for {{NAME}}; {{FEELER_CLAWS}}\n"})
    write_tree(folder, {"RULES.md": "old\n"})
    world.duty({"agents": None})
    code, _out, err = world.conduct("start", "agents")
    assert code == 0, err
    assert tree(folder)["RULES.md"].startswith(b"Feeler rules for agents; It uses the claw `knives`:")


def test_finish_asks_a_running_feeler_to_write_up_offer_its_scripts_and_hand_over(world):
    feeler(world)
    world.duty({"agents": "fresh"})
    code, out, err = world.conduct("finish", "agents")
    assert code == 0, err
    (mail,) = sent(world)
    assert mail["args"][:7] == ["send", "--as", "bernstein", "--to", "agents", "--subject", "Finish: write up and hand over"]
    assert mail["stdin"] == (
        "Finish (from bernstein, 18 October 2026).\n\n"
        "Squirrel has asked this feeler to finish: its one job is done, or as done as it will be. At the\n"
        "next safe point:\n\n"
        "1. Write what was found, plainly, in CLAUDE.md under \"What was found\": the answer first, then\n"
        "   what it rests on, what is unsure, and where each file is.\n"
        "2. List every script in tools/ with what it did and a proposal for each: offer it to a claw (name\n"
        "   the claw; the request goes by mail on Squirrel's OK), or leave it here as a record. Run nothing\n"
        "   new for this.\n"
        "3. Bring \"Where things stand\" up to date, commit, and send the handover as START-HERE.txt says.\n"
        "4. Reply to this message with what was found in two lines and the scripts you propose to offer.\n"
        "5. Last of all, archive this session if you have a tool that archives a session; if you have\n"
        "   none, say so in your last line to him.\n\n"
        "Squirrel moves the folder to not-current/ himself when he has read the reply.\n")
    assert out == "Sent the Finish message to agents.\n"


def test_finish_is_only_for_a_feeler_that_has_a_session_on_duty(world):
    feeler(world)
    world.project("recipes-tools", "code")
    world.duty({"agents": None, "recipes-tools": "fresh"})
    code, out, _err = world.conduct("finish", "agents")
    assert (code, out) == (0, "Nobody is on duty for agents: nothing to finish.\n")
    code, _out, err = world.conduct("finish", "recipes-tools")
    assert code == 3 and err == "conduct: recipes-tools is not a feeler: finish is for a one-off project; use stop\n"
    code, _out, err = world.conduct("finish", "nobody")
    assert code == 3
    assert sent(world) == []


def test_finish_dry_run_shows_the_message_and_sends_nothing(world):
    feeler(world)
    world.duty({"agents": "fresh"})
    code, out, _err = world.conduct("finish", "--dry-run", "agents")
    assert code == 0 and "Would send to agents, as bernstein, subject \"Finish: write up and hand over\":" in out
    assert out.endswith("Dry run: nothing was sent.\n") and sent(world) == []
