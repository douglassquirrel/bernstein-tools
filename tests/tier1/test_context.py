import json
import os

import pytest

from bernstein import context

SID = "local_11111111-1111-4111-8111-111111111111"
CLI = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
SESSION = {"id": SID, "link": "claude://claude.ai/epitaxy/" + SID, "app": "code", "last_activity": None}
PRIVATE = "private words that must never leave the transcript"


def reply(figures=(10, 2000, 30000), when="2026-10-18T09:30:07.123Z", side=False, **more):
    """One reply as a transcript holds it (invented): the fields that are read, and words that must not be."""
    usage = dict(zip(("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"), figures))
    usage.update(output_tokens=77, service_tier="standard")
    line = {"type": "assistant", "isSidechain": side, "timestamp": when, "uuid": "u-1",
            "message": {"model": "invented-model", "content": [{"type": "text", "text": PRIVATE}], "usage": usage}}
    line.update(more)
    return line


def said(text="hello"):
    return {"type": "user", "isSidechain": False, "timestamp": "2026-10-18T09:29:00.000Z",
            "message": {"role": "user", "content": text + " " + PRIVATE}}


def world(tmp_path, lines, cli=CLI, sid=SID, store="store", transcripts="projects", folder="-p-recipes-tools",
          end="\n"):
    """An invented store with one session's entry, and its transcript: (store, transcripts, the transcript)."""
    store, transcripts = str(tmp_path / store), str(tmp_path / transcripts)
    os.makedirs(os.path.join(store, "acct", "org"))
    with open(os.path.join(store, "acct", "org", sid + ".json"), "w", encoding="utf-8") as f:
        json.dump({"sessionId": sid, "cliSessionId": cli, "cwd": "/p/recipes-tools", "title": PRIVATE}, f)
    os.makedirs(os.path.join(transcripts, folder))
    path = os.path.join(transcripts, folder, CLI + ".jsonl")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in lines)
                + (end if lines else ""))
    return store, transcripts, path


def asked(found, window=200000, warn=60, session=SESSION, **more):
    return context.context_of(found[0], found[1], session, window, warn, **more)


def test_the_figure_is_the_sum_of_the_three_input_figures_of_the_newest_reply(tmp_path):
    found = world(tmp_path, [said(), reply((1, 2, 3), "2026-10-18T09:00:00.000Z"), said("more"),
                             reply((10, 2000, 30000), "2026-10-18T09:30:07.123Z")])
    assert asked(found) == {"tokens": 32010, "window": 200000, "percent": 16, "as_of": "2026-10-18T09:30:07Z",
                            "warn": False}


def test_lines_after_the_newest_reply_that_are_not_replies_do_not_hide_it(tmp_path):
    found = world(tmp_path, [reply((5, 5, 990)), said(), {"type": "custom-title", "title": PRIVATE},
                             {"type": "last-prompt"}, ["a list"], 7, "not json at all {", ""])
    assert asked(found)["tokens"] == 1000 and asked(found)["as_of"] == "2026-10-18T09:30:07Z"


def test_a_session_that_was_compacted_shows_the_smaller_figure_it_has_now(tmp_path):
    found = world(tmp_path, [reply((0, 0, 190000), "2026-10-18T09:00:00.000Z"),
                             reply((0, 0, 30000), "2026-10-18T09:10:00.000Z")])
    assert asked(found) == {"tokens": 30000, "window": 200000, "percent": 15, "as_of": "2026-10-18T09:10:00Z",
                            "warn": False}


def test_a_sub_agent_s_reply_is_passed_over(tmp_path):
    found = world(tmp_path, [reply((0, 0, 50000), "2026-10-18T09:00:00.000Z"),
                             reply((0, 0, 900), "2026-10-18T09:20:00.000Z", side=True)])
    assert asked(found)["tokens"] == 50000 and asked(found)["as_of"] == "2026-10-18T09:00:00Z"


def test_a_last_line_the_app_is_half_way_through_writing_is_passed_over(tmp_path):
    half = json.dumps(reply((0, 0, 999999)))[:80]
    found = world(tmp_path, [reply((0, 0, 50000)), half], end="")
    assert asked(found)["tokens"] == 50000


