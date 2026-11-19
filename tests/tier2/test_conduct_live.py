"""conduct status says whether a session is alive in each project's folder on the Mac, from the listing
`claude agents --json` prints (PLAN.md, "Whether a session is alive", Settled 174). The claude here is the
stand-in: it prints what World.live() gave it. Every name, folder and id is invented."""

import json
import os

import pytest
from conftest import tree
from test_conduct import feeler
from test_conduct_status import DREAMING, a_pair, entry
from test_session_setting import ganglion

DORMANT = {"status": "dormant", "set": "2026-10-18T09:20:00Z", "until": None}
NAME = "soups-tools · 18 October"
UNREAD = ("conduct status: the listing of live sessions could not be read ({}): nothing is said of which "
          "sessions are alive.\n")


CLI = "00000000-0000-4000-8000-000000000000"
NO_REPLY = {"id": CLI, "model": None, "effort": None, "last_reply": None}


def listed(cwd, name=NAME, status="idle", started=1792051200000, pid=4242, kind="interactive", sid=CLI):
    """One session as `claude agents --json` prints it."""
    return {"pid": pid, "cwd": cwd, "kind": kind, "startedAt": started, "sessionId": sid, "name": name,
            "status": status}


def transcript(world, cli=CLI, model="invented-model-7", effort="xhigh", when="2026-10-18T09:12:00.000Z",
               root=None):
    """An invented transcript of that name where the settings say transcripts are: one thing said, one reply."""
    folder = os.path.join(root or os.path.join(world.home, ".claude", "projects"), "-invented-folder")
    os.makedirs(folder, exist_ok=True)
    lines = [{"type": "user", "message": {"role": "user", "content": "private words"}},
             {"type": "assistant", "isSidechain": False, "timestamp": when, "effort": effort,
              "message": {"model": model, "content": [{"type": "text", "text": "private words"}]}}]
    path = os.path.join(folder, cli + ".jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(json.dumps(line) + "\n" for line in lines))
    return path


def claw(world, duty=None, **how):
    """A lone tools project, soups-tools, alone in the duty listing; its folder."""
    folder = world.project("soups-tools", "code", sister="")
    world.listing([entry("soups-tools", duty, **how)])
    return folder


def after_pace(out, name="soups-tools"):
    """What a mailbox's line says after its pace."""
    (line,) = [line for line in out.splitlines() if line.startswith(name + " ")]
    rest = line.split("  pace ", 1)[1]
    return rest.split("  ", 1)[1] if "  " in rest else ""


def row(world, name="soups-tools"):
    code, out, err = world.conduct("status", "--json")
    assert (code, err) == (0, "")
    return next(r for r in json.loads(out)["mailboxes"] if r["mailbox"] == name)


# --- a session alive, and none ---

@pytest.mark.parametrize("status", ["idle", "busy"])
def test_status_names_the_session_alive_in_a_project_s_folder_and_says_busy_or_idle(world, status):
    folder = claw(world, "fresh")
    world.live([listed(folder, status=status)])
    code, out, err = world.conduct("status")
    assert (code, err) == (0, "")
    assert out == ("soups-tools  running  code      on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)"
                   f'  new 0  open 0  pace normal  alive ("soups-tools · 18 October", {status})\n')
    assert row(world)["live"] == dict({"name": NAME, "status": status, "kind": "interactive",
                                       "started": "2026-10-15T08:00:00Z", "pid": 4242, "count": 1}, **NO_REPLY)
    assert row(world)["live_note"] is None


def test_status_says_no_session_alive_of_a_project_that_is_off_and_has_none(world):
    claw(world)
    code, out, err = world.conduct("status")
    assert (code, err) == (0, "")
    assert out == "soups-tools  off  code      nobody on duty  new 0  open 0  pace normal  no session alive\n"
    assert (row(world)["live"], row(world)["live_note"]) == (None, None)


def test_status_json_says_the_listing_was_read(world):
    claw(world)
    said = json.loads(world.conduct("status", "--json")[1])
    assert sorted(said) == ["live_elsewhere", "live_listing", "mailboxes", "root", "skipped"]
    assert said["live_listing"] == {"read": True, "why": None}


@pytest.mark.parametrize("duty, how, alive, note", [
    ("stale", {}, True, "alive, not watching mail"),
    ("stale", {"reported": DORMANT}, True, "alive, not watching mail"),
    ("stale", {}, False, "no session alive: it ended without a handover"),
    ("stale", {"pace": "relaxed"}, False, "no session alive: it ended without a handover"),
    ("fresh", {}, False, "no session alive, though its duty is fresh: a watch has outlived its session"),
    (None, {"handover": True}, True, "alive after its handover: not archived"),
    (None, {}, True, "alive, not on duty"),
])
def test_status_says_in_words_where_the_duty_and_the_listing_disagree(world, duty, how, alive, note):
    folder = claw(world, duty, **how)
    world.live([listed(folder)] if alive else [])
    code, out, err = world.conduct("status")
    assert (code, err) == (0, "")
    field = after_pace(out).split("  reporting ")[0]
    assert field == note + (' ("soups-tools · 18 October", idle)' if alive else "")
    assert row(world)["live_note"] == note
    assert (row(world)["live"] is not None) == alive


def test_a_stale_duty_at_the_relaxed_pace_with_a_session_alive_is_no_disagreement(world):
    folder = claw(world, "stale", pace="relaxed")
    world.live([listed(folder)])
    assert after_pace(world.conduct("status")[1]) == 'alive ("soups-tools · 18 October", idle)'
    assert row(world)["live_note"] is None and row(world)["state"] == "quiet"


def test_the_field_comes_after_the_pace_and_before_what_the_session_reports(world):
    folder = claw(world, "fresh", reported=DORMANT)
    world.live([listed(folder)])
    assert world.conduct("status")[1].endswith(
        '  pace normal  alive ("soups-tools · 18 October", idle)  reporting "dormant"\n')


def test_two_sessions_in_one_folder_are_said_with_each_name(world):
    folder = claw(world, "fresh")
    world.live([listed(folder, name="second", started=1792051260000, status="busy", pid=2),
                listed(folder, name="first", pid=1)])
    assert after_pace(world.conduct("status")[1]) == (
        '2 sessions alive in its folder ("first", idle; "second", busy)')
    assert row(world)["live"] == dict({"name": "second", "status": "busy", "kind": "interactive",
                                       "started": "2026-10-15T08:01:00Z", "pid": 2, "count": 2,
                                       "names": ["first", "second"]}, **NO_REPLY)
    assert row(world)["live_note"] == "2 sessions alive in its folder"


def test_a_session_in_a_folder_that_is_no_project_s_changes_no_line(world):
    folder = claw(world)
    other = os.path.join(world.home, "elsewhere")
    os.makedirs(other)
    world.live([listed(other), listed(os.path.dirname(folder), name="the folder above"),
                listed(os.path.join(folder, "inside"), name="a folder inside")])
    assert after_pace(world.conduct("status")[1]) == "no session alive"
    assert row(world)["live"] is None


def test_a_session_s_name_is_printed_as_data(world):
    folder = claw(world, "fresh")
    name = 'a "quoted" \\ name\nwith $HOME, </script> and é 漢'
    world.live([listed(folder, name=name)])
    out = world.conduct("status")[1]
    assert out.count("\n") == 1
    assert after_pace(out) == 'alive ("a \\"quoted\\" \\\\ name\\nwith $HOME, </script> and é 漢", idle)'
    assert row(world)["live"]["name"] == name


# --- which projects ---

def test_a_ganglion_on_the_mac_and_a_conductor_are_looked_at_like_a_tools_project(world):
    nc = ganglion(world, "SESSION=code")
    conductor = world.conductor("maestro")
    tools = world.project("maestro-tools", "code", sister="maestro")
    world.listing([entry("recipes", "fresh"), entry("recipes-tools"), entry("maestro", "stale"),
                   entry("maestro-tools")])
    world.live([listed(nc, name="recipes · 18 October"), listed(conductor, name="maestro · 18 October", status="busy"),
                listed(tools, name="maestro-tools · 18 October")])
    out = world.conduct("status")[1]
    assert after_pace(out, "recipes") == 'alive ("recipes · 18 October", idle)'
    assert after_pace(out, "recipes-tools") == "no session alive"
    assert after_pace(out, "maestro") == 'alive, not watching mail ("maestro · 18 October", busy)'
    assert after_pace(out, "maestro-tools") == 'alive, not on duty ("maestro-tools · 18 October", idle)'


@pytest.mark.parametrize("duty", [None, "fresh", "stale"])
def test_a_cowork_project_s_line_is_exactly_as_it_is_with_no_listing_at_all(world, duty):
    nc = ganglion(world)                    # recipes runs in Claude Cowork
    agents = feeler(world)
    world.listing([entry("recipes", duty), entry("agents", duty), entry("recipes-tools")])
    os.remove(os.path.join(world.bin, "claude"))
    _code, before, _err = world.conduct("status")
    os.symlink(os.path.join(os.path.dirname(__file__), "stub.sh"), os.path.join(world.bin, "claude"))
    world.live([listed(nc), listed(agents)])            # even a Claude Code session opened in its folder
    code, out, err = world.conduct("status")
    assert (code, err) == (0, "")
    lines, were = out.splitlines(), before.splitlines()
    assert lines[:2] == were[:2] and "alive" not in lines[0] + lines[1]
    assert lines[2] == were[2] + "  no session alive"
    for name in ("recipes", "agents"):
        assert (row(world, name)["live"], row(world, name)["live_note"]) == (None, None)


def test_a_mailbox_with_no_project_and_a_project_start_would_refuse_get_no_field(world):
    folder = world.project("recipes", "non-code")       # its sister recipes-tools is not there
    world.listing([entry("recipes", "stale"), entry("nowhere", "stale")])
    world.live([listed(folder)])
    code, out, err = world.conduct("status")
    assert (code, err) == (0, "")
    for line in out.splitlines():
        assert "  pace normal  cannot start: " in line and "alive" not in line
    assert (row(world, "recipes")["live"], row(world, "nowhere")["live_note"]) == (None, None)


def test_the_project_s_folder_matches_through_a_link_a_trailing_slash_and_a_tilde(world):
    folder = claw(world, "fresh")
    os.symlink(world.code, os.path.join(world.home, "link to code"))
    world.write_conf("CODE_DIR=~/link to code/\n")
    world.live([listed(folder + "/")])
    assert after_pace(world.conduct("status")[1]) == 'alive ("soups-tools · 18 October", idle)'
    world.live([listed(os.path.join(world.home, "link to code", "soups-tools"))])
    assert after_pace(world.conduct("status")[1]) == 'alive ("soups-tools · 18 October", idle)'


# --- the listing cannot be read: status is as before, and says so in one line ---

def as_before(world):
    """What status prints with no claude at all, less the one line: the lines of before this was built."""
    return ("soups-tools  stale  code      on duty mac, last beat 2026-10-18T09:30:00Z (10 minutes ago)"
            "  new 0  open 0  pace normal\n")


@pytest.mark.parametrize("printed, why", [
    ("", "claude agents --json did not print the expected JSON"),
    ("Please sign in to continue.", "claude agents --json did not print the expected JSON"),
    ('{"sessions": []}', "claude agents --json did not print the expected JSON"),
    ("[{\"cwd\": ", "claude agents --json did not print the expected JSON"),
])
def test_a_listing_that_is_not_the_expected_json_leaves_status_as_before_with_one_line(world, printed, why):
    claw(world, "stale")
    world.live(printed)
    assert world.conduct("status") == (0, as_before(world), UNREAD.format(why))
    code, out, err = world.conduct("status", "--json")
    said = json.loads(out)
    assert (code, err) == (0, UNREAD.format(why))
    assert said["live_listing"] == {"read": False, "why": why}
    assert (said["mailboxes"][0]["live"], said["mailboxes"][0]["live_note"]) == (None, None)


def test_a_claude_that_fails_leaves_status_as_before_with_one_line(world):
    folder = claw(world, "stale")
    world.live([listed(folder)])
    world.fail("claude:agents:3")
    assert world.conduct("status") == (
        0, as_before(world), UNREAD.format("claude agents --json failed (exit 3)"))


def test_no_claude_on_path_and_no_setting_leaves_status_as_before_with_one_line(world):
    claw(world, "stale")
    os.remove(os.path.join(world.bin, "claude"))
    assert world.conduct("status") == (0, as_before(world), UNREAD.format("claude was not found"))
    code, out, err = world.conduct("status", "--json")
    assert (code, err) == (0, UNREAD.format("claude was not found"))
    assert json.loads(out)["live_listing"] == {"read": False, "why": "claude was not found"}


# --- the setting, and what is run ---

def test_the_setting_claude_names_the_command_and_a_tilde_is_the_home_folder(world):
    folder = claw(world, "fresh")
    world.live([listed(folder)])
    tools = os.path.join(world.home, "my tools")
    os.makedirs(tools)
    os.rename(os.path.join(world.bin, "claude"), os.path.join(tools, "claude"))     # the stand-in acts by its name
    world.write_conf("CLAUDE=~/my tools/claude\n")
    code, out, err = world.conduct("status")
    assert (code, err) == (0, "") and after_pace(out) == 'alive ("soups-tools · 18 October", idle)'
    world.write_conf(f"CLAUDE={os.path.join(world.home, 'nowhere', 'claude')}\n")
    assert world.conduct("status")[2] == UNREAD.format(f"{world.home}/nowhere/claude was not found")


def test_status_runs_claude_once_with_agents_json_and_writes_nothing(world):
    folder = claw(world, "stale")
    world.live([listed(folder)])
    projects = os.path.join(world.home, "projects")
    before = tree(projects)
    assert world.conduct("status")[0] == 0
    assert tree(projects) == before
    assert [(c["prog"], c["args"]) for c in world.calls()] == [
        ("lobster-mail", ["duty", "status", "--all", "--json", "--root", world.mail]),
        ("claude", ["agents", "--json"])]


def test_status_with_no_mailboxes_still_says_whether_the_listing_was_read(world):
    world.listing([])
    assert world.conduct("status") == (0, f"No mailboxes in {world.mail}.\n", "")
    assert json.loads(world.conduct("status", "--json")[1]) == {
        "root": world.mail, "mailboxes": [], "skipped": [], "live_listing": {"read": True, "why": None},
        "live_elsewhere": []}


def test_the_readme_s_example_is_what_status_prints(world):
    _nc, tools, _video = a_pair(world)
    world.listing([entry("recipes", "fresh", new=2, reported=DREAMING), entry("recipes-tools", handover=True),
                   entry("video-tools", "stale", pace="relaxed")])
    world.live([listed(tools, name="recipes-tools · 18 October")])
    code, out, err = world.conduct("status")
    assert (code, err) == (0, "")
    with open(os.path.join(os.path.dirname(__file__), "..", "..", "README.md"), encoding="utf-8") as f:
        readme = f.read()
    assert "  $ ./conduct status\n" + "".join("  " + line + "\n" for line in out.splitlines()) in readme
    assert out.splitlines()[1].endswith(
        'pace normal  alive after its handover: not archived ("recipes-tools · 18 October", idle)')


def test_help_says_status_shows_whether_a_session_is_alive(world):
    code, out, err = world.conduct("--help")
    assert (code, err) == (0, "")
    assert "whether a session is alive in its folder" in " ".join(out.split())


# --- what the live session is running on, and sessions elsewhere (Request 28, Settled 175) ---

def test_live_says_the_model_the_effort_and_the_time_of_the_session_s_newest_reply(world):
    folder = claw(world, "fresh")
    world.live([listed(folder)])
    path = transcript(world)
    with open(path, "rb") as f:
        before = f.read()
    found = row(world)["live"]
    assert (found["id"], found["model"], found["effort"], found["last_reply"]) == (
        CLI, "invented-model-7", "xhigh", "2026-10-18T09:12:00Z")
    assert list(found) == ["name", "status", "kind", "started", "pid", "count", "id", "model", "effort", "last_reply"]
    with open(path, "rb") as f:
        assert f.read() == before
    assert "private words" not in world.conduct("status", "--json")[1]


def test_the_transcript_is_the_one_named_by_the_session_given_and_is_looked_for_where_the_setting_says(world, tmp_path):
    folder = claw(world, "fresh")
    other = "11111111-1111-4111-8111-111111111111"
    world.live([listed(folder, name="older", sid=other), listed(folder, name="newer", started=1792051260000)])
    transcript(world, other, model="the-older-one")
    transcript(world, CLI, model="the-newer-one", root=str(tmp_path / "my transcripts"))
    assert row(world)["live"]["model"] is None                  # the newer session's is not where the default looks
    world.write_conf(f"APP_TRANSCRIPTS={tmp_path / 'my transcripts'}\n")
    assert (row(world)["live"]["name"], row(world)["live"]["model"]) == ("newer", "the-newer-one")


@pytest.mark.parametrize("sid", [None, 7, "../../etc/passwd", "*", "not-an-id"])
def test_a_session_whose_id_names_no_transcript_has_no_model_effort_or_time(world, sid):
    folder = claw(world, "fresh")
    transcript(world)
    world.live([listed(folder, sid=sid)])
    found = row(world)["live"]
    assert (found["model"], found["effort"], found["last_reply"]) == (None, None, None)
    assert found["id"] == (sid if isinstance(sid, str) else None)


def test_the_text_form_says_nothing_of_the_model_the_effort_or_the_reply(world):
    folder = claw(world, "fresh")
    world.live([listed(folder)])
    plain = world.conduct("status")
    transcript(world)
    assert world.conduct("status") == plain
    assert "invented-model-7" not in plain[1] and "xhigh" not in plain[1]


def test_sessions_alive_in_no_listed_mailbox_s_folder_are_listed_elsewhere_oldest_first(world):
    folder = claw(world, "fresh")
    nc = ganglion(world)                                        # recipes, in Claude Cowork, and recipes-tools
    world.listing([entry("soups-tools", "fresh"), entry("recipes"), entry("recipes-tools")])
    away = os.path.join(world.home, "some where")
    os.makedirs(away)
    os.symlink(away, os.path.join(world.home, "a link"))
    inside = os.path.join(folder, "soups-tools")
    world.live([listed(inside, name="inside a project", started=1792051320000, pid=3, status="busy"),
                listed(os.path.join(world.home, "a link") + "/", name='away "x" </script>', pid=2, kind="background"),
                listed(folder), listed(nc, name="in a Cowork project's folder")])
    said = json.loads(world.conduct("status", "--json")[1])
    assert said["live_elsewhere"] == [
        {"folder": os.path.realpath(away), "name": 'away "x" </script>', "status": "idle", "kind": "background",
         "started": "2026-10-15T08:00:00Z", "pid": 2},
        {"folder": os.path.realpath(inside), "name": "inside a project", "status": "busy", "kind": "interactive",
         "started": "2026-10-15T08:02:00Z", "pid": 3}]
    assert world.conduct("status")[1].count("\n") == 3         # and the text form has a line for each mailbox only


def test_with_the_listing_unread_elsewhere_is_null_not_an_empty_list(world):
    claw(world, "fresh")
    world.fail("claude")
    assert json.loads(world.conduct("status", "--json")[1])["live_elsewhere"] is None
    os.remove(os.path.join(world.bin, "fail"))
    assert json.loads(world.conduct("status", "--json")[1])["live_elsewhere"] == []


def test_each_row_says_where_its_session_runs(world):
    ganglion(world)                                             # recipes (Claude Cowork) and recipes-tools
    feeler(world)
    world.conductor("maestro")
    world.project("maestro-tools", "code", sister="maestro")
    mac = world.project("stews", "non-code")
    world.project("stews-tools", "code")
    with open(os.path.join(mac, "lobster.conf"), "a") as f:
        f.write("SESSION=code\n")
    lost = world.project("lost", "non-code")                    # its sister is not there: start would refuse
    assert os.path.isdir(lost)
    names = ["recipes", "recipes-tools", "agents", "maestro", "maestro-tools", "stews", "stews-tools", "lost", "nowhere"]
    world.listing([entry(name) for name in names])
    rows = {r["mailbox"]: r for r in json.loads(world.conduct("status", "--json")[1])["mailboxes"]}
    assert {name: rows[name]["runs_in"] for name in names} == {
        "recipes": "cowork", "recipes-tools": "code", "agents": "cowork", "maestro": "code", "maestro-tools": "code",
        "stews": "code", "stews-tools": "code", "lost": None, "nowhere": None}
    assert list(rows["recipes"])[-3:] == ["live", "live_note", "runs_in"]
    world.fail("claude")
    again = {r["mailbox"]: r["runs_in"] for r in json.loads(world.conduct("status", "--json")[1])["mailboxes"]}
    assert again == {name: rows[name]["runs_in"] for name in names}     # whether or not the listing was read
