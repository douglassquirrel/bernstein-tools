"""A ganglion on the Mac: a non-code project whose lobster.conf says SESSION=code runs as a Claude Code
session (PLAN.md, "A ganglion on the Mac: SESSION=code", Settled 168). conduct, here."""

import json
import os
from urllib.parse import parse_qsl, urlsplit

import pytest
from conftest import tree, write_tree
from test_conduct_status import COWORK, SID, app_store, entry
from test_session_setting import calls, ganglion

NAME = "recipes · 18 October"
MAC = "A Claude Code session on the Mac would open, as SESSION=code in its lobster.conf says.\n"


def link_in(out):
    return next(line.strip() for line in out.splitlines() if line.strip().startswith("claude://"))


def asked(link):
    """(the app's path, the folders, the first line) of a link that opens a session."""
    parts = urlsplit(link)
    pairs = parse_qsl(parts.query)
    return (parts.netloc + parts.path, [v for k, v in pairs if k == "folder"],
            "".join(v for k, v in pairs if k == "q"))


def first_line(folder, name=NAME):
    return (f"Session title: {name}. This session must work in {folder}. If your working folder is anything else, "
            "say \"the app opened me in the wrong folder\" and stop. Otherwise read START-HERE.txt there and do what "
            "it says, starting with its step 0 before anything else.")


@pytest.mark.parametrize("line", ["SESSION=", "SESSION=cowork", "SESSION = cowork ", "# SESSION=code"])
def test_a_ganglion_that_says_cowork_or_nothing_starts_exactly_as_one_with_no_such_line(world, line):
    folder = ganglion(world)
    plain = world.conduct("start", "--dry-run", "recipes")
    with open(os.path.join(folder, "lobster.conf"), "a") as f:
        f.write(line + "\n")
    assert world.conduct("start", "--dry-run", "recipes") == plain
    assert plain[0] == 0 and "claude://cowork/new?" in plain[1] and "SESSION" not in plain[1]
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "")
    assert out.endswith("Opened a Claude session for recipes: confirm its folders, then send its first line.\n")
    assert calls(world, "open")[0]["args"][0].startswith("claude://cowork/new?")
    assert "A Claude Cowork session has no tool for naming a session" in calls(world, "send")[0]["stdin"]


def test_the_dry_run_of_a_ganglion_on_the_mac_shows_a_claude_code_session_in_its_folder(world):
    folder = ganglion(world, "SESSION=code")
    before = tree(folder)
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "")
    link = link_in(out)
    assert asked(link) == ("code/new", [folder], first_line(folder))
    assert "cowork" not in link and "~/mnt" not in out
    assert out.startswith('Would send to recipes, as bernstein, subject "Start: recipes":\n\nStart (from bernstein, ')
    assert "If you have a tool that names or renames a\nsession" in out and "Claude Cowork" not in out
    assert out.endswith(f"Would open:\n  {link}\n{MAC}Would name the session: {NAME}\n"
                        "Dry run: nothing was sent or opened.\n")
    assert calls(world, "send") == [] and calls(world, "open") == [] and tree(folder) == before


def test_start_opens_a_claude_code_session_for_a_ganglion_on_the_mac_and_says_who_sets_its_model(world):
    folder = ganglion(world, "SESSION=code")
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "")
    assert len(calls(world, "open")) == 1 and len(calls(world, "open")[0]["args"]) == 1
    assert calls(world, "open")[0]["args"][0].startswith("claude://code/new?folder=")
    assert asked(calls(world, "open")[0]["args"][0]) == ("code/new", [folder], first_line(folder))
    message = calls(world, "send")[0]
    assert message["args"][:6] == ["send", "--as", "bernstein", "--to", "recipes", "--subject"]
    assert f'This session\'s name is "{NAME}". If you have a tool that names or renames a\nsession' in message["stdin"]
    assert "Claude Cowork" not in message["stdin"]
    assert out == ("Sent the Start message to recipes.\n"
                   f"The session is to be named: {NAME}\n"
                   "Opened a Claude Code session for recipes: confirm its folder, then send its first line.\n"
                   "Ask a bernstein session in the desktop app to set its model and effort to opus, high.\n")


def test_a_ganglion_on_the_mac_keeps_its_name_brief_and_pace(world, tmp_path):
    folder = ganglion(world, "SESSION=code")
    brief = tmp_path / "brief.md"
    brief.write_text("Transcribe \"tape 3\" with $WHISPER é\n", encoding="utf-8")
    code, out, err = world.conduct("start", "recipes", "--name", "Tape 3", "--brief", str(brief), "--pace", "eager")
    assert (code, err) == (0, "")
    assert asked(calls(world, "open")[0]["args"][0]) == ("code/new", [folder], first_line(folder, "Tape 3"))
    assert calls(world, "send")[0]["stdin"].endswith(
        "Then this brief, from Squirrel:\n\nTranscribe \"tape 3\" with $WHISPER é\n")
    assert calls(world, "pace")[0]["args"][:4] == ["pace", "--as", "recipes", "eager"]
    assert "The session is to be named: Tape 3\n" in out


