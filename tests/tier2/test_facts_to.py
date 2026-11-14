"""--facts-to FILE: the commands that write in projects say what they did, for a notice (PLAN.md, Settled 162)."""

import json
import os

import pytest
from conftest import tree, write_tree
from test_drop_backlog import drop, unused
from test_notice import notice, sends
from test_set_conf import pair, setconf

WHEN = "18 October 2026, 09:40Z"


def read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_drop_backlog_writes_where_each_projects_backlog_went_and_a_notice_is_filled_from_it(world, tmp_path):
    nc = unused(world, "recipes", "non-code")
    tools = unused(world, "recipes-tools", "code")
    plain = world.project("menus", "non-code")                                 # keeps no tickets: nothing to say
    world.duty({"recipes": None, "recipes-tools": None, "menus": None})
    facts = str(tmp_path / "facts.json")
    code, out, err = drop(world, "--dry-run", "--facts-to", facts, "recipes", "recipes-tools", "menus")
    assert (code, err) == (0, "") and not os.path.exists(facts)
    assert out.endswith(f"Dry run: nothing was moved. The facts for a notice would be written to {facts}.\n")
    code, out, err = drop(world, "--facts-to", facts, "recipes", "recipes-tools", "menus")
    assert (code, err) == (0, "")
    assert out.endswith(f"The facts for a notice are in {facts}.\n")
    kept = "_to_delete/backlog-removed-2026-10-18-0940/backlog"
    assert read(facts) == {"recipes": {"KEPT": f"{nc}/{kept}", "WHEN": WHEN},
                           "recipes-tools": {"KEPT": f"{tools}/{kept}", "WHEN": WHEN}}
    write_tree(str(tmp_path), {"body.md": "{{PROJECT}}: moved on {{WHEN}} to {{KEPT}}.\n"})
    code, out, err = notice(world, "--subject", "Notice: Backlog", "--body", str(tmp_path / "body.md"), "--facts",
                            facts, "recipes", "recipes-tools")
    assert (code, err) == (0, "")
    assert [c["stdin"] for c in sends(world)] == [f"recipes: moved on {WHEN} to {nc}/{kept}.\n",
                                                  f"recipes-tools: moved on {WHEN} to {tools}/{kept}.\n"]
    assert tree(plain) == {"lobster.conf": tree(plain)["lobster.conf"], "START-HERE.txt": b"Start menus.\n"}


def test_set_conf_adds_what_it_changed_to_the_facts_already_there_and_nothing_when_nothing_changed(world, tmp_path):
    folder = pair(world)
    facts = str(tmp_path / "facts.json")
    write_tree(str(tmp_path), {"facts.json": '{"menus": {"KEPT": "/elsewhere"}}'})
    code, out, err = setconf(world, "--dry-run", "--facts-to", facts, "recipes", "MODEL=fable")
    assert (code, err) == (0, "") and read(facts) == {"menus": {"KEPT": "/elsewhere"}}
    assert out.endswith(f"The facts for a notice would be written to {facts}.\n")
    code, out, err = setconf(world, "--facts-to", facts, "recipes", "MODEL=fable")
    assert (code, err) == (0, "") and out.endswith(f"The facts for a notice are in {facts}.\n")
    kept = f"{folder}/_to_delete/before-conf-change-2026-10-18-0940/lobster.conf"
    assert read(facts) == {"menus": {"KEPT": "/elsewhere"},
                           "recipes": {"KEPT": kept, "KEY": "MODEL", "WAS": "MODEL=opus", "NOW": "MODEL=fable",
                                       "WHEN": WHEN}}
    before = read(facts)
    code, out, err = setconf(world, "--facts-to", facts, "recipes", "MODEL=fable")      # nothing to change
    assert (code, err) == (0, "") and read(facts) == before and "facts" not in out
    code, out, err = setconf(world, "--facts-to", facts, "recipes", "EFFORT=extreme")   # refused
    assert code == 3 and read(facts) == before
    os.makedirs(os.path.join(world.home, "models"))
    code, out, err = setconf(world, "--facts-to", facts, "recipes", "FOLDERS=~/models")  # a line that is added
    assert (code, err) == (0, "")
    assert read(facts)["recipes"] == {"KEPT": kept.replace("-0940", "-0940-2"), "KEY": "FOLDERS", "WAS": "",
                                      "NOW": "FOLDERS=~/models", "WHEN": WHEN}
    assert read(facts)["menus"] == {"KEPT": "/elsewhere"}


