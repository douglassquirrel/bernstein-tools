"""set-conf: set one setting in one project's lobster.conf, keeping the file as it was (PLAN.md, Settled 159)."""

import datetime
import io
import os
import subprocess
import sys

import pytest
from conftest import tree, write_tree

NOW = datetime.datetime(2026, 10, 18, 9, 40, tzinfo=datetime.timezone.utc)
KEPT = os.path.join("_to_delete", "before-conf-change-2026-10-18-0940", "lobster.conf")
OWED = "Nothing was committed and nothing was sent: {} is owed a notice by mail of this change.\n"
DRY = "Dry run: nothing was changed. After the real run {} is owed a notice by mail of the change.\n"


def setconf(world, *argv):
    from bernstein import setconf as command
    out, err = io.StringIO(), io.StringIO()
    env = {"PATH": world.bin + os.pathsep + "/usr/bin:/bin", "HOME": world.home, "BERNSTEIN_CONF": world.conf}
    code = command.main(list(argv), env=env, today=NOW, out=out, err=err, sleep=lambda seconds: None)
    return code, out.getvalue(), err.getvalue()


def pair(world, conf=None):
    """recipes and recipes-tools with nobody on duty; conf replaces the non-code half's lobster.conf, as bytes."""
    folder = world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    write_tree(folder, {"CLAUDE.md": "Ours.\n", "notes/keep.md": "kept é\n"})
    if conf is not None:
        with open(os.path.join(folder, "lobster.conf"), "wb") as f:
            f.write(conf)
    world.duty({"recipes": None, "recipes-tools": None})
    return folder


def test_help_names_the_command_and_its_form(world):
    code, out, err = setconf(world, "--help")
    assert (code, err) == (0, "")
    assert "usage: set-conf [-h] [--dry-run] [--facts-to FILE] PROJECT KEY=VALUE" in out
    for word in ("SISTER", "CLAWS", "FOLDERS", "MODEL", "EFFORT", "_to_delete"):
        assert word in out


@pytest.mark.parametrize("argv, said", [
    ((), "the following arguments are required: PROJECT, KEY=VALUE"),
    (("recipes",), "the following arguments are required: KEY=VALUE"),
    (("recipes", "MODEL=opus", "EFFORT=high"), "unrecognized arguments: EFFORT=high"),
    (("--force", "recipes", "MODEL=opus"), "unrecognized arguments: --force"),
])
def test_a_run_without_exactly_one_project_and_one_setting_is_exit_2_and_looks_at_nothing(world, argv, said):
    folder = pair(world)
    before = tree(folder)
    code, out, err = setconf(world, *argv)
    assert (code, out, err) == (2, "", f"set-conf: {said} (set-conf --help shows the form)\n")
    assert tree(folder) == before and world.calls() == []


@pytest.mark.parametrize("argument", ["MODEL", "=opus", "opus"])
def test_a_setting_that_is_not_key_equals_value_is_exit_2(world, argument):
    folder = pair(world)
    before = tree(folder)
    code, out, err = setconf(world, "recipes", argument)
    assert (code, out) == (2, "")
    assert err == (f"set-conf: {argument!r} is not KEY=VALUE: give the setting and its new value, as in "
                   "FOLDERS=~/models/voices (set-conf --help shows the form)\n")
    assert tree(folder) == before and world.calls() == []


def test_a_bad_line_in_bernsteins_own_settings_is_exit_2(world):
    folder = pair(world)
    before = tree(folder)
    world.write_conf("EFFORT=extreme\n")
    code, out, err = setconf(world, "recipes", "MODEL=fable")
    assert (code, out) == (2, "")
    assert err == f"set-conf: {world.conf}: line 7: EFFORT must be one of low, medium, high, xhigh, max\n"
    assert tree(folder) == before and world.calls() == []


