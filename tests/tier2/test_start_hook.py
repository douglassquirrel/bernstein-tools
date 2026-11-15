"""The lobster-mail start hook of a ganglion on the Mac: conduct start puts the template's .claude/settings.json
in a SESSION=code project that lacks the hook, keeping any file it replaces (PLAN.md, "A ganglion on the Mac:
SESSION=code", step 5; Settled 168). Nothing else in the project is touched, and no other project's file is."""

import os
import shlex

import pytest
from conftest import tree, write_tree
from test_session_setting import HOOK, calls, ganglion

REL = ".claude/settings.json"
KEPT = "_to_delete/before-hook-2026-10-18-0940/.claude/settings.json"


def on_the_mac(world, settings=None, line="SESSION=code"):
    """A ganglion on the Mac whose .claude/settings.json holds `settings` (None: there is no such file), and
    a template with the hook: (its folder, the hook as the template renders it for this mail root)."""
    folder = ganglion(world, line)
    write_tree(world.template, {"non-code/" + REL: HOOK.replace("ROOT", "{{MAIL_ROOT_SHELL}}")})
    write_tree(folder, {"CLAUDE.md": "The project's own.\n", "notes/keep.md": "kept é\n"})
    os.remove(os.path.join(folder, REL))
    os.rmdir(os.path.join(folder, ".claude"))
    if settings is not None:
        write_tree(folder, {REL: settings})
    return folder, HOOK.replace("ROOT", shlex.quote(world.mail))


def test_a_ganglion_on_the_mac_with_no_settings_file_is_given_the_templates_hook_before_its_session_opens(world):
    folder, hook = on_the_mac(world)
    path = os.path.join(folder, REL)
    before = tree(folder)
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "")
    assert f"Would put the lobster-mail start hook in {path}, which is not there.\n" in out
    assert tree(folder) == before and calls(world, "send") == []
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "")
    assert tree(folder) == dict(before, **{REL: hook.encode()})
    assert out.startswith(f"Put the lobster-mail start hook in {path} (there was no such file).\n"
                          "Sent the Start message to recipes.\n")
    assert ("bernstein put the lobster-mail start hook in .claude/settings.json just before this session started:\n"
            "there was no such file. Say so in the diary, and commit it with your next commit.\n\n"
            ) in calls(world, "send")[0]["stdin"]
    assert [c["prog"] for c in world.calls() if c["prog"] in ("open",) or c["args"][:1] == ["send"]] == [
        "lobster-mail", "open"]
    code, out, err = world.conduct("start", "recipes")                    # and the next start finds it right
    assert (code, err) == (0, "") and "hook" not in out and "hook" not in calls(world, "send")[1]["stdin"]
    assert tree(folder) == dict(before, **{REL: hook.encode()})


OWN = '{"env": {"WHISPER": "/opt/whisper"}, "permissions": {"allow": ["Bash(ls:*)"]}}\n'


@pytest.mark.parametrize("settings", [
    "{}\n", "", "not json at all\n", OWN,
    HOOK.replace("ROOT", "/another/mail"),                                    # the hook, for another mail root
    HOOK.replace(" --root ROOT", ""),                                         # the hook, with no mail root
    '{"command": "lobster-mail check --project x --root ROOT"}\n',            # lobster-mail, but not its start
])
def test_a_settings_file_without_the_hook_is_replaced_whole_and_kept_as_it_was(world, settings):
    settings = settings.replace("ROOT", shlex.quote(world.mail))
    folder, hook = on_the_mac(world, settings)
    path, kept = os.path.join(folder, REL), os.path.join(folder, KEPT)
    before = tree(folder)
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "")
    assert (f"Would replace {path}, which has no lobster-mail start hook for {world.mail}, with the template's, "
            f"keeping the file as it is in {kept}\n") in out
    assert tree(folder) == before and calls(world, "send") == []
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "")
    assert tree(folder) == dict(before, **{REL: hook.encode(), KEPT: settings.encode()})
    assert out.startswith(f"Replaced {path}, which had no lobster-mail start hook for {world.mail}, with the "
                          f"template's (the file as it was is in {kept}).\nSent the Start message to recipes.\n")
    assert ("bernstein replaced .claude/settings.json with the template's just before this session started: it had\n"
            "no lobster-mail start hook for this mail root. The file as it was is\n"
            "_to_delete/before-hook-2026-10-18-0940/.claude/settings.json: carry across any settings of this\n"
            "project's own that it held, say so in the diary, and commit.\n\n") in calls(world, "send")[0]["stdin"]


def test_a_settings_file_that_has_the_hook_is_left_alone_whatever_else_it_holds(world):
    for extra in ("", ', "env": {"WHISPER": "/opt/whisper"}, "permissions": {"allow": ["Bash(ls:*)"]}'):
        settings = HOOK.replace("ROOT", shlex.quote(world.mail)).replace("}]}]}}\n", "}]}]}" + extra + "}\n")
        folder, _hook = on_the_mac(world, settings)
        path = os.path.join(folder, REL)
        before, stamp = tree(folder), os.stat(path).st_mtime_ns
        code, out, err = world.conduct("start", "--dry-run", "recipes")
        assert (code, err) == (0, "")
        assert f"{path} has the lobster-mail start hook: it would be left as it is.\n" in out
        code, out, err = world.conduct("start", "recipes")
        assert (code, err) == (0, "") and "hook" not in out
        assert "hook" not in calls(world, "send")[-1]["stdin"]
        assert tree(folder) == before and os.stat(path).st_mtime_ns == stamp


