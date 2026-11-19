"""What conduct stop, dormant and reset say of a stale duty once the listing of live sessions is read
(PLAN.md, "Whether a session is alive", 5; Settled 174). Words only: what each verb does is as before, and
with the listing unread, or for a project that does not run on the Mac, so are its words."""

import os

import pytest
from test_conduct_live import DORMANT, NAME, listed
from test_conduct_status import entry
from test_session_setting import ganglion

BEAT = "2026-10-18T09:30:00Z"
ONE = '("soups-tools · 18 October", idle)'


def claws(world, soups="stale", stews=None, **how):
    """Two lone tools projects, soups-tools and stews-tools; their folders."""
    folders = (world.project("soups-tools", "code", sister=""), world.project("stews-tools", "code", sister=""))
    world.listing([entry("soups-tools", soups, **how), entry("stews-tools", stews)])
    return folders


def progs(world):
    return [(c["prog"], c["args"][0]) for c in world.calls()]


def alive_words(verb, lead=f"soups-tools's duty is stale (last beat {BEAT})", sessions=ONE):
    message, then = {"stop": ("Stop", "stop it"), "dormant": ("Dormant", "make it dormant")}[verb]
    return (f"{lead} and a session is alive in its folder {sessions}: it is not watching mail, so a {message} "
            f"would wait until Squirrel next types to it, and none was sent. Speak to that session in the app "
            f"first, then {then}.\n")


def gone_words(verb, lead=f"soups-tools's duty is stale (last beat {BEAT})"):
    message = {"stop": "Stop", "dormant": "Dormant"}[verb]
    return (f"{lead} and no session is alive in its folder: it ended without a handover, and no {message} was "
            "sent. conduct reset soups-tools clears it.\n")


AS_BEFORE = {"stop": "Nobody is on duty for soups-tools: nothing to stop.\n",
             "dormant": "Nobody is on duty for soups-tools: nothing to make dormant.\n"}


# --- stop and dormant, one project ---

@pytest.mark.parametrize("verb", ["stop", "dormant"])
def test_a_stale_duty_with_a_session_alive_is_said_so_and_nothing_is_sent(world, verb):
    soups, _stews = claws(world)
    world.live([listed(soups)])
    assert world.conduct(verb, "soups-tools") == (0, alive_words(verb), "")
    assert world.conduct(verb, "--dry-run", "soups-tools") == (0, alive_words(verb), "")
    assert progs(world) == [("lobster-mail", "duty"), ("claude", "agents")] * 2


@pytest.mark.parametrize("verb", ["stop", "dormant"])
def test_a_stale_duty_with_no_session_alive_is_said_to_have_ended_without_a_handover(world, verb):
    claws(world)
    assert world.conduct(verb, "soups-tools") == (0, gone_words(verb), "")
    assert progs(world) == [("lobster-mail", "duty"), ("claude", "agents")]


@pytest.mark.parametrize("verb", ["stop", "dormant"])
def test_a_duty_stale_at_the_relaxed_pace_is_spoken_of_in_the_same_words(world, verb):
    soups, _stews = claws(world, pace="relaxed")
    world.live([listed(soups)])
    assert world.conduct(verb, "soups-tools") == (0, alive_words(verb), "")


def test_stop_of_a_dormant_session_whose_duty_is_stale_keeps_its_lead_and_says_what_is_alive(world):
    soups, _stews = claws(world, reported=DORMANT)
    lead = f"soups-tools reports itself dormant and its duty is stale (last beat {BEAT})"
    assert world.conduct("stop", "soups-tools") == (0, gone_words("stop", lead), "")
    world.live([listed(soups, status="busy")])
    assert world.conduct("stop", "soups-tools") == (
        0, alive_words("stop", lead, '("soups-tools · 18 October", busy)'), "")


