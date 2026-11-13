"""local-history's pure parts: what is left out of a folder's history, and the lines that say so."""

import os

import pytest

from bernstein import localhistory


def lay(root, files):
    for rel, text in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)


def test_keeps_the_folders_own_files_with_their_sizes(tmp_path):
    lay(tmp_path, {"DIARY.md": "12345", "tools/README.md": "abc", "tool/.git/HEAD": "x"})
    found = localhistory.scan(str(tmp_path))
    assert sorted(found["files"]) == [("DIARY.md", 5), ("tools/README.md", 3)]


def test_leaves_out_a_checkout_inside_by_its_own_path_and_does_not_look_in_it(tmp_path):
    lay(tmp_path, {"PLAN.md": "p", "tool/.git/HEAD": "x", "tool/code.py": "c", "old/deep/co/.git/HEAD": "x",
                   "old/deep/co/a.py": "a", "old/note.md": "n"})
    found = localhistory.scan(str(tmp_path))
    assert found["nested"] == ["old/deep/co", "tool"]
    assert sorted(found["files"]) == [("PLAN.md", 1), ("old/note.md", 1)]


def test_a_checkout_whose_git_is_a_file_is_left_out_too(tmp_path):
    lay(tmp_path, {"PLAN.md": "p", "worktree/.git": "gitdir: elsewhere\n", "worktree/a.py": "a"})
    assert localhistory.scan(str(tmp_path))["nested"] == ["worktree"]


def test_leaves_out_venv_to_delete_pycache_and_ds_store_at_any_depth(tmp_path):
    lay(tmp_path, {"PLAN.md": "p", ".venv/bin/pip": "x", "_to_delete/old.md": "x", "tools/__pycache__/a.pyc": "x",
                   "tools/_to_delete/b.md": "x", ".DS_Store": "x", "tools/.DS_Store": "x", "tools/keep.py": "k",
                   "tool/.git/HEAD": "x"})
    found = localhistory.scan(str(tmp_path))
    assert sorted(found["files"]) == [("PLAN.md", 1), ("tools/keep.py", 1)]
    assert found["left_out"] == [".venv", "_to_delete", "tools/__pycache__", "tools/_to_delete"]


def test_leaves_out_the_whole_top_inbox_its_readme_too_and_only_the_top_inbox(tmp_path):
    lay(tmp_path, {"inbox/README.md": "r", "inbox/sample.mov": "big", "inbox/done/old.txt": "o",
                   "notes/inbox/kept.txt": "k", "tool/.git/HEAD": "x"})
    found = localhistory.scan(str(tmp_path))
    assert sorted(found["files"]) == [("notes/inbox/kept.txt", 1)]
    assert found["left_out"] == ["inbox"]


def test_an_empty_folder_has_nothing(tmp_path):
    assert localhistory.scan(str(tmp_path)) == {"nested": [], "left_out": [], "files": []}


def test_names_with_spaces_and_accents_in_both_unicode_forms_are_kept_as_they_are(tmp_path):
    nfc, nfd = "café notes.md", "café plan.md"
    lay(tmp_path, {nfc: "1", nfd: "22", "my tool/.git/HEAD": "x"})
    found = localhistory.scan(str(tmp_path))
    assert sorted(found["files"]) == sorted([(nfc, 1), (nfd, 2)])
    assert found["nested"] == ["my tool"]


def test_the_exclude_lines_name_each_checkout_from_the_top_and_the_fixed_names():
    lines = localhistory.exclude_lines(["old/deep/co", "tool"])
    assert lines[0].startswith("# ")
    assert lines[1:] == ["/old/deep/co/", "/tool/", ".venv/", "_to_delete/", "__pycache__/", ".DS_Store",
                         "/inbox/"]


@pytest.mark.parametrize("rel, line", [
    ("my tool", "/my tool/"),
    ("a*b", "/a\\*b/"),
    ("what?", "/what\\?/"),
    ("[x]", "/\\[x]/"),
    ("back\\slash", "/back\\\\slash/"),
    ("#hash", "/#hash/"),
    ("!bang", "/!bang/"),
    ("$HOME</script>", "/$HOME</script>/"),
    ("café", "/café/"),
    ("trail ", "/trail\\ /"),
])
def test_a_checkouts_name_is_data_in_its_exclude_line_never_a_pattern(rel, line):
    assert localhistory.pattern_for(rel) == line


def test_a_name_with_a_line_break_cannot_be_an_exclude_line():
    with pytest.raises(ValueError):
        localhistory.pattern_for("two\nlines")


def test_the_exclude_file_is_made_when_git_left_none(tmp_path):
    localhistory.write_exclude(str(tmp_path), ["# head", "/tool/"])
    assert (tmp_path / ".git" / "info" / "exclude").read_text(encoding="utf-8") == "# head\n/tool/\n"


def test_the_exclude_lines_go_after_what_git_init_wrote_there(tmp_path):
    lay(tmp_path, {".git/info/exclude": "# git's own comment\n"})
    localhistory.write_exclude(str(tmp_path), ["# head", "/tool/"])
    assert (tmp_path / ".git" / "info" / "exclude").read_text(encoding="utf-8") == "# git's own comment\n# head\n/tool/\n"


def test_the_exclude_lines_start_on_a_line_of_their_own_when_gits_file_ends_without_one(tmp_path):
    lay(tmp_path, {".git/info/exclude": "# no line end"})
    localhistory.write_exclude(str(tmp_path), ["/tool/"])
    assert (tmp_path / ".git" / "info" / "exclude").read_text(encoding="utf-8") == "# no line end\n/tool/\n"
