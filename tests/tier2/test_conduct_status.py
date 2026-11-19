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
        "recipes-tools  handed-over  code      nobody on duty  new 0  open 0  pace normal  no session alive\n"
        "video-tools    quiet        code      on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)"
        "  new 0  open 0  pace relaxed  no session alive: it ended without a handover\n")


def test_status_json_joins_each_mailbox_with_its_project(world):
    nc, tools, video = a_pair(world)
    recipes = entry("recipes", "fresh", new=2, reported=DREAMING)
    world.listing([recipes, entry("recipes-tools", handover=True), entry("video-tools")], skipped=["odd"])
    code, out, err = world.conduct("status", "--json")
    assert (code, err) == (0, "")
    said = json.loads(out)
    assert sorted(said) == ["live_listing", "mailboxes", "root", "skipped"]
    assert (said["root"], said["skipped"]) == (world.mail, ["odd"])
    assert said["mailboxes"] == [
        {"mailbox": "recipes", "state": "running", "kind": "non-code", "folder": nc, "model": "opus",
         "effort": "high", "sister": "recipes-tools", "claws": ["recipes-tools", "video-tools"], "serves": [],
         "refused": None, "duty": recipes["duty"], "pace": "normal", "new": 2, "open": 0,
         "handover_waiting": False, "reported": DREAMING, "session": None, "context": None, "live": None,
         "live_note": None},
        {"mailbox": "recipes-tools", "state": "handed-over", "kind": "code", "folder": tools, "model": "opus",
         "effort": "high", "sister": "recipes", "claws": [], "serves": ["recipes"], "refused": None,
         "duty": None, "pace": "normal", "new": 0, "open": 0, "handover_waiting": True, "reported": None, "session": None,
         "context": None, "live": None, "live_note": None},
        {"mailbox": "video-tools", "state": "off", "kind": "code", "folder": video, "model": "opus",
         "effort": "high", "sister": "", "claws": [], "serves": ["recipes"], "refused": None,
         "duty": None, "pace": "normal", "new": 0, "open": 0, "handover_waiting": False, "reported": None, "session": None,
         "context": None, "live": None, "live_note": None}]


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
        ("lobster-mail", ["duty", "status", "--all", "--json", "--root", world.mail]),
        ("claude", ["agents", "--json"])] * 2


def test_status_with_no_mailboxes_says_so_and_exits_0(world):
    world.listing([])
    assert world.conduct("status") == (0, f"No mailboxes in {world.mail}.\n", "")
    code, out, _err = world.conduct("status", "--json")
    assert code == 0 and json.loads(out) == {"root": world.mail, "mailboxes": [], "skipped": [],
                                             "live_listing": {"read": True, "why": None}}


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
                                                "app": "code", "last_activity": "2026-11-11T12:58:12Z"}
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


COWORK = "session_01AAAAAAAAAAAAAAAAAAAAAA"


def test_status_gives_a_non_code_project_the_link_to_its_newest_cowork_session(world, tmp_path):
    nc, tools, _video = a_pair(world)
    desk = os.path.join(world.home, "Library", "Application Support", "Claude", "local-agent-mode-sessions")
    os.makedirs(os.path.join(desk, "acct", "org"))
    listed = os.path.join(desk, "acct", "org", "remote-session-spaces.json")
    with open(listed, "w", encoding="utf-8") as f:
        json.dump({"entries": [{"sessionId": "session_01OLDOLDOLDOLDOLDOLDOLDOL", "folders": [nc, world.mail]},
                               {"sessionId": COWORK, "folders": [nc, world.mail, tools]}]}, f)
    world.listing([entry("recipes", "fresh"), entry("recipes-tools")])
    before = tree(desk)
    code, out, err = world.conduct("status", "--json")
    rows = {r["mailbox"]: r for r in json.loads(out)["mailboxes"]}
    assert (code, err) == (0, "")
    assert rows["recipes"]["session"] == {"id": COWORK, "link": "claude://claude.ai/cowork/" + COWORK,
                                          "app": "cowork", "last_activity": None}
    assert rows["recipes-tools"]["session"] is None         # only connected to that session, not its own folder
    assert tree(desk) == before
    elsewhere = tmp_path / "desk 2" / "a" / "b"
    elsewhere.mkdir(parents=True)
    (elsewhere / "remote-session-spaces.json").write_text(json.dumps(
        {"entries": [{"sessionId": "session_01ELSEWHEREELSEWHEREELSE", "folders": [nc]}]}))
    world.write_conf(f"APP_COWORK_SESSIONS={tmp_path / 'desk 2'}\n")
    code, out, _err = world.conduct("status", "--json")
    assert code == 0 and json.loads(out)["mailboxes"][0]["session"]["id"] == "session_01ELSEWHEREELSEWHEREELSE"