def test_a_last_line_with_no_line_end_is_read_when_it_is_whole(tmp_path):
    found = world(tmp_path, [reply((0, 0, 50000)), reply((0, 0, 60000))], end="")
    assert asked(found)["tokens"] == 60000


def test_a_line_that_is_not_utf_8_is_passed_over(tmp_path):
    found = world(tmp_path, [reply((0, 0, 50000))])
    with open(found[2], "ab") as f:
        f.write(b'{"type": "assistant", "bad": "\xff\xfe"}\n')
    assert asked(found)["tokens"] == 50000


def test_a_time_with_no_fraction_of_a_second_is_read_too(tmp_path):
    found = world(tmp_path, [reply(when="2026-10-18T09:30:07Z")])
    assert asked(found)["as_of"] == "2026-10-18T09:30:07Z"


@pytest.mark.parametrize("lines", [
    [],
    [said()],
    [said(), {"type": "custom-title", "title": "assistant"}],
    ["not json", "assistant but not json"],
    [reply((0, 0, 900), side=True)],
])
def test_a_transcript_with_no_reply_yet_is_not_known(tmp_path, lines):
    assert asked(world(tmp_path, lines)) is None


def broken(**change):
    """A reply with one thing wrong: usage=…, message=…, timestamp=…, or one figure by its key."""
    line = reply()
    for key, value in change.items():
        if key in ("message", "timestamp"):
            line[key] = value
        elif key == "usage":
            line["message"]["usage"] = value
        elif value is KeyError:
            del line["message"]["usage"][key]
        else:
            line["message"]["usage"][key] = value
    return line


@pytest.mark.parametrize("newest", [
    broken(input_tokens=KeyError),
    broken(cache_creation_input_tokens=KeyError),
    broken(cache_read_input_tokens=KeyError),
    broken(input_tokens="10"),
    broken(cache_read_input_tokens=30000.0),
    broken(cache_creation_input_tokens=True),
    broken(input_tokens=None),
    broken(cache_read_input_tokens=-1),
    broken(input_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0),
    broken(usage=None),
    broken(usage=[10, 2000, 30000]),
    broken(usage=32010),
    broken(message="a string"),
    broken(message=None),
    broken(timestamp=None),
    broken(timestamp=1794401892175),
    broken(timestamp="yesterday"),
    broken(timestamp="2026-10-18 09:30:07"),
    broken(timestamp="2026-13-45T09:30:07.123Z"),
    {"type": "assistant"},
])
def test_a_newest_reply_that_is_not_the_shape_expected_is_not_known_and_no_older_one_is_used(tmp_path, newest):
    found = world(tmp_path, [reply((0, 0, 50000), "2026-10-18T09:00:00.000Z"), newest])
    assert asked(found) is None


def test_a_project_with_no_session_and_a_cowork_session_are_not_known(tmp_path):
    found = world(tmp_path, [reply()])
    assert asked(found, session=None) is None
    cowork = {"id": "session_01AAAAAAAAAAAAAAAAAAAAAA", "link": "claude://claude.ai/cowork/session_01AAAAAAAAAAAAAAAAAAAAAA",
              "app": "cowork", "last_activity": None}
    assert asked(found, session=cowork) is None
    assert asked(found, session=dict(SESSION, app="cowork")) is None
    assert asked(found, session="a string") is None
    assert asked(found, session={"app": "code"}) is None
    assert asked(found, session=dict(SESSION, id=7)) is None
    assert asked(found) is not None                             # and the session as it should be is known


@pytest.mark.parametrize("sid", ["local_other", "*", "local_1111111-1111-4111-8111-111111111111",
                                 "../../projects/-p-recipes-tools/" + CLI, SID + "\n", ""])
def test_a_session_whose_id_is_not_the_app_s_kind_is_not_known(tmp_path, sid):
    found = world(tmp_path, [reply()])
    assert asked(found, session=dict(SESSION, id=sid)) is None