def test_a_ganglion_on_the_mac_may_name_further_folders_which_are_there_and_not_connected(world):
    models = os.path.join(world.home, "models", "kokoro voices")
    again = os.path.join(world.home, "other", "kokoro voices")          # the same last name: no clash on the Mac
    own = os.path.join(world.home, "elsewhere", "recipes")              # nor with the project's own
    for path in (models, again, own):
        os.makedirs(path)
    folder = ganglion(world, f"SESSION=code\nFOLDERS=~/models/kokoro voices:{again}:{own}")
    named = f"{models}, {again}, {own}"
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "")
    assert asked(link_in(out))[1] == [folder]
    assert (f"Named in FOLDERS in its lobster.conf, and there on the Mac with nothing to connect: {named}\n"
            f"Would name the session: {NAME}\n") in out
    assert "connect, from FOLDERS" not in out
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "")
    assert asked(calls(world, "open")[0]["args"][0])[1] == [folder]
    assert (f"Named in FOLDERS in its lobster.conf, and there on the Mac with nothing to connect: {named}\n"
            f"The session is to be named: {NAME}\n") in out
    assert "connected, from FOLDERS" not in out


def test_a_ganglion_on_the_mac_is_still_refused_a_further_folder_that_is_not_there_or_not_a_full_path(world):
    folder = ganglion(world, "SESSION=code")
    conf = os.path.join(folder, "lobster.conf")
    absent = os.path.join(world.home, "models", "kokoro")
    for line, said in (("FOLDERS=models/kokoro", ("the folder models/kokoro in FOLDERS, which is not a full path: "
                                                 "start it with / or ~/")),
                       ("FOLDERS=~/models/kokoro", (f"the folder {absent} in FOLDERS, which is not a folder on this "
                                                   "Mac: make it, or correct the line"))):
        with open(conf, "a") as f:
            f.write(line + "\n")
        for argv in (("start", "recipes"), ("start", "--dry-run", "recipes")):
            assert world.conduct(*argv) == (3, "", f"conduct: {conf} names {said}\n")
    assert calls(world, "send") == [] and calls(world, "open") == []


def test_a_ganglion_on_the_mac_with_further_claws_opens_in_its_own_folder_alone_and_still_needs_them_there(world):
    folder = ganglion(world, "SESSION=code\nCLAWS=video-tools word-tools")
    conf = os.path.join(folder, "lobster.conf")
    world.project("video-tools", "code", public=True, under="video", sister="")
    os.makedirs(os.path.join(world.code, "recipes-tools-secrets"))
    assert world.conduct("start", "--dry-run", "recipes") == (
        3, "", (f"conduct: the claw word-tools is not in {world.code} or a folder directly inside it: make it, or "
               f"correct CLAWS in {conf}\n"))
    world.project("word-tools", "code", sister="")
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "") and asked(link_in(out))[1] == [folder]


def session_of(world, mailbox):
    code, out, err = world.conduct("status", "--json")
    assert (code, err) == (0, "")
    return {r["mailbox"]: r for r in json.loads(out)["mailboxes"]}[mailbox]


def test_status_gives_a_ganglion_on_the_mac_its_claude_code_session_before_a_cowork_one(world):
    folder = ganglion(world)
    app_store(world, [(SID, folder, 1794401892175, False)])
    desk = os.path.join(world.home, "Library", "Application Support", "Claude", "local-agent-mode-sessions", "a", "o")
    os.makedirs(desk)
    with open(os.path.join(desk, "remote-session-spaces.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": [{"sessionId": COWORK, "folders": [folder, world.mail]}]}, f)
    world.listing([entry("recipes", "fresh")])
    plain = session_of(world, "recipes")
    assert plain["session"]["id"] == COWORK and plain["kind"] == "non-code"
    with open(os.path.join(folder, "lobster.conf"), "a") as f:
        f.write("SESSION=code\n")
    row = session_of(world, "recipes")
    assert row["session"]["id"] == SID and row["session"]["app"] == "code"
    assert row["session"]["link"] == "claude://claude.ai/epitaxy/" + SID
    differ = ("session", "live_note", "runs_in")    # and on the Mac its session can be seen: none is alive here
    assert (plain["runs_in"], row["runs_in"]) == ("cowork", "code")
    assert {k: v for k, v in row.items() if k not in differ} == {k: v for k, v in plain.items() if k not in differ}
    assert plain["live_note"] is None
    assert row["live_note"] == "no session alive, though its duty is fresh: a watch has outlived its session"
    os.remove(os.path.join(world.home, "Library", "Application Support", "Claude", "claude-code-sessions", "acct",
                           "org", SID + ".json"))
    assert session_of(world, "recipes")["session"]["id"] == COWORK      # none of its own kind: the other will do