def test_one_line_changes_the_file_as_it_was_is_kept_and_nothing_else_in_the_project_changes(world):
    folder = pair(world)
    voices = os.path.join(world.home, "models", "kokoro")
    os.makedirs(voices)
    with open(os.path.join(folder, "lobster.conf"), "ab") as f:
        f.write(b"# further folders\nFOLDERS=\n# the end\n")
    conf = os.path.join(folder, "lobster.conf")
    os.chmod(conf, 0o640)
    before = tree(folder)
    code, out, err = setconf(world, "recipes", "FOLDERS=~/models/kokoro")
    assert (code, err) == (0, "")
    after = tree(folder)
    was = before["lobster.conf"]
    assert after.pop(KEPT) == was
    assert after.pop("lobster.conf") == was.replace(b"\nFOLDERS=\n", b"\nFOLDERS=~/models/kokoro\n")
    del before["lobster.conf"]
    assert after == before                                        # no temporary file, nothing else touched
    assert os.stat(conf).st_mode & 0o777 == 0o640
    assert out == (f"recipes: {conf}\n"
                   "  was: FOLDERS=\n"
                   "  now: FOLDERS=~/models/kokoro\n"
                   f"  the file as it was is kept in {folder}/{KEPT}\n" + OWED.format("recipes"))
    assert [(c["prog"], c["args"][:3]) for c in world.calls()] == [("lobster-mail", ["duty", "status", "--all"])]


def test_dry_run_prints_what_the_real_run_then_does_and_changes_nothing(world):
    folder = pair(world)
    conf = os.path.join(folder, "lobster.conf")
    before = tree(folder)
    code, out, err = setconf(world, "--dry-run", "recipes", "EFFORT=xhigh")
    assert (code, err) == (0, "")
    assert out == (f"recipes: {conf}\n"
                   "  is:       EFFORT=high\n"
                   "  would be: EFFORT=xhigh\n"
                   f"  the file as it is would be kept in {folder}/{KEPT}\n" + DRY.format("recipes"))
    assert tree(folder) == before and not os.path.lexists(os.path.join(folder, "_to_delete"))
    code, out, err = setconf(world, "recipes", "EFFORT=xhigh")
    assert (code, err) == (0, "")
    assert out == (f"recipes: {conf}\n"
                   "  was: EFFORT=high\n"
                   "  now: EFFORT=xhigh\n"
                   f"  the file as it was is kept in {folder}/{KEPT}\n" + OWED.format("recipes"))
    assert tree(folder)["lobster.conf"] == before["lobster.conf"].replace(b"EFFORT=high", b"EFFORT=xhigh")


@pytest.mark.parametrize("argument, said", [
    ("MODEL=opus", "MODEL is already opus"),
    ("MODEL= opus ", "MODEL is already opus"),
    ("FOLDERS=", "FOLDERS is already empty (the file has no FOLDERS line, which reads the same)"),
    ("SISTER=recipes-tools", "SISTER is already recipes-tools"),
])
def test_a_setting_that_already_has_the_value_is_exit_0_and_nothing_is_changed_or_looked_up(world, argument, said):
    folder = pair(world)
    before = tree(folder)
    world.duty({"recipes": "fresh"})                              # not even the duty is asked about
    for argv in (("recipes", argument), ("--dry-run", "recipes", argument)):
        code, out, err = setconf(world, *argv)
        assert (code, err) == (0, "")
        assert out == f"recipes: {said} in {folder}/lobster.conf: nothing to change\n"
    assert tree(folder) == before and world.calls() == []


def test_an_empty_value_that_is_written_as_an_empty_line_already_is_no_change(world):
    folder = pair(world, conf=b"KIND=non-code\nSELF=recipes\nSISTER=recipes-tools\nCLAWS=\nMODEL=opus\nEFFORT=high\n")
    code, out, err = setconf(world, "recipes", "CLAWS=")
    assert (code, out, err) == (0, f"recipes: CLAWS is already empty in {folder}/lobster.conf: nothing to change\n", "")


