import json
import os

from conftest import tree


def entry(name, duty=None, pace="normal", handover=False, reported=None, new=0, open_=0, changing=False):
    """A mailbox as lobster-mail's duty status --all --json lists it. duty: None, "fresh" or "stale"."""
    held = None
    if duty:
        held = {"mailbox": name, "holder": "mac", "since": "2026-10-18T09:00:00Z",
                "last_beat": "2026-10-18T09:30:00Z", "stale": duty == "stale", "minutes": 10,
                "reported": reported}
    return {"mailbox": name, "duty": held, "duty_changing": changing, "new": new, "open": open_,
            "handover_waiting": handover, "pace": pace, "reported": reported}


DREAMING = {"status": "dreaming", "set": "2026-10-18T09:20:00Z", "until": "2026-10-18T10:20:00Z"}


def a_pair(world):
    nc = world.project("recipes", "non-code", claws=("video-tools",))
    tools = world.project("recipes-tools", "code")
    video = world.project("video-tools", "code", public=True, under="video", sister="")
    return nc, tools, video


def test_status_prints_one_line_per_mailbox_and_exits_0(world):
    a_pair(world)
    world.listing([entry("bernstein", "fresh", open_=1), entry("recipes", "fresh", new=2, reported=DREAMING),
                   entry("recipes-tools", handover=True), entry("video-tools", "stale", pace="relaxed")])
    code, out, err = world.conduct("status")
    assert (code, err) == (0, "")
    assert out == (
        "bernstein      running      -         on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)"
        f"  new 0  open 1  pace normal  cannot start: no project bernstein in {world.non_code} or {world.code},"
        " or a folder directly inside either\n"
        "recipes        running      non-code  on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)"
        '  new 2  open 0  pace normal  reporting "dreaming" until 2026-10-18T10:20:00Z\n'
        "recipes-tools  handed-over  code      nobody on duty  new 0  open 0  pace normal\n"
        "video-tools    quiet        code      on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)"
        "  new 0  open 0  pace relaxed\n")


def test_status_json_joins_each_mailbox_with_its_project(world):
    nc, tools, video = a_pair(world)
    recipes = entry("recipes", "fresh", new=2, reported=DREAMING)
    world.listing([recipes, entry("recipes-tools", handover=True), entry("video-tools")], skipped=["odd"])
    code, out, err = world.conduct("status", "--json")
    assert (code, err) == (0, "")
    said = json.loads(out)
    assert sorted(said) == ["mailboxes", "root", "skipped"]
    assert (said["root"], said["skipped"]) == (world.mail, ["odd"])
    assert said["mailboxes"] == [
        {"mailbox": "recipes", "state": "running", "kind": "non-code", "folder": nc, "model": "opus",
         "effort": "high", "sister": "recipes-tools", "claws": ["recipes-tools", "video-tools"], "serves": [],
         "refused": None, "duty": recipes["duty"], "pace": "normal", "new": 2, "open": 0,
         "handover_waiting": False, "reported": DREAMING, "session": None},
        {"mailbox": "recipes-tools", "state": "handed-over", "kind": "code", "folder": tools, "model": "opus",
         "effort": "high", "sister": "recipes", "claws": [], "serves": ["recipes"], "refused": None,
         "duty": None, "pace": "normal", "new": 0, "open": 0, "handover_waiting": True, "reported": None, "session": None},
        {"mailbox": "video-tools", "state": "off", "kind": "code", "folder": video, "model": "opus",
         "effort": "high", "sister": "", "claws": [], "serves": ["recipes"], "refused": None,
         "duty": None, "pace": "normal", "new": 0, "open": 0, "handover_waiting": False, "reported": None, "session": None}]


def test_status_says_why_start_would_refuse_a_project(world):
    folder = world.project("recipes", "non-code")       # its sister recipes-tools is not there
    world.listing([entry("recipes")])
    code, out, _err = world.conduct("status", "--json")
    row = json.loads(out)["mailboxes"][0]
    assert code == 0 and row["kind"] is None and row["state"] == "off"
    assert row["refused"] == (f"the sister tools project recipes-tools is not in {world.code} or a folder directly "
                              f"inside it: make it, or correct SISTER in {os.path.join(folder, 'lobster.conf')}")


