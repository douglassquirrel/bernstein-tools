"""drop-backlog: take Backlog out of a project that never used it, keeping what it removes (PLAN.md, Settled 147)."""

import datetime
import io
import os
import subprocess
import sys

import pytest
from conftest import tree, write_tree

NOW = datetime.datetime(2026, 10, 18, 9, 40, tzinfo=datetime.timezone.utc)
SETTINGS = 'project_name: "Recipes"\ntask_prefix: "re"\nzero_padded_ids: 3\n'
EMPTY = ("tasks", "completed", "drafts", "decisions", "docs", "milestones", "archive/tasks", "archive/drafts")
KEPT = os.path.join("_to_delete", "backlog-removed-2026-10-18-0940")


def drop(world, *argv):
    from bernstein import dropbacklog
    out, err = io.StringIO(), io.StringIO()
    env = {"PATH": world.bin + os.pathsep + "/usr/bin:/bin", "HOME": world.home, "BERNSTEIN_CONF": world.conf}
    code = dropbacklog.main(list(argv), env=env, today=NOW, out=out, err=err, sleep=lambda seconds: None)
    return code, out.getvalue(), err.getvalue()


def unused(world, name, kind, public=False, extra=None):
    """A project whose Backlog was set up and never used: its settings and Backlog's empty folders."""
    folder = world.project(name, kind, public=public)
    write_tree(folder, {"backlog/config.yml": SETTINGS, "CLAUDE.md": "Ours.\n", "notes/keep.md": "kept é\n"})
    for empty in EMPTY:
        os.makedirs(os.path.join(folder, "backlog", empty))
    write_tree(folder, extra or {})
    return folder


def moves(world):
    return [c for c in world.calls() if c["prog"] != "lobster-mail"]


def test_help_names_the_command_and_a_run_with_no_project_is_exit_2(world):
    code, out, _err = drop(world, "--help")
    assert code == 0 and "usage: drop-backlog" in out and "--dry-run" in out
    code, out, err = drop(world)
    assert (code, out) == (2, "") and err.startswith("drop-backlog: ") and "drop-backlog --help" in err


def test_an_unused_backlog_is_moved_whole_into_the_projects_to_delete_and_nothing_else_changes(world):
    nc = unused(world, "recipes", "non-code", extra={"backlog/.DS_Store": "finder"})
    outer = unused(world, "recipes-tools", "code", public=True)
    world.duty({"recipes": None, "recipes-tools": "handed over"})
    before = {f: tree(f) for f in (nc, outer)}
    code, out, err = drop(world, "recipes", "recipes-tools")
    assert (code, err) == (0, "")
    for folder in (nc, outer):
        after = tree(folder)
        assert not os.path.lexists(os.path.join(folder, "backlog"))
        assert after == {(os.path.join(KEPT, rel) if rel.startswith("backlog" + os.sep) else rel): data
                         for rel, data in before[folder].items()}
        for empty in EMPTY:
            assert os.path.isdir(os.path.join(folder, KEPT, "backlog", empty))
    assert out == (f"recipes: moved {nc}/backlog to {nc}/{KEPT}/backlog\n"
                   f"recipes-tools: moved {outer}/backlog to {outer}/{KEPT}/backlog\n"
                   "Backlog removed from 2 projects. Nothing was committed: each project's next session commits "
                   "the removal.\n")
    assert moves(world) == []


def test_dry_run_says_what_it_would_move_and_changes_nothing(world):
    nc = unused(world, "recipes", "non-code")
    world.duty({"recipes": None})
    before = tree(nc)
    code, out, err = drop(world, "--dry-run", "recipes")
    assert (code, err) == (0, "")
    assert out == (f"recipes: would move {nc}/backlog to {nc}/{KEPT}/backlog\n"
                   "Dry run: nothing was moved.\n")
    assert tree(nc) == before and os.path.isdir(os.path.join(nc, "backlog", "tasks"))


@pytest.mark.parametrize("held, said", [
    ({"backlog/tasks/re-001 - Fix-the-oven.md": "t\n"}, "1 file besides its settings (tasks/re-001 - Fix-the-oven.md)"),
    ({"backlog/drafts/draft-1.md": "d\n", "backlog/decisions/decision-1.md": "d\n", "backlog/docs/doc-1.md": "d\n"},
     "3 files besides its settings (decisions/decision-1.md, docs/doc-1.md, drafts/draft-1.md)"),
    ({"backlog/archive/tasks/a.md": "", "backlog/completed/b.md": "", "backlog/milestones/m.md": "",
      "backlog/tasks/c.md": "", "backlog/tasks/d.md": ""},
     "5 files besides its settings (archive/tasks/a.md, completed/b.md, milestones/m.md and 2 more)"),
])
def test_a_backlog_that_holds_anything_but_its_settings_is_in_use_and_no_project_of_the_run_is_touched(world, held, said):
    clean = unused(world, "menus", "non-code")
    used = unused(world, "recipes", "non-code", extra=held)
    world.duty({"recipes": None, "menus": None})
    before = tree(clean), tree(used)
    for argv in (("menus", "recipes"), ("--dry-run", "menus", "recipes")):
        code, out, err = drop(world, *argv)
        assert (code, out) == (3, "")
        assert err == (f"drop-backlog: recipes keeps tickets: {used}/backlog holds {said}. It is left alone, and "
                       "nothing was moved in any project\n")
    assert (tree(clean), tree(used)) == before


