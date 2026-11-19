"""A conductor, the project whose session runs the commands, and its claw are a pair (PLAN.md, Settled 160)."""

import os

import pytest
from conftest import tree, write_tree

from bernstein import conduct


def found(world, name):
    return conduct.find_project(name, world.non_code, world.code, world.home)


@pytest.mark.parametrize("under, outer", [("", True), ("", False), ("music", True)])
def test_a_conductor_is_found_in_the_code_folder_with_its_claw_and_needs_no_start_here(world, under, outer):
    folder = world.conductor("maestro", under=under, outer=outer)
    claw = world.project("maestro-tools", "code", public=True, sister="maestro")
    p = found(world, "maestro")
    assert (p.kind, p.folder, p.checkout, p.sister) == ("conductor", folder, folder, "maestro-tools")
    assert (p.claw_names, p.claws) == (["maestro-tools"], [(os.path.join(claw, "maestro-tools"), None)])
    assert (p.model, p.effort, p.folders) == ("fable", "xhigh", [])
    assert not os.path.exists(os.path.join(folder, "START-HERE.txt"))


@pytest.mark.parametrize("change, why", [
    (("SISTER=maestro-tools\n", "SISTER=\n"), ("{conf} has no SISTER, the claw a conductor works with: add a line "
     "such as SISTER=maestro-tools")),
    (("SISTER=maestro-tools\n", ""), ("{conf} has no SISTER, the claw a conductor works with: add a line such as "
     "SISTER=maestro-tools")),
    (("SISTER=maestro-tools\n", "SISTER=gone-tools\n"), ("the sister tools project gone-tools is not in {code} or a "
     "folder directly inside it: make it, or correct SISTER in {conf}")),
    (("EFFORT=xhigh\n", "EFFORT=xhigh\nCLAWS=word-tools\n"), ("{conf} says KIND=conductor and CLAWS=word-tools: a "
     "conductor has one claw, the one SISTER names")),
    (("EFFORT=xhigh\n", "EFFORT=xhigh\nFOLDERS=~/models\n"), ("{conf} says KIND=conductor and FOLDERS=~/models: a "
     "Claude Code session opens in one folder, so only a non-code project or a feeler can name further folders")),
    (("MODEL=fable\n", ""), "{conf} has no MODEL, which START-HERE.txt step 0 reads: add a line such as MODEL=opus"),
])
def test_a_conductor_whose_settings_would_not_do_is_refused_in_plain_words(world, change, why):
    folder = world.conductor("maestro")
    world.project("maestro-tools", "code", sister="maestro")
    world.project("word-tools", "code", sister="")
    os.makedirs(os.path.join(world.home, "models"))
    conf = os.path.join(folder, "lobster.conf")
    with open(conf) as f:
        text = f.read()
    assert change[0] in text
    with open(conf, "w") as f:
        f.write(text.replace(*change))
    with pytest.raises(conduct.ProjectRefused) as refused:
        found(world, "maestro")
    assert str(refused.value) == why.format(conf=conf, code=world.code)


def test_a_conductor_in_the_non_code_folder_and_an_unknown_kind_are_refused(world):
    folder = os.path.join(world.non_code, "maestro")
    write_tree(folder, {"lobster.conf": "KIND=conductor\nSELF=maestro\nSISTER=maestro-tools\nMODEL=opus\nEFFORT=high\n"})
    world.project("maestro-tools", "code", sister="maestro")
    with pytest.raises(conduct.ProjectRefused) as refused:
        found(world, "maestro")
    assert str(refused.value) == (f"{folder}/lobster.conf says KIND=conductor, but {folder} is in the non-code "
                                  f"folder: a conductor lives in {world.code}, in maestro-code/ or maestro/")
    with open(os.path.join(folder, "lobster.conf"), "w") as f:
        f.write("KIND=soloist\nMODEL=opus\nEFFORT=high\n")
    with pytest.raises(conduct.ProjectRefused) as refused:
        found(world, "maestro")
    assert str(refused.value) == (f"{folder}/lobster.conf says KIND=soloist: it must be code, non-code, feeler or "
                                  "conductor")


