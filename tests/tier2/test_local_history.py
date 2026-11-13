"""local-history against the stubs: what it prints, what it asks git to do, and everything it refuses."""

import os

import pytest
from conftest import tree, write_tree

from bernstein import localhistory

MESSAGE = "Start of this folder's local history (no remote)"


def git_calls(world):
    return [(c["args"], c["cwd"]) for c in world.calls() if c["prog"] == "git"]


def outside_git(folder):
    return {rel: data for rel, data in tree(folder).items() if not rel.startswith(".git" + os.sep)}


# --- a dry run

def test_a_dry_run_says_what_would_be_committed_and_left_out_and_makes_nothing(world):
    folder = world.outer("pat")
    world.duty({"pat": None})
    before = tree(folder)
    code, out, err = world.local_history("--dry-run", folder)
    assert (code, err) == (0, "")
    assert out == (
        f"Would start a local history in {folder}: 3 files, 79 bytes, no remote.\n"
        "  Largest: lobster.conf (50 bytes), DIARY.md (23 bytes), CLAUDE.md (6 bytes)\n"
        "  Left out: pat/ (a git repository), .venv/, _to_delete/, inbox/\n"
        "  Duty: nobody is on duty for pat.\n"
        "Dry run: nothing was made.\n")
    assert git_calls(world) == []
    assert tree(folder) == before


def test_a_dry_run_of_a_folder_with_no_lobster_conf_says_duty_was_not_checked_and_asks_nobody(world):
    folder = world.outer("solo", lobster=False)
    code, out, err = world.local_history("--dry-run", folder)
    assert (code, err) == (0, "")
    assert "  Duty: not checked (no lobster.conf here names a mailbox).\n" in out
    assert world.calls() == []


# --- the real thing

def test_makes_the_repository_writes_the_exclude_lines_adds_everything_and_commits_once(world):
    folder = world.outer("pat")
    world.duty({"pat": None})
    code, out, err = world.local_history(folder)
    assert (code, err) == (0, "")
    assert git_calls(world) == [
        (["init", "-b", "main"], folder),
        (["config", "user.name", "Claude"], folder),
        (["config", "user.email", "claude@douglassquirrel.com"], folder),
        (["add", "-A"], folder),
        (["commit", "-q", "-m", MESSAGE], folder),
    ]
    with open(os.path.join(folder, ".git", "info", "exclude"), encoding="utf-8") as f:
        assert f.read() == "\n".join(localhistory.exclude_lines(["pat"])) + "\n"
    assert out.startswith(f"Started a local history in {folder}: 3 files, 79 bytes, no remote.\n")
    assert "Dry run" not in out


def test_changes_no_file_that_was_in_the_folder(world):
    folder = world.outer("pat")
    world.duty({"pat": None})
    before = tree(folder)
    assert world.local_history(folder)[0] == 0
    assert outside_git(folder) == before


def test_never_adds_a_remote_and_never_pushes(world):
    one, two = world.outer("pat"), world.outer("solo", lobster=False)
    world.duty({"pat": None})
    assert world.local_history(one, two)[0] == 0
    verbs = {args[0] for args, _ in git_calls(world)}
    assert verbs == {"init", "config", "add", "commit"}


def test_several_folders_are_each_done_in_the_order_given(world):
    one, two = world.outer("pat"), world.outer("quinn")
    world.duty({"pat": None, "quinn": None})
    code, out, _ = world.local_history(two, one)
    assert code == 0
    assert [cwd for args, cwd in git_calls(world) if args[0] == "init"] == [two, one]
    assert out.index(two) < out.index(one)


def test_awkward_names_reach_git_and_the_exclude_file_as_data(world):
    name = "it's $HOME \"q\" café"
    folder = world.outer(name, lobster=False, files={"odd [x]*/.git/HEAD": "r\n", "odd [x]*/a.py": "a\n"})
    code, out, err = world.local_history(folder)
    assert (code, err) == (0, "")
    assert out.startswith(f"Started a local history in {folder}: ")
    assert all(cwd == folder for _, cwd in git_calls(world))
    with open(os.path.join(folder, ".git", "info", "exclude"), encoding="utf-8") as f:
        lines = f.read().split("\n")
    assert "/" + name + "/" in lines and "/odd \\[x]\\*/" in lines