def test_a_second_copy_kept_in_the_same_minute_goes_beside_the_first(world):
    folder, hook = on_the_mac(world, "{}\n")
    write_tree(folder, {KEPT: "an earlier one\n"})
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "")
    files = tree(folder)
    second = KEPT.replace("0940", "0940-2")
    assert (files[KEPT], files[second], files[REL]) == (b"an earlier one\n", b"{}\n", hook.encode())
    assert f"(the file as it was is in {os.path.join(folder, second)})" in out
    assert "_to_delete/before-hook-2026-10-18-0940-2/.claude/settings.json" in calls(world, "send")[0]["stdin"]


@pytest.mark.parametrize("line", [None, "SESSION=cowork", "SESSION="])
def test_a_ganglion_in_claude_cowork_is_never_given_the_hook_nor_is_a_tools_project(world, line):
    folder, _hook = on_the_mac(world, "{}\n", line)
    tools = os.path.join(world.code, "recipes-tools")
    before = (tree(folder), tree(tools))
    for project in ("recipes", "recipes-tools"):
        for argv in (("start", "--dry-run", project), ("start", project)):
            code, out, err = world.conduct(*argv)
            assert (code, err) == (0, "") and "hook" not in out
    assert (tree(folder), tree(tools)) == before
    assert all("hook" not in c["stdin"] for c in calls(world, "send"))


def test_a_start_that_is_refused_never_touches_the_settings_file(world):
    folder, _hook = on_the_mac(world, "{}\n")
    before = tree(folder)
    world.duty({"recipes": "fresh", "recipes-tools": None})
    assert world.conduct("start", "recipes")[0] == 3
    world.duty({"recipes": None, "recipes-tools": None})
    assert world.conduct("start", "recipes", "--name", "")[0] == 2
    assert world.conduct("start", "recipes", "--brief", os.path.join(world.home, "no such brief"))[0] == 2
    with open(os.path.join(folder, "lobster.conf"), "a") as f:
        f.write("FOLDERS=~/not there\n")
    assert world.conduct("start", "recipes")[0] == 3
    assert {k: v for k, v in tree(folder).items() if k != "lobster.conf"} == {
        k: v for k, v in before.items() if k != "lobster.conf"}
    assert calls(world, "send") == [] and calls(world, "open") == []


@pytest.mark.parametrize("template_hook, why", [
    (None, "the template has no non-code/.claude/settings.json to put in {folder}"),
    ("{}\n", "the template's non-code/.claude/settings.json has no lobster-mail start hook for {mail}"),
    (HOOK.replace(" --root ROOT", ""),
     "the template's non-code/.claude/settings.json has no lobster-mail start hook for {mail}"),
])
def test_a_template_that_cannot_give_the_hook_is_exit_4_and_nothing_is_written_sent_or_opened(world, template_hook, why):
    folder, _hook = on_the_mac(world, "{}\n")
    if template_hook is None:
        os.remove(os.path.join(world.template, "non-code", REL))
    else:
        write_tree(world.template, {"non-code/" + REL: template_hook})
    before = tree(folder)
    for argv in (("start", "recipes"), ("start", "--dry-run", "recipes")):
        assert world.conduct(*argv) == (
            4, "", "conduct: " + why.format(folder=folder, mail=world.mail) + ", so a Claude Code session in "
                   f"{folder} would not read its mail when it starts: nothing was sent or opened\n")
    assert tree(folder) == before and calls(world, "send") == [] and calls(world, "open") == []
    write_tree(folder, {REL: HOOK.replace("ROOT", shlex.quote(world.mail))})       # with the hook there already,
    assert world.conduct("start", "--dry-run", "recipes")[0] == 0                # the template is not asked


def test_a_settings_file_that_is_a_folder_or_a_link_is_left_alone_and_the_start_refused(world):
    folder, _hook = on_the_mac(world)
    path = os.path.join(folder, REL)
    os.makedirs(path)
    said = "it is left alone, and a Claude Code session there would not read its mail when it starts: nothing was sent or opened\n"
    assert world.conduct("start", "recipes") == (3, "", f"conduct: {path} is a folder, not a file: {said}")
    os.rmdir(path)
    elsewhere = os.path.join(world.home, "elsewhere.json")
    with open(elsewhere, "w") as f:
        f.write("{}\n")
    os.symlink(elsewhere, path)
    for argv in (("start", "recipes"), ("start", "--dry-run", "recipes")):
        assert world.conduct(*argv) == (3, "", f"conduct: {path} is a link, not a file: {said}")
    with open(elsewhere) as f:
        assert f.read() == "{}\n"
    assert os.path.islink(path) and calls(world, "send") == [] and calls(world, "open") == []