def test_a_tools_project_knows_when_its_sister_is_a_conductor_and_is_otherwise_as_before(world):
    folder = world.conductor("maestro")
    claw = world.project("maestro-tools", "code", public=True, sister="maestro")
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.project("word-tools", "code", sister="")
    world.project("orphan-tools", "code", sister="nobody")
    p = found(world, "maestro-tools")
    assert (p.kind, p.folder, p.checkout, p.sister) == ("code", claw, os.path.join(claw, "maestro-tools"), "maestro")
    assert (p.serves_conductor, p.claws, p.claw_names) == (folder, [], [])
    for name in ("recipes-tools", "word-tools", "orphan-tools", "recipes"):
        assert found(world, name).serves_conductor is None
    assert found(world, "maestro").serves_conductor is None


def test_a_sister_whose_lobster_conf_cannot_be_read_is_not_taken_for_a_conductor(world):
    folder = world.conductor("maestro")
    world.project("maestro-tools", "code", sister="maestro")
    with open(os.path.join(folder, "lobster.conf"), "wb") as f:
        f.write(b"KIND=conductor\nSELF=maestro\n# caf\xe9\n")
    assert found(world, "maestro-tools").serves_conductor is None
    os.remove(os.path.join(folder, "lobster.conf"))
    assert found(world, "maestro-tools").serves_conductor is None
    assert tree(folder) == {"CLAUDE.md": b"The conductor's own rules.\n", ".git/HEAD": b"ref: refs/heads/main\n"}


def pair_on_duty(world, state="fresh"):
    """maestro and its claw, an ordinary pair, and the mailbox bernstein, each with a session in this state."""
    folder = world.conductor("maestro")
    world.project("maestro-tools", "code", sister="maestro")
    world.project("recipes", "non-code")
    world.project("recipes-tools", "code")
    world.duty({name: state for name in ("bernstein", "maestro", "maestro-tools", "recipes", "recipes-tools")})
    return folder


def sends(world):
    return [(c["args"][c["args"].index("--to") + 1], c["args"][c["args"].index("--subject") + 1].split(":")[0])
            for c in world.calls() if c["prog"] == "lobster-mail" and c["args"][:1] == ["send"]]


@pytest.mark.parametrize("argv", [
    ("start", "maestro"), ("start", "maestro", "--dry-run"), ("start", "maestro", "--again", "--pace", "eager"),
    ("finish", "maestro"), ("finish", "maestro", "--dry-run"), ("dormant", "maestro"), ("dormant", "maestro", "--dry-run"),
    ("wake", "maestro"), ("dream", "maestro"), ("dream", "maestro", "--minutes", "30", "--dry-run"),
])
@pytest.mark.parametrize("state", ["fresh", None])
def test_the_verbs_that_have_nothing_to_do_to_a_conductor_refuse_it_and_send_set_and_open_nothing(world, argv, state):
    folder = pair_on_duty(world, state)
    before = tree(folder)
    code, out, err = world.conduct(*argv)
    assert (code, out) == (3, "")
    assert err == (f"conduct: maestro is a conductor, the session that runs conduct: conduct {argv[0]} has nothing "
                   "to do to it; Squirrel starts and stops it himself\n")
    assert world.calls() == [] and tree(folder) == before


@pytest.mark.parametrize("verb, said", [("stop", "Stop"), ("dormant", "Dormant"), ("wake", "Wake"), ("dream", "Dream")])
def test_all_passes_over_every_conductor_as_it_passes_over_bernsteins_mailbox(world, verb, said):
    pair_on_duty(world)
    code, out, err = world.conduct(verb, "--all", "--dry-run")
    assert (code, err) == (0, "")
    assert "maestro-tools" in out and "to maestro," not in out and "of maestro " not in out
    code, out, err = world.conduct(verb, "--all")
    assert (code, err) == (0, "")
    assert sends(world) == [("maestro-tools", said), ("recipes", said), ("recipes-tools", said)]


@pytest.mark.parametrize("verb, nothing", [("stop", "stop"), ("dormant", "make dormant"), ("wake", "wake"),
                                           ("dream", "dream")])
def test_all_with_only_conductors_and_bernstein_on_duty_has_nothing_to_do(world, verb, nothing):
    world.conductor("maestro")
    world.project("maestro-tools", "code", sister="maestro")
    world.duty({"bernstein": "fresh", "maestro": "fresh", "maestro-tools": None})
    code, out, err = world.conduct(verb, "--all")
    assert (code, out, err) == (0, f"Nobody is on duty anywhere but bernstein: nothing to {nothing}.\n", "")
    assert sends(world) == []


