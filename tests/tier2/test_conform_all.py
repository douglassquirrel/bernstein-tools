"""conform --all: every lobster project the settings can find, in one run (PLAN.md, Settled 161)."""

import json
import os
import shlex

import pytest
from conftest import tree, write_tree

TEMPLATE = {
    "common/global-files": "RULES.md\n",
    "common/sections/served-sister.md": "## The sister project: {{NAME}}\n\nServes it.\n",
    "common/sections/served-any.md": "## Who may ask\n\nAny lobster project.\n",
    "common/sections/served-conductor.md": "## Its conductor\n\nOnly {{REQUESTER}}.\n",
    "non-code/CLAUDE.md": "# {{NAME}}\n\n## The pair: {{NAME}} and {{TOOLS}}\n",
    "code/CLAUDE.md": "# {{TOOLS}}\n\n{{> sections/served-{{SERVED}}.md}}\n",
    "non-code/RULES.md": "Rules for {{SELF}}.\n",
    "code/RULES.md": "Rules for {{TOOLS}}, serving {{SERVING}}.\n",
    "feeler/RULES.md": "Feeler rules for {{NAME}}.\n",
    "feeler/CLAUDE.md": "# {{NAME}}\n",
    "feeler/START-HERE.txt": "Start {{NAME}}.\n",
}
HOOK = '{{"command": "\\"$HOME/l/lobster-mail\\" start --project \\"$CLAUDE_PROJECT_DIR\\" --root {root}"}}\n'
BEHIND = "  a start mends: the template's current RULES.md (a global file: conduct start brings it up to date)\n"


def lay(world, name, kind, sister="", under="", public=False, serving=None, mailbox=True):
    """A project with everything conform asks of its kind, in line with TEMPLATE: its folder."""
    if kind == "code":
        folder = os.path.join(world.code, under, name + "-code" if public else name)
        section = "## The sister project: " + sister if sister else "## Who may ask"
        files = {"CLAUDE.md": f"# {name}\n\n{section}\n\nOurs.\n",
                 "RULES.md": "Rules for {}, serving {}.\n".format(
                     name, serving or (f"`{sister}`" if sister else "Squirrel's lobster projects"))}
    elif kind == "non-code":
        folder = os.path.join(world.non_code, under, name)
        files = {"CLAUDE.md": f"# {name}\n\n## The pair: {name} and {sister}\n\nOurs.\n",
                 "RULES.md": f"Rules for {name}.\n"}
    else:
        folder = os.path.join(world.non_code, under, name)
        files = {"CLAUDE.md": f"# {name}\n\nOurs.\n", "RULES.md": f"Feeler rules for {name}.\n"}
    files.update({"lobster.conf": f"KIND={kind}\nSELF={name}\nSISTER={sister}\nMODEL=opus\nEFFORT=high\n",
                  "START-HERE.txt": f"Start {name}.\n"})
    if kind != "feeler":
        files.update({".claude/settings.json": HOOK.format(root=shlex.quote(world.mail)),
                      "inbox/README.md": "Inbox.\n"})
    files[(name + "/" if public else "") + ".git/HEAD"] = "ref\n"
    write_tree(folder, files)
    if mailbox:
        os.makedirs(os.path.join(world.mail, name), exist_ok=True)
    return folder


def an_estate(world):
    """Every kind of project in one world, with what is wrong with each: {name: folder}."""
    write_tree(world.template, TEMPLATE)
    at = {"menus": lay(world, "menus", "non-code", "menus-tools"),
          "menus-tools": lay(world, "menus-tools", "code", "menus"),
          "recipes": lay(world, "recipes", "non-code", "recipes-tools", under="eat"),
          "recipes-tools": lay(world, "recipes-tools", "code", "recipes", under="eat", public=True),
          "maestro": world.conductor("maestro"),
          "maestro-tools": lay(world, "maestro-tools", "code", "maestro", public=True, serving="`maestro`"),
          "agents": lay(world, "agents", "feeler"),
          "word-tools": lay(world, "word-tools", "code", mailbox=False),
          "odd": os.path.join(world.non_code, "odd"),
          "twice": os.path.join(world.non_code, "a", "twice")}
    write_tree(at["maestro-tools"], {"CLAUDE.md": "# maestro-tools\n\n## Its conductor\n\nOurs.\n"})
    os.makedirs(os.path.join(world.mail, "maestro"))
    for name in ("recipes", "recipes-tools"):                                  # behind the template, both halves
        write_tree(at[name], {"RULES.md": "Rules as they were.\n"})
    os.remove(os.path.join(at["word-tools"], "START-HERE.txt"))                # a gap nothing mends
    os.makedirs(at["odd"])
    with open(os.path.join(at["odd"], "lobster.conf"), "wb") as f:
        f.write(b"KIND=non-code\n# caf\xe9\n")
    for under in ("a", "b"):
        write_tree(os.path.join(world.non_code, under, "twice"), {"lobster.conf": "KIND=feeler\n"})
    os.makedirs(os.path.join(world.mail, "bernstein"))                         # a mailbox with no project
    write_tree(world.non_code, {".hidden/secret/lobster.conf": "KIND=feeler\n", "notes/readme.md": "not a project\n"})
    return at