@pytest.mark.parametrize("verb", ["stop", "dormant"])
def test_every_session_alive_in_the_folder_is_named(world, verb):
    soups, _stews = claws(world)
    world.live([listed(soups, name="first"), listed(soups, name='se"cond', started=1792051260000, status="busy")])
    then = {"stop": "stop it", "dormant": "make it dormant"}[verb]
    assert world.conduct(verb, "soups-tools")[1] == alive_words(
        verb, sessions='("first", idle; "se\\"cond", busy)').replace(
            "a session is alive", "2 sessions are alive").replace(
            f"Speak to that session in the app first, then {then}.", "Speak to them in the app first.")


@pytest.mark.parametrize("verb", ["stop", "dormant"])
@pytest.mark.parametrize("broken", ["not found", "fails", "not json"])
def test_with_the_listing_unread_the_words_are_exactly_as_before(world, verb, broken):
    soups, _stews = claws(world)
    world.live([listed(soups)] if broken != "not json" else "Please sign in.")
    if broken == "not found":
        os.remove(os.path.join(world.bin, "claude"))
    if broken == "fails":
        world.fail("claude")
    assert world.conduct(verb, "soups-tools") == (0, AS_BEFORE[verb], "")


def test_stop_of_a_dormant_session_with_the_listing_unread_is_as_before(world):
    claws(world, reported=DORMANT)
    world.fail("claude")
    assert world.conduct("stop", "soups-tools") == (
        0, (f"soups-tools reports itself dormant and its duty is stale (last beat {BEAT}): it is not watching "
            "mail, so a Stop would wait until Squirrel next types to it, and none was sent. Speak to that session "
            "in the app first, then stop it.\n"), "")


@pytest.mark.parametrize("verb, before", [
    ("stop", "Nobody is on duty for recipes: nothing to stop.\n"),
    ("dormant", "Nobody is on duty for recipes: nothing to make dormant.\n")])
def test_a_cowork_project_and_a_mailbox_with_no_project_are_as_before_and_claude_is_not_run(world, verb, before):
    folder = ganglion(world)
    world.listing([entry("recipes", "stale"), entry("nowhere", "stale")])
    world.live([listed(folder)])
    assert world.conduct(verb, "recipes") == (0, before, "")
    assert world.conduct(verb, "nowhere") == (0, before.replace("recipes", "nowhere"), "")
    assert progs(world) == [("lobster-mail", "duty")] * 2


@pytest.mark.parametrize("verb", ["stop", "dormant"])
def test_a_ganglion_on_the_mac_is_looked_at(world, verb):
    folder = ganglion(world, "SESSION=code")
    world.listing([entry("recipes", "stale")])
    world.live([listed(folder, name="recipes · 18 October")])
    assert world.conduct(verb, "recipes")[1] == alive_words(
        verb, f"recipes's duty is stale (last beat {BEAT})", '("recipes · 18 October", idle)')


@pytest.mark.parametrize("argv", [("stop", "soups-tools"), ("dormant", "soups-tools"), ("stop", "stews-tools"),
                                  ("dormant", "stews-tools"), ("stop", "--all"), ("dormant", "--all"),
                                  ("wake", "soups-tools"), ("dream", "soups-tools"), ("wake", "--all")])
def test_claude_is_not_run_where_no_stale_duty_is_spoken_of(world, argv):
    claws(world, soups="fresh")
    assert world.conduct(*argv)[0] == 0
    assert "claude" not in [c["prog"] for c in world.calls()]


@pytest.mark.parametrize("argv", [("wake", "soups-tools"), ("wake", "--all"), ("dream", "soups-tools"),
                                  ("dream", "--all"), ("finish", "soups-tools")])
def test_wake_dream_and_finish_never_run_claude_even_for_a_stale_duty(world, argv):
    claws(world)
    world.conduct(*argv)
    assert "claude" not in [c["prog"] for c in world.calls()]