def test_a_conductors_claw_is_started_stopped_and_reset_as_any_tools_project(world):
    pair_on_duty(world, None)
    code, out, err = world.conduct("start", "maestro-tools", "--dry-run")
    assert (code, err) == (0, "") and 'Would send to maestro-tools, as bernstein, subject "Start: maestro-tools"' in out
    assert "claude://code/new?" in out
    world.duty({"maestro-tools": "fresh"})
    code, out, err = world.conduct("stop", "maestro-tools")
    assert (code, out, err) == (0, "Sent the Stop message to maestro-tools.\n", "")
    world.duty({"maestro-tools": "stale"})
    code, out, err = world.conduct("reset", "maestro-tools", "--dry-run")
    assert (code, err) == (0, "") and out.startswith("maestro-tools: mac is on duty but stale")


def test_reset_and_stop_by_name_are_still_open_for_a_conductor(world):
    pair_on_duty(world, "stale")
    code, out, err = world.conduct("reset", "maestro", "--dry-run")
    assert (code, err) == (0, "")
    assert out.startswith("maestro: mac is on duty but stale") and out.endswith(
        "Dry run: nothing was closed, given up or sent.\n")
    world.duty({"maestro": "fresh"})
    code, out, err = world.conduct("reset", "maestro")
    assert code == 3 and err.startswith("conduct: a session is on duty for maestro (mac, last beat")
    code, out, err = world.conduct("stop", "maestro")
    assert (code, out, err) == (0, "Sent the Stop message to maestro.\n", "")


SERVED = {
    "common/global-files": "RULES.md\n",
    "common/sections/served-sister.md": "## Who may ask\n\nOnly its sister, {{REQUESTER}}.\n",
    "common/sections/served-any.md": "## Who may ask: any lobster project\n\nAny project.\n",
    "common/sections/served-conductor.md": "## Who may ask: its conductor\n\nOnly {{REQUESTER}}, which runs what it builds.\n",
    "code/RULES.md": ("Rules for {{TOOLS}}.\n{{> sections/served-{{SERVED}}.md}}\n"
                      "It talks to {{TALKS_TO}}, at {{NONCODE_PATH}}; requests go to {{SEND_TO}}.\n"),
    "code/CLAUDE.md": "# {{TOOLS}}\n\n## What this is\n\nOurs.\n",
}


def rules(world, names):
    """Each of these tools projects with rules that have fallen behind the template SERVED, and nobody on duty."""
    write_tree(world.template, SERVED)
    for name in names:
        folder = conduct.find_folder(name, world.non_code, world.code)[0]
        write_tree(folder, {"RULES.md": "old rules\n", "CLAUDE.md": f"# {name}\n\n## What this is\n\nOurs.\n"})
    world.duty({name: None for name in names})


def test_start_renders_the_claws_rules_for_its_conductor_with_the_conductors_section(world):
    conductor = world.conductor("maestro")
    claw = world.project("maestro-tools", "code", public=True, sister="maestro")
    world.project("recipes", "non-code")
    pair = world.project("recipes-tools", "code")
    lone = world.project("word-tools", "code", sister="")
    rules(world, ["maestro-tools", "recipes-tools", "word-tools"])
    shown = "~" + conductor[len(world.home):]
    for name in ("maestro-tools", "recipes-tools", "word-tools"):
        code, _out, err = world.conduct("start", name)
        assert (code, err) == (0, "")
    assert tree(claw)["RULES.md"].decode() == (
        "Rules for maestro-tools.\n## Who may ask: its conductor\n\nOnly `maestro`, which runs what it builds.\n"
        f"It talks to its conductor, `maestro`, at {shown}; requests go to maestro.\n")
    assert tree(pair)["RULES.md"].decode() == (
        "Rules for recipes-tools.\n## Who may ask\n\nOnly its sister, `recipes`.\n"
        "It talks to its sister project, `recipes`, at ~/projects/non-code/recipes; requests go to recipes.\n")
    assert tree(lone)["RULES.md"].decode().startswith(
        "Rules for word-tools.\n## Who may ask: any lobster project\n\nAny project.\n")
    assert tree(claw)["_to_delete/before-global-update-2026-10-18-0940/RULES.md"] == b"old rules\n"
    assert tree(conductor) == {"CLAUDE.md": b"The conductor's own rules.\n", ".git/HEAD": b"ref: refs/heads/main\n",
                               "lobster.conf": b"KIND=conductor\nSELF=maestro\nSISTER=maestro-tools\nMODEL=fable\n"
                                               b"EFFORT=xhigh\n"}