def test_all_checks_every_project_once_in_the_form_that_fits_it_and_counts_the_two_kinds_of_gap_apart(world):
    at = an_estate(world)
    before = tree(world.home)
    code, out, err = world.conform("--all")
    assert err == ""
    assert out == (
        f"menus (non-code): {at['menus']}\n  in line\n"
        f"menus-tools (code): {at['menus-tools']}\n  in line\n"
        "\n"
        f"recipes (non-code): {at['recipes']}\n{BEHIND}"
        f"recipes-tools (code): {at['recipes-tools']}\n{BEHIND}"
        "\n"
        f"maestro (conductor): {at['maestro']}\n  in line\n"
        f"maestro-tools (code): {at['maestro-tools']}\n  in line\n"
        "\n"
        f"agents (feeler): {at['agents']}\n  in line\n"
        "\n"
        f"word-tools (code): {at['word-tools']}\n"
        "  missing: START-HERE.txt\n"
        f"  missing: the mailbox word-tools in {world.mail}\n"
        "\n"
        f"odd: cannot be checked\n  {at['odd']}/lobster.conf is not plain UTF-8 text: save it again as UTF-8\n"
        "\n"
        f"twice: cannot be checked\n  twice is in two places, {world.non_code}/a/twice and {world.non_code}/b/twice: "
        "keep one, or rename the other\n"
        "\n"
        f"bernstein: a mailbox in {world.mail} with no lobster project\n"
        "10 projects: 2 things to bring into line, 2 more that a conduct start mends, 2 projects that could not be "
        "checked.\n")
    assert code == 1
    assert tree(world.home) == before and world.calls() == []                  # it reads only, and runs nothing


def test_all_is_exit_0_when_only_a_start_is_needed_and_says_so_when_everything_is_in_line(world):
    write_tree(world.template, TEMPLATE)
    nc = lay(world, "menus", "non-code", "menus-tools")
    tools = lay(world, "menus-tools", "code", "menus")
    lone = lay(world, "word-tools", "code", under="words", public=True)
    code, out, err = world.conform("--all")
    assert (code, err) == (0, "")
    assert out == (f"menus (non-code): {nc}\n  in line\nmenus-tools (code): {tools}\n  in line\n\n"
                   f"word-tools (code): {lone}\n  in line\n\n"
                   "3 projects: all in line.\n")
    write_tree(lone, {"RULES.md": "Rules as they were.\n"})
    code, out, err = world.conform("--all")
    assert (code, err) == (0, "")
    assert out.endswith(f"word-tools (code): {lone}\n{BEHIND}\n"
                        "3 projects: nothing to bring into line, 1 that a conduct start mends.\n")


def test_all_with_no_project_anywhere_says_so(world):
    write_tree(world.template, TEMPLATE)
    os.makedirs(os.path.join(world.code, "not-a-project", "src"))
    code, out, err = world.conform("--all")
    assert (code, out, err) == (0, (f"No lobster project in {world.non_code} or {world.code}, or a folder directly "
                                   "inside either.\n"), "")


def test_a_half_is_checked_once_and_a_tools_project_with_no_pair_to_be_half_of_is_still_checked(world):
    write_tree(world.template, TEMPLATE)
    shared = lay(world, "word-tools", "code")                                  # a lone claw, home to two projects
    essays = lay(world, "essays", "non-code", "word-tools")
    letters = lay(world, "letters", "non-code", "word-tools")
    for folder, name in ((essays, "essays"), (letters, "letters")):
        write_tree(folder, {"CLAUDE.md": f"# {name}\n\n## The pair: {name} and word-tools\n\nOurs.\n"})
    stray = lay(world, "stray-tools", "code", "essays")                        # says essays, which names another
    orphan = lay(world, "orphan-tools", "code", "ghost")                       # says ghost, which is not there
    alone = lay(world, "alone", "non-code", "")                                # a non-code project naming no claw
    code, out, err = world.conform("--all")
    assert (code, err) == (1, "")
    assert out == (
        f"essays (non-code): {essays}\n  in line\nword-tools (code): {shared}\n  in line\n"
        "\n"
        f"letters (non-code): {letters}\n  in line\nword-tools (code): see above\n"
        "\n"
        f"ghost (non-code): not found\n  ghost is not in {world.non_code} or a folder directly inside it\n"
        f"orphan-tools (code): {orphan}\n  in line\n"
        "\n"
        f"essays (non-code): see above\nstray-tools (code): {stray}\n  in line\n"
        "\n"
        f"alone: cannot be checked\n  {alone}/lobster.conf names no SISTER, the tools project a non-code project "
        "works with\n"
        "\n"
        "6 projects: 1 thing to bring into line, 1 project that could not be checked.\n")


