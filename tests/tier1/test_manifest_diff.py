"""manifest's pure functions: what differs between two records of a folder, and what was expected."""

import pytest

from bernstein import manifest


def f(sha, size=3):
    return {"size": size, "sha256": sha}


NONE = {"changed": [], "moved": [], "added": [], "gone": []}


def test_the_same_record_has_no_difference():
    files = {"a.md": f("aa"), "b/c.md": f("bb"), "l": {"link": "a.md"}}
    assert manifest.differences(files, dict(files)) == NONE


def test_a_file_changed_added_and_gone_are_each_named_in_order_of_path():
    before = {"z.md": f("11"), "a.md": f("22"), "gone.md": f("33"), "also-gone.md": f("44")}
    after = {"z.md": f("99"), "a.md": f("88", 7), "new.md": f("55"), "b/new.md": f("66")}
    assert manifest.differences(before, after) == {
        "changed": ["a.md", "z.md"], "moved": [], "added": ["b/new.md", "new.md"],
        "gone": ["also-gone.md", "gone.md"]}


def test_a_file_at_a_new_path_with_the_same_bytes_is_a_move_not_a_gone_and_an_added():
    before = {"backlog/config.yml": f("c1"), "backlog/tasks/t1.md": f("t1"), "keep.md": f("k")}
    after = {"_to_delete/backlog-removed/backlog/config.yml": f("c1"),
             "_to_delete/backlog-removed/backlog/tasks/t1.md": f("t1"), "keep.md": f("k")}
    assert manifest.differences(before, after) == {
        "changed": [], "added": [], "gone": [],
        "moved": [("backlog/config.yml", "_to_delete/backlog-removed/backlog/config.yml"),
                  ("backlog/tasks/t1.md", "_to_delete/backlog-removed/backlog/tasks/t1.md")]}


def test_files_of_the_same_bytes_are_paired_by_name_first_then_in_order_of_path():
    before = {"a/one.md": f("s"), "a/two.md": f("s"), "a/three.md": f("s")}
    after = {"b/two.md": f("s"), "b/one.md": f("s"), "b/zzz.md": f("s"), "b/extra.md": f("s")}
    assert manifest.differences(before, after) == {
        "changed": [], "gone": [], "added": ["b/zzz.md"],
        "moved": [("a/one.md", "b/one.md"), ("a/three.md", "b/extra.md"), ("a/two.md", "b/two.md")]}


def test_the_same_checksum_with_another_size_is_not_a_move():
    assert manifest.differences({"a": f("s", 3)}, {"b": f("s", 4)}) == dict(NONE, added=["b"], gone=["a"])


def test_an_empty_file_is_never_a_move_and_nor_is_a_link_or_a_special_file():
    before = {"a/empty": f("e3", 0), "a/link": {"link": "x"}, "a/pipe": {"special": True}}
    after = {"b/empty": f("e3", 0), "b/link": {"link": "x"}, "b/pipe": {"special": True}}
    assert manifest.differences(before, after) == dict(
        NONE, added=["b/empty", "b/link", "b/pipe"], gone=["a/empty", "a/link", "a/pipe"])


def test_a_file_that_became_a_link_or_a_link_that_points_elsewhere_is_changed():
    before = {"a": f("s"), "l": {"link": "x"}, "same": {"link": "y"}}
    after = {"a": {"link": "s"}, "l": {"link": "z"}, "same": {"link": "y"}}
    assert manifest.differences(before, after) == dict(NONE, changed=["a", "l"])


@pytest.mark.parametrize("path, patterns, fits", [
    ("_to_delete/backlog-removed/backlog/tasks/t1.md", ["_to_delete/*"], True),      # * crosses /
    ("backlog/config.yml", ["_to_delete/*", "backlog/*"], True),
    ("PLAN.md", ["_to_delete/*", "backlog/*"], False),
    ("not_to_delete/x", ["_to_delete/*"], False),
    ("x/_to_delete/y", ["_to_delete/*"], False),                                     # from the folder's top
    ("lobster.conf", ["lobster.conf"], True),
    ("Lobster.conf", ["lobster.conf"], False),                                       # by case, on any disk
    ("a/b.md", [], False),
    ("notes [1].md", ["notes [[]1].md"], True),
    ("café/x", ["café/*"], True),
])
def test_a_path_matches_a_shell_pattern_from_the_top_of_the_project_s_folder(path, patterns, fits):
    assert manifest.matches(path, patterns) is fits


def test_not_expected_lists_each_difference_outside_the_patterns_and_a_move_must_fit_at_both_ends():
    diff = {"changed": ["PLAN.md", "backlog/config.yml"],
            "moved": [("backlog/a.md", "_to_delete/x/backlog/a.md"), ("backlog/b.md", "elsewhere/b.md"),
                      ("DIARY.md", "_to_delete/DIARY.md")],
            "added": ["_to_delete/note.md", "new.md"], "gone": ["old.md", "backlog/c.md"]}
    assert manifest.not_expected(diff, ["_to_delete/*", "backlog/*"]) == {
        "changed": ["PLAN.md"], "moved": [("backlog/b.md", "elsewhere/b.md"), ("DIARY.md", "_to_delete/DIARY.md")],
        "added": ["new.md"], "gone": ["old.md"]}
    assert manifest.not_expected(diff, ["*"]) == NONE
    assert manifest.not_expected(NONE, []) == NONE


def test_the_lines_say_changed_moved_added_and_gone_in_that_order_one_path_a_line():
    diff = {"changed": ["a b.md"], "moved": [("x/one.md", "y/one.md")], "added": ["new.md", "z.md"],
            "gone": ["old.md"]}
    assert manifest.lines(diff) == ["changed: a b.md", "moved:   x/one.md -> y/one.md", "added:   new.md",
                                    "added:   z.md", "gone:    old.md"]
    assert manifest.lines(NONE) == []