def test_status_asks_lobster_mail_once_and_sends_opens_and_writes_nothing(world):
    a_pair(world)
    world.listing([entry("recipes", "fresh"), entry("recipes-tools"), entry("video-tools")])
    projects = os.path.join(world.home, "projects")     # the projects and the mail root; the stub's own Python
    before = tree(projects)                             # keeps a bytecode cache elsewhere under HOME
    assert world.conduct("status")[0] == 0 and world.conduct("status", "--json")[0] == 0
    assert tree(projects) == before and len(before) == 6
    assert [(c["prog"], c["args"]) for c in world.calls()] == [
        ("lobster-mail", ["duty", "status", "--all", "--json", "--root", world.mail])] * 2


def test_status_with_no_mailboxes_says_so_and_exits_0(world):
    world.listing([])
    assert world.conduct("status") == (0, f"No mailboxes in {world.mail}.\n", "")
    code, out, _err = world.conduct("status", "--json")
    assert code == 0 and json.loads(out) == {"root": world.mail, "mailboxes": [], "skipped": []}


def test_status_keeps_an_awkward_reported_status_exactly_in_json(world):
    world.project("recipes-tools", "code", sister="")
    nasty = {"status": 'he said "hi" \\ $HOME </script> café 日本', "set": "2026-10-18T09:20:00Z", "until": None}
    world.listing([entry("recipes-tools", "fresh", reported=nasty)])
    code, out, _err = world.conduct("status", "--json")
    assert code == 0 and json.loads(out)["mailboxes"][0]["reported"] == nasty
    code, out, _err = world.conduct("status")
    assert code == 0 and out.count("\n") == 1 and 'reporting "he said \\"hi\\" \\\\ $HOME </script> café 日本"' in out


def test_status_marks_a_report_past_its_finish_time_overdue_by_conduct_s_clock(world):
    world.project("recipes-tools", "code", sister="")
    over = {"status": "dreaming", "set": "2026-10-18T08:00:00Z", "until": "2026-10-18T09:00:00Z"}   # NOW is 09:40
    world.listing([entry("recipes-tools", "fresh", reported=over)])
    assert world.conduct("status")[1].endswith('reporting "dreaming" until 2026-10-18T09:00:00Z (overdue)\n')


def test_status_takes_no_project_and_no_dry_run(world):
    world.listing([entry("recipes")])
    for argv, word in ((("status", "recipes"), "recipes"), (("status", "--dry-run"), "--dry-run"),
                       (("status", "--all"), "--all")):
        code, out, err = world.conduct(*argv)
        assert (code, out) == (2, "")
        assert err == f"conduct: unrecognized arguments: {word} (conduct --help shows the form)\n"
    assert world.calls() == []


def test_status_when_lobster_mail_fails_is_exit_4_with_its_reason(world):
    world.fail("lobster-mail:duty")
    code, out, err = world.conduct("status")
    assert (code, out) == (4, "")
    assert err == "conduct: lobster-mail duty status --all failed (exit 1)\n  lobster-mail: stub failure\n"


def test_status_when_the_listing_is_not_the_expected_json_is_exit_4(world):
    with open(os.path.join(world.bin, "duty.json"), "w") as f:
        f.write("not json")
    code, out, err = world.conduct("status", "--json")
    assert (code, out) == (4, "")
    assert err == "conduct: lobster-mail duty status --all --json did not print the expected JSON\n"


def test_status_looks_again_while_a_duty_is_changing_then_gives_up_with_exit_4(world):
    world.listing([entry("recipes", changing=True)])
    naps = []
    code, out, err = world.conduct("status", sleep=naps.append)
    assert (code, out, naps) == (4, "", [1, 1, 1])
    assert err == "conduct: the duty of recipes kept changing while it was read; run conduct again\n"


def test_help_shows_the_status_form(world):
    code, out, _err = world.conduct("--help")
    assert code == 0 and "conduct status [--json]" in out


SID = "local_11111111-1111-4111-8111-111111111111"
OLD = "local_22222222-2222-4222-8222-222222222222"