def test_json_holds_exactly_what_the_text_does_and_the_text_is_printed_from_it(world):
    from bernstein import conform
    at = an_estate(world)
    code, out, err = world.conform("--all", "--json")
    assert (code, err) == (1, "")
    data = json.loads(out)
    assert sorted(data) == ["blocks", "mailboxes_without_a_project", "totals"]
    assert data["totals"] == {"projects": 10, "nothing_mends": 2, "a_start_mends": 2, "cannot_be_checked": 2}
    assert data["mailboxes_without_a_project"] == ["bernstein"]
    behind = {"missing": "the template's current RULES.md (a global file: conduct start brings it up to date)",
              "start_mends": True}
    assert data["blocks"][1] == [
        {"name": "recipes", "kind": "non-code", "folder": at["recipes"], "state": "checked", "why": None,
         "gaps": [behind]},
        {"name": "recipes-tools", "kind": "code", "folder": at["recipes-tools"], "state": "checked", "why": None,
         "gaps": [behind]}]
    assert data["blocks"][4] == [
        {"name": "word-tools", "kind": "code", "folder": at["word-tools"], "state": "checked", "why": None,
         "gaps": [{"missing": "START-HERE.txt", "start_mends": False},
                  {"missing": f"the mailbox word-tools in {world.mail}", "start_mends": False}]}]
    assert data["blocks"][5] == [
        {"name": "odd", "kind": None, "folder": None, "state": "cannot be checked", "gaps": [],
         "why": f"{at['odd']}/lobster.conf is not plain UTF-8 text: save it again as UTF-8"}]
    assert [[h["name"] for h in block] for block in data["blocks"]] == [
        ["menus", "menus-tools"], ["recipes", "recipes-tools"], ["maestro", "maestro-tools"], ["agents"],
        ["word-tools"], ["odd"], ["twice"]]
    settings = {"NON_CODE_DIR": world.non_code, "CODE_DIR": world.code, "MAIL_ROOT": world.mail}
    assert conform.survey_text(data, settings) == world.conform("--all")[1]
    assert out.endswith("\n") and "\n " in out                               # indented, a line a value


def test_all_takes_no_project_and_json_goes_only_with_all(world):
    an_estate(world)
    for argv, said in ((("--all", "menus"), "--all checks every project: name none with it"),
                       (("--all", "menus", "menus-tools"), "--all checks every project: name none with it"),
                       (("--json", "menus", "menus-tools"), "--json goes with --all"),
                       (("--json",), "--json goes with --all"),
                       ((), "the following arguments are required: project"),
                       (("--all", "--dry-run"), "unrecognized arguments: --dry-run")):
        code, out, err = world.conform(*argv)
        assert (code, out, err) == (2, "", f"conform: {said} (conform --help shows the form)\n")
    code, out, _err = world.conform("--help")
    assert code == 0 and "--all" in out and "--json" in out and "conduct start mends" in out