def test_a_template_with_no_section_for_a_conductors_claw_is_exit_4_naming_the_file_it_must_provide(world):
    world.conductor("maestro")
    claw = world.project("maestro-tools", "code", sister="maestro")
    rules(world, ["maestro-tools"])
    os.remove(os.path.join(world.template, "common", "sections", "served-conductor.md"))
    before = tree(claw)
    for argv in (("start", "maestro-tools"), ("start", "maestro-tools", "--dry-run")):
        code, out, err = world.conduct(*argv)
        assert (code, out) == (4, "")
        assert err == ("conduct: the template cannot be read: code/RULES.md: the include "
                       "sections/served-conductor.md is not in common/\n")
    assert tree(claw) == before


def status_entry(name, duty=None):
    held = None
    if duty:
        held = {"mailbox": name, "holder": "mac", "since": "2026-10-18T09:00:00Z",
                "last_beat": "2026-10-18T09:30:00Z", "stale": duty == "stale", "minutes": 10, "reported": None}
    return {"mailbox": name, "duty": held, "duty_changing": False, "new": 0, "open": 0,
            "handover_waiting": False, "pace": "normal", "reported": None}


def test_status_lists_a_conductor_and_its_claw_as_a_pair(world):
    import json
    conductor = world.conductor("maestro")
    claw = world.project("maestro-tools", "code", public=True, sister="maestro")
    world.project("word-tools", "code", sister="")
    world.listing([status_entry("maestro", "fresh"), status_entry("maestro-tools"), status_entry("word-tools")])
    code, out, err = world.conduct("status", "--json")
    assert (code, err) == (0, "")
    rows = {r["mailbox"]: r for r in json.loads(out)["mailboxes"]}
    assert [(r["kind"], r["folder"], r["sister"], r["claws"], r["serves"], r["refused"], r["model"], r["effort"])
            for r in (rows["maestro"], rows["maestro-tools"], rows["word-tools"])] == [
        ("conductor", conductor, "maestro-tools", ["maestro-tools"], [], None, "fable", "xhigh"),
        ("code", claw, "maestro", [], ["maestro"], None, "opus", "high"),
        ("code", os.path.join(world.code, "word-tools"), "", [], [], None, "opus", "high")]
    code, out, err = world.conduct("status")
    assert (code, err) == (0, "")
    assert out == (
        "maestro        running  conductor  on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)"
        "  new 0  open 0  pace normal  no session alive, though its duty is fresh: a watch has outlived its session\n"
        "maestro-tools  off      code       nobody on duty  new 0  open 0  pace normal  no session alive\n"
        "word-tools     off      code       nobody on duty  new 0  open 0  pace normal  no session alive\n")
    assert [c["args"][:2] for c in world.calls()] == [["duty", "status"], ["agents", "--json"]] * 2


HOOK = '{{"command": "\\"$HOME/l/lobster-mail\\" start --project \\"$CLAUDE_PROJECT_DIR\\" --root {root}"}}\n'
CLAW_CLAUDE = "# maestro-tools\n\n## What this is\n\nOurs.\n\n## Who may ask: its conductor\n\nOurs.\n"