def refused(world, folder, *argv, code=3):
    """Run it twice, for real and as a dry run: the same refusal, nothing printed, nothing changed or made."""
    before = tree(folder) if os.path.isdir(folder) else None
    said = set()
    for run in (argv, ("--dry-run",) + argv):
        got, out, err = setconf(world, *run)
        assert (got, out) == (code, "")
        assert err.startswith("set-conf: ") and err.endswith("\n") and err.count("\n") == 1
        said.add(err[len("set-conf: "):-1])
    if before is not None:
        assert tree(folder) == before and not os.path.lexists(os.path.join(folder, "_to_delete"))
    assert len(said) == 1
    return said.pop()


@pytest.mark.parametrize("argument, why", [
    ("KIND=code", "KIND and SELF say what a project is, and set-conf never changes them"),
    ("SELF=menus", "KIND and SELF say what a project is, and set-conf never changes them"),
    ("PACE=eager", "set-conf does not know the setting PACE: it sets SISTER, CLAWS, FOLDERS, MODEL or EFFORT"),
    ("MODEL=opus\nKIND=code", "the value for MODEL has a line break in it: a setting is one line"),
])
def test_a_setting_it_does_not_change_and_a_value_with_a_line_break_are_exit_3_before_anything_is_looked_at(
        world, argument, why):
    folder = pair(world)
    assert refused(world, folder, "recipes", argument) == why + "; nothing was changed"
    assert world.calls() == []


def test_a_project_that_cannot_be_found_or_is_in_two_places_is_exit_3(world):
    folder = pair(world)
    assert refused(world, os.path.join(world.non_code, "menus"), "menus", "MODEL=fable") == (
        f"no project menus in {world.non_code} or {world.code}, or a folder directly inside either; nothing was "
        "changed")
    os.makedirs(os.path.join(world.code, "recipes"))
    assert refused(world, folder, "recipes", "MODEL=fable") == (
        f"recipes is in two places, {folder} and {world.code}/recipes: keep one, or rename the other; nothing was "
        "changed")
    assert world.calls() == []


def test_a_project_with_no_lobster_conf_or_one_that_is_not_a_plain_utf_8_file_is_exit_3(world, tmp_path):
    folder = pair(world)
    conf = os.path.join(folder, "lobster.conf")
    real = str(tmp_path / "real.conf")
    os.rename(conf, real)
    assert refused(world, folder, "recipes", "MODEL=fable") == (
        f"{folder} has no lobster.conf, so it is not a lobster project whose settings can be set; nothing was changed")
    os.symlink(real, conf)
    assert refused(world, folder, "recipes", "MODEL=fable") == (
        f"{conf} is a link, not a file: it is left alone; nothing was changed")
    os.remove(conf)
    os.mkdir(conf)
    assert refused(world, folder, "recipes", "MODEL=fable") == (
        f"{conf} is a folder, not a file: it is left alone; nothing was changed")
    os.rmdir(conf)
    with open(conf, "wb") as f:
        f.write("KIND=non-code\nSISTER=recipes-tools\nMODEL=opus\nEFFORT=high\n# café\n".encode("latin-1"))
    assert refused(world, folder, "recipes", "MODEL=fable") == (
        f"{conf} is not plain UTF-8 text: save it again as UTF-8; nothing was changed")
    with open(real, "rb") as f:
        assert b"MODEL=opus" in f.read()                         # what the link pointed at was not touched either
    assert world.calls() == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_a_lobster_conf_that_cannot_be_read_is_exit_3(world):
    folder = pair(world)
    conf = os.path.join(folder, "lobster.conf")
    os.chmod(conf, 0o000)
    try:
        got, out, err = setconf(world, "recipes", "MODEL=fable")
    finally:
        os.chmod(conf, 0o644)
    assert (got, out) == (3, "")
    assert err == f"set-conf: {conf} cannot be read (Permission denied): check its permissions; nothing was changed\n"
    assert not os.path.lexists(os.path.join(folder, "_to_delete"))


