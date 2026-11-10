import pytest

from bernstein import podium

NAMES = {"bernstein", "recipes", "recipes-tools", "video tools"}


@pytest.mark.parametrize("action, argv, brief", [
    ({"verb": "start", "project": "recipes"}, ["start", "recipes"], None),
    ({"verb": "start", "project": "recipes", "pace": "eager"}, ["start", "recipes", "--pace", "eager"], None),
    ({"verb": "start", "project": "recipes", "brief": "Draft the menu.\n"}, ["start", "recipes"], "Draft the menu.\n"),
    ({"verb": "start", "project": "recipes", "brief": "", "pace": None}, ["start", "recipes"], None),
    ({"verb": "stop", "project": "recipes-tools"}, ["stop", "recipes-tools"], None),
    ({"verb": "stop", "project": "recipes", "wait": 120}, ["stop", "recipes", "--wait", "120"], None),
    ({"verb": "stop", "all": True}, ["stop", "--all"], None),
    ({"verb": "stop", "all": True, "wait": 1}, ["stop", "--all", "--wait", "1"], None),
    ({"verb": "dormant", "project": "video tools"}, ["dormant", "video tools"], None),
    ({"verb": "dormant", "all": True}, ["dormant", "--all"], None),
    ({"verb": "wake", "project": "recipes"}, ["wake", "recipes"], None),
    ({"verb": "wake", "all": True}, ["wake", "--all"], None),
    ({"verb": "dream", "project": "recipes"}, ["dream", "recipes", "--minutes", "60", "--then", "dormant"], None),
    ({"verb": "dream", "project": "recipes", "minutes": 5, "then": "stop"},
     ["dream", "recipes", "--minutes", "5", "--then", "stop"], None),
    ({"verb": "dream", "all": True, "minutes": 240, "then": "dormant"},
     ["dream", "--all", "--minutes", "240", "--then", "dormant"], None),
    ({"verb": "stop", "project": "recipes", "all": False}, ["stop", "recipes"], None),
])
def test_an_action_from_the_page_becomes_conduct_s_arguments(action, argv, brief):
    assert podium.command_for(action, NAMES) == (argv, brief)


@pytest.mark.parametrize("action, why", [
    ("stop recipes", "an action must be a JSON object"),
    (["stop"], "an action must be a JSON object"),
    ({}, "podium does not offer the verb None"),
    ({"verb": "status"}, "podium does not offer the verb 'status'"),
    ({"verb": "rm", "project": "recipes"}, "podium does not offer the verb 'rm'"),
    ({"verb": ["stop"], "project": "recipes"}, "podium does not offer the verb ['stop']"),
    ({"verb": "stop"}, "name one project, or everything at once"),
    ({"verb": "stop", "project": "recipes", "all": True}, "name one project, or everything at once"),
    ({"verb": "stop", "all": "yes"}, "name one project, or everything at once"),
    ({"verb": "start", "all": True}, "start is for one project at a time"),
    ({"verb": "stop", "project": "nope"}, "'nope' is not a mailbox in the listing podium last showed"),
    ({"verb": "stop", "project": "--all"}, "'--all' is not a mailbox in the listing podium last showed"),
    ({"verb": "stop", "project": 7}, "7 is not a mailbox in the listing podium last showed"),
    ({"verb": "stop", "project": "bernstein"}, "podium does not act on bernstein's own session"),
    ({"verb": "stop", "project": "recipes", "dry_run": True}, "stop does not take dry_run"),
    ({"verb": "stop", "project": "recipes", "minutes": 60}, "stop does not take minutes"),
    ({"verb": "dormant", "project": "recipes", "wait": 5}, "dormant does not take wait"),
    ({"verb": "wake", "all": True, "pace": "eager"}, "wake does not take pace"),
    ({"verb": "dream", "project": "recipes", "brief": "x"}, "dream does not take brief"),
    ({"verb": "start", "project": "recipes", "pace": "fast"}, "the pace must be eager, normal or relaxed"),
    ({"verb": "start", "project": "recipes", "brief": 3}, "the brief must be text"),
    ({"verb": "start", "project": "recipes", "brief": "x" * 20001}, "the brief is longer than 20000 characters"),
    ({"verb": "stop", "project": "recipes", "wait": 0}, "the wait must be a whole number of seconds from 1 to 600"),
    ({"verb": "stop", "project": "recipes", "wait": 601}, "the wait must be a whole number of seconds from 1 to 600"),
    ({"verb": "stop", "project": "recipes", "wait": "60"}, "the wait must be a whole number of seconds from 1 to 600"),
    ({"verb": "stop", "project": "recipes", "wait": True}, "the wait must be a whole number of seconds from 1 to 600"),
    ({"verb": "dream", "project": "recipes", "minutes": 4}, "the minutes must be a whole number from 5 to 240"),
    ({"verb": "dream", "project": "recipes", "minutes": 241}, "the minutes must be a whole number from 5 to 240"),
    ({"verb": "dream", "project": "recipes", "minutes": 60.5}, "the minutes must be a whole number from 5 to 240"),
    ({"verb": "dream", "project": "recipes", "then": "sleep"}, "then must be dormant or stop"),
])
def test_an_action_podium_does_not_offer_is_refused_with_the_reason(action, why):
    with pytest.raises(podium.Refused) as refused:
        podium.command_for(action, NAMES)
    assert str(refused.value) == why


def test_a_name_that_looks_like_a_flag_is_refused_even_if_a_mailbox_has_it():
    with pytest.raises(podium.Refused) as refused:
        podium.command_for({"verb": "stop", "project": "-x"}, {"-x"})
    assert str(refused.value) == "'-x' cannot be given to conduct as a project: it starts with a dash"


def test_the_command_is_shown_as_it_could_be_typed_and_a_brief_by_its_length():
    assert podium.shown(["stop", "recipes"], None) == "conduct stop recipes"
    assert podium.shown(["dormant", "video tools"], None) == "conduct dormant 'video tools'"
    assert podium.shown(["start", "recipes", "--pace", "eager"], "Draft the menu.\n") == \
        "conduct start recipes --pace eager --brief <the brief typed in podium, 16 characters>"
    assert podium.shown(["stop", "--all"], None, dry_run=True) == "conduct stop --all --dry-run"
