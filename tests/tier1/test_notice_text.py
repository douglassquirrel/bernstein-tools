"""notice's text: the places in a body, filling them, and the facts file (PLAN.md, "notice", Settled 162)."""

import datetime
import json

import pytest

from bernstein import facts
from bernstein.notice import filled, places

BODY = ("Notice for {{PROJECT}}.\n\nYour Backlog was moved on {{WHEN}} to {{KEPT}},\nin {{FOLDER}}. {{WHEN}} again.\n"
        "Left alone: {{to fill: x}}, {{lower}}, {{ WHEN }}, {WHEN}, {{> sections/x.md}} and {{A1}}.\n")


def test_the_places_in_a_body_are_the_capitals_in_double_braces_each_once_in_order():
    assert places(BODY) == ["PROJECT", "WHEN", "KEPT", "FOLDER"]
    assert places("Nothing to fill here: {{to fill: later}}.\n") == [] and places("") == []
    assert places("{{A_B}}{{A}}{{A_B}}{{_}}") == ["A_B", "A", "_"]


def test_each_place_is_filled_and_everything_else_in_braces_is_left_exactly_as_written():
    got = filled(BODY, {"PROJECT": "recipes", "WHEN": "14 November 2026, 11:47Z", "KEPT": "/p/_to_delete/x",
                        "FOLDER": "/p", "UNUSED": "never seen"})
    assert got == ("Notice for recipes.\n\nYour Backlog was moved on 14 November 2026, 11:47Z to /p/_to_delete/x,\n"
                   "in /p. 14 November 2026, 11:47Z again.\n"
                   "Left alone: {{to fill: x}}, {{lower}}, {{ WHEN }}, {WHEN}, {{> sections/x.md}} and {{A1}}.\n")


@pytest.mark.parametrize("value", [
    "{{PROJECT}} and {{KEPT}}", "it's $HOME `id` $(id)", "back\\slash \\1 \\g<0>", "</script><b>", "café café",
    "two\nlines\r\n", "", "%s {} {0}",
])
def test_a_fact_is_data_put_in_once_and_never_filled_itself(value):
    assert filled("a {{KEPT}} b {{PROJECT}} c\n", {"KEPT": value, "PROJECT": "recipes"}) == f"a {value} b recipes c\n"


def test_a_facts_file_is_a_block_of_named_text_for_each_project_and_round_trips():
    data = {"recipes": {"KEPT": "/p/it's \"here\" café", "WHEN": "14 November 2026, 11:47Z"}, "menus": {}}
    text = facts.text_of(data)
    assert text.endswith("}\n") and "café" in text and json.loads(text) == data
    assert facts.read(text, "f.json") == data
    assert facts.read("{}", "f.json") == {}


@pytest.mark.parametrize("text, why", [
    ("", "f.json is not JSON"),
    ("{recipes: 1}", "f.json is not JSON"),
    ("[]", "f.json is not a facts file: it must be one JSON object, with a block for each project"),
    ('"recipes"', "f.json is not a facts file: it must be one JSON object, with a block for each project"),
    ('{"recipes": ["KEPT"]}', "f.json: the block for recipes must be a JSON object of facts"),
    ('{"recipes": {"kept": "x"}}', ("f.json: recipes's fact 'kept' must be named in capitals and underscores, as "
     "its place in a notice is written")),
    ('{"recipes": {"KEPT IT": "x"}}', ("f.json: recipes's fact 'KEPT IT' must be named in capitals and underscores, "
     "as its place in a notice is written")),
    ('{"recipes": {"": "x"}}', ("f.json: recipes's fact '' must be named in capitals and underscores, as its place "
     "in a notice is written")),
    ('{"recipes": {"COUNT": 3}}', "f.json: recipes's fact COUNT must be text, in quotation marks"),
    ('{"recipes": {"KEPT": null}}', "f.json: recipes's fact KEPT must be text, in quotation marks"),
    ('{"recipes": {"PROJECT": "x"}}', "f.json: recipes's block gives PROJECT, which notice fills in itself"),
    ('{"recipes": {"FOLDER": "x"}}', "f.json: recipes's block gives FOLDER, which notice fills in itself"),
])
def test_a_file_that_is_not_a_facts_file_is_refused_saying_why(text, why):
    with pytest.raises(facts.FactsRefused) as refused:
        facts.read(text, "f.json")
    assert str(refused.value) == why


def test_when_is_the_day_and_the_time_in_utc_as_a_notice_says_it():
    assert facts.when(datetime.datetime(2026, 11, 4, 9, 7, tzinfo=datetime.timezone.utc)) == "4 November 2026, 09:07Z"
    assert facts.when(datetime.datetime(2026, 1, 31, 23, 59, tzinfo=datetime.timezone.utc)) == "31 January 2026, 23:59Z"


def test_recording_a_block_makes_the_file_or_adds_to_it_and_replaces_only_that_projects_block(tmp_path):
    path = str(tmp_path / "facts.json")
    assert facts.held(path) == {}
    facts.record(path, "recipes", {"KEPT": "/a café", "WHEN": "now"})
    facts.record(path, "menus", {"KEPT": "/b"})
    assert facts.held(path) == {"recipes": {"KEPT": "/a café", "WHEN": "now"}, "menus": {"KEPT": "/b"}}
    facts.record(path, "recipes", {"KEPT": "/c"})
    assert facts.held(path) == {"recipes": {"KEPT": "/c"}, "menus": {"KEPT": "/b"}}
    with open(path, encoding="utf-8") as f:
        assert f.read() == facts.text_of({"recipes": {"KEPT": "/c"}, "menus": {"KEPT": "/b"}})
    assert sorted(p.name for p in tmp_path.iterdir()) == ["facts.json"]         # no temporary file is left


def test_a_file_that_is_there_and_is_not_a_facts_file_is_never_added_to(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("Not facts.\n")
    for call in (lambda: facts.held(str(path)), lambda: facts.record(str(path), "recipes", {"KEPT": "/a"})):
        with pytest.raises(facts.FactsRefused) as refused:
            call()
        assert str(refused.value) == f"{path} is not JSON"
    assert path.read_text() == "Not facts.\n"
    path.write_bytes(b"\xff\xfe")
    with pytest.raises(facts.FactsRefused) as refused:
        facts.held(str(path))
    assert str(refused.value) == f"{path} is not plain UTF-8 text"
    with pytest.raises(facts.FactsRefused) as refused:
        facts.held(str(tmp_path))
    assert str(refused.value) == f"{tmp_path} cannot be read (Is a directory)"