@pytest.mark.parametrize("state", ["fresh", "stale"])
def test_a_project_with_anyone_on_duty_fresh_or_stale_is_refused(world, state):
    folder = pair(world)
    world.duty({"recipes": state})
    assert refused(world, folder, "recipes", "MODEL=fable") == (
        "mac is on duty for recipes (last beat 2026-10-18T09:30:00Z): a project's files are not changed under a "
        "session. Stop it with conduct stop, or conduct reset if it is gone; nothing was changed")


def test_a_duty_listing_that_cannot_be_had_is_exit_4_and_nothing_is_changed(world):
    folder = pair(world)
    before = tree(folder)
    world.fail("lobster-mail")
    for argv in (("recipes", "MODEL=fable"), ("--dry-run", "recipes", "MODEL=fable")):
        code, out, err = setconf(world, *argv)
        assert (code, out) == (4, "")
        assert err == ("set-conf: lobster-mail duty status --all failed (exit 1)\n  lobster-mail: stub failure\n"
                       "  nothing was changed\n")
    assert tree(folder) == before


def test_a_file_in_the_way_of_the_temporary_file_is_never_written_over(world):
    folder = pair(world)
    write_tree(folder, {"lobster.conf.set-conf-new": "left by something else\n"})
    assert refused(world, folder, "recipes", "MODEL=fable") == (
        f"{folder}/lobster.conf.set-conf-new is in the way: set-conf writes the new file there first, and never "
        "writes over anything. Look at it, and move it away if an earlier run left it; nothing was changed")


FEELER = b"KIND=feeler\nSELF=agents\nSISTER=\nCLAWS=\nMODEL=opus\nEFFORT=high\n"


def feeler(world):
    folder = os.path.join(world.non_code, "agents")
    write_tree(folder, {"lobster.conf": FEELER.decode(), "START-HERE.txt": "Start agents.\n"})
    return folder


@pytest.mark.parametrize("project, argument, why", [
    ("recipes", "FOLDERS=~/nowhere", ("conduct start would refuse recipes: {conf} names the folder {home}/nowhere in "
     "FOLDERS, which is not a folder on this Mac: make it, or correct the line")),
    ("recipes", "FOLDERS=models/kokoro", ("conduct start would refuse recipes: {conf} names the folder models/kokoro "
     "in FOLDERS, which is not a full path: start it with / or ~/")),
    ("recipes", "FOLDERS=~/models/recipes-tools", ("conduct start would refuse recipes: {conf} names the folder "
     "{home}/models/recipes-tools in FOLDERS, but {code}/recipes-tools is connected too: a session sees each as "
     "~/mnt/recipes-tools, so their last names must differ")),
    ("recipes-tools", "FOLDERS=~/models", ("conduct start would refuse recipes-tools: {conf} says KIND=code and "
     "FOLDERS=~/models: a Claude Code session opens in one folder, so only a non-code project or a feeler can "
     "name further folders")),
    ("recipes", "MODEL=", ("conduct start would refuse recipes: {conf} has no MODEL, which START-HERE.txt step 0 "
     "reads: add a line such as MODEL=opus")),
    ("recipes", "EFFORT=", ("conduct start would refuse recipes: {conf} has no EFFORT, which START-HERE.txt step 0 "
     "reads: add a line such as EFFORT=high")),
    ("recipes", "MODEL=opus 4", "the file would not do: MODEL must be one word, such as opus or sonnet"),
    ("recipes", "MODEL=opus;rm", "the file would not do: MODEL must be one word, such as opus or sonnet"),
    ("recipes", "EFFORT=extreme", "the file would not do: EFFORT must be one of low, medium, high, xhigh, max"),
    ("recipes", "EFFORT=High", "the file would not do: EFFORT must be one of low, medium, high, xhigh, max"),
    ("recipes", "CLAWS=word-tools missing-tools", ("conduct start would refuse recipes: the claw missing-tools is not "
     "in {code} or a folder directly inside it: make it, or correct CLAWS in {conf}")),
    ("recipes", "SISTER=", ("conduct start would refuse recipes: {conf} has no SISTER, the tools project a non-code "
     "session works with: add a line such as SISTER=recipes-tools")),
    ("recipes", "SISTER=missing-tools", ("conduct start would refuse recipes: the sister tools project missing-tools "
     "is not in {code} or a folder directly inside it: make it, or correct SISTER in {conf}")),
    ("agents", "SISTER=word-tools", ("conduct start would refuse agents: {conf} says KIND=feeler and "
     "SISTER=word-tools: a feeler has no home claw; name the tools projects it uses in CLAWS")),
])
def test_a_value_that_would_stop_the_project_from_starting_is_refused_and_nothing_is_changed(world, project,
                                                                                           argument, why):
    folders = {"recipes": pair(world), "agents": feeler(world), "word-tools": world.project("word-tools", "code"),
               "recipes-tools": os.path.join(world.code, "recipes-tools")}
    os.makedirs(os.path.join(world.home, "models", "recipes-tools"))
    world.duty({"recipes": "fresh"})                              # the value is judged before the duty is asked
    folder = folders[project]
    key, _equals, value = argument.partition("=")
    filled = why.format(conf=os.path.join(folder, "lobster.conf"), home=world.home, code=world.code)
    assert refused(world, folder, project, argument) == f"with {key}={value} {filled}; nothing was changed"
    assert world.calls() == []