def test_a_folder_given_with_a_trailing_slash_or_relative_is_the_same_folder(world, monkeypatch):
    folder = world.outer("solo", lobster=False)
    monkeypatch.chdir(os.path.dirname(folder))
    code, out, _ = world.local_history("--dry-run", "solo-code/")
    assert code == 0
    assert f"Would start a local history in {os.path.realpath(folder)}: " in out


# --- refusals: nothing is made anywhere

def refused(world, code, *argv):
    got, out, err = world.local_history(*argv)
    assert (got, out) == (code, "")
    assert git_calls(world) == []
    assert err.startswith("local-history: ") and err.endswith("\n") and "Traceback" not in err
    return err


def test_refuses_a_folder_that_is_not_there(world):
    missing = os.path.join(world.code, "nowhere-code")
    assert refused(world, 2, missing) == f"local-history: there is no folder {missing}\n"


def test_refuses_a_file_given_as_a_folder(world):
    folder = world.outer("solo", lobster=False)
    path = os.path.join(folder, "CLAUDE.md")
    assert refused(world, 2, path) == f"local-history: {path} is a file, not a folder\n"


def test_refuses_a_folder_that_already_has_a_git_folder_and_leaves_it_alone(world):
    folder = world.outer("solo", lobster=False, files={".git/HEAD": "mine\n"})
    before = tree(folder)
    err = refused(world, 3, folder)
    assert err == f"local-history: {folder} already has a .git: it has a history, or is itself a checkout. Nothing was made.\n"
    assert tree(folder) == before


def test_refuses_a_folder_inside_a_git_repository(world):
    write_tree(world.code, {".git/HEAD": "above\n"})
    folder = world.outer("solo", lobster=False)
    err = refused(world, 3, folder)
    assert err == (f"local-history: {folder} is inside the git repository at {world.code}: "
                   "it is already in a history. Nothing was made.\n")


def test_refuses_a_folder_with_no_checkout_inside(world):
    folder = os.path.join(world.code, "plain")
    write_tree(folder, {"notes.md": "n\n"})
    err = refused(world, 3, folder)
    assert err == (f"local-history: nothing inside {folder} is a git repository, so it is not the folder around "
                   "a checkout. Nothing was made.\n")


def test_refuses_a_checkout_name_with_a_line_break(world):
    folder = world.outer("solo", lobster=False, files={"two\nlines/.git/HEAD": "r\n"})
    err = refused(world, 3, folder)
    assert "a folder inside it has a line break in its name" in err and "Nothing was made." in err


@pytest.mark.parametrize("state", ["fresh", "stale"])
def test_refuses_while_a_session_is_on_duty_for_the_folders_project(world, state):
    folder = world.outer("pat")
    world.duty({"pat": state})
    err = refused(world, 3, folder)
    assert err == (f"local-history: a session is on duty for pat (mac): its folder {folder} is not changed while "
                   "it works. Ask it to hand over first (conduct stop pat). Nothing was made.\n")


def test_a_project_with_no_mailbox_listed_has_nobody_on_duty(world):
    folder = world.outer("pat")
    world.duty({"other": "fresh"})
    code, out, _ = world.local_history("--dry-run", folder)
    assert code == 0 and "  Duty: nobody is on duty for pat.\n" in out


def test_one_refusal_among_several_folders_means_none_is_made(world):
    good, busy = world.outer("pat"), world.outer("quinn")
    world.duty({"pat": None, "quinn": "fresh"})
    before = tree(good)
    refused(world, 3, good, busy)
    assert tree(good) == before


