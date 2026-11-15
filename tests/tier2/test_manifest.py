"""manifest save and compare on invented projects: what is recorded, what is said to differ, what is refused,
and that nothing but the one FILE is ever written. It runs no other program, so no stub is called."""

import hashlib
import io
import json
import os
import shutil
import unicodedata

import pytest
from conftest import NOW, tree, write_tree

from bernstein import manifest


def run(world, *argv):
    out, err = io.StringIO(), io.StringIO()
    env = {"PATH": world.bin + os.pathsep + "/usr/bin:/bin", "HOME": world.home, "BERNSTEIN_CONF": world.conf}
    code = manifest.main(list(argv), env=env, now=NOW, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def entry(text):
    return {"size": len(text.encode("utf-8")), "sha256": sha(text)}


def a_pair(world):
    """A non-code project and a public tools project, with things that are left out and things that are not."""
    nc = world.project("recipes", "non-code")
    write_tree(nc, {"CLAUDE.md": "rules\n", "backlog/config.yml": 'task_prefix: "re"\n',
                    "backlog/tasks/re-001.md": "a task\n", "inbox/sample.dat": "real data\n",
                    "_to_delete/old.md": "old\n", ".git/HEAD": "ref\n", ".DS_Store": "finder\n",
                    "deep/.DS_Store": "finder\n", "deep/__pycache__/x.pyc": "cache\n"})
    outer = world.project("recipes-tools", "code", public=True)
    write_tree(outer, {"DIARY.md": "a diary\n", ".git/HEAD": "ref\n", "recipes-tools/.git/HEAD": "ref\n",
                       "recipes-tools/code.py": "pass\n", "recipes-tools/.venv/bin/pip": "x\n",
                       "recipes-tools/.pytest_cache/v": "c\n", "recipes-tools/.ruff_cache/v": "c\n",
                       "recipes-tools/tests/__pycache__/t.pyc": "c\n", "recipes-tools/tests/test_a.py": "t\n"})
    return nc, outer


def saved(world, *projects, name="before.json"):
    path = os.path.join(world.home, name)
    code, _out, err = run(world, "save", path, *projects)
    assert (code, err) == (0, ""), err
    return path


def test_save_records_every_file_with_its_size_and_checksum_and_leaves_out_git_venv_and_caches(world):
    nc, outer = a_pair(world)
    before = tree(world.home)
    path = os.path.join(world.home, "before.json")
    code, out, err = run(world, "save", path, "recipes", "recipes-tools")
    assert (code, err) == (0, "")
    assert out == (f"recipes: 7 files in {nc}\nrecipes-tools: 5 files in {outer}\n"
                   f"Saved to {path}. Nothing else was written.\n")
    with open(path, encoding="utf-8") as f:
        record = json.load(f)
    assert record == {
        "manifest": 1, "saved": "2026-10-18T09:40:00Z",
        "left_out": [".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", ".DS_Store"],
        "projects": [
            {"name": "recipes", "folder": nc, "files": {
                "CLAUDE.md": entry("rules\n"), "START-HERE.txt": entry("Start recipes.\n"),
                "_to_delete/old.md": entry("old\n"), "backlog/config.yml": entry('task_prefix: "re"\n'),
                "backlog/tasks/re-001.md": entry("a task\n"), "inbox/sample.dat": entry("real data\n"),
                "lobster.conf": entry("KIND=non-code\nSELF=recipes\nSISTER=recipes-tools\nMODEL=opus\nEFFORT=high\n")}},
            {"name": "recipes-tools", "folder": outer, "files": {
                "DIARY.md": entry("a diary\n"), "START-HERE.txt": entry("Start recipes-tools.\n"),
                "lobster.conf": entry("KIND=code\nSELF=recipes-tools\nSISTER=recipes\nMODEL=opus\nEFFORT=high\n"),
                "recipes-tools/code.py": entry("pass\n"), "recipes-tools/tests/test_a.py": entry("t\n")}}]}
    after = tree(world.home)
    assert after.pop("before.json") and after == before       # the one FILE, and nothing else
    assert world.calls() == []


@pytest.mark.parametrize("change, said, code", [
    (lambda w, p: None, "the project recipes is named twice", 2),
    (lambda w, p: write_tree(w.home, {"before.json": "kept\n"}),
     "{path} is there already: manifest save never writes over a file; give another name, or move it away", 2),
    (lambda w, p: shutil.rmtree(os.path.join(w.non_code, "recipes")),
     "no project recipes in {nc} or {code}, or a folder directly inside either", 3),
    (lambda w, p: (shutil.rmtree(os.path.join(w.non_code, "recipes")), w.project("recipes", "non-code", under="old"),
                   w.project("recipes", "non-code", under="older")),
     "recipes is in two places, {nc}/old/recipes and {nc}/older/recipes: keep one, or rename the other", 3),
    (lambda w, p: w.write_conf("EFFORT=extreme\n"),
     "{conf}: line 7: EFFORT must be one of low, medium, high, xhigh, max", 2),
])
def test_save_with_a_fault_writes_no_file_and_says_which(world, change, said, code):
    a_pair(world)
    path = os.path.join(world.home, "before.json")
    change(world, path)
    before = tree(world.home)
    twice = ["recipes"] if "twice" in said else []
    assert run(world, "save", path, "recipes", "recipes-tools", *twice) == (
        code, "", "manifest: " + said.format(path=path, nc=world.non_code, code=world.code, conf=world.conf)
        + "; nothing was saved\n")
    assert tree(world.home) == before


def test_save_refuses_a_file_inside_a_project_or_in_a_folder_that_is_not_there_and_a_name_that_is_a_path(world):
    nc, _outer = a_pair(world)
    inside = os.path.join(nc, "inbox", "before.json")
    assert run(world, "save", inside, "recipes") == (
        2, "", (f"manifest: {inside} is inside the project recipes ({nc}): keep the record outside the projects it "
               "is of; nothing was saved\n"))
    nowhere = os.path.join(world.home, "no such folder", "before.json")
    assert run(world, "save", nowhere, "recipes") == (
        2, "", f"manifest: the folder {os.path.dirname(nowhere)} is not there; nothing was saved\n")
    for name in ("../recipes", "old/recipes", ".", ""):
        assert run(world, "save", os.path.join(world.home, "b.json"), name) == (
            2, "", f"manifest: {name!r} is not a project's name; nothing was saved\n")
    assert not os.path.exists(inside) and not os.path.exists(os.path.join(world.home, "b.json"))


def test_a_file_that_cannot_be_written_is_said_and_with_no_settings_file_the_usual_folders_are_used(world):
    nc, _outer = a_pair(world)
    shut = os.path.join(world.home, "shut")
    os.makedirs(shut)
    os.chmod(shut, 0o555)
    path = os.path.join(shut, "before.json")
    try:
        assert run(world, "save", path, "recipes") == (
            2, "", f"manifest: {path} cannot be written (Permission denied); nothing was saved\n")
    finally:
        os.chmod(shut, 0o755)
    os.remove(world.conf)               # no settings file: ~/projects/non-code and ~/projects/code, under HOME
    path = os.path.join(world.home, "before.json")
    assert run(world, "save", path, "recipes") == (
        0, f"recipes: 7 files in {nc}\nSaved to {path}. Nothing else was written.\n", "")


def test_a_file_or_folder_that_cannot_be_read_is_exit_4_and_nothing_is_saved(world):
    nc, _outer = a_pair(world)
    path = os.path.join(world.home, "before.json")
    for shut in (os.path.join(nc, "CLAUDE.md"), os.path.join(nc, "backlog", "tasks")):
        mode = os.stat(shut).st_mode
        os.chmod(shut, 0)
        try:
            assert run(world, "save", path, "recipes") == (
                4, "", (f"manifest: {shut} cannot be read (Permission denied): check its permissions; nothing "
                       "was saved\n"))
        finally:
            os.chmod(shut, mode)
        assert not os.path.exists(path)


def test_a_link_is_recorded_as_a_link_and_never_followed_and_a_pipe_as_special(world, tmp_path):
    nc = world.project("recipes", "non-code")
    outside = tmp_path / "outside"
    write_tree(str(outside), {"secret.md": "not the project's\n", "more/deep.md": "nor this\n"})
    os.symlink(str(outside), os.path.join(nc, "linked-folder"))
    os.symlink(str(outside / "secret.md"), os.path.join(nc, "linked-file"))
    os.symlink("nowhere/at/all", os.path.join(nc, "broken"))
    os.symlink(str(outside), os.path.join(nc, ".venv"))                # left out by name, link or not
    os.mkfifo(os.path.join(nc, "pipe"))
    with open(saved(world, "recipes"), encoding="utf-8") as f:
        files = json.load(f)["projects"][0]["files"]
    assert files == {"START-HERE.txt": entry("Start recipes.\n"),
                     "lobster.conf": entry("KIND=non-code\nSELF=recipes\nSISTER=recipes-tools\nMODEL=opus\nEFFORT=high\n"),
                     "broken": {"link": "nowhere/at/all"}, "linked-file": {"link": str(outside / "secret.md")},
                     "linked-folder": {"link": str(outside)}, "pipe": {"special": True}}


def test_a_very_large_file_is_read_in_pieces(world, monkeypatch):
    nc = world.project("recipes", "non-code")
    data = (b"0123456789abcdef" * 4096) * 40 + b"tail"          # 2.5 MiB and four bytes: three pieces
    with open(os.path.join(nc, "big.bin"), "wb") as f:
        f.write(data)
    sizes = []
    real_open = open

    class Counting(io.BufferedReader):
        def read(self, n=-1):
            sizes.append(n)
            return super().read(n)

    def counting_open(path, mode="r", *args, **kwargs):
        if mode == "rb" and str(path).endswith("big.bin"):
            return Counting(io.FileIO(path))
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", counting_open)
    with real_open(saved(world, "recipes"), encoding="utf-8") as f:
        files = json.load(f)["projects"][0]["files"]
    assert files["big.bin"] == {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    assert sizes == [1 << 20] * 4          # three pieces and the empty read that ends it: never the whole file


ODD = ['it\'s "quoted".md', "back\\slash $HOME `x`.md", "two  spaces .md", unicodedata.normalize("NFC", "café.md"),
       unicodedata.normalize("NFD", "naïve.md"), "日本/語.md", "</script>.md"]


def test_names_with_spaces_quotes_and_accents_in_both_forms_are_recorded_and_compare_as_no_difference(world):
    nc = world.project("recipes", "non-code")
    write_tree(nc, {name: f"{i}\n" for i, name in enumerate(ODD)})
    path = saved(world, "recipes")
    with open(path, encoding="utf-8") as f:
        files = json.load(f)["projects"][0]["files"]
    on_disk = {os.path.relpath(os.path.join(here, n), nc) for here, _, names in os.walk(nc) for n in names}
    assert set(files) == on_disk and len(files) == len(ODD) + 2
    assert {unicodedata.normalize("NFC", name) for name in files} >= {unicodedata.normalize("NFC", n) for n in ODD}
    assert run(world, "compare", path) == (
        0, f"recipes: no difference ({len(ODD) + 2} files)\nNo difference in 1 project since 2026-10-18T09:40:00Z.\n", "")


def test_compare_says_no_difference_when_nothing_changed_or_only_a_file_s_time_did(world):
    nc, _outer = a_pair(world)
    path = saved(world, "recipes", "recipes-tools")
    os.utime(os.path.join(nc, "CLAUDE.md"), (1, 1))
    write_tree(nc, {".git/index": "git's own\n", "deep/__pycache__/y.pyc": "new cache\n", ".DS_Store": "moved window\n"})
    before = tree(world.home)
    assert run(world, "compare", path) == (
        0, ("recipes: no difference (7 files)\nrecipes-tools: no difference (5 files)\n"
           "No difference in 2 projects since 2026-10-18T09:40:00Z.\n"), "")
    assert tree(world.home) == before
    assert world.calls() == []


def change_things(nc, outer):
    """What a run like drop-backlog does to recipes, and four other changes to recipes-tools."""
    kept = os.path.join(nc, "_to_delete", "backlog-removed-2026-10-18")
    os.makedirs(kept)
    os.rename(os.path.join(nc, "backlog"), os.path.join(kept, "backlog"))
    write_tree(outer, {"DIARY.md": "", "recipes-tools/new.py": "new\n"})
    os.remove(os.path.join(outer, "recipes-tools", "code.py"))
    os.remove(os.path.join(outer, "START-HERE.txt"))
    os.symlink("DIARY.md", os.path.join(outer, "START-HERE.txt"))


def test_compare_prints_exactly_what_was_changed_moved_added_and_gone_and_exits_1(world):
    nc, outer = a_pair(world)
    path = saved(world, "recipes", "recipes-tools")
    change_things(nc, outer)
    before = tree(world.home)
    assert run(world, "compare", path) == (
        1, ("recipes: 2 differences\n"
           "  moved:   backlog/config.yml -> _to_delete/backlog-removed-2026-10-18/backlog/config.yml\n"
           "  moved:   backlog/tasks/re-001.md -> _to_delete/backlog-removed-2026-10-18/backlog/tasks/re-001.md\n"
           "recipes-tools: 4 differences\n"
           "  changed: DIARY.md\n"
           "  changed: START-HERE.txt\n"
           "  added:   recipes-tools/new.py\n"
           "  gone:    recipes-tools/code.py\n"
           "6 differences in 2 of 2 projects since 2026-10-18T09:40:00Z.\n"), "")
    assert tree(world.home) == before


def test_expect_only_is_a_plain_yes_for_a_move_into_to_delete_and_a_no_when_one_other_file_also_changed(world):
    nc, _outer = a_pair(world)
    path = saved(world, "recipes")
    kept = os.path.join(nc, "_to_delete", "backlog-removed")
    os.makedirs(kept)
    os.rename(os.path.join(nc, "backlog"), os.path.join(kept, "backlog"))
    moved = ("recipes: 2 differences\n"
             "  moved:   backlog/config.yml -> _to_delete/backlog-removed/backlog/config.yml\n"
             "  moved:   backlog/tasks/re-001.md -> _to_delete/backlog-removed/backlog/tasks/re-001.md\n")
    assert run(world, "compare", path, "--expect-only", "_to_delete/*", "--expect-only", "backlog/*") == (
        0, moved + "2 differences in 1 of 1 project since 2026-10-18T09:40:00Z.\n"
                   "Every difference is at an expected path (_to_delete/*, backlog/*).\n", "")
    assert run(world, "compare", path, "--expect-only", "_to_delete/*")[0] == 1      # a move must fit at both ends
    write_tree(nc, {"CLAUDE.md": "emptied by mistake\n"})
    assert run(world, "compare", "--expect-only", "_to_delete/*", "--expect-only", "backlog/*", path) == (
        1, "recipes: 3 differences\n  changed: CLAUDE.md\n" + moved.split("\n", 1)[1]
           + "3 differences in 1 of 1 project since 2026-10-18T09:40:00Z.\n"
             "Not expected (outside _to_delete/*, backlog/*):\n  recipes: changed: CLAUDE.md\n", "")


def test_expect_only_with_no_difference_is_exit_0(world):
    a_pair(world)
    path = saved(world, "recipes")
    assert run(world, "compare", path, "--expect-only", "nothing/*") == (
        0, "recipes: no difference (7 files)\nNo difference in 1 project since 2026-10-18T09:40:00Z.\n", "")


@pytest.mark.parametrize("text", ["not json", "[]", '{"manifest": 2, "saved": "x", "projects": []}',
                                  '{"manifest": 1, "saved": "x", "projects": [{"name": "recipes"}]}',
                                  '{"manifest": 1, "saved": "x", "projects": [{"name": "r", "folder": "/x", "files": []}]}',
                                  '{"manifest": 1, "saved": 3, "projects": []}'])
def test_compare_refuses_a_file_that_is_not_a_manifest(world, text):
    path = os.path.join(world.home, "odd.json")
    with open(path, "w") as f:
        f.write(text)
    assert run(world, "compare", path) == (2, "", f"manifest: {path} is not a record that manifest save wrote\n")


def test_compare_refuses_a_file_that_is_not_there_a_project_that_has_gone_and_one_that_cannot_be_read(world):
    nc, _outer = a_pair(world)
    missing = os.path.join(world.home, "none.json")
    assert run(world, "compare", missing) == (
        2, "", f"manifest: {missing} cannot be read (No such file or directory)\n")
    path = saved(world, "recipes")
    shut = os.path.join(nc, "inbox")
    os.chmod(shut, 0)
    try:
        assert run(world, "compare", path) == (
            4, "", f"manifest: {shut} cannot be read (Permission denied): check its permissions\n")
    finally:
        os.chmod(shut, 0o755)
    shutil.rmtree(nc)
    assert run(world, "compare", path) == (
        3, "", f"manifest: the project recipes is no longer at {nc}, where it was when the record was saved\n")


def test_compare_needs_no_settings_and_reads_the_folders_the_record_names(world):
    a_pair(world)
    path = saved(world, "recipes")
    world.write_conf("NON_CODE_DIR=/nowhere\nnot a line\n")
    assert run(world, "compare", path)[0] == 0


def test_the_forms_that_are_refused_and_help(world):
    for argv, said in ((), "say save or compare (manifest --help shows the form)"), \
                       (("save",), "the following arguments are required: FILE, PROJECT (manifest --help shows the form)"), \
                       (("save", "x.json"), "the following arguments are required: PROJECT (manifest --help shows the form)"), \
                       (("compare",), "the following arguments are required: FILE (manifest --help shows the form)"), \
                       (("compare", "a", "b"), "unrecognized arguments: b (manifest --help shows the form)"), \
                       (("check", "a"), ("argument VERB: invalid choice: 'check' (choose from 'save', 'compare') "
                                        "(manifest --help shows the form)")):
        assert run(world, *argv) == (2, "", f"manifest: {said}\n")
    code, out, err = run(world, "--help")
    assert (code, err) == (0, "")
    assert "manifest save FILE PROJECT [PROJECT ...]\n" in out and "manifest compare FILE [--expect-only PATTERN]...\n" in out