def test_it_is_the_file_as_it_would_be_that_is_judged_so_a_wrong_setting_can_be_put_right(world):
    folder = pair(world, conf=b"KIND=non-code\nSELF=recipes\nSISTER=recipes-tools\nCLAWS=gone-tools\nMODEL=opus\n")
    conf = os.path.join(folder, "lobster.conf")
    assert world.conduct("start", "--dry-run", "recipes")[0] == 3            # two faults: a claw that is gone, no EFFORT
    assert refused(world, folder, "recipes", "MODEL=fable") == (
        f"with MODEL=fable conduct start would refuse recipes: {conf} has no EFFORT, which START-HERE.txt step 0 "
        "reads: add a line such as EFFORT=high; nothing was changed")
    code, out, err = setconf(world, "recipes", "EFFORT=high")
    assert code == 3 and "the claw gone-tools is not in" in err
    code, out, err = setconf(world, "recipes", "CLAWS=")
    assert code == 3 and "has no EFFORT" in err
    with open(conf, "ab") as f:
        f.write(b"EFFORT=high\n")
    code, out, err = setconf(world, "recipes", "CLAWS=")
    assert (code, err) == (0, "") and "  was: CLAWS=gone-tools\n  now: CLAWS=\n" in out
    assert world.conduct("start", "--dry-run", "recipes")[0] == 0


def test_a_setting_the_file_lacks_is_added_as_its_last_line_and_the_output_says_so(world):
    folder = pair(world)
    os.makedirs(os.path.join(world.home, "models", "kokoro"))
    conf = os.path.join(folder, "lobster.conf")
    was = tree(folder)["lobster.conf"]
    code, out, err = setconf(world, "--dry-run", "recipes", "FOLDERS=~/models/kokoro")
    assert (code, err) == (0, "")
    assert out == (f"recipes: {conf}\n"
                   "  is:       (no FOLDERS line)\n"
                   "  would be: FOLDERS=~/models/kokoro (added as the last line)\n"
                   f"  the file as it is would be kept in {folder}/{KEPT}\n" + DRY.format("recipes"))
    code, out, err = setconf(world, "recipes", "FOLDERS=~/models/kokoro")
    assert (code, err) == (0, "")
    assert out == (f"recipes: {conf}\n"
                   "  was: (no FOLDERS line)\n"
                   "  now: FOLDERS=~/models/kokoro (added as the last line)\n"
                   f"  the file as it was is kept in {folder}/{KEPT}\n" + OWED.format("recipes"))
    assert tree(folder)["lobster.conf"] == was + b"FOLDERS=~/models/kokoro\n"


