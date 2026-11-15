"""new-lobster --check-template on invented templates: every way listed, one fault at a time, --show, and
that the template is never written to. It runs no other program."""

import os

import pytest
from conftest import TEMPLATE, tree, write_tree

SOUND = dict(TEMPLATE, **{
    "common/version": "18 October 2026 (2)\n",
    "common/global-files": "RULES.md\nSTART-HERE.txt\ninbox/README.md\n",
    "common/sections/served-sister.md": "Serves its sister, {{REQUESTER}}.\n",
    "common/sections/served-any.md": "Serves any lobster project.\n",
    "common/sections/served-conductor.md": "Serves its conductor, {{REQUESTER}}.\n",
    "common/sections/backlog-yes.md": "Tickets from {{BACKLOG_PREFIX}}-001.\n",
    "common/sections/backlog-no.md": "No tickets here.\n",
    "non-code/START-HERE.txt": "Start {{NAME}}.\n",
    "non-code/RULES.md": ("Rules for {{NAME}}, template {{TEMPLATE_VERSION}}.\n{{> sections/backlog-{{BACKLOG}}.md}}\n"
                          "{{OTHER_CLAWS}}\n"),
    "code/RULES.md": ("Rules for {{TOOLS}}, template {{TEMPLATE_VERSION}}.\n{{> sections/served-{{SERVED}}.md}}\n"
                      "{{> sections/backlog-{{BACKLOG}}.md}}\n"),
    "code/.claude/settings.json": '{"env": {"TOOLS": "{{TOOLS}}"}}\n',
    "feeler/CLAUDE.md": "# {{NAME}}\n\n{{to fill: what this is for}}\n\n{{FEELER_CLAWS}}\n",
    "feeler/RULES.md": "Rules for the feeler {{NAME}}, template {{TEMPLATE_VERSION}}.\n",
    "feeler/START-HERE.txt": "Start {{NAME}}.\n",
    "feeler/DIARY.md": "# Diary of {{NAME}}, begun {{DATE}}\n",
})

CLEAN = (["non-code" + rest + ": 6 files, 1 to fill" for rest in (
              "", ",public", ",tickets", ",public,tickets", ",claws", ",public,claws", ",tickets,claws",
              ",public,tickets,claws")]
         + [kind + rest + f": {n} files, 0 to fill" for kind in ("code", "claw", "conductor-claw")
            for rest, n in (("", 10), (",public", 11), (",tickets", 10), (",public,tickets", 11))]
         + [f"feeler{rest}: 5 files, 1 to fill; does not get inbox/README.md" for rest in ("", ",claw", ",claws")])


def sound(world, **changes):
    files = dict(SOUND, **{k: v for k, v in changes.items() if v is not None})
    for gone in (k for k, v in changes.items() if v is None):
        del files[gone]
    for rel in list(tree(world.template)):
        os.remove(os.path.join(world.template, rel))
    write_tree(world.template, files)


def head(world):
    return (f"Template: {world.template}\nVersion: 18 October 2026 (2)\n"
            "Global files: RULES.md, START-HERE.txt, inbox/README.md\n")


def test_a_sound_template_lists_every_way_exits_0_and_writes_nothing(world):
    sound(world)
    before = (tree(world.home), tree(world.template))
    code, out, err = world.run("--check-template")
    assert (code, err) == (0, "")
    assert out == head(world) + "\n" + "".join(line + "\n" for line in CLEAN) + "\n23 ways: all render clean.\n"
    assert (tree(world.home), tree(world.template)) == before
    assert world.calls() == []


def lines_of(out):
    return out.split("\n\n")[1].splitlines()


