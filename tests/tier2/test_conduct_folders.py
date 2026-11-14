"""FOLDERS in lobster.conf: further folders a project's session needs connected (PLAN.md, Settled 154)."""

import os
from urllib.parse import parse_qsl, urlsplit

import pytest
from conftest import write_tree


def connected(link):
    """The folders a cowork link connects, in order."""
    return [value for key, value in parse_qsl(urlsplit(link).query) if key == "folder"]


def needing(world, line, kind="non-code"):
    """A project whose lobster.conf has this FOLDERS line, with nobody on duty."""
    if kind == "feeler":
        folder = os.path.join(world.non_code, "recipes")
        write_tree(folder, {"lobster.conf": "KIND=feeler\nSELF=recipes\nSISTER=\nCLAWS=\nMODEL=opus\nEFFORT=high\n",
                            "START-HERE.txt": "Start recipes.\n"})
    else:
        folder = world.project("recipes", "non-code")
        world.project("recipes-tools", "code")
    with open(os.path.join(folder, "lobster.conf"), "a") as f:
        f.write(line + "\n")
    world.duty({"recipes": None, "recipes-tools": None})
    return folder


def calls(world, verb):
    return [c for c in world.calls() if c["args"][:1] == [verb] or c["prog"] == verb]


@pytest.mark.parametrize("kind", ["non-code", "feeler"])
def test_start_connects_the_further_folders_a_projects_settings_name_after_the_usual_ones(world, kind):
    models = os.path.join(world.home, "models", "kokoro voices")
    odd = os.path.join(world.home, "it's $HOME “é”")
    os.makedirs(models)
    os.makedirs(odd)
    folder = needing(world, "FOLDERS= ~/models/kokoro voices : " + odd + ":", kind)
    usual = [folder, world.mail] + ([os.path.join(world.code, "recipes-tools")] if kind == "non-code" else []) + [world.bin]
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "")
    link = next(line.strip() for line in out.splitlines() if line.strip().startswith("claude://"))
    assert connected(link) == usual + [models, odd]
    assert f"Would also connect, from FOLDERS in its lobster.conf: {models}, {odd}\n" in out
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "")
    assert connected(calls(world, "open")[0]["args"][0]) == usual + [models, odd]
    assert f"Also connected, from FOLDERS in its lobster.conf: {models}, {odd}\n" in out


@pytest.mark.parametrize("line", ["FOLDERS=", "FOLDERS= : ", "CLAWS="])
def test_a_project_that_names_no_further_folders_starts_as_before(world, line):
    folder = needing(world, line)
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "") and "FOLDERS" not in out
    assert connected(calls(world, "open")[0]["args"][0]) == [
        folder, world.mail, os.path.join(world.code, "recipes-tools"), world.bin]


def test_start_refuses_a_further_folder_that_is_not_a_full_path_not_there_or_not_a_folder(world):
    folder = needing(world, "FOLDERS=models/kokoro")
    conf = os.path.join(folder, "lobster.conf")
    absent = os.path.join(world.home, "models", "kokoro")
    a_file = os.path.join(world.home, "notes.txt")
    with open(a_file, "w") as f:
        f.write("x\n")
    for line, said in (
        ("FOLDERS=models/kokoro", "the folder models/kokoro in FOLDERS, which is not a full path: start it with / or ~/"),
        ("FOLDERS=~other/x", "the folder ~other/x in FOLDERS, which is not a full path: start it with / or ~/"),
        ("FOLDERS=~/models/kokoro", (f"the folder {absent} in FOLDERS, which is not a folder on this Mac: make it, "
                                     "or correct the line")),
        (f"FOLDERS={world.home}:{a_file}", (f"the folder {a_file} in FOLDERS, which is not a folder on this Mac: "
                                            "make it, or correct the line")),
    ):
        with open(conf, "a") as f:
            f.write(line + "\n")
        for argv in (("start", "recipes"), ("start", "--dry-run", "recipes")):
            code, out, err = world.conduct(*argv)
            assert (code, out, err) == (3, "", f"conduct: {conf} names {said}\n")
    assert calls(world, "send") == [] and calls(world, "open") == []


def test_start_refuses_two_connected_folders_a_session_would_see_under_one_name(world):
    folder = needing(world, "FOLDERS=")
    conf = os.path.join(folder, "lobster.conf")
    tools = os.path.join(world.code, "recipes-tools")
    for clash, other in ((os.path.join(world.home, "elsewhere", "recipes-tools"), tools),
                         (os.path.join(world.home, "elsewhere", "recipes"), folder)):
        os.makedirs(clash)
        with open(conf, "a") as f:
            f.write(f"FOLDERS={clash}\n")
        code, _out, err = world.conduct("start", "recipes")
        name = os.path.basename(clash)
        assert code == 3 and err == (f"conduct: {conf} names the folder {clash} in FOLDERS, but {other} is connected "
                                     f"too: a session sees each as ~/mnt/{name}, so their last names must differ\n")
    twice = os.path.join(world.home, "a", "voices"), os.path.join(world.home, "b", "voices")
    for path in twice:
        os.makedirs(path)
    with open(conf, "a") as f:
        f.write(f"FOLDERS={twice[0]}:{twice[1]}\n")
    code, _out, err = world.conduct("start", "recipes")
    assert code == 3 and f"names the folder {twice[1]} in FOLDERS, but {twice[0]} is connected too" in err
    assert calls(world, "send") == [] and calls(world, "open") == []


def test_a_tools_project_cannot_name_further_folders_its_session_opens_in_one(world):
    folder = world.project("recipes-tools", "code")
    with open(os.path.join(folder, "lobster.conf"), "a") as f:
        f.write(f"FOLDERS={world.home}\n")
    world.duty({"recipes-tools": None})
    code, _out, err = world.conduct("start", "recipes-tools")
    assert code == 3 and err == (f"conduct: {folder}/lobster.conf says KIND=code and FOLDERS={world.home}: a Claude "
                                 "Code session opens in one folder, so only a non-code project or a feeler can name "
                                 "further folders\n")
    assert calls(world, "send") == [] and calls(world, "open") == []


def test_status_says_a_project_with_a_missing_further_folder_cannot_start(world):
    folder = needing(world, "FOLDERS=~/models/kokoro")
    code, out, _err = world.conduct("status")
    assert code == 0
    assert (f"cannot start: {folder}/lobster.conf names the folder {world.home}/models/kokoro in FOLDERS, which is "
            "not a folder on this Mac") in out


def test_finish_still_finds_a_feeler_whose_further_folder_is_named_from_the_home_folder(world):
    os.makedirs(os.path.join(world.home, "models", "kokoro"))
    needing(world, "FOLDERS=~/models/kokoro", "feeler")
    world.duty({"recipes": "fresh"})
    code, out, err = world.conduct("finish", "recipes")
    assert (code, err) == (0, "") and "Sent the Finish message to recipes." in out