@pytest.mark.parametrize("cli", [None, 7, "", "*", "aaaaaaaa", "../" + CLI, CLI.upper(), CLI + "\n", ["a", "list"]])
def test_a_store_entry_that_does_not_name_a_transcript_is_not_known(tmp_path, cli):
    assert asked(world(tmp_path, [reply()], cli=cli)) is None


def test_a_store_entry_that_is_missing_or_not_json_or_not_an_object_is_not_known(tmp_path):
    found = world(tmp_path, [reply()])
    entry = os.path.join(found[0], "acct", "org", SID + ".json")
    for text in ("{", json.dumps(["a list"]), json.dumps({"sessionId": SID}), ""):
        with open(entry, "w", encoding="utf-8") as f:
            f.write(text)
        assert asked(found) is None
    os.remove(entry)
    assert asked(found) is None
    assert context.context_of(str(tmp_path / "nowhere"), found[1], SESSION, 200000, 60) is None
    assert context.context_of(entry, found[1], SESSION, 200000, 60) is None


def test_a_session_with_two_entries_in_the_store_is_not_known(tmp_path):
    found = world(tmp_path, [reply()])
    os.makedirs(os.path.join(found[0], "acct2", "org2"))
    with open(os.path.join(found[0], "acct2", "org2", SID + ".json"), "w", encoding="utf-8") as f:
        json.dump({"sessionId": SID, "cliSessionId": CLI}, f)
    assert asked(found) is None