@pytest.mark.parametrize("argv", [("stop", "recipes"), ("stop", "--dry-run", "recipes"), ("dormant", "recipes"),
                                  ("wake", "recipes"), ("dream", "recipes"), ("dream", "recipes", "--then", "stop"),
                                  ("waiting",), ("stop", "--all"), ("dormant", "--all")])
# status, and reset of a stale duty, say what is alive in its folder: test_conduct_live.py, test_conduct_live_verbs.py
def test_every_other_verb_does_for_a_ganglion_on_the_mac_what_it_does_for_any_ganglion(world, argv):
    folder = ganglion(world)
    world.duty({"recipes": "fresh", "recipes-tools": None})
    world.repo(folder)

    def run():
        log = os.path.join(world.bin, "calls.log")
        if os.path.exists(log):
            os.remove(log)
        return world.conduct(*argv), world.calls()

    plain = run()
    with open(os.path.join(folder, "lobster.conf"), "a") as f:
        f.write("SESSION=code\n")
    assert run() == plain
    assert plain[0][0] == 0 and plain[0][2] == ""


HOME_CLAW = "the home claw, `recipes-tools`: **read and run only**; never write, commit, install or make a `.venv` in it |\n"
IN_THE_MACHINE = {
    "RULES.md": ("Rules for recipes.\nYour claws are under ~/mnt:\n| `~/mnt/recipes-tools` | " + HOME_CLAW
                 + "| `~/mnt/video-tools` | the claw `video-tools`: read and run only, as above |\n"),
    "START-HERE.txt": "Start recipes in a cowork session.\n"}
ON_THE_MAC = {
    "RULES.md": ("Rules for recipes.\nYour claws are on the Mac:\n| `~/projects/code/recipes-tools` | " + HOME_CLAW
                 + "| `~/projects/code/video/video-tools-code/video-tools` | the claw `video-tools`: read and run "
                   "only, as above |\n"),
    "START-HERE.txt": "Start recipes in a code session.\n"}


def split_ganglion(world):
    """A ganglion with a further claw that keeps the template's global files apart, as rendered for a session
    in the virtual machine, and a template that says one thing to each kind of session."""
    folder = ganglion(world, "CLAWS=video-tools")
    world.project("video-tools", "code", public=True, under="video", sister="")
    write_tree(world.template, {
        "common/global-files": "RULES.md\nSTART-HERE.txt\n",
        "common/sections/where-cowork.md": "Your claws are under ~/mnt:\n{{CLAW_MOUNTS}}\n",
        "common/sections/where-code.md": "Your claws are on the Mac:\n{{CLAW_MOUNTS}}\n",
        "non-code/RULES.md": "Rules for {{NAME}}.\n{{> sections/where-{{SESSION}}.md}}\n",
        "non-code/START-HERE.txt": "Start {{NAME}} in a {{SESSION}} session.\n"})
    write_tree(folder, dict(IN_THE_MACHINE, **{"CLAUDE.md": "The project's own.\n"}))
    return folder


def test_the_start_after_a_switch_brings_the_files_for_the_new_kind_of_session_and_keeps_the_old(world):
    folder = split_ganglion(world)
    conf = os.path.join(folder, "lobster.conf")
    before = tree(folder)
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "") and "up to date" not in out                 # in line, for the virtual machine
    with open(conf, "a") as f:
        f.write("SESSION=code\n")
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "")
    assert f"Would bring up to date in {folder}: RULES.md, START-HERE.txt\n" in out
    assert tree(folder) == dict(before, **{"lobster.conf": before["lobster.conf"] + b"SESSION=code\n"})
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "")
    kept = "_to_delete/before-global-update-2026-10-18-0940"
    files = tree(folder)
    assert {rel: files[rel].decode() for rel in ON_THE_MAC} == ON_THE_MAC
    assert {rel: files[f"{kept}/{rel}"].decode() for rel in IN_THE_MACHINE} == IN_THE_MACHINE
    assert sorted(files) == sorted(list(before) + [f"{kept}/RULES.md", f"{kept}/START-HERE.txt"])
    assert files["CLAUDE.md"] == b"The project's own.\n"
    assert f"Brought up to date in {folder}: RULES.md, START-HERE.txt (the old copies are in " in out
    assert "RULES.md, START-HERE.txt. They are the template's" in calls(world, "send")[0]["stdin"]
    assert calls(world, "open")[0]["args"][0].startswith("claude://code/new?")
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "") and "up to date" not in out                 # in line, for the Mac
    with open(conf, "a") as f:
        f.write("SESSION=cowork\n")                                           # and back again
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "")
    files = tree(folder)
    assert {rel: files[rel].decode() for rel in IN_THE_MACHINE} == IN_THE_MACHINE
    assert {rel: files[f"{kept}-2/{rel}"].decode() for rel in ON_THE_MAC} == ON_THE_MAC
    assert calls(world, "open")[1]["args"][0].startswith("claude://cowork/new?")