@pytest.mark.parametrize("changes, bad, fault, last", [
    ({"feeler/CLAUDE.md": "# {{NAME}}\n{{> sections/feeler-note.md}}\n"},
     ["feeler", "feeler,claw", "feeler,claws"],
     "feeler/CLAUDE.md: the include sections/feeler-note.md is not in common/", "3 faults in 3 ways"),
    ({"common/sections/repo-public.md": "{{TOOLS}} is public, {{NOPE}}.\n"},
     [k + r for k in ("code", "claw", "conductor-claw") for r in (",public", ",public,tickets")],
     "code/CLAUDE.md: unknown placeholder {{NOPE}}", "6 faults in 6 ways"),
    ({"common/sections/backlog-yes.md": None},
     ["non-code" + r for r in (",tickets", ",public,tickets", ",tickets,claws", ",public,tickets,claws")],
     "non-code/RULES.md: the include sections/backlog-yes.md is not in common/", "10 faults in 10 ways"),
    ({"common/sections/backlog-no.md": None},
     ["non-code", "non-code,public", "non-code,claws", "non-code,public,claws"],
     "non-code/RULES.md: the include sections/backlog-no.md is not in common/", "10 faults in 10 ways"),
    ({"common/sections/served-conductor.md": None},
     ["conductor-claw" + r for r in ("", ",public", ",tickets", ",public,tickets")],
     "code/RULES.md: the include sections/served-conductor.md is not in common/", "4 faults in 4 ways"),
    ({"code/.claude/settings.json": '{"env": {"TOOLS": {{TOOLS}}}}\n'},
     [k + r for k in ("code", "claw", "conductor-claw") for r in ("", ",public", ",tickets", ",public,tickets")],
     "code/.claude/settings.json: not valid JSON once filled in", "12 faults in 12 ways"),
    ({"feeler/RULES.md": None, "feeler/START-HERE.txt": None, "feeler/CLAUDE.md": None, "feeler/DIARY.md": None},
     ["feeler", "feeler,claw", "feeler,claws"],
     "the template folder {template} has no feeler/ folder", "3 faults in 3 ways"),
])
def test_a_way_that_cannot_be_rendered_is_named_with_the_file_and_the_reason_and_the_exit_code_is_4(
        world, changes, bad, fault, last):
    sound(world, **changes)
    assert ("has no feeler/" in fault) == (not os.path.isdir(os.path.join(world.template, "feeler")))
    before = tree(world.template)
    code, out, err = world.run("--check-template")
    assert (code, err) == (4, "")
    said = lines_of(out)
    fault = fault.replace("{template}", world.template)
    for way in bad:
        at = said.index(f"{way}: cannot be rendered")
        assert said[at + 1] == f"  fault: {fault}"
    assert out.endswith(f"\n23 ways: {last}.\n")
    faulty = int(last.split()[0])
    assert sum(1 for line in said if line.startswith("  fault: ")) == faulty
    assert sum(1 for line in said if line in CLEAN) == 23 - faulty        # every other way is as it was
    assert tree(world.template) == before


def test_double_braces_left_in_a_rendered_file_are_a_fault_with_the_file_and_the_line(world):
    sound(world, **{"non-code/CLAUDE.md": "# {{NAME}}\n\n{{to fill: the purpose}}\nSee {{Name}} and {{> sections/rule.md}}\n"})
    code, out, err = world.run("--check-template")
    assert (code, err) == (4, "")
    said = lines_of(out)
    assert said[:2] == ["non-code: 6 files, 1 to fill",
                        "  fault: CLAUDE.md: {{ left in line 4: See {{Name}} and {{> sections/rule.md}}"]
    assert out.endswith("\n23 ways: 8 faults in 8 ways.\n")


def test_a_global_file_that_reads_differently_on_another_day_is_a_fault(world):
    sound(world, **{"code/RULES.md": "Rules for {{TOOLS}}, written {{DATE}}.\n"})
    code, out, err = world.run("--check-template")
    assert (code, err) == (4, "")
    said = lines_of(out)
    assert said[said.index("code: 10 files, 0 to fill") + 1] == (
        "  fault: RULES.md is a global file and reads differently on another day: use {{TEMPLATE_VERSION}} "
        "in it, not {{DATE}}")
    assert out.endswith("\n23 ways: 12 faults in 12 ways.\n")
    assert "feeler: 5 files, 1 to fill; does not get inbox/README.md" in said      # its DIARY.md may use the date


def test_a_global_file_that_one_kind_does_not_get_is_a_note_and_the_exit_code_stays_0(world):
    sound(world, **{"code/RULES.md": None})
    code, out, err = world.run("--check-template")
    assert (code, err) == (0, "")
    said = lines_of(out)
    assert "code: 9 files, 0 to fill; does not get RULES.md" in said
    assert "claw,public,tickets: 10 files, 0 to fill; does not get RULES.md" in said
    assert "non-code: 6 files, 1 to fill" in said
    assert out.endswith("\n23 ways: all render clean.\n")


def test_a_template_with_no_version_and_no_global_files_says_so_and_a_bad_list_is_a_fault_of_the_template(world):
    sound(world, **{"common/version": None, "common/global-files": None})
    code, out, err = world.run("--check-template")
    assert (code, err) == (0, "")
    assert out.startswith(f"Template: {world.template}\nVersion: none (the template has no common/version)\n"
                          "Global files: none\n\nnon-code: 6 files, 1 to fill\n")
    assert "feeler: 5 files, 1 to fill\n" in out
    sound(world, **{"common/global-files": "RULES.md\n../CLAUDE.md\n"})
    code, out, err = world.run("--check-template")
    assert (code, err) == (4, "")
    assert out.startswith(f"Template: {world.template}\nVersion: 18 October 2026 (2)\nGlobal files: none\n"
                          "  fault: common/global-files: ../CLAUDE.md is not a path inside a project\n\n")
    assert out.endswith("\n23 ways: 1 fault in the template itself.\n")