def test_conduct_start_writes_which_global_files_it_replaced_and_nothing_when_it_replaced_none(world, tmp_path):
    from test_conduct import split_claw
    folder = split_claw(world)
    facts = str(tmp_path / "facts.json")
    code, out, err = world.conduct("start", "recipes-tools", "--dry-run", "--facts-to", facts)
    assert (code, err) == (0, "") and not os.path.exists(facts)
    assert f"Would write the facts for a notice to {facts}.\n" in out
    code, out, err = world.conduct("start", "recipes-tools", "--facts-to", facts)
    assert (code, err) == (0, "") and f"The facts for a notice are in {facts}.\n" in out
    assert read(facts) == {"recipes-tools": {"KEPT": f"{folder}/_to_delete/before-global-update-2026-10-18-0940",
                                             "FILES": "RULES.md", "WHEN": WHEN}}
    os.remove(facts)
    code, out, err = world.conduct("start", "recipes-tools", "--again", "--facts-to", facts)   # nothing is behind now
    assert (code, err) == (0, "") and not os.path.exists(facts) and "facts" not in out


@pytest.mark.parametrize("command", ["drop-backlog", "set-conf", "conduct start"])
def test_a_file_that_is_not_a_facts_file_or_a_folder_that_is_not_there_is_exit_2_before_anything_is_done(
        world, tmp_path, command):
    from test_conduct import split_claw
    if command == "conduct start":
        folder = split_claw(world)
    elif command == "drop-backlog":
        folder = unused(world, "recipes-tools", "code")
        world.duty({"recipes-tools": None})
    else:
        pair(world)
        folder = os.path.join(world.code, "recipes-tools")
    before = tree(folder)
    notes = tmp_path / "notes.md"
    notes.write_text("Not facts.\n")
    for path, why in ((str(notes), (f"--facts-to {notes} is there already and is not a facts file ({notes} is not "
                                   "JSON)")),
                      (str(tmp_path / "gone" / "f.json"), (f"--facts-to {tmp_path}/gone/f.json: the folder {tmp_path}/gone "
                                                          "is not there: make it first"))):
        if command == "conduct start":
            code, out, err = world.conduct("start", "recipes-tools", "--facts-to", path)
            name = "conduct"
        elif command == "drop-backlog":
            code, out, err = drop(world, "--facts-to", path, "recipes-tools")
            name = "drop-backlog"
        else:
            code, out, err = setconf(world, "--facts-to", path, "recipes-tools", "MODEL=fable")
            name = "set-conf"
        assert (code, out) == (2, "") and err.startswith(f"{name}: {why}")
    assert tree(folder) == before and notes.read_text() == "Not facts.\n" and world.calls() == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes anywhere")
def test_facts_that_cannot_be_written_after_the_change_are_exit_4_saying_the_change_was_made(world, tmp_path):
    folder = pair(world)
    shut = tmp_path / "shut"
    shut.mkdir()
    os.chmod(shut, 0o555)
    try:
        code, out, err = setconf(world, "--facts-to", str(shut / "f.json"), "recipes", "MODEL=fable")
    finally:
        os.chmod(shut, 0o755)
    assert code == 4 and "  now: MODEL=fable\n" in out
    assert err == (f"set-conf: the change was made, but the facts for a notice could not be written to {shut}/f.json "
                   "(Permission denied)\n")
    assert b"MODEL=fable" in tree(folder)["lobster.conf"]


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes anywhere")
def test_drop_backlog_and_conduct_start_say_so_too_when_the_facts_cannot_be_written(world, tmp_path):
    from test_conduct import opened, sent, split_claw
    claw = split_claw(world)
    nc = unused(world, "menus", "non-code")
    world.duty({"recipes-tools": None, "menus": None})
    shut = tmp_path / "shut"
    shut.mkdir()
    os.chmod(shut, 0o555)
    try:
        code, out, err = drop(world, "--facts-to", str(shut / "f.json"), "menus")
        started = world.conduct("start", "recipes-tools", "--facts-to", str(shut / "f.json"))
    finally:
        os.chmod(shut, 0o755)
    assert code == 4 and out.startswith(f"menus: moved {nc}/backlog to ")
    assert err == ("drop-backlog: the change was made, but the facts for a notice could not be written to "
                   f"{shut}/f.json (Permission denied). Moved: menus\n")
    assert started[0] == 4 and started[1].startswith(f"Brought up to date in {claw}: RULES.md")
    assert started[2] == ("conduct: the change was made, but the facts for a notice could not be written to "
                          f"{shut}/f.json (Permission denied); nothing was sent or opened\n")
    assert sent(world) == [] and opened(world) == []
