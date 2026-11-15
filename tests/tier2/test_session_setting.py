"""SESSION in lobster.conf: a non-code project may say its session is a Claude Code one on the Mac
(PLAN.md, "A ganglion on the Mac: SESSION=code", Settled 168). Read and refused here; set by set-conf."""

import os

import pytest
from conftest import tree, write_tree
from test_set_conf import DRY, KEPT, OWED, setconf

ONLY = ("only a non-code project says which kind of session it runs in (a tools project and a conductor run in "
        "Claude Code, a feeler in Claude Cowork): take the line out")


def ganglion(world, line=None):
    """recipes and recipes-tools with nobody on duty; line is added to the non-code half's lobster.conf."""
    folder = world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    if line is not None:
        with open(os.path.join(folder, "lobster.conf"), "a") as f:
            f.write(line + "\n")
    world.duty({"recipes": None, "recipes-tools": None})
    return folder


def calls(world, verb):
    return [c for c in world.calls() if c["args"][:1] == [verb] or c["prog"] == verb]


@pytest.mark.parametrize("value", ["mac", "Code", "CODE", "claude-code", "code cowork", "yes"])
def test_start_and_its_dry_run_refuse_a_session_that_is_not_cowork_or_code_and_status_says_so(world, value):
    folder = ganglion(world, f"SESSION={value}")
    conf = os.path.join(folder, "lobster.conf")
    said = f"{conf} says SESSION={value}: it must be cowork or code (no SESSION line means cowork)"
    before = tree(folder)
    for argv in (("start", "recipes"), ("start", "--dry-run", "recipes")):
        assert world.conduct(*argv) == (3, "", f"conduct: {said}\n")
    assert calls(world, "send") == [] and calls(world, "open") == [] and tree(folder) == before
    code, out, _err = world.conduct("status")
    assert code == 0 and f"cannot start: {said}" in out


@pytest.mark.parametrize("value", ["code", "cowork"])
def test_a_tools_project_that_names_a_session_is_refused(world, value):
    folder = world.project("recipes-tools", "code")
    with open(os.path.join(folder, "lobster.conf"), "a") as f:
        f.write(f"SESSION={value}\n")
    world.duty({"recipes-tools": None})
    for argv in (("start", "recipes-tools"), ("start", "--dry-run", "recipes-tools")):
        assert world.conduct(*argv) == (
            3, "", f"conduct: {folder}/lobster.conf says KIND=code and SESSION={value}: {ONLY}\n")
    assert calls(world, "send") == [] and calls(world, "open") == []


@pytest.mark.parametrize("value", ["code", "cowork"])
def test_a_feeler_that_names_a_session_is_refused(world, value):
    folder = os.path.join(world.non_code, "agents")
    write_tree(folder, {"lobster.conf": f"KIND=feeler\nSELF=agents\nSISTER=\nMODEL=opus\nEFFORT=high\nSESSION={value}\n",
                        "START-HERE.txt": "Start agents.\n"})
    world.duty({"agents": None})
    assert world.conduct("start", "agents") == (
        3, "", f"conduct: {folder}/lobster.conf says KIND=feeler and SESSION={value}: {ONLY}\n")
    assert calls(world, "send") == [] and calls(world, "open") == []


def test_status_says_a_conductor_that_names_a_session_cannot_start(world):
    folder = world.conductor("maestro", extra="SESSION=code\n")
    world.project("maestro-tools", "code", sister="maestro")
    world.duty({"maestro": None, "maestro-tools": None})
    code, out, _err = world.conduct("status")
    assert code == 0
    assert f"cannot start: {folder}/lobster.conf says KIND=conductor and SESSION=code: {ONLY}" in out


def test_help_of_set_conf_names_the_sixth_setting(world):
    code, out, err = setconf(world, "--help")
    assert (code, err) == (0, "")
    assert "SISTER, CLAWS, FOLDERS, MODEL, EFFORT or SESSION" in " ".join(out.split())


def test_set_conf_sets_the_session_and_sets_it_back_keeping_the_file_each_time(world):
    folder = ganglion(world)
    conf = os.path.join(folder, "lobster.conf")
    before = tree(folder)
    kept = os.path.join(folder, KEPT)
    code, out, err = setconf(world, "--dry-run", "recipes", "SESSION=code")
    assert (code, err) == (0, "")
    assert out == (f"recipes: {conf}\n  is:       (no SESSION line)\n  would be: SESSION=code (added as the last line)\n"
                   f"  the file as it is would be kept in {kept}\n" + DRY.format("recipes"))
    assert tree(folder) == before
    code, out, err = setconf(world, "recipes", "SESSION=code")
    assert (code, err) == (0, "")
    assert out == (f"recipes: {conf}\n  was: (no SESSION line)\n  now: SESSION=code (added as the last line)\n"
                   f"  the file as it was is kept in {kept}\n" + OWED.format("recipes"))
    after = tree(folder)
    assert after.pop(KEPT) == before["lobster.conf"]
    assert after.pop("lobster.conf") == before["lobster.conf"] + b"SESSION=code\n"
    assert after == {k: v for k, v in before.items() if k != "lobster.conf"}
    code, out, err = setconf(world, "recipes", "SESSION=cowork")
    assert (code, err) == (0, "")
    assert "  was: SESSION=code\n  now: SESSION=cowork\n" in out
    assert tree(folder)["lobster.conf"] == before["lobster.conf"] + b"SESSION=cowork\n"
    code, out, err = setconf(world, "recipes", "SESSION=")
    assert (code, err) == (0, "") and "  was: SESSION=cowork\n  now: SESSION=\n" in out


@pytest.mark.parametrize("project, value, why", [
    ("recipes", "mac", "{conf} says SESSION=mac: it must be cowork or code (no SESSION line means cowork)"),
    ("recipes", "Code", "{conf} says SESSION=Code: it must be cowork or code (no SESSION line means cowork)"),
    ("recipes-tools", "code", "{conf} says KIND=code and SESSION=code: " + ONLY),
    ("recipes-tools", "cowork", "{conf} says KIND=code and SESSION=cowork: " + ONLY),
    ("agents", "code", "{conf} says KIND=feeler and SESSION=code: " + ONLY),
])
def test_set_conf_refuses_a_session_it_does_not_know_and_one_on_another_kind_of_project(world, project, value, why):
    ganglion(world)
    write_tree(os.path.join(world.non_code, "agents"), {
        "lobster.conf": "KIND=feeler\nSELF=agents\nSISTER=\nMODEL=opus\nEFFORT=high\n", "START-HERE.txt": "Start.\n"})
    world.duty({"recipes": None, "recipes-tools": None, "agents": None})
    folder = {"recipes": os.path.join(world.non_code, "recipes"), "agents": os.path.join(world.non_code, "agents"),
              "recipes-tools": os.path.join(world.code, "recipes-tools")}[project]
    before = tree(folder)
    for argv in ((project, f"SESSION={value}"), ("--dry-run", project, f"SESSION={value}")):
        code, out, err = setconf(world, *argv)
        assert (code, out) == (3, "")
        assert err == (f"set-conf: with SESSION={value} conduct start would refuse {project}: "
                       + why.format(conf=os.path.join(folder, "lobster.conf")) + "; nothing was changed\n")
    assert tree(folder) == before
