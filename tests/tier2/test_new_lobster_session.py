"""new-lobster --session code: a pair whose non-code project runs as a Claude Code session on the Mac from its
first day (PLAN.md, "A ganglion on the Mac: SESSION=code", Settled 168)."""

import os

import pytest
from conftest import tree, write_tree

ON_THE_MAC = "  Its session is a Claude Code one on the Mac (SESSION=code in its lobster.conf).\n"


def for_both(world):
    """A template that names the session in lobster.conf and says one thing to each kind of session."""
    write_tree(world.template, {
        "common/lobster.conf": "KIND={{KIND}}\nSISTER={{SISTER}}\nMODEL={{MODEL_SETTING}}\nEFFORT={{EFFORT}}\nSESSION={{SESSION}}\n",
        "common/sections/where-cowork.md": "Your claws are under ~/mnt:\n{{CLAW_MOUNTS}}\n",
        "common/sections/where-code.md": "Your claws are on the Mac:\n{{CLAW_MOUNTS}}\n",
        "non-code/START-HERE.txt": "Start {{NAME}}.\n{{> sections/where-{{SESSION}}.md}}\n"})


def made(world):
    return os.path.join(world.non_code, "recipes"), os.path.join(world.code, "recipes-tools")


def test_a_pair_made_for_the_mac_says_so_in_its_settings_and_is_rendered_with_real_paths(world):
    for_both(world)
    code, out, err = world.run("recipes", "--session", "code")
    assert (code, err) == (0, "")
    nc, tools = made(world)
    files = tree(nc)
    assert files["lobster.conf"] == b"KIND=non-code\nSISTER=recipes-tools\nMODEL=opus\nEFFORT=high\nSESSION=code\n"
    assert files["START-HERE.txt"] == (
        b"Start recipes.\nYour claws are on the Mac:\n| `~/projects/code/recipes-tools` | the home claw, "
        b"`recipes-tools`: **read and run only**; never write, commit, install or make a `.venv` in it |\n")
    assert tree(tools)["lobster.conf"] == b"KIND=code\nSISTER=recipes\nMODEL=opus\nEFFORT=high\nSESSION=\n"
    assert out.startswith(f"Made recipes: {nc}\n{ON_THE_MAC}Made recipes-tools: {tools}\n")
    world.duty({"recipes": None, "recipes-tools": None})
    code, shown, err = world.conduct("start", "--dry-run", "recipes")        # and conduct takes it as one
    assert (code, err) == (0, "") and "claude://code/new?" in shown
    code, shown, err = world.conduct("start", "--dry-run", "recipes-tools")
    assert (code, err) == (0, "") and "claude://code/new?" in shown


@pytest.mark.parametrize("flags", [(), ("--session", "cowork")])
def test_a_pair_made_without_the_flag_or_for_cowork_is_as_ever(world, flags):
    for_both(world)
    code, out, err = world.run("recipes", *flags)
    assert (code, err) == (0, "")
    nc, tools = made(world)
    assert tree(nc)["lobster.conf"] == b"KIND=non-code\nSISTER=recipes-tools\nMODEL=opus\nEFFORT=high\nSESSION=cowork\n"
    assert tree(nc)["START-HERE.txt"].startswith(b"Start recipes.\nYour claws are under ~/mnt:\n| `~/mnt/recipes-tools` |")
    assert out.startswith(f"Made recipes: {nc}\nMade recipes-tools: {tools}\n") and "SESSION" not in out


def test_with_a_template_that_never_names_the_session_the_flag_changes_nothing_but_cowork_and_none(world):
    plain = world.run("--dry-run", "recipes")
    assert world.run("--dry-run", "recipes", "--session", "cowork") == plain
    assert plain[0] == 0 and "SESSION" not in plain[1]


def test_the_dry_run_says_the_session_will_be_on_the_mac_and_makes_nothing(world):
    for_both(world)
    plain = world.run("--dry-run", "recipes")
    code, out, err = world.run("--dry-run", "recipes", "--session", "code")
    assert (code, err) == (0, "")
    nc = made(world)[0]
    assert out == plain[1].replace(f"Make recipes: {nc}\n", f"Make recipes: {nc}\n" + ON_THE_MAC.replace(
        "Its session is", "Its session would be"))
    assert "Its session would be a Claude Code one on the Mac" in out
    assert os.listdir(world.non_code) == [] and os.listdir(world.code) == []