def app_store(world, sessions):
    """The desktop app's session store, invented, where the settings say it is: [(id, folder, last, archived)]."""
    store = os.path.join(world.home, "Library", "Application Support", "Claude", "claude-code-sessions")
    folder = os.path.join(store, "acct", "org")
    os.makedirs(folder, exist_ok=True)
    for sid, cwd, last, archived in sessions:
        with open(os.path.join(folder, sid + ".json"), "w", encoding="utf-8") as f:
            json.dump({"sessionId": sid, "cwd": cwd, "isArchived": archived, "lastActivityAt": last}, f)
    return store


def test_status_gives_each_project_the_link_to_its_newest_session_in_the_desktop_app(world):
    _nc, tools, video = a_pair(world)
    store = app_store(world, [(SID, tools, 1794401892175, False), (OLD, tools, 1794300000000, False),
                              ("local_33333333-3333-4333-8333-333333333333", video, 1794409999999, True)])
    world.listing([entry("recipes", "fresh"), entry("recipes-tools"), entry("video-tools")])
    before = tree(store)
    code, out, err = world.conduct("status", "--json")
    rows = {r["mailbox"]: r for r in json.loads(out)["mailboxes"]}
    assert (code, err) == (0, "")
    assert rows["recipes-tools"]["session"] == {"id": SID, "link": "claude://claude.ai/epitaxy/" + SID,
                                                "last_activity": "2026-11-11T12:58:12Z"}
    assert rows["video-tools"]["session"] is None           # its only session is archived
    assert rows["recipes"]["session"] is None               # no Claude Code session was opened in its folder
    assert tree(store) == before                            # the app's store is only read


def test_status_reads_the_app_s_sessions_from_where_the_setting_says(world, tmp_path):
    _nc, tools, _video = a_pair(world)
    elsewhere = tmp_path / "my store" / "acct" / "org"
    elsewhere.mkdir(parents=True)
    (elsewhere / (SID + ".json")).write_text(json.dumps(
        {"sessionId": SID, "cwd": tools, "isArchived": False, "lastActivityAt": 1794401892175}))
    world.write_conf(f"APP_SESSIONS={tmp_path / 'my store'}\n")
    world.listing([entry("recipes-tools")])
    code, out, _err = world.conduct("status", "--json")
    assert code == 0 and json.loads(out)["mailboxes"][0]["session"]["id"] == SID


def test_status_finds_the_session_of_a_mailbox_whose_project_cannot_be_started(world):
    bare = os.path.join(world.code, "bernstein-code")       # a folder with no lobster.conf, as bernstein's own
    os.makedirs(bare)
    app_store(world, [(SID, bare, 1794401892175, False)])
    world.listing([entry("bernstein", "fresh")])
    code, out, _err = world.conduct("status", "--json")
    row = json.loads(out)["mailboxes"][0]
    assert code == 0 and row["kind"] is None and row["refused"].endswith("has no lobster.conf: is it a lobster project?")
    assert row["folder"] == bare and row["session"]["id"] == SID


def test_status_works_as_before_when_the_app_s_store_is_not_there_or_holds_rubbish(world):
    a_pair(world)
    world.listing([entry("recipes-tools")])
    code, out, err = world.conduct("status", "--json")       # no store at all under this HOME
    assert (code, err) == (0, "") and json.loads(out)["mailboxes"][0]["session"] is None
    store = app_store(world, [])
    with open(os.path.join(store, "acct", "org", SID + ".json"), "w") as f:
        f.write("not json")
    code, out, err = world.conduct("status")
    assert (code, err) == (0, "") and out.startswith("recipes-tools  off")


def test_a_mailbox_whose_project_is_in_two_places_has_no_folder_and_no_session(world):
    world.project("recipes", "non-code")
    os.makedirs(os.path.join(world.code, "recipes"))            # the same name among the code projects too
    app_store(world, [(SID, os.path.join(world.code, "recipes"), 1794401892175, False)])
    world.listing([entry("recipes")])
    code, out, _err = world.conduct("status", "--json")
    row = json.loads(out)["mailboxes"][0]
    assert code == 0 and "is in two places" in row["refused"]
    assert row["folder"] is None and row["session"] is None