def test_of_a_setting_written_twice_the_last_line_is_changed_and_the_output_says_there_are_two(world):
    twice = b"MODEL=sonnet\nKIND=non-code\nSELF=recipes\nSISTER=recipes-tools\nMODEL=opus\nEFFORT=high\nMODEL = haiku\n"
    folder = pair(world, conf=twice)
    conf = os.path.join(folder, "lobster.conf")
    for argv, first, second in ((("--dry-run", "recipes", "MODEL=fable"), "is:       ", "would be: "),
                                (("recipes", "MODEL=fable"), "was: ", "now: ")):
        code, out, err = setconf(world, *argv)
        assert (code, err) == (0, "")
        assert out.startswith(f"recipes: {conf}\n"
                              "  MODEL is set on lines 1, 5 and 7: conduct reads the last, and that is the line "
                              "changed\n"
                              f"  {first}MODEL = haiku\n"
                              f"  {second}MODEL =fable\n")
    assert tree(folder)["lobster.conf"] == twice[:-len(b" haiku\n")] + b"fable\n"


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes anywhere")
@pytest.mark.parametrize("locked", ["the project's folder", "its _to_delete"])
def test_a_write_that_fails_is_exit_4_and_leaves_the_project_as_it_was(world, locked):
    folder = pair(world)
    write_tree(folder, {"_to_delete/old.md": "old\n"})
    before = tree(folder)
    shut = folder if locked == "the project's folder" else os.path.join(folder, "_to_delete")
    os.chmod(shut, 0o555)
    try:
        code, out, err = setconf(world, "recipes", "MODEL=fable")
    finally:
        os.chmod(shut, 0o755)
    conf = os.path.join(folder, "lobster.conf")
    assert (code, out) == (4, "")
    assert err == (f"set-conf: {conf} could not be changed (Permission denied): it is as it was, and nothing this "
                   "run made is left\n")
    assert tree(folder) == before


def test_a_rename_that_fails_at_the_last_step_takes_away_the_kept_copy_and_the_temporary_file(world, monkeypatch):
    from bernstein import setconf as command
    folder = pair(world)
    before = tree(folder)

    def full(source, target):
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(command.os, "replace", full)
    code, out, err = setconf(world, "recipes", "MODEL=fable")
    conf = os.path.join(folder, "lobster.conf")
    assert (code, out) == (4, "")
    assert err == (f"set-conf: {conf} could not be changed (No space left on device): it is as it was, and nothing "
                   "this run made is left\n")
    assert tree(folder) == before and not os.path.lexists(os.path.join(folder, "_to_delete"))


def test_a_file_that_appears_in_the_way_at_the_last_moment_is_neither_written_over_nor_taken_away(tmp_path):
    from bernstein import setconf as command
    conf, temp = str(tmp_path / "lobster.conf"), str(tmp_path / "lobster.conf.set-conf-new")
    kept = str(tmp_path / "_to_delete" / "before-conf-change-x" / "lobster.conf")
    write_tree(str(tmp_path), {"lobster.conf": "MODEL=opus\n", "lobster.conf.set-conf-new": "someone else's\n"})
    before = tree(str(tmp_path))
    with pytest.raises(command.Stop) as stopped:
        command.write(conf, temp, kept, b"MODEL=opus\n", b"MODEL=fable\n", 0o644)
    assert stopped.value.code == 4 and "could not be changed (File exists)" in stopped.value.message
    assert tree(str(tmp_path)) == before