def test_a_template_whose_settings_cannot_say_code_stops_the_run_before_anything_is_made(world):
    for argv in (("recipes", "--session", "code"), ("--dry-run", "recipes", "--session", "code"),
                 ("--render-into", os.path.join(world.home, "rendered"), "recipes", "--session", "code")):
        code, out, err = world.run(*argv)
        assert (code, out) == (4, "")
        assert err == ("new-lobster: the template cannot be used: the lobster.conf it renders for a non-code project "
                       "does not say SESSION=code, so a project made from it would open in Claude Cowork: add the "
                       "line SESSION={{SESSION}} to its common/lobster.conf; nothing was made\n")
    assert os.listdir(world.non_code) == [] and os.listdir(world.code) == []
    assert not os.path.exists(os.path.join(world.home, "rendered"))
    assert [c for c in world.calls() if c["args"][:1] != ["duty"]] == []


@pytest.mark.parametrize("argv, said", [
    (("recipes", "--session", "mac"), "--session must be cowork or code, not mac"),
    (("recipes", "--session", "Code"), "--session must be cowork or code, not Code"),
    (("recipes", "--session", ""), "--session must be cowork or code, not an empty value"),
    (("word-tools", "--claw", "--session", "code"),
     "--session cannot be used with --claw: a tools project always runs in Claude Code"),
    (("word-tools", "--claw", "--session", "cowork"),
     "--session cannot be used with --claw: a tools project always runs in Claude Code"),
    (("agents", "--feeler", "--session", "code"),
     "--session cannot be used with --feeler: a feeler runs in Claude Cowork"),
    (("recipes", "--session"), "argument --session: expected one argument"),
])
def test_a_session_that_is_not_known_or_not_for_this_kind_of_project_is_exit_2_and_nothing_is_made(world, argv, said):
    for_both(world)
    code, out, err = world.run(*argv)
    assert (code, out, err) == (2, "", f"new-lobster: {said} (new-lobster --help shows the form)\n")
    assert os.listdir(world.non_code) == [] and os.listdir(world.code) == [] and world.calls() == []


def test_help_names_the_flag(world):
    code, out, err = world.run("--help")
    assert (code, err) == (0, "")
    assert "--session" in out and "Claude Code session on the Mac" in " ".join(out.split())


def test_render_into_renders_an_existing_pair_for_the_mac_with_each_claw_where_it_is(world):
    for_both(world)
    world.project("video-tools", "code", public=True, under="video", sister="")
    out_dir = os.path.join(world.home, "rendered")
    code, out, err = world.run("--render-into", out_dir, "recipes", "--session", "code", "--claws",
                               "video-tools word-tools")
    assert (code, err) == (0, "")
    files = tree(out_dir)
    assert files["non-code/lobster.conf"] == b"KIND=non-code\nSISTER=recipes-tools\nMODEL=opus\nEFFORT=high\nSESSION=code\n"
    assert files["non-code/START-HERE.txt"].decode() == (
        "Start recipes.\nYour claws are on the Mac:\n| `~/projects/code/recipes-tools` | the home claw, "
        "`recipes-tools`: **read and run only**; never write, commit, install or make a `.venv` in it |\n"
        "| `~/projects/code/video/video-tools-code/video-tools` | the claw `video-tools`: read and run only, as above |\n"
        "| `~/projects/code/word-tools` | the claw `word-tools`: read and run only, as above |\n")
    assert files["code/lobster.conf"] == b"KIND=code\nSISTER=recipes\nMODEL=opus\nEFFORT=high\nSESSION=\n"
    other = os.path.join(world.home, "rendered 2")
    code, _out, err = world.run("--render-into", other, "recipes", "--claws", "video-tools word-tools")
    assert (code, err) == (0, "")
    assert tree(other)["non-code/START-HERE.txt"].startswith(b"Start recipes.\nYour claws are under ~/mnt:\n")
    assert {rel: data for rel, data in tree(other).items() if not rel.startswith("non-code/")} == {
        rel: data for rel, data in files.items() if not rel.startswith("non-code/")}