def test_a_file_that_is_behind_is_mended_by_a_start_only_where_the_project_keeps_every_global_file(world):
    write_tree(world.template, dict(TEMPLATE, **{"common/global-files": "RULES.md\nMORE.md\n",
                                                 "code/MORE.md": "More for {{TOOLS}}.\n"}))
    whole = lay(world, "whole-tools", "code")
    part = lay(world, "part-tools", "code")
    write_tree(whole, {"RULES.md": "old\n", "MORE.md": "old\n"})
    write_tree(part, {"RULES.md": "old\n"})                                    # and no MORE.md at all
    code, out, err = world.conform("--all")
    assert (code, err) == (1, "")
    assert out == (
        f"part-tools (code): {part}\n"
        "  missing: the template's current RULES.md (a global file: conduct start brings it up to date)\n"
        "  missing: MORE.md, one of the template's global files\n"
        "\n"
        f"whole-tools (code): {whole}\n{BEHIND}{BEHIND.replace('RULES.md', 'MORE.md')}"
        "\n"
        "2 projects: 2 things to bring into line, 2 more that a conduct start mends.\n")
    world.duty({"whole-tools": None, "part-tools": None})                      # and conduct start does as conform said
    assert world.conduct("start", "whole-tools")[0] == 0 and world.conduct("start", "part-tools")[0] == 0
    assert tree(whole)["RULES.md"] == b"Rules for whole-tools, serving Squirrel's lobster projects.\n"
    assert tree(part)["RULES.md"] == b"old\n"
    code, out, _err = world.conform("whole-tools")                              # a project named alone prints as ever
    assert (code, out) == (0, f"whole-tools (code): {whole}\n  in line\nThe claw is in line.\n")
    code, out, _err = world.conform("part-tools")
    assert code == 1 and "  missing: the template's current RULES.md (a global file" in out


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_what_cannot_be_checked_never_stops_the_run_but_a_template_that_cannot_be_used_does(world):
    write_tree(world.template, TEMPLATE)
    good = lay(world, "word-tools", "code")
    sick = lay(world, "sick", "non-code", "sick-tools")                        # its settings cannot be read
    sick_tools = lay(world, "sick-tools", "code", "sick")
    with open(os.path.join(sick, "lobster.conf"), "wb") as f:
        f.write(b"\xff\xfe")
    lay(world, "agents", "feeler")
    lay(world, "hanger-tools", "code", "agents")                               # says a feeler is its sister
    strange = lay(world, "strange", "non-code", "x")
    write_tree(strange, {"lobster.conf": "KIND=tentacle\n"})
    baton = world.conductor("baton", claw="")
    locked = lay(world, "locked-tools", "code")                                # its Backlog settings are shut
    write_tree(locked, {"backlog/config.yml": 'task_prefix: "lt"\n'})
    os.chmod(os.path.join(locked, "backlog", "config.yml"), 0)
    try:
        code, out, err = world.conform("--all")
    finally:
        os.chmod(os.path.join(locked, "backlog", "config.yml"), 0o644)
    assert (code, err) == (1, "")
    assert out == (
        f"agents (feeler): {world.non_code}/agents\n  in line\n"
        "\n"
        "hanger-tools: cannot be checked\n  agents is a feeler, which has no tools project: give its name alone\n"
        "\n"
        f"locked-tools: cannot be checked\n  {locked}/backlog/config.yml cannot be read (Permission denied), so the "
        "prefix of locked-tools's tickets is not known: check its permissions\n"
        "\n"
        f"sick (non-code): see below\nsick-tools (code): {sick_tools}\n  in line\n"
        "\n"
        f"word-tools (code): {good}\n  in line\n"
        "\n"
        f"baton: cannot be checked\n  {baton}/lobster.conf names no SISTER, the claw a conductor works with\n"
        "\n"
        f"sick: cannot be checked\n  {sick}/lobster.conf is not plain UTF-8 text: save it again as UTF-8\n"
        "\n"
        f"strange: cannot be checked\n  {strange}/lobster.conf says KIND=tentacle: it must be code, non-code, "
        "feeler or conductor\n"
        "\n"
        "8 projects: nothing to bring into line, 5 projects that could not be checked.\n")
    os.remove(os.path.join(world.template, "common", "sections", "served-any.md"))
    code, out, err = world.conform("--all")
    assert code == 4 and err == ("conform: the template cannot be read: [Errno 2] No such file or directory: "
                                 f"'{world.template}/common/sections/served-any.md'\n")


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_a_lobster_conf_that_cannot_be_opened_is_listed_and_the_rest_are_still_checked(world):
    write_tree(world.template, TEMPLATE)
    good = lay(world, "word-tools", "code")
    shut = lay(world, "shut-tools", "code")
    os.chmod(os.path.join(shut, "lobster.conf"), 0)
    try:
        code, out, err = world.conform("--all")
    finally:
        os.chmod(os.path.join(shut, "lobster.conf"), 0o644)
    assert (code, err) == (1, "")
    assert out == (f"word-tools (code): {good}\n  in line\n\n"
                   f"shut-tools: cannot be checked\n  {shut}/lobster.conf cannot be read (Permission denied): check "
                   "its permissions\n\n"
                   "2 projects: nothing to bring into line, 1 project that could not be checked.\n")


def test_a_folder_that_is_a_project_is_not_looked_into_for_more_projects(world):
    write_tree(world.template, TEMPLATE)
    outer = lay(world, "word-tools", "code", public=True)
    write_tree(outer, {"word-tools/lobster.conf": "KIND=code\nSELF=word-tools\n",      # a copy that strayed in
                       "word-tools/vendor/lobster.conf": "KIND=feeler\n"})
    nc = lay(world, "menus", "non-code", "word-tools")
    write_tree(nc, {"drafts/lobster.conf": "KIND=feeler\n"})
    code, out, err = world.conform("--all")
    assert (code, err) == (1, "")
    assert out == (f"menus (non-code): {nc}\n  in line\n"
                   f"word-tools (code): {outer}\n"
                   f"  missing: lobster.conf beside the checkout, not in it ({outer}/word-tools)\n"
                   "\n"
                   "2 projects: 1 thing to bring into line.\n")