def test_two_changes_in_the_same_minute_keep_two_copies_and_never_write_over_one(world):
    folder = pair(world)
    first = tree(folder)["lobster.conf"]
    assert setconf(world, "recipes", "MODEL=fable")[0] == 0
    second = tree(folder)["lobster.conf"]
    code, out, err = setconf(world, "recipes", "EFFORT=max")
    assert (code, err) == (0, "")
    again = KEPT.replace("-0940", "-0940-2")
    assert f"  the file as it was is kept in {folder}/{again}\n" in out
    code, out, err = setconf(world, "--dry-run", "recipes", "EFFORT=low")
    assert f"would be kept in {folder}/{KEPT.replace('-0940', '-0940-3')}\n" in out
    after = tree(folder)
    assert (after[KEPT], after[again]) == (first, second) and first != second
    assert after["lobster.conf"] == first.replace(b"MODEL=opus", b"MODEL=fable").replace(b"EFFORT=high", b"EFFORT=max")
    assert sorted(os.listdir(os.path.join(folder, "_to_delete"))) == [
        "before-conf-change-2026-10-18-0940", "before-conf-change-2026-10-18-0940-2"]


@pytest.mark.parametrize("conf, argument, after", [
    (b"KIND=non-code\r\nSELF=recipes\r\nSISTER=recipes-tools\r\nMODEL=opus\r\nEFFORT=high\r\n", "MODEL=fable",
     b"KIND=non-code\r\nSELF=recipes\r\nSISTER=recipes-tools\r\nMODEL=fable\r\nEFFORT=high\r\n"),
    (b"KIND=non-code\r\nSELF=recipes\r\nSISTER=recipes-tools\r\nMODEL=opus\r\nEFFORT=high", "CLAWS=word-tools",
     b"KIND=non-code\r\nSELF=recipes\r\nSISTER=recipes-tools\r\nMODEL=opus\r\nEFFORT=high\r\nCLAWS=word-tools\r\n"),
    ((b"MODEL=opus\n# caf\xc3\xa9, cafe\xcc\x81 \xe2\x80\x9cquoted\xe2\x80\x9d\n\n\nKIND=non-code\nSISTER=recipes-tools\n"
     b"EFFORT=high"), "EFFORT=low",
     (b"MODEL=opus\n# caf\xc3\xa9, cafe\xcc\x81 \xe2\x80\x9cquoted\xe2\x80\x9d\n\n\nKIND=non-code\nSISTER=recipes-tools\n"
     b"EFFORT=low")),
    (b"\xef\xbb\xbf# saved by an editor that adds a mark\nKIND=non-code\nSISTER=recipes-tools\nMODEL=opus\nEFFORT=high\n",
     "MODEL=fable",
     b"\xef\xbb\xbf# saved by an editor that adds a mark\nKIND=non-code\nSISTER=recipes-tools\nMODEL=fable\nEFFORT=high\n"),
])
def test_line_endings_accents_and_every_other_byte_of_the_file_come_through_a_real_run(world, conf, argument, after):
    folder = pair(world, conf=conf)
    world.project("word-tools", "code")
    code, _out, err = setconf(world, "recipes", argument)
    assert (code, err) == (0, "")
    got = tree(folder)
    assert (got["lobster.conf"], got[KEPT]) == (after, conf)


def test_a_value_with_quotes_dollars_backslashes_spaces_and_accents_is_data_and_conduct_start_then_connects_it(world):
    folder = pair(world)
    odd = "it's $HOME `id` \\n \"q\" </script> café café %s {{x}}"
    os.makedirs(os.path.join(world.home, "models", odd))
    os.makedirs(os.path.join(world.home, "voices"))
    value = f"~/models/{odd}: {world.home}/voices"
    code, out, err = setconf(world, "recipes", "FOLDERS=" + value)
    assert (code, err) == (0, "")
    assert f"  now: FOLDERS={value} (added as the last line)\n" in out
    assert tree(folder)["lobster.conf"].endswith(("EFFORT=high\nFOLDERS=" + value + "\n").encode("utf-8"))
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "")
    assert (f"Would also connect, from FOLDERS in its lobster.conf: {world.home}/models/{odd}, "
            f"{world.home}/voices\n") in out