def test_refuses_the_same_folder_named_twice(world):
    folder = world.outer("solo", lobster=False)
    assert refused(world, 2, folder, folder + "/") == f"local-history: {folder} is named twice\n"


def test_refuses_no_folder_at_all_and_an_unknown_flag(world):
    assert "local-history --help shows the form" in refused(world, 2)
    assert "local-history --help shows the form" in refused(world, 2, "--force", world.outer("solo", lobster=False))


def test_refuses_settings_it_cannot_read(world):
    world.write_conf("EFFORT=enormous\n")
    err = refused(world, 2, "--dry-run", world.outer("pat"))
    assert world.conf in err


def test_help_shows_the_form_and_exits_0(world):
    code, out, err = world.local_history("--help")
    assert (code, err) == (0, "")
    assert "usage: local-history [-h] [--dry-run] FOLDER [FOLDER ...]" in out and "no remote" in out


# --- a program that fails

def test_git_failing_at_the_start_stops_with_its_words_and_exit_5(world):
    folder = world.outer("solo", lobster=False)
    world.fail("git:init")
    code, out, err = world.local_history(folder)
    assert (code, out) == (5, "")
    assert err == f"local-history: git init failed (exit 1) in {folder}\n  git: stub failure\n"


def test_git_failing_later_says_which_git_folders_were_already_made(world):
    one, two = world.outer("solo", lobster=False), world.outer("duo", lobster=False)
    world.fail("git:commit")
    code, _, err = world.local_history(one, two)
    assert code == 5
    assert err == (f"local-history: git commit failed (exit 1) in {one}\n  git: stub failure\n"
                   f"Already made, and left as it is: {one}/.git\n")
    assert [cwd for args, cwd in git_calls(world) if args[0] == "init"] == [one]


def test_git_missing_is_a_plain_error(world):
    folder = world.outer("solo", lobster=False)
    os.remove(os.path.join(world.bin, "git"))
    code, out, err = world.local_history(folder, path=world.bin)      # the stubs alone: no real git to fall back on
    assert (code, out) == (5, "")
    assert err.startswith(f"local-history: git init could not be run in {folder} (") and "Traceback" not in err


def test_lobster_mail_failing_stops_before_anything_is_made(world):
    folder = world.outer("pat")
    world.fail("lobster-mail")
    err = refused(world, 5, folder)
    assert err == "local-history: lobster-mail duty status --all failed (exit 1)\n  lobster-mail: stub failure\n"


def test_a_duty_listing_that_is_not_the_expected_json_stops_before_anything_is_made(world):
    folder = world.outer("pat")
    with open(os.path.join(world.bin, "duty.json"), "w") as f:
        f.write("not json")
    err = refused(world, 5, folder)
    assert err == "local-history: lobster-mail duty status --all --json did not print the expected JSON\n"


def test_refuses_a_folder_with_nothing_of_its_own_to_keep(world):
    folder = os.path.join(world.code, "bare-code")
    write_tree(folder, {"bare/.git/HEAD": "r\n", "bare/a.py": "a\n", "_to_delete/old.md": "o\n"})
    err = refused(world, 3, folder)
    assert err == (f"local-history: {folder} holds nothing of its own to keep: everything in it is a checkout or "
                   "is left out. Nothing was made.\n")


def test_a_lobster_conf_that_names_no_project_is_not_checked_for_duty(world):
    folder = world.outer("solo", lobster=False, files={"lobster.conf": "# a comment\nKIND=code\nSELF=\n"})
    code, out, err = world.local_history("--dry-run", folder)
    assert (code, err) == (0, "")
    assert "  Duty: not checked (no lobster.conf here names a mailbox).\n" in out
    assert world.calls() == []


def test_lobster_mail_that_cannot_be_run_is_a_plain_error(world):
    folder = world.outer("pat")
    os.remove(os.path.join(world.bin, "lobster-mail"))
    err = refused(world, 5, folder)
    assert err.startswith("local-history: lobster-mail duty status --all could not be run (") and "Traceback" not in err
