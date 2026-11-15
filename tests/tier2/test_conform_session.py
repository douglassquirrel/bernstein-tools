"""conform and a ganglion on the Mac: a non-code project whose lobster.conf says SESSION=code is checked
against the files rendered for a Claude Code session (PLAN.md, "A ganglion on the Mac: SESSION=code")."""

import os

import pytest
from test_conform import GLOBAL, NC_RULES, SECTIONS, feeler_in_line, pair_in_line, split_pair, write

BEHIND = "  missing: the template's current RULES.md (a global file: conduct start brings it up to date)\n"
HOME_CLAW = "the home claw, `recipes-tools`: **read and run only**; never write, commit, install or make a `.venv` in it |\n"
IN_THE_MACHINE = (NC_RULES + "| `~/mnt/recipes-tools` | " + HOME_CLAW
                  + "| `~/mnt/knives` | the claw `knives`: read and run only, as above |\n")
ON_THE_MAC = (NC_RULES + "| `~/projects/code/eat/recipes-tools-code/recipes-tools` | " + HOME_CLAW
              + "| `~/projects/code/knives` | the claw `knives`: read and run only, as above |\n")


def says(folder, line):
    with open(os.path.join(folder, "lobster.conf"), "a") as f:
        f.write(line + "\n")


def test_a_ganglion_is_checked_against_the_global_files_rendered_for_its_own_kind_of_session(world):
    nc, outer, _checkout = split_pair(world)
    write(world.template, {"non-code/RULES.md": GLOBAL["non-code/RULES.md"] + "{{CLAW_MOUNTS}}\n"})
    write(nc, {"RULES.md": IN_THE_MACHINE})
    in_line = (0, f"recipes (non-code): {nc}\n  in line\nrecipes-tools (code): {outer}\n  in line\n"
                  "Both halves are in line.\n", "")
    behind = (1, f"recipes (non-code): {nc}\n{BEHIND}recipes-tools (code): {outer}\n  in line\n"
                 "1 thing to bring into line.\n", "")
    assert world.conform("recipes", "recipes-tools") == in_line
    says(nc, "SESSION=code")                          # its files are those of a session in the virtual machine
    assert world.conform("recipes", "recipes-tools") == behind
    write(nc, {"RULES.md": ON_THE_MAC})
    assert world.conform("recipes", "recipes-tools") == in_line
    says(nc, "SESSION=cowork")                        # and the other way round
    assert world.conform("recipes", "recipes-tools") == behind


def test_a_section_the_template_gives_one_kind_of_session_is_asked_of_that_kind_only(world):
    nc, outer, _checkout = pair_in_line(world)
    write(world.template, {"common/sections/where-cowork.md": "## In the virtual machine\n\nUnder ~/mnt.\n",
                           "common/sections/where-code.md": "## On the Mac\n\nWhere they are.\n",
                           "non-code/CLAUDE.md": SECTIONS["non-code/CLAUDE.md"] + "\n{{> sections/where-{{SESSION}}.md}}\n"})
    lacks = (f"recipes (non-code): {nc}\n  missing: the section \"## {{}}\" in CLAUDE.md\n"
             f"recipes-tools (code): {outer}\n  in line\n1 thing to bring into line.\n")
    assert world.conform("recipes", "recipes-tools") == (1, lacks.format("In the virtual machine"), "")
    says(nc, "SESSION=code")
    assert world.conform("recipes", "recipes-tools") == (1, lacks.format("On the Mac"), "")
    with open(os.path.join(nc, "CLAUDE.md"), "a") as f:
        f.write("\n## On the Mac\n\nOurs.\n")
    code, out, err = world.conform("recipes", "recipes-tools")
    assert (code, err) == (0, "") and out.endswith("Both halves are in line.\n")


@pytest.mark.parametrize("value", ["mac", "Code", "code cowork"])
def test_a_session_that_is_neither_cowork_nor_code_is_listed(world, value):
    nc, outer, _checkout = pair_in_line(world)
    says(nc, f"SESSION={value}")
    assert world.conform("recipes", "recipes-tools") == (
        1, f"recipes (non-code): {nc}\n"
           f"  missing: SESSION=cowork or SESSION=code in lobster.conf, or no SESSION line (it says SESSION={value})\n"
           f"recipes-tools (code): {outer}\n  in line\n1 thing to bring into line.\n", "")


ONLY = "  missing: an empty SESSION in lobster.conf (it says SESSION={}; only a non-code project names its kind of session)\n"


@pytest.mark.parametrize("value", ["code", "cowork"])
def test_a_session_named_by_a_tools_project_or_a_feeler_is_listed(world, value):
    nc, outer, _checkout = pair_in_line(world)
    says(outer, f"SESSION={value}")
    assert world.conform("recipes", "recipes-tools") == (
        1, f"recipes (non-code): {nc}\n  in line\nrecipes-tools (code): {outer}\n" + ONLY.format(value)
           + "1 thing to bring into line.\n", "")
    folder = feeler_in_line(world)
    says(folder, f"SESSION={value}")
    code, out, _err = world.conform("agents")
    assert code == 1 and out == f"agents (feeler): {folder}\n" + ONLY.format(value) + "1 thing to bring into line.\n"


def test_a_session_named_by_a_conductor_is_listed(world):
    folder = world.conductor("maestro", extra="SESSION=code\n")
    world.project("maestro-tools", "code", sister="maestro")
    code, out, _err = world.conform("maestro", "maestro-tools")
    assert code == 1 and out.startswith(f"maestro (conductor): {folder}\n" + ONLY.format("code"))


def test_a_ganglion_on_the_mac_may_name_further_folders_and_is_still_asked_for_its_hook(world):
    nc, outer, _checkout = pair_in_line(world)
    os.makedirs(os.path.join(world.home, "models", "kokoro"))
    says(nc, "SESSION=code\nFOLDERS=~/models/kokoro")
    code, out, err = world.conform("recipes", "recipes-tools")
    assert (code, err) == (0, "") and out.endswith("Both halves are in line.\n")
    os.remove(os.path.join(nc, ".claude", "settings.json"))
    assert world.conform("recipes", "recipes-tools") == (
        1, f"recipes (non-code): {nc}\n  missing: .claude/settings.json (the lobster-mail start hook)\n"
           f"recipes-tools (code): {outer}\n  in line\n1 thing to bring into line.\n", "")


def test_all_counts_a_ganglion_on_the_mac_like_any_other(world):
    nc, _outer, _checkout = split_pair(world)
    plain = world.conform("--all")
    says(nc, "SESSION=code")
    assert world.conform("--all") == plain and plain[0] == 0 and "in line" in plain[1]
    write(world.template, {"non-code/RULES.md": GLOBAL["non-code/RULES.md"] + "{{CLAW_MOUNTS}}\n"})
    write(nc, {"RULES.md": IN_THE_MACHINE})
    code, out, err = world.conform("--all")
    assert (code, err) == (0, "")
    assert "  a start mends: the template's current RULES.md (a global file: conduct start brings it up to date)\n" in out