@pytest.mark.parametrize("verb", ["stop", "dormant", "reset"])
def test_the_verbs_run_the_claude_the_setting_names(world, verb):
    soups, _stews = claws(world)
    world.live([listed(soups)])
    tools = os.path.join(world.home, "my tools")
    os.makedirs(tools)
    os.rename(os.path.join(world.bin, "claude"), os.path.join(tools, "claude"))
    world.write_conf("CLAUDE=~/my tools/claude\n")
    assert f"a session is alive in its folder {ONE}" in world.conduct(verb, "--dry-run", "soups-tools")[1].replace(
        "A session", "a session")


# --- stop and dormant, --all ---

def sent(world):
    return [c["args"][c["args"].index("--to") + 1] for c in world.calls()
            if c["prog"] == "lobster-mail" and c["args"][0] == "send"]


@pytest.mark.parametrize("verb", ["stop", "dormant"])
def test_all_sends_to_the_fresh_and_says_of_each_stale_duty_passed_over_what_is_alive(world, verb):
    soups = world.project("soups-tools", "code", sister="")
    world.project("stews-tools", "code", sister="")
    world.project("pies-tools", "code", sister="")
    world.listing([entry("soups-tools", "stale"), entry("stews-tools", "stale"), entry("pies-tools", "fresh")])
    world.live([listed(soups)])
    code, out, err = world.conduct(verb, "--all")
    assert (code, err) == (0, "") and sent(world) == ["pies-tools"]
    assert out.endswith(alive_words(verb) + gone_words(verb).replace("soups-tools", "stews-tools"))
    assert [c["prog"] for c in world.calls()].count("claude") == 1


@pytest.mark.parametrize("verb", ["stop", "dormant"])
def test_all_as_a_dry_run_says_the_same_after_its_last_line_and_sends_nothing(world, verb):
    soups, _stews = claws(world, stews="fresh")
    world.live([listed(soups)])
    code, out, err = world.conduct(verb, "--all", "--dry-run")
    assert (code, err) == (0, "") and sent(world) == []
    last = {"stop": "Dry run: nothing was sent.\n", "dormant": "Dry run: nothing was sent or set.\n"}[verb]
    assert out.endswith(last + alive_words(verb))


@pytest.mark.parametrize("verb, nothing", [
    ("stop", "Nobody is on duty anywhere but bernstein: nothing to stop.\n"),
    ("dormant", "Nobody is on duty anywhere but bernstein: nothing to make dormant.\n")])
def test_all_with_nobody_fresh_says_of_each_stale_duty_what_is_alive_and_then_that_there_is_nothing(world, verb, nothing):
    claws(world)
    assert world.conduct(verb, "--all") == (0, gone_words(verb) + nothing, "")


@pytest.mark.parametrize("verb", ["stop", "dormant"])
def test_all_with_the_listing_unread_passes_a_stale_duty_over_as_before(world, verb):
    claws(world, stews="fresh")
    world.fail("claude")
    plain = world.conduct(verb, "--all")
    assert plain[0] == 0 and "stale" not in plain[1] and sent(world) == ["stews-tools"]


def test_all_never_speaks_of_a_conductor_s_own_stale_duty(world):
    conductor = world.conductor("maestro")
    world.project("maestro-tools", "code", sister="maestro")
    world.listing([entry("maestro", "stale"), entry("bernstein", "stale"), entry("maestro-tools", "fresh")])
    world.live([listed(conductor)])
    out = world.conduct("stop", "--all", "--dry-run")[1]
    assert "stale" not in out and "claude" not in [c["prog"] for c in world.calls()]


# --- reset ---

def reset_lead(holder="mac"):
    return f"soups-tools: {holder} is on duty but stale (last beat {BEAT})."


ALIVE_RESET = (" A session is alive in its folder {}, not watching mail. Reset is for a session that is gone: speak "
               "to that session in the app, or stop it there, before you reset it.\n")
GONE_RESET = " No session is alive in its folder: it ended without a handover, which is what reset is for.\n"