@pytest.mark.parametrize("state", ["fresh", "stale"])
def test_a_project_with_anyone_on_duty_fresh_or_stale_is_refused_and_nothing_is_moved(world, state):
    nc = unused(world, "recipes", "non-code")
    world.duty({"recipes": state})
    before = tree(nc)
    code, out, err = drop(world, "recipes")
    assert (code, out) == (3, "")
    assert err == ("drop-backlog: mac is on duty for recipes (last beat 2026-10-18T09:30:00Z): a project's files "
                   "are not changed under a session. Stop it with conduct stop, or conduct reset if it is gone; "
                   "nothing was moved in any project\n")
    assert tree(nc) == before


def test_an_unknown_project_one_in_two_places_or_a_backlog_that_is_a_link_is_exit_3(world, tmp_path):
    nc = unused(world, "recipes", "non-code")
    world.duty({"recipes": None})
    code, _out, err = drop(world, "recipes", "menus")
    assert code == 3 and err == (f"drop-backlog: no project menus in {world.non_code} or {world.code}, or a folder "
                                 "directly inside either; nothing was moved in any project\n")
    os.makedirs(os.path.join(world.code, "recipes"))
    code, _out, err = drop(world, "recipes")
    assert code == 3 and err.startswith("drop-backlog: recipes is in two places, ")
    os.rmdir(os.path.join(world.code, "recipes"))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    os.rename(os.path.join(nc, "backlog"), os.path.join(nc, "backlog-real"))
    os.symlink(str(elsewhere), os.path.join(nc, "backlog"))
    code, _out, err = drop(world, "recipes")
    assert code == 3 and err == (f"drop-backlog: {nc}/backlog is a link, not a folder: it is left alone; nothing "
                                 "was moved in any project\n")
    assert os.path.islink(os.path.join(nc, "backlog")) and os.listdir(elsewhere) == []


def test_a_project_that_keeps_no_tickets_already_is_passed_over_and_a_project_with_no_mailbox_is_done(world):
    plain = world.project("menus", "non-code")
    nc = unused(world, "recipes", "non-code")
    world.duty({"menus": None})                                   # recipes has no mailbox: nobody can be on duty
    before = tree(plain)
    code, out, err = drop(world, "menus", "recipes")
    assert (code, err) == (0, "")
    assert out == (f"menus: keeps no tickets already ({plain} has no backlog/): nothing to move\n"
                   f"recipes: moved {nc}/backlog to {nc}/{KEPT}/backlog\n"
                   "Backlog removed from 1 project. Nothing was committed: each project's next session commits "
                   "the removal.\n")
    assert tree(plain) == before
    code, out, _err = drop(world, "menus", "recipes")
    assert code == 0 and out.endswith("Nothing to remove.\n") and out.count("keeps no tickets already") == 2


def test_a_second_removal_in_the_same_minute_never_writes_over_a_kept_copy(world):
    nc = unused(world, "recipes", "non-code")
    world.duty({"recipes": None})
    assert drop(world, "recipes")[0] == 0
    write_tree(nc, {"backlog/config.yml": "again\n"})
    code, out, err = drop(world, "recipes")
    assert (code, err) == (0, "") and f"to {nc}/{KEPT}-2/backlog\n" in out
    kept = tree(os.path.join(nc, "_to_delete"))
    assert kept["backlog-removed-2026-10-18-0940/backlog/config.yml"] == SETTINGS.encode()
    assert kept["backlog-removed-2026-10-18-0940-2/backlog/config.yml"] == b"again\n"


def test_a_duty_listing_that_cannot_be_had_or_a_bad_settings_line_stops_before_anything_moves(world):
    nc = unused(world, "recipes", "non-code")
    world.fail("lobster-mail")
    code, _out, err = drop(world, "recipes")
    assert code == 4 and err.startswith("drop-backlog: lobster-mail duty status --all failed (exit 1)")
    world.fail()
    world.write_conf("EFFORT=extreme\n")
    code, _out, err = drop(world, "recipes")
    assert (code, err) == (2, f"drop-backlog: {world.conf}: line 7: EFFORT must be one of low, medium, high, xhigh, max\n")
    assert os.path.isfile(os.path.join(nc, "backlog", "config.yml"))


def test_a_move_that_fails_part_way_is_exit_4_saying_what_was_moved(world):
    first = unused(world, "menus", "non-code")
    second = unused(world, "recipes", "non-code", extra={"_to_delete/old.md": "old\n"})
    world.duty({"recipes": None, "menus": None})
    os.chmod(os.path.join(second, "_to_delete"), 0o555)
    try:
        code, out, err = drop(world, "menus", "recipes")
    finally:
        os.chmod(os.path.join(second, "_to_delete"), 0o755)
    assert code == 4 and out == f"menus: moved {first}/backlog to {first}/{KEPT}/backlog\n"
    assert err == (f"drop-backlog: {second}/backlog could not be moved to {second}/{KEPT}/backlog (Permission "
                   "denied): it is where it was. Moved before that: menus\n")
    assert os.path.isfile(os.path.join(second, "backlog", "config.yml"))


def test_the_command_file_runs_as_a_program(world):
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    done = subprocess.run([sys.executable, os.path.join(here, "drop-backlog"), "--help"], capture_output=True,
                          text=True, check=False, env={"PATH": "/usr/bin:/bin", "HOME": world.home})
    assert done.returncode == 0 and "usage: drop-backlog" in done.stdout