@pytest.mark.parametrize("way, rel, flags, name, half", [
    ("non-code,public,tickets,claws", "CLAUDE.md",
     ("--public", "--backlog", "--claws", "first-tools second-tools"), "example", "non-code"),
    ("non-code", "RULES.md", (), "example", "non-code"),
    ("code,public", "CLAUDE.md", ("--public",), "example", "code"),
    ("code,tickets", "RULES.md", ("--backlog",), "example", "code"),
    ("claw,public,tickets", "RULES.md", ("--claw", "--public", "--backlog"), "example-tools", "code"),
    ("claw", "example-tools.conf.example", ("--claw",), "example-tools", "code"),
    ("feeler,claws", "CLAUDE.md", ("--feeler", "--claws", "first-tools second-tools"), "example", "feeler"),
    ("feeler", "lobster.conf", ("--feeler",), "example", "feeler"),
])
def test_show_prints_exactly_what_render_into_would_write_for_that_file(world, tmp_path, way, rel, flags, name, half):
    sound(world)
    into = str(tmp_path / "into")
    code, _out, err = world.run("--render-into", into, *flags, name)
    assert (code, err) == (0, "")
    with open(os.path.join(into, half, rel), encoding="utf-8") as f:
        written = f.read()
    before = tree(world.template)
    assert world.run("--check-template", "--show", way, rel) == (0, written, "")
    assert tree(world.template) == before


def test_show_for_a_conductor_s_claw_names_the_conductor(world):
    sound(world)
    assert world.run("--check-template", "--show", "conductor-claw", "RULES.md") == (
        0, "Rules for example-tools, template 18 October 2026 (2).\nServes its conductor, `example`.\nNo tickets here.\n", "")


def test_show_refuses_a_way_or_a_file_that_is_not_there_and_a_way_that_cannot_be_rendered(world):
    sound(world, **{"common/sections/served-any.md": None})
    code, out, err = world.run("--check-template", "--show", "tools", "RULES.md")
    assert (code, out) == (2, "")
    assert err == ("new-lobster: there is no way called tools; the ways are: non-code, non-code,public, "
                   "non-code,tickets, non-code,public,tickets, non-code,claws, non-code,public,claws, "
                   "non-code,tickets,claws, non-code,public,tickets,claws, code, code,public, code,tickets, "
                   "code,public,tickets, claw, claw,public, claw,tickets, claw,public,tickets, conductor-claw, "
                   "conductor-claw,public, conductor-claw,tickets, conductor-claw,public,tickets, feeler, "
                   "feeler,claw, feeler,claws\n")
    assert world.run("--check-template", "--show", "feeler", "PLAN.md") == (
        2, "", ("new-lobster: the way feeler has no file PLAN.md; its files are: CLAUDE.md, DIARY.md, RULES.md, "
               "START-HERE.txt, lobster.conf\n"))
    assert world.run("--check-template", "--show", "claw", "RULES.md") == (
        4, "", ("new-lobster: the template cannot be used: code/RULES.md: the include sections/served-any.md is "
               "not in common/\n"))


def test_a_template_that_is_not_there_is_exit_4_and_template_names_another(world, tmp_path):
    other = str(tmp_path / "other template")
    assert world.run("--check-template", "--template", other) == (
        4, "", f"new-lobster: the template cannot be used: the template folder {other} is not there\n")
    write_tree(other, SOUND)
    code, out, err = world.run("--check-template", "--template", other)
    assert (code, err) == (0, "")
    assert out.startswith(f"Template: {other}\n") and out.endswith("\n23 ways: all render clean.\n")


def test_with_no_settings_file_the_usual_template_folder_is_looked_for(world):
    os.remove(world.conf)
    usual = os.path.join(world.home, "projects", "code", "bernstein-code", "templates", "lobster")
    assert world.run("--check-template") == (
        4, "", f"new-lobster: the template cannot be used: the template folder {usual} is not there\n")
    write_tree(usual, SOUND)
    assert world.run("--check-template")[0] == 0


def test_check_template_takes_no_project_and_no_other_flag_and_a_bad_settings_line_is_exit_2(world):
    sound(world)
    for argv, said in ((("--check-template", "example"), "unrecognized arguments: example"),
                       (("--check-template", "--dry-run"), "unrecognized arguments: --dry-run"),
                       (("--check-template", "--public"), "unrecognized arguments: --public"),
                       (("--check-template", "--show", "feeler"), "argument --show: expected 2 arguments")):
        assert world.run(*argv) == (2, "", f"new-lobster: {said} (new-lobster --help shows the form)\n")
    world.write_conf("EFFORT=extreme\n")
    assert world.run("--check-template") == (
        2, "", f"new-lobster: {world.conf}: line 7: EFFORT must be one of low, medium, high, xhigh, max\n")


def test_help_shows_the_check(world):
    code, out, err = world.run("--help")
    assert (code, err) == (0, "")
    assert "new-lobster --check-template [--template DIR] [--show WAY FILE]" in out


def test_a_template_file_that_is_not_utf8_is_a_fault_not_a_traceback(world):
    sound(world)
    with open(os.path.join(world.template, "feeler", "RULES.md"), "wb") as f:
        f.write(b"caf\xe9\n")
    code, out, err = world.run("--check-template")
    assert (code, err) == (4, "")
    assert "feeler: cannot be rendered\n  fault: a file in feeler/ or common/ is not plain UTF-8 text\n" in out
    assert out.endswith("\n23 ways: 3 faults in 3 ways.\n")