@pytest.mark.parametrize("how", [{}, {"reported": DORMANT}, {"pace": "relaxed"}])
def test_reset_says_first_that_a_session_is_alive_and_still_does_what_it_did(world, how):
    soups, _stews = claws(world, **how)
    world.live([listed(soups)])
    code, out, err = world.conduct("reset", "--dry-run", "soups-tools")
    assert (code, err) == (0, "")
    assert out.startswith(reset_lead() + ALIVE_RESET.format(ONE) + "Would close nothing")
    assert out.endswith("Dry run: nothing was closed, given up or sent.\n")
    code, out, err = world.conduct("reset", "soups-tools")
    assert (code, err) == (0, "")
    assert out.startswith(reset_lead() + ALIVE_RESET.format(ONE))
    assert out.endswith("soups-tools is reset: conduct start soups-tools will start it afresh.\n")
    assert [c["args"][0] for c in world.calls() if c["prog"] == "lobster-mail"][-1] == "handover"


@pytest.mark.parametrize("how", [{}, {"reported": DORMANT}, {"pace": "relaxed"}])
def test_reset_says_that_no_session_is_alive_in_place_of_telling_him_to_look(world, how):
    claws(world, **how)
    out = world.conduct("reset", "--dry-run", "soups-tools")[1]
    assert out.startswith(reset_lead() + GONE_RESET + "Would close nothing")
    assert "Look at it in the app" not in out and "only if that session is gone" not in out


def test_reset_looks_at_a_ganglion_on_the_mac(world):
    folder = ganglion(world, "SESSION=code")
    world.listing([entry("recipes", "stale")])
    world.live([listed(folder, name="recipes · 18 October")])
    assert world.conduct("reset", "--dry-run", "recipes")[1].startswith(
        f"recipes: mac is on duty but stale (last beat {BEAT})."
        + ALIVE_RESET.format('("recipes · 18 October", idle)'))


def test_reset_names_every_session_alive(world):
    soups, _stews = claws(world)
    world.live([listed(soups, name="First"), listed(soups, name="SECOND", started=1792051260000)])
    assert world.conduct("reset", "--dry-run", "soups-tools")[1].startswith(
        reset_lead() + ' 2 sessions are alive in its folder ("First", idle; "SECOND", idle), not watching mail. '
        "Reset is for a session that is gone: speak to them in the app, or stop them there, before you reset it.\n")


def test_reset_with_the_listing_unread_and_of_a_cowork_project_is_as_before(world):
    claws(world, reported=DORMANT)
    world.fail("claude")
    out = world.conduct("reset", "--dry-run", "soups-tools")[1]
    assert out.startswith(reset_lead() + " It reported itself dormant. A dormant session on the Mac keeps a quiet "
                          "watch that keeps its duty fresh, so a stale duty means that watch has ended")
    folder = ganglion(world)
    world.listing([entry("recipes", "stale", pace="relaxed")])
    os.remove(os.path.join(world.bin, "fail"))
    world.live([listed(folder)])
    out = world.conduct("reset", "--dry-run", "recipes")[1]
    assert out.startswith(f"recipes: mac is on duty but stale (last beat {BEAT}). Its mail pace is relaxed, at "
                          "which a live session's duty is stale between turns")
    assert [c["prog"] for c in world.calls()].count("claude") == 1      # the first run's, not the Cowork project's


def test_reset_with_nobody_on_duty_or_a_fresh_duty_does_not_run_claude(world):
    claws(world, soups=None, stews="fresh")
    assert world.conduct("reset", "soups-tools")[0] == 0
    assert world.conduct("reset", "stews-tools")[0] == 3
    assert "claude" not in [c["prog"] for c in world.calls()]


def test_the_name_of_a_session_is_never_more_than_data_in_these_words(world):
    soups, _stews = claws(world)
    world.live([listed(soups, name='x"; rm -rf $HOME\n</script> é')])
    for verb in ("stop", "dormant", "reset"):
        out = world.conduct(verb, "--dry-run", "soups-tools")[1]
        assert '("x\\"; rm -rf $HOME\\n</script> é", idle)' in out
    assert NAME not in out
