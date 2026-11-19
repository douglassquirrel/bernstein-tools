"""podium's line says what conduct status --json says is alive in a project's folder (PLAN.md, "Whether a
session is alive", 6). podium works nothing out: it prints `live` and `live_note` as they are given."""

import pytest
from test_podium_view import NOW, row

from bernstein import podium

LIVE = {"name": "soups-tools · 18 October", "status": "idle", "kind": "interactive",
        "started": "2026-10-18T07:36:00Z", "pid": 4242, "count": 1}


def line(state="running", duty="mac", **more):
    return podium.row_html(dict(row("soups-tools", state, duty=duty), **more), NOW)


def test_a_row_from_a_conduct_that_says_nothing_of_live_sessions_is_drawn_as_before():
    assert 'class="live' not in line()
    assert line(live=None, live_note=None) == line()


def test_a_session_alive_is_said_with_its_name_and_busy_or_idle_after_who_is_on_duty():
    html = line(live=LIVE, live_note=None)
    assert ('<ul class="facts"><li>Claude Code, 3 min ago</li>'
            '<li class="live">alive (soups-tools · 18 October, idle)</li><li>opus, high</li></ul>') in html
    assert '<li class="live">alive (soups-tools · 18 October, busy)</li>' in line(live=dict(LIVE, status="busy"),
                                                                                  live_note=None)


@pytest.mark.parametrize("state, duty, note", [
    ("stale", "mac", "alive, not watching mail"),
    ("handed-over", None, "alive after its handover: not archived"),
    ("off", None, "alive, not on duty"),
    ("running", "mac", "2 sessions alive in its folder"),
])
def test_the_note_leads_where_the_duty_and_the_listing_disagree(state, duty, note):
    assert f'<li class="live">{note} (soups-tools · 18 October, idle)</li>' in line(
        state, duty, live=LIVE, live_note=note)


@pytest.mark.parametrize("note", ["no session alive: it ended without a handover",
                                  "no session alive, though its duty is fresh: a watch has outlived its session"])
def test_a_note_with_no_session_is_said_alone(note):
    assert f'<li class="live">{note}</li>' in line("stale", live=None, live_note=note)


def test_a_project_that_is_off_with_no_session_and_no_note_says_nothing_as_the_usual_goes_unsaid():
    html = line("off", None, live=None, live_note=None)
    assert "alive" not in html


def test_a_name_and_a_note_are_text_on_the_page_never_markup():
    odd = dict(LIVE, name='<script>alert("x")</script> & é', status="<b>idle</b>")
    html = line(live=odd, live_note="<i>alive</i>")
    assert ('<li class="live">&lt;i&gt;alive&lt;/i&gt; (&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; é, '
            "&lt;b&gt;idle&lt;/b&gt;)</li>") in html
    assert "<script>" not in html and "<i>" not in html


@pytest.mark.parametrize("found, said", [
    (dict(LIVE, name=None), "alive (a session with no name, idle)"),
    (dict(LIVE, name=7), "alive (a session with no name, idle)"),
    (dict(LIVE, status=None), "alive (soups-tools · 18 October, status not known)"),
    (dict(LIVE, status=["idle"]), "alive (soups-tools · 18 October, status not known)"),
    ({}, "alive (a session with no name, status not known)"),
])
def test_a_fact_conduct_could_not_give_is_said_as_not_known(found, said):
    assert f'<li class="live">{said}</li>' in line(live=found, live_note=None)


@pytest.mark.parametrize("found, note", [("alive", None), (["a"], None), (7, None), (None, 7), (None, ["x"]),
                                         (True, {"a": 1})])
def test_live_and_a_note_that_are_not_the_shape_conduct_gives_say_nothing(found, note):
    assert 'class="live' not in line(live=found, live_note=note)