def orchestra_in_line(world):
    """A conductor and its public claw with everything conform asks of each: (conductor's folder, claw's outer)."""
    import shlex
    write_tree(world.template, dict(SERVED, **{
        "code/CLAUDE.md": "# {{TOOLS}}\n\n## What this is\n\n{{> sections/served-{{SERVED}}.md}}\n"}))
    conductor = world.conductor("maestro")
    outer = world.project("maestro-tools", "code", public=True, sister="maestro")
    shown = "~" + conductor[len(world.home):]
    write_tree(outer, {
        ".claude/settings.json": HOOK.format(root=shlex.quote(world.mail)), "inbox/README.md": "Inbox.\n",
        "CLAUDE.md": CLAW_CLAUDE,
        "RULES.md": ("Rules for maestro-tools.\n## Who may ask: its conductor\n\nOnly `maestro`, which runs what it "
                     f"builds.\nIt talks to its conductor, `maestro`, at {shown}; requests go to maestro.\n"),
        "maestro-tools/.git/HEAD": "ref\n"})
    for box in ("maestro", "maestro-tools"):
        os.makedirs(os.path.join(world.mail, box))
    return conductor, outer


def test_conform_checks_a_conductor_and_its_claw_as_a_pair_and_asks_the_conductor_only_for_what_it_has(world):
    conductor, outer = orchestra_in_line(world)
    before = tree(conductor), tree(outer)
    code, out, err = world.conform("maestro", "maestro-tools")
    assert (code, err) == (0, "")
    assert out == (f"maestro (conductor): {conductor}\n  in line\n"
                   f"maestro-tools (code): {outer}\n  in line\n"
                   "Both halves are in line.\n")
    assert (tree(conductor), tree(outer)) == before
    assert sorted(tree(conductor)) == [".git/HEAD", "CLAUDE.md", "lobster.conf"]      # no START-HERE, hook or inbox
    assert world.calls() == []


def test_conform_names_each_thing_a_conductor_lacks(world):
    conductor, outer = orchestra_in_line(world)
    os.makedirs(os.path.join(world.home, "models"))
    write_tree(conductor, {"lobster.conf": "KIND=conductor\nSELF=baton\nSISTER=other-tools\nEFFORT=xhigh\n"
                                           "CLAWS=word-tools\nFOLDERS=~/models\n"})
    os.remove(os.path.join(conductor, "CLAUDE.md"))
    os.remove(os.path.join(conductor, ".git", "HEAD"))
    os.rmdir(os.path.join(conductor, ".git"))
    os.rmdir(os.path.join(world.mail, "maestro"))
    code, out, err = world.conform("maestro", "maestro-tools")
    assert (code, err) == (1, "")
    assert out == (f"maestro (conductor): {conductor}\n"
                   "  missing: SELF=maestro in lobster.conf (it says baton)\n"
                   "  missing: SISTER=maestro-tools in lobster.conf (it says other-tools)\n"
                   "  missing: MODEL in lobster.conf\n"
                   "  missing: an empty CLAWS in lobster.conf (a conductor has one claw, the one SISTER names)\n"
                   "  missing: an empty FOLDERS in lobster.conf (a Claude Code session opens in one folder)\n"
                   "  missing: CLAUDE.md\n"
                   f"  missing: a git repository in {conductor}\n"
                   f"  missing: the mailbox maestro in {world.mail}\n"
                   f"maestro-tools (code): {outer}\n  in line\n"
                   "8 things to bring into line.\n")


def test_conform_checks_the_claw_as_the_tools_half_of_its_conductors_pair(world):
    conductor, outer = orchestra_in_line(world)
    write_tree(outer, {"lobster.conf": "KIND=code\nSELF=maestro-tools\nSISTER=\nMODEL=opus\nEFFORT=high\n",
                       "CLAUDE.md": "# maestro-tools\n\n## What this is\n\n## Who may ask: any lobster project\n",
                       "RULES.md": "Rules for a lone claw.\n"})
    code, out, err = world.conform("maestro", "maestro-tools")
    assert (code, err) == (1, "")
    assert out == (f"maestro (conductor): {conductor}\n  in line\n"
                   f"maestro-tools (code): {outer}\n"
                   "  missing: SISTER=maestro in lobster.conf\n"
                   "  missing: the section \"## Who may ask: its conductor\" in CLAUDE.md\n"
                   "  missing: the template's current RULES.md (a global file: conduct start brings it up to date)\n"
                   "3 things to bring into line.\n")