CLI = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PRIVATE = "private words that must never leave the transcript"


def transcript(world, sid, cli, figures, when="2026-10-18T09:30:07.123Z", root=None, folder=None):
    """Name a session's transcript in its store entry, and write it (invented) where the settings say
    transcripts are: one thing said, and one reply with the three figures."""
    store = os.path.join(world.home, "Library", "Application Support", "Claude", "claude-code-sessions")
    entry_path = os.path.join(store, "acct", "org", sid + ".json")
    with open(entry_path, encoding="utf-8") as f:
        data = json.load(f)
    data["cliSessionId"] = cli
    with open(entry_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    root = root or os.path.join(world.home, ".claude", "projects")
    os.makedirs(os.path.join(root, folder or "-invented-folder"), exist_ok=True)
    usage = dict(zip(("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"), figures))
    lines = [{"type": "user", "message": {"role": "user", "content": PRIVATE}},
             {"type": "assistant", "isSidechain": False, "timestamp": when,
              "message": {"content": [{"type": "text", "text": PRIVATE}], "usage": usage}},
             {"type": "last-prompt", "lastPrompt": PRIVATE}]
    with open(os.path.join(root, folder or "-invented-folder", cli + ".jsonl"), "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(line) + "\n" for line in lines))
    return root


def test_status_json_says_how_full_the_context_window_of_each_claude_code_session_is(world):
    _nc, tools, video = a_pair(world)
    store = app_store(world, [(SID, tools, 1794401892175, False), (OLD, video, 1794300000000, False)])
    root = transcript(world, SID, CLI, (10, 5709, 130000))
    world.listing([entry("recipes", "fresh"), entry("recipes-tools"), entry("video-tools")])
    before = tree(store), tree(root)
    code, out, err = world.conduct("status", "--json")
    rows = {r["mailbox"]: r for r in json.loads(out)["mailboxes"]}
    assert (code, err) == (0, "")
    assert rows["recipes-tools"]["context"] == {"tokens": 135719, "window": 1000000, "percent": 14,
                                                "as_of": "2026-10-18T09:30:07Z", "warn": False}
    assert rows["video-tools"]["session"]["id"] == OLD and rows["video-tools"]["context"] is None   # no transcript
    assert rows["recipes"]["session"] is None and rows["recipes"]["context"] is None                # no session
    assert list(rows["recipes-tools"])[-4:] == ["session", "context", "live", "live_note"]
    assert PRIVATE not in out
    assert (tree(store), tree(root)) == before                  # the app's files are only read
    assert [(c["prog"], c["args"][:2]) for c in world.calls()] == [("lobster-mail", ["duty", "status"]),
                                                                   ("claude", ["agents", "--json"])]


def test_the_window_s_size_the_warning_level_and_where_transcripts_are_come_from_the_settings(world, tmp_path):
    _nc, tools, _video = a_pair(world)
    app_store(world, [(SID, tools, 1794401892175, False)])
    transcript(world, SID, CLI, (0, 0, 119000), root=str(tmp_path / "my transcripts"), folder="it's [1] *")
    world.listing([entry("recipes-tools")])
    world.write_conf(f"APP_TRANSCRIPTS={tmp_path / 'my transcripts'}\nCONTEXT_WINDOW=200000\n")
    code, out, _err = world.conduct("status", "--json")
    assert code == 0 and json.loads(out)["mailboxes"][0]["context"] == {
        "tokens": 119000, "window": 200000, "percent": 60, "as_of": "2026-10-18T09:30:07Z", "warn": True}
    world.write_conf(f"APP_TRANSCRIPTS={tmp_path / 'my transcripts'}\nCONTEXT_WINDOW=200000\nCONTEXT_WARN=61\n")
    code, out, _err = world.conduct("status", "--json")
    assert code == 0 and json.loads(out)["mailboxes"][0]["context"]["warn"] is False
    world.write_conf("CONTEXT_WINDOW=200000\n")             # transcripts back where none is: not known
    code, out, err = world.conduct("status", "--json")
    assert (code, err) == (0, "") and json.loads(out)["mailboxes"][0]["context"] is None


def test_status_marks_a_session_at_or_over_60_of_a_million_when_the_settings_say_nothing(world):
    _nc, tools, video = a_pair(world)
    other = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    app_store(world, [(SID, tools, 1794401892175, False), (OLD, video, 1794300000000, False)])
    transcript(world, SID, CLI, (0, 0, 594999))
    transcript(world, OLD, other, (0, 0, 595000))
    world.listing([entry("recipes-tools"), entry("video-tools")])
    rows = {r["mailbox"]: r["context"] for r in json.loads(world.conduct("status", "--json")[1])["mailboxes"]}
    assert (rows["recipes-tools"]["percent"], rows["recipes-tools"]["warn"]) == (59, False)
    assert (rows["video-tools"]["percent"], rows["video-tools"]["warn"]) == (60, True)


def test_a_cowork_session_s_context_is_not_known(world):
    nc, _tools, _video = a_pair(world)
    desk = os.path.join(world.home, "Library", "Application Support", "Claude", "local-agent-mode-sessions")
    os.makedirs(os.path.join(desk, "acct", "org"))
    with open(os.path.join(desk, "acct", "org", "remote-session-spaces.json"), "w", encoding="utf-8") as f:
        json.dump({"entries": [{"sessionId": COWORK, "folders": [nc]}]}, f)
    world.listing([entry("recipes", "fresh")])
    code, out, err = world.conduct("status", "--json")
    row = json.loads(out)["mailboxes"][0]
    assert (code, err) == (0, "") and row["session"]["app"] == "cowork" and row["context"] is None


def test_a_transcript_that_is_not_the_shape_expected_is_not_known_and_is_no_error(world):
    _nc, tools, _video = a_pair(world)
    app_store(world, [(SID, tools, 1794401892175, False)])
    root = transcript(world, SID, CLI, (0, 0, "many"))
    world.listing([entry("recipes-tools")])
    code, out, err = world.conduct("status", "--json")
    assert (code, err) == (0, "") and json.loads(out)["mailboxes"][0]["context"] is None
    with open(os.path.join(root, "-invented-folder", CLI + ".jsonl"), "wb") as f:
        f.write(b"\xff\xfe not a transcript at all")
    code, out, err = world.conduct("status", "--json")
    assert (code, err) == (0, "") and json.loads(out)["mailboxes"][0]["context"] is None


def test_the_text_form_of_status_says_nothing_of_the_context_window(world):
    _nc, tools, _video = a_pair(world)
    world.listing([entry("recipes-tools")])
    plain = world.conduct("status")
    app_store(world, [(SID, tools, 1794401892175, False)])
    transcript(world, SID, CLI, (0, 0, 990000))
    assert world.conduct("status") == plain == (
        0, "recipes-tools  off  code      nobody on duty  new 0  open 0  pace normal  no session alive\n", "")


def test_a_context_setting_that_is_not_a_number_stops_status_with_exit_2(world):
    world.listing([entry("recipes-tools")])
    world.write_conf("CONTEXT_WARN=high\n")
    assert world.conduct("status", "--json") == (
        2, "", f"conduct: {world.conf}: line 7: CONTEXT_WARN must be a whole number from 1 to 100\n")
    world.write_conf("CONTEXT_WINDOW=1M\n")
    assert world.conduct("status") == (
        2, "", f"conduct: {world.conf}: line 7: CONTEXT_WINDOW must be a whole number from 1000 to 100000000\n")