def test_the_hook_and_the_global_files_are_both_brought_and_both_said(world):
    folder, hook = on_the_mac(world, "{}\n")
    write_tree(world.template, {"common/global-files": "RULES.md\nSTART-HERE.txt\n",
                                "non-code/RULES.md": "Rules v2 for {{NAME}}.\n",
                                "non-code/START-HERE.txt": "Start {{NAME}}.\n"})
    write_tree(folder, {"RULES.md": "Rules v1.\n"})
    code, out, err = world.conduct("start", "--dry-run", "recipes")
    assert (code, err) == (0, "")
    assert f"Would bring up to date in {folder}: RULES.md\nWould replace {folder}/{REL}, which has no" in out
    code, out, err = world.conduct("start", "recipes")
    assert (code, err) == (0, "")
    files = tree(folder)
    assert (files["RULES.md"], files[REL], files[KEPT]) == (b"Rules v2 for recipes.\n", hook.encode(), b"{}\n")
    assert files["_to_delete/before-global-update-2026-10-18-0940/RULES.md"] == b"Rules v1.\n"
    assert out.startswith(f"Brought up to date in {folder}: RULES.md (the old copies are in ")
    assert f"\nReplaced {folder}/{REL}, which had no lobster-mail start hook" in out
    message = calls(world, "send")[0]["stdin"]
    assert "RULES.md. They are the template's" in message and "bernstein replaced .claude/settings.json" in message


def test_a_settings_file_that_cannot_be_written_is_exit_4_and_nothing_is_sent_or_opened(world):
    folder, _hook = on_the_mac(world)
    os.makedirs(os.path.join(folder, ".claude"))
    os.chmod(os.path.join(folder, ".claude"), 0o500)
    try:
        code, out, err = world.conduct("start", "recipes")
    finally:
        os.chmod(os.path.join(folder, ".claude"), 0o700)
    assert (code, out) == (4, "")
    assert err == (f"conduct: the lobster-mail start hook could not be put in {folder}/{REL} (Permission denied): "
                   "nothing was sent or opened\n")
    assert os.listdir(os.path.join(folder, ".claude")) == []
    assert calls(world, "send") == [] and calls(world, "open") == []


def test_a_settings_file_that_cannot_be_read_is_exit_3_and_is_left_alone(world):
    folder, _hook = on_the_mac(world, "{}\n")
    path = os.path.join(folder, REL)
    os.chmod(path, 0)
    try:
        for argv in (("start", "recipes"), ("start", "--dry-run", "recipes")):
            assert world.conduct(*argv) == (
                3, "", (f"conduct: {path} cannot be read (Permission denied): check its permissions; a Claude Code "
                       "session there would not read its mail when it starts: nothing was sent or opened\n"))
    finally:
        os.chmod(path, 0o644)
    with open(path) as f:
        assert f.read() == "{}\n"
    assert not os.path.exists(os.path.join(folder, "_to_delete"))
    assert calls(world, "send") == [] and calls(world, "open") == []


def test_a_template_whose_hook_is_not_json_once_filled_in_is_exit_4_and_nothing_is_written(world):
    folder, _hook = on_the_mac(world, "{}\n")
    write_tree(world.template, {"non-code/" + REL: '{"command": lobster-mail start --project x --root {{MAIL_ROOT_SHELL}}}\n'})
    before = tree(folder)
    assert world.conduct("start", "recipes") == (
        4, "", "conduct: the template cannot be read: non-code/.claude/settings.json: not valid JSON once filled in\n")
    assert tree(folder) == before and calls(world, "send") == [] and calls(world, "open") == []


def test_ticket_settings_that_cannot_be_read_stop_the_start_before_the_hook_is_touched(world):
    folder, _hook = on_the_mac(world, "{}\n")
    write_tree(folder, {"backlog/config.yml": "task_prefix: RE\n"})
    config = os.path.join(folder, "backlog", "config.yml")
    os.chmod(config, 0)
    try:
        code, out, err = world.conduct("start", "recipes")
    finally:
        os.chmod(config, 0o644)
    assert (code, out) == (3, "")
    assert err == (f"conduct: {config} cannot be read (Permission denied), so the prefix of recipes's tickets is "
                   "not known: check its permissions\n")
    with open(os.path.join(folder, REL)) as f:
        assert f.read() == "{}\n"
    assert calls(world, "send") == [] and calls(world, "open") == []


def test_a_settings_file_that_appears_while_the_start_runs_is_never_written_over(world, monkeypatch):
    from bernstein import conduct
    folder, _hook = on_the_mac(world, "appeared after the look\n")
    monkeypatch.setattr(conduct.hook, "state", lambda folder, root: "missing")     # the look found no file
    code, out, err = world.conduct("start", "recipes")
    assert (code, out) == (4, "")
    assert err == (f"conduct: the lobster-mail start hook could not be put in {folder}/{REL} (File exists): "
                   "nothing was sent or opened\n")
    with open(os.path.join(folder, REL)) as f:
        assert f.read() == "appeared after the look\n"
    assert calls(world, "send") == [] and calls(world, "open") == []
