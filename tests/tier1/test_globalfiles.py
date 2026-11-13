import datetime
import os

import pytest

from bernstein import globalfiles
from bernstein.render import TemplateRefused, render_half

DAY = datetime.date(2026, 10, 18)


def template(tmp_path, files):
    for rel, text in files.items():
        p = tmp_path / "tmpl" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return str(tmp_path / "tmpl")


def test_a_template_names_its_global_files_one_a_line_with_comments_and_blank_lines(tmp_path):
    t = template(tmp_path, {"common/global-files": "# owned by the template\nRULES.md\n\n  START-HERE.txt  \ninbox/README.md\n"})
    assert globalfiles.declared(t) == ["RULES.md", "START-HERE.txt", "inbox/README.md"]


def test_a_template_without_the_list_has_no_global_files(tmp_path):
    assert globalfiles.declared(template(tmp_path, {"README.md": "x\n"})) == []


@pytest.mark.parametrize("line", ["/etc/passwd", "../other/CLAUDE.md", "a/../../b", "~/x"])
def test_a_global_file_must_be_a_path_inside_the_project(tmp_path, line):
    t = template(tmp_path, {"common/global-files": line + "\n"})
    with pytest.raises(TemplateRefused) as refused:
        globalfiles.declared(t)
    assert str(refused.value) == f"common/global-files: {line} is not a path inside a project"


def test_the_templates_version_is_a_placeholder_in_every_file_and_empty_when_there_is_none(tmp_path):
    files = {"common/inbox/README.md": "i\n", "common/lobster.conf": "c\n", "code/RULES.md": "Rules, {{TEMPLATE_VERSION}}.\n"}
    t = template(tmp_path, files)
    assert render_half(t, "code", {"TOOLS": "x"}, False)["RULES.md"] == "Rules, .\n"
    template(tmp_path, {"common/version": "13 November 2026 (b)\n"})
    assert render_half(t, "code", {"TOOLS": "x"}, False)["RULES.md"] == "Rules, 13 November 2026 (b).\n"


def test_what_a_folder_lacks_of_the_global_files_is_missing_or_behind(tmp_path):
    folder = tmp_path / "p"
    (folder / "inbox").mkdir(parents=True)
    (folder / "RULES.md").write_text("old\n", encoding="utf-8")
    (folder / "inbox" / "README.md").write_text("same é\n", encoding="utf-8")
    rendered = {"RULES.md": "new\n", "START-HERE.txt": "start\n", "inbox/README.md": "same é\n"}
    assert globalfiles.state(rendered, str(folder)) == [("RULES.md", "behind"), ("START-HERE.txt", "missing")]
    assert globalfiles.is_split(rendered, str(folder)) is False
    (folder / "START-HERE.txt").write_text("anything\n", encoding="utf-8")
    assert globalfiles.is_split(rendered, str(folder)) is True
    assert globalfiles.is_split({}, str(folder)) is False


def test_bringing_up_to_date_replaces_only_what_is_behind_and_keeps_each_old_copy(tmp_path):
    folder = tmp_path / "p q"
    (folder / "inbox").mkdir(parents=True)
    (folder / "RULES.md").write_text("old rules\n", encoding="utf-8")
    (folder / "inbox" / "README.md").write_text("old inbox\n", encoding="utf-8")
    (folder / "START-HERE.txt").write_text("start\n", encoding="utf-8")
    (folder / "CLAUDE.md").write_text("the project's own\n", encoding="utf-8")
    rendered = {"RULES.md": "new rules\n", "START-HERE.txt": "start\n", "inbox/README.md": "new inbox\n"}
    done, kept = globalfiles.bring_up_to_date(rendered, str(folder), "2026-10-18-0940")
    assert done == ["RULES.md", "inbox/README.md"]
    assert kept == os.path.join(str(folder), "_to_delete", "before-global-update-2026-10-18-0940")
    assert (folder / "RULES.md").read_text(encoding="utf-8") == "new rules\n"
    assert (folder / "inbox" / "README.md").read_text(encoding="utf-8") == "new inbox\n"
    assert open(os.path.join(kept, "RULES.md"), encoding="utf-8").read() == "old rules\n"
    assert open(os.path.join(kept, "inbox", "README.md"), encoding="utf-8").read() == "old inbox\n"
    assert (folder / "CLAUDE.md").read_text(encoding="utf-8") == "the project's own\n"
    assert sorted(os.listdir(folder)) == ["CLAUDE.md", "RULES.md", "START-HERE.txt", "_to_delete", "inbox"]


def test_nothing_behind_writes_nothing_and_a_second_update_the_same_minute_never_overwrites_a_kept_copy(tmp_path):
    folder = tmp_path / "p"
    folder.mkdir()
    (folder / "RULES.md").write_text("one\n", encoding="utf-8")
    assert globalfiles.bring_up_to_date({"RULES.md": "one\n"}, str(folder), "s") == ([], None)
    assert os.listdir(folder) == ["RULES.md"]
    _, first = globalfiles.bring_up_to_date({"RULES.md": "two\n"}, str(folder), "s")
    _, second = globalfiles.bring_up_to_date({"RULES.md": "three\n"}, str(folder), "s")
    assert first.endswith("before-global-update-s") and second.endswith("before-global-update-s-2")
    assert open(os.path.join(first, "RULES.md")).read() == "one\n"
    assert open(os.path.join(second, "RULES.md")).read() == "two\n"