def test_a_session_with_no_transcript_or_with_two_of_the_name_is_not_known(tmp_path):
    found = world(tmp_path, [reply()])
    twin = os.path.join(found[1], "-p-somewhere-else")
    os.makedirs(twin)
    with open(os.path.join(twin, CLI + ".jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps(reply((0, 0, 7))) + "\n")
    assert asked(found) is None                                 # two of the name: which is it?
    os.remove(os.path.join(twin, CLI + ".jsonl"))
    assert asked(found)["tokens"] == 32010
    os.remove(found[2])
    assert asked(found) is None                                 # none of the name
    os.makedirs(found[2])
    assert asked(found) is None                                 # a folder of the name, not a file
    assert context.context_of(found[0], str(tmp_path / "nowhere"), SESSION, 200000, 60) is None


def test_another_session_s_transcript_in_the_same_folder_is_not_read(tmp_path):
    found = world(tmp_path, [reply((0, 0, 50000))])
    with open(os.path.join(os.path.dirname(found[2]), OTHER + ".jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps(reply((0, 0, 7), "2026-10-18T11:00:00.000Z")) + "\n")
    assert asked(found)["tokens"] == 50000


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads any file")
def test_a_transcript_or_an_entry_that_cannot_be_read_is_not_known(tmp_path):
    found = world(tmp_path, [reply()])
    os.chmod(found[2], 0)
    try:
        assert asked(found) is None
    finally:
        os.chmod(found[2], 0o600)
    entry = os.path.join(found[0], "acct", "org", SID + ".json")
    os.chmod(entry, 0)
    try:
        assert asked(found) is None
    finally:
        os.chmod(entry, 0o600)


@pytest.mark.parametrize("block", [1, 7, 64, 1000, 4096])
def test_a_transcript_longer_than_one_block_is_read_from_its_end_backwards(tmp_path, block):
    long_line = {"type": "api-request-blob", "blob": "x" * 5000 + " assistant é"}
    lines = [reply((0, 0, 100 + n), f"2026-10-18T09:00:{n:02d}.000Z") for n in range(40)]
    found = world(tmp_path, lines + [reply((1, 20, 300), "2026-10-18T09:45:00.500Z"), long_line, said("é" * 300)])
    assert asked(found, block=block) == {"tokens": 321, "window": 200000, "percent": 0,
                                         "as_of": "2026-10-18T09:45:00Z", "warn": False}


def test_only_the_end_of_a_long_transcript_is_read(tmp_path, monkeypatch):
    lines = [reply((0, 0, 100 + n)) for n in range(200)]
    found = world(tmp_path, lines + [reply((0, 0, 4242))])
    size, read = os.path.getsize(found[2]), []
    real = open

    def counting(path, mode="r", *args, **more):
        f = real(path, mode, *args, **more)
        if str(path) == found[2]:
            assert mode == "rb"                                 # opened for reading, never for writing
            inner = f.read
            f = Reader(f, lambda n=-1: (read.append(n), inner(n))[1])
        return f

    class Reader:
        def __init__(self, f, read):
            self.f, self.read = f, read

        def __getattr__(self, name):
            return getattr(self.f, name)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            self.f.close()

    monkeypatch.setattr("builtins.open", counting)
    assert asked(found, block=2048)["tokens"] == 4242
    assert read and all(0 < n <= 2048 for n in read) and sum(read) < size / 10


@pytest.mark.parametrize("window, level, tokens, percent, warn", [
    (1000, 60, 594, 59, False),         # 59.4%
    (1000, 60, 595, 60, True),          # 59.5%: a half is rounded up, and the mark goes by the figure shown
    (1000, 60, 600, 60, True),
    (1000, 60, 604, 60, True),
    (1000, 60, 610, 61, True),
    (1000, 60, 5, 1, False),            # 0.5%
    (1000, 60, 25, 3, False),           # 2.5%: up, not to the even figure
    (1000, 60, 4, 0, False),
    (1000, 75, 744, 74, False),
    (1000, 75, 745, 75, True),
    (1000, 1, 4, 0, False),
    (1000, 1, 5, 1, True),
    (1000, 100, 994, 99, False),
    (1000, 100, 995, 100, True),
    (1000, 60, 1500, 150, True),        # more than the setting says the window holds: said as it is
    (1000000, 60, 135719, 14, False),
    (1000000, 60, 599999, 60, True),
    (200000, 60, 119000, 60, True),
    (200000, 60, 118999, 59, False),
])
def test_the_percentage_is_rounded_as_the_app_rounds_it_and_marked_at_or_over_the_level(tmp_path, window, level,
                                                                                         tokens, percent, warn):
    found = world(tmp_path, [reply((0, 0, tokens))])
    got = asked(found, window=window, warn=level)
    assert (got["tokens"], got["window"], got["percent"], got["warn"]) == (tokens, window, percent, warn)


# no slash: a folder's name cannot hold one, so </script> is here without it
AWKWARD = "it's a \"store\" $HOME `x` \\ [1] * ? <script> café été \U0001F980"


def test_folders_with_awkward_names_are_only_ever_names(tmp_path):
    found = world(tmp_path, [reply()], store=AWKWARD + " s", transcripts=AWKWARD + " t", folder="-p-" + AWKWARD)
    assert asked(found)["tokens"] == 32010
    decoy = os.path.join(str(tmp_path), "decoy", "acct", "org")     # what a * or a [1] in the name must not reach
    os.makedirs(decoy)
    with open(os.path.join(decoy, SID + ".json"), "w", encoding="utf-8") as f:
        json.dump({"cliSessionId": CLI}, f)
    assert asked(found)["tokens"] == 32010


def snapshot(root):
    seen = {}
    for folder, _, files in os.walk(root):
        for name in files:
            path = os.path.join(folder, name)
            with open(path, "rb") as f:
                seen[path] = (f.read(), os.stat(path).st_mtime_ns, os.stat(path).st_mode)
    return seen


def test_every_file_read_is_byte_for_byte_unchanged_and_nothing_is_made(tmp_path):
    found = world(tmp_path, [said(), reply(), said(), reply((0, 0, 70000)), "half a li"], end="")
    before = snapshot(str(tmp_path))
    assert asked(found)["tokens"] == 70000
    assert asked(found, session=None) is None
    assert snapshot(str(tmp_path)) == before


def test_no_word_of_the_conversation_leaves_the_transcript(tmp_path):
    found = world(tmp_path, [said(), reply(), said()])
    got = asked(found)
    assert sorted(got) == ["as_of", "percent", "tokens", "warn", "window"]
    assert PRIVATE not in json.dumps(got) and "invented-model" not in json.dumps(got)


# --- the model, effort and time of a live session's newest reply (Request 28) ---

NOT_KNOWN = {"model": None, "effort": None, "last_reply": None}


def test_the_newest_reply_of_a_transcript_named_by_its_id_gives_the_model_the_effort_and_its_time(tmp_path):
    _store, transcripts, _path = world(tmp_path, [
        reply(when="2026-10-18T09:00:00.000Z", effort="low"), said(),
        reply(when="2026-10-18T09:30:07.123Z", effort="xhigh", perTurnEffort="max", requestedModel="another"),
        said("after"), {"type": "last-prompt"}])
    assert context.reply_of(transcripts, CLI) == {"model": "invented-model", "effort": "xhigh",
                                                  "last_reply": "2026-10-18T09:30:07Z"}


def test_a_sub_agent_s_reply_is_not_the_session_s(tmp_path):
    _store, transcripts, _path = world(tmp_path, [
        reply(when="2026-10-18T09:00:00.000Z", effort="high"),
        reply(when="2026-10-18T09:50:00.000Z", side=True, effort="low")])
    assert context.reply_of(transcripts, CLI)["last_reply"] == "2026-10-18T09:00:00Z"
    assert context.reply_of(transcripts, CLI)["effort"] == "high"


@pytest.mark.parametrize("change, key", [
    ({"effort": 7}, "effort"), ({"effort": None}, "effort"), ({"effort": ["high"]}, "effort"),
    ({"timestamp": "yesterday"}, "last_reply"), ({"timestamp": 1792315200}, "last_reply"),
    ({"message": {"model": 5}}, "model"), ({"message": {}}, "model"), ({"message": "words"}, "model"),
])
def test_a_fact_the_reply_does_not_hold_as_expected_is_not_known_and_the_others_still_are(tmp_path, change, key):
    line = reply(effort="high")
    line.update(change)
    _store, transcripts, _path = world(tmp_path, [line])
    found = context.reply_of(transcripts, CLI)
    assert found[key] is None
    assert [k for k, v in found.items() if v is None] == [key]


def test_a_reply_with_no_effort_at_all_as_an_older_claude_wrote_it_gives_the_rest(tmp_path):
    _store, transcripts, _path = world(tmp_path, [reply()])
    assert context.reply_of(transcripts, CLI) == {"model": "invented-model", "effort": None,
                                                  "last_reply": "2026-10-18T09:30:07Z"}


@pytest.mark.parametrize("ident", [None, 7, "", "*", "../" + CLI, CLI + "/..", SID, CLI.upper(), "a" * 36,
                                   CLI[:-1] + "?", "[a]aaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"])
def test_an_id_that_is_not_a_transcript_s_name_finds_nothing(tmp_path, ident):
    _store, transcripts, _path = world(tmp_path, [reply(effort="high")])
    assert context.reply_of(transcripts, ident) == NOT_KNOWN


def test_no_transcript_two_transcripts_one_with_no_reply_and_one_that_cannot_be_opened_are_not_known(tmp_path):
    _store, transcripts, _path = world(tmp_path, [said()])
    assert context.reply_of(transcripts, CLI) == NOT_KNOWN                 # no reply yet
    assert context.reply_of(transcripts, OTHER) == NOT_KNOWN               # no transcript
    assert context.reply_of(str(tmp_path / "nowhere"), CLI) == NOT_KNOWN
    os.makedirs(os.path.join(transcripts, "-another-folder"))
    with open(os.path.join(transcripts, "-another-folder", CLI + ".jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps(reply(effort="high")) + "\n")
    assert context.reply_of(transcripts, CLI) == NOT_KNOWN                 # there twice
    os.makedirs(os.path.join(transcripts, "-a-third", OTHER + ".jsonl"))
    assert context.reply_of(transcripts, OTHER) == NOT_KNOWN               # a folder of that name


def test_no_word_of_the_conversation_is_in_what_is_read_and_the_transcript_is_not_changed(tmp_path):
    _store, transcripts, path = world(tmp_path, [said(), reply(effort="high"), said("more")])
    with open(path, "rb") as f:
        before = f.read()
    assert PRIVATE not in json.dumps(context.reply_of(transcripts, CLI))
    with open(path, "rb") as f:
        assert f.read() == before