def test_conform_says_plainly_when_the_claw_cannot_be_found_or_the_pair_is_named_by_half(world):
    conductor, _outer = orchestra_in_line(world)
    code, out, err = world.conform("maestro", "baton-tools")
    assert (code, err) == (1, "")
    assert out == (f"maestro (conductor): {conductor}\n"
                   "  missing: SISTER=baton-tools in lobster.conf (it says maestro-tools)\n"
                   "baton-tools (code): not found\n"
                   f"  baton-tools is not in {world.code} or a folder directly inside it\n"
                   "2 things to bring into line.\n")
    code, out, err = world.conform("maestro")
    assert (code, out, err) == (2, "", ("conform: maestro is a conductor: give its claw too, as in conform maestro "
                                       "maestro-tools\n"))
    code, out, err = world.conform("maestro-tools")
    assert (code, out, err) == (2, "", ("conform: maestro-tools is the claw of the conductor maestro: check them "
                                       "together, conform maestro maestro-tools\n"))


def test_a_claw_that_names_a_conductor_which_is_not_there_is_a_plain_gap(world):
    _conductor, outer = orchestra_in_line(world)
    write_tree(outer, {"lobster.conf": "KIND=code\nSELF=maestro-tools\nSISTER=ghost\nMODEL=opus\nEFFORT=high\n"})
    code, out, err = world.conform("ghost", "maestro-tools")
    assert (code, err) == (1, "")
    assert out.startswith(f"ghost (non-code): not found\n  ghost is not in {world.non_code} or a folder directly "
                          "inside it\n")
    code, out, err = world.conform("maestro-tools")
    assert code == 1 and "  missing: SISTER= (empty: a lone claw) in lobster.conf (it says ghost)\n" in out


def test_set_conf_refuses_a_conductor_and_still_sets_its_claws_sister(world):
    from test_set_conf import refused, setconf
    conductor = world.conductor("maestro")
    claw = world.project("maestro-tools", "code", sister="")          # as it is before the pair is joined
    world.duty({"maestro": None, "maestro-tools": None})
    for argument in ("MODEL=opus", "SISTER=other-tools", "CLAWS=word-tools"):
        assert refused(world, conductor, "maestro", argument) == (
            "maestro is a conductor: its lobster.conf is its own, and is changed there by hand; nothing was changed")
    assert world.calls() == []
    code, out, err = setconf(world, "maestro-tools", "SISTER=maestro")
    assert (code, err) == (0, "") and "  was: SISTER=\n  now: SISTER=maestro\n" in out
    assert tree(claw)["lobster.conf"] == b"KIND=code\nSELF=maestro-tools\nSISTER=maestro\nMODEL=opus\nEFFORT=high\n"
    assert conduct.find_project("maestro-tools", world.non_code, world.code, world.home).serves_conductor == conductor


def test_drop_backlog_refuses_a_conductor_and_moves_nothing_in_any_project(world):
    from test_drop_backlog import SETTINGS, drop, unused
    conductor = world.conductor("maestro")
    write_tree(conductor, {"backlog/config.yml": SETTINGS})
    nc = unused(world, "recipes", "non-code")
    world.duty({"maestro": None, "recipes": None})
    before = tree(conductor), tree(nc)
    for argv in (("recipes", "maestro"), ("--dry-run", "maestro", "recipes")):
        code, out, err = drop(world, *argv)
        assert (code, out) == (3, "")
        assert err == ("drop-backlog: maestro is a conductor: its files are its own, and are changed there by hand; "
                       "nothing was moved in any project\n")
    assert (tree(conductor), tree(nc)) == before


def test_a_tools_project_whose_settings_cannot_be_read_is_still_checked_alone_as_before(world):
    _conductor, outer = orchestra_in_line(world)
    with open(os.path.join(outer, "lobster.conf"), "wb") as f:
        f.write(b"KIND=code\nSISTER=maestro\n# caf\xe9\n")
    code, out, err = world.conform("maestro-tools")
    assert (code, err) == (1, "") and "  missing: lobster.conf as plain UTF-8 text\n" in out
    os.makedirs(os.path.join(world.code, "elsewhere", "maestro-tools"))
    os.makedirs(os.path.join(world.code, "other", "maestro-tools"))
    os.makedirs(os.path.join(world.code, "third"))
    os.rename(outer, os.path.join(world.code, "third", "maestro-tools-code"))
    code, out, err = world.conform("maestro-tools")
    assert (code, err) == (1, "") and "maestro-tools (code): not found\n  maestro-tools is in three places" in out