def test_a_tools_project_in_a_code_folder_and_a_feeler_are_changed_where_their_lobster_conf_is(world):
    outer = world.project("recipes-tools", "code", public=True, under="cooking")
    world.project("word-tools", "code")
    loose = feeler(world)
    code, out, err = setconf(world, "recipes-tools", "MODEL=fable")
    assert (code, err) == (0, "") and out.startswith(f"recipes-tools: {outer}/lobster.conf\n")
    assert b"MODEL=fable\n" in tree(outer)["lobster.conf"] and tree(outer)[KEPT].count(b"MODEL=opus\n") == 1
    assert os.listdir(os.path.join(outer, "recipes-tools")) == []            # nothing goes into the checkout
    code, out, err = setconf(world, "agents", "CLAWS=word-tools")
    assert (code, err) == (0, "")
    assert tree(loose)["lobster.conf"] == FEELER.replace(b"CLAWS=\n", b"CLAWS=word-tools\n")
    assert tree(loose)[KEPT] == FEELER
    assert [c["prog"] for c in world.calls()] == ["lobster-mail", "lobster-mail"]    # no git, no mail sent


def test_the_command_file_runs_as_a_program(world):
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    done = subprocess.run([sys.executable, os.path.join(here, "set-conf"), "--help"], capture_output=True,
                          text=True, check=False, env={"PATH": "/usr/bin:/bin", "HOME": world.home})
    assert done.returncode == 0 and "usage: set-conf" in done.stdout
    folder = pair(world)
    env = {"PATH": world.bin + os.pathsep + "/usr/bin:/bin", "HOME": world.home, "BERNSTEIN_CONF": world.conf}
    done = subprocess.run([sys.executable, os.path.join(here, "set-conf"), "recipes", "MODEL=fable"],
                          capture_output=True, text=True, check=False, env=env, cwd=world.home)
    assert (done.returncode, done.stderr) == (0, "")
    stamp = os.listdir(os.path.join(folder, "_to_delete"))
    assert len(stamp) == 1 and stamp[0].startswith("before-conf-change-20")
    done = subprocess.run([sys.executable, os.path.join(here, "set-conf"), "recipes", "KIND=code"],
                          capture_output=True, text=True, check=False, env=env, cwd=world.home)
    assert (done.returncode, done.stdout) == (3, "") and done.stderr.startswith("set-conf: KIND and SELF say")


def test_what_a_failed_write_could_not_take_away_again_is_named(world, monkeypatch):
    from bernstein import setconf as command
    folder = pair(world)
    conf = os.path.join(folder, "lobster.conf")
    was = tree(folder)["lobster.conf"]

    def full(source, target):
        raise OSError(28, "No space left on device")

    def stuck(path):
        raise OSError(13, "Permission denied")
    monkeypatch.setattr(command.os, "replace", full)
    monkeypatch.setattr(command.os, "remove", stuck)
    code, out, err = setconf(world, "recipes", "MODEL=fable")
    assert (code, out) == (4, "")
    assert err == (f"set-conf: {conf} could not be changed (No space left on device): it is as it was. Left behind, "
                   f"to be looked at and removed by hand: {folder}/{KEPT}, {conf}.set-conf-new\n")
    assert tree(folder)["lobster.conf"] == was


def test_with_no_settings_file_the_defaults_are_used(world):
    folder = pair(world)
    from bernstein import setconf as command
    out, err = io.StringIO(), io.StringIO()
    code = command.main(["recipes", "MODEL=opus"], env={"PATH": "/usr/bin:/bin", "HOME": world.home}, today=NOW,
                        out=out, err=err, sleep=lambda seconds: None)
    assert (code, err.getvalue()) == (0, "")
    assert out.getvalue() == f"recipes: MODEL is already opus in {folder}/lobster.conf: nothing to change\n"
