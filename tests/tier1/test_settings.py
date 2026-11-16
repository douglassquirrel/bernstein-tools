import pytest

from bernstein.settings import SettingsRefused, options_for_new_lobster, read_settings

HOME = "/home/sq"


def test_an_empty_file_gives_the_defaults_with_home_filled_in():
    assert read_settings("", HOME) == {
        "TEMPLATE": "/home/sq/projects/code/bernstein-code/templates/lobster",
        "NON_CODE_DIR": "/home/sq/projects/non-code",
        "CODE_DIR": "/home/sq/projects/code",
        "MODEL": "opus",
        "EFFORT": "high",
        "LOBSTER_MAIL": "/home/sq/projects/code/lobster-tools-code/lobster-tools/lobster-mail",
        "MAIL_ROOT": "/home/sq/projects/mail",
        "PYTHON": "/usr/bin/python3",
        "PODIUM_PORT": "8417",
        "PODIUM_LOG": "/home/sq/.bernstein/podium.log",
        "APP_SESSIONS": "/home/sq/Library/Application Support/Claude/claude-code-sessions",
        "APP_COWORK_SESSIONS": "/home/sq/Library/Application Support/Claude/local-agent-mode-sessions",
        "APP_TRANSCRIPTS": "/home/sq/.claude/projects",
        "CONTEXT_WINDOW": "1000000",
        "CONTEXT_WARN": "60",
    }


def test_a_setting_overrides_its_default_and_comments_blank_lines_and_quotes_are_handled():
    text = "# my settings\n\nCODE_DIR = ~/work/code\nMODEL='sonnet'\nEFFORT=\"max\"\n"
    got = read_settings(text, HOME)
    assert (got["CODE_DIR"], got["MODEL"], got["EFFORT"]) == ("/home/sq/work/code", "sonnet", "max")
    assert got["NON_CODE_DIR"] == "/home/sq/projects/non-code"


def test_a_path_with_spaces_and_non_ascii_letters_is_kept_whole():
    got = read_settings('TEMPLATE="~/My Drive/modèles"\n', HOME)
    assert got["TEMPLATE"] == "/home/sq/My Drive/modèles"


@pytest.mark.parametrize(
    "text, why",
    [
        ("CODE_DIR=~/x\nFOO=1\n", "line 2: unknown setting FOO"),
        ("just words\n", "line 1: not a KEY=value line: just words"),
        ("EFFORT=extreme\n", "line 1: EFFORT must be one of low, medium, high, xhigh, max"),
        ("MODEL=\n", "line 1: MODEL is empty"),
        ("MODEL=opus 5\n", "line 1: MODEL must be one word, such as opus or sonnet"),
        ("PODIUM_PORT=web\n", "line 1: PODIUM_PORT must be a whole number from 0 to 65535"),
        ("# c\nPODIUM_PORT=65536\n", "line 2: PODIUM_PORT must be a whole number from 0 to 65535"),
        ("PODIUM_PORT=-1\n", "line 1: PODIUM_PORT must be a whole number from 0 to 65535"),
        ("PODIUM_PORT=80.5\n", "line 1: PODIUM_PORT must be a whole number from 0 to 65535"),
        ("PODIUM_PORT=\n", "line 1: PODIUM_PORT must be a whole number from 0 to 65535"),
        ("CONTEXT_WARN=sixty\n", "line 1: CONTEXT_WARN must be a whole number from 1 to 100"),
        ("CONTEXT_WARN=0\n", "line 1: CONTEXT_WARN must be a whole number from 1 to 100"),
        ("CONTEXT_WARN=101\n", "line 1: CONTEXT_WARN must be a whole number from 1 to 100"),
        ("CONTEXT_WARN=60%\n", "line 1: CONTEXT_WARN must be a whole number from 1 to 100"),
        ("CONTEXT_WARN=59.5\n", "line 1: CONTEXT_WARN must be a whole number from 1 to 100"),
        ("CONTEXT_WARN=\n", "line 1: CONTEXT_WARN must be a whole number from 1 to 100"),
        ("# c\nCONTEXT_WINDOW=1,000,000\n", "line 2: CONTEXT_WINDOW must be a whole number from 1000 to 100000000"),
        ("CONTEXT_WINDOW=999\n", "line 1: CONTEXT_WINDOW must be a whole number from 1000 to 100000000"),
        ("CONTEXT_WINDOW=100000001\n", "line 1: CONTEXT_WINDOW must be a whole number from 1000 to 100000000"),
        ("CONTEXT_WINDOW=1M\n", "line 1: CONTEXT_WINDOW must be a whole number from 1000 to 100000000"),
        ("CONTEXT_WINDOW=-200000\n", "line 1: CONTEXT_WINDOW must be a whole number from 1000 to 100000000"),
        ("CONTEXT_WINDOW=\n", "line 1: CONTEXT_WINDOW must be a whole number from 1000 to 100000000"),
        ("CONTEXT_WINDOW=٢٠٠٠٠٠\n", "line 1: CONTEXT_WINDOW must be a whole number from 1000 to 100000000"),
    ],
)
def test_refuses_a_bad_settings_line_naming_it(text, why):
    with pytest.raises(SettingsRefused) as refused:
        read_settings(text, HOME)
    assert str(refused.value) == why


def test_the_name_and_the_settings_make_the_options():
    o = options_for_new_lobster(["recipes"], read_settings("", HOME))
    assert (o.name, o.public, o.dry_run, o.model, o.effort) == ("recipes", False, False, "opus", "high")
    assert o.code_dir == "/home/sq/projects/code"


def test_flags_win_over_settings():
    settings = read_settings("MODEL=sonnet\nCODE_DIR=~/a\n", HOME)
    o = options_for_new_lobster(
        ["--public", "--dry-run", "--model", "opus", "--effort", "low", "--code-dir", "/b",
         "--non-code-dir", "/c", "--template", "/t", "recipes"], settings)
    assert (o.public, o.dry_run, o.model, o.effort) == (True, True, "opus", "low")
    assert (o.code_dir, o.non_code_dir, o.template) == ("/b", "/c", "/t")


def test_refuses_a_bad_effort_flag():
    with pytest.raises(SettingsRefused) as refused:
        options_for_new_lobster(["--effort", "huge", "recipes"], read_settings("", HOME))
    assert str(refused.value) == "--effort must be one of low, medium, high, xhigh, max"


def test_refuses_a_bad_name_with_the_rule():
    with pytest.raises(SettingsRefused) as refused:
        options_for_new_lobster(["Recipes"], read_settings("", HOME))
    assert str(refused.value) == "the name Recipes cannot be used: use only lower-case letters, digits and hyphens"


def test_an_absolute_path_is_kept_as_it_is():
    assert read_settings("CODE_DIR=/srv/code\n", HOME)["CODE_DIR"] == "/srv/code"


def test_claw_takes_a_tools_name_and_refuses_the_pair_flags():
    o = options_for_new_lobster(["--claw", "word-tools"], read_settings("", HOME))
    assert (o.claw, o.name, o.claws) == (True, "word-tools", [])
    for flag in ("--tools", "--non-code-path"):
        with pytest.raises(SettingsRefused) as refused:
            options_for_new_lobster(["--claw", "--render-into", "/d", flag, "x", "word-tools"], read_settings("", HOME))
        assert str(refused.value) == f"{flag} cannot be used with --claw, which has no non-code half"
    with pytest.raises(SettingsRefused) as refused:
        options_for_new_lobster(["--claw", "Word Tools"], read_settings("", HOME))
    assert str(refused.value) == "the claw name Word Tools cannot be used: use only lower-case letters, digits and hyphens"


def test_claws_lists_the_further_claws_a_non_code_project_uses_and_needs_render_into():
    o = options_for_new_lobster(["--render-into", "/d", "--claws", "word-tools  google-docs-tools", "beyond-ai"],
                                read_settings("", HOME))
    assert (o.claw, o.claws) == (False, ["word-tools", "google-docs-tools"])
    assert options_for_new_lobster(["recipes"], read_settings("", HOME)).claws == []
    with pytest.raises(SettingsRefused) as refused:
        options_for_new_lobster(["--claws", "word-tools", "recipes"], read_settings("", HOME))
    assert str(refused.value) == "--claws needs --render-into"
    with pytest.raises(SettingsRefused) as refused:
        options_for_new_lobster(["--render-into", "/d", "--claws", "word-tools Bad", "recipes"], read_settings("", HOME))
    assert str(refused.value) == "the claw name Bad cannot be used: use only lower-case letters, digits and hyphens"
    with pytest.raises(SettingsRefused) as refused:
        options_for_new_lobster(["--render-into", "/d", "--claws", "word-tools", "--claw", "x-tools"], read_settings("", HOME))
    assert str(refused.value) == "--claws cannot be used with --claw, which has no non-code half"


def test_the_podium_port_setting_is_kept_when_it_is_a_port_number():
    assert read_settings("PODIUM_PORT=9000\n", HOME)["PODIUM_PORT"] == "9000"
    assert read_settings('PODIUM_PORT="0"\n', HOME)["PODIUM_PORT"] == "0"
    assert read_settings("PODIUM_PORT=65535\n", HOME)["PODIUM_PORT"] == "65535"


def test_the_podium_log_setting_is_a_path_with_home_filled_in():
    assert read_settings("PODIUM_LOG=~/logs/my podium.log\n", HOME)["PODIUM_LOG"] == "/home/sq/logs/my podium.log"
    assert read_settings("PODIUM_LOG=/var/tmp/p.log\n", HOME)["PODIUM_LOG"] == "/var/tmp/p.log"



def test_the_context_window_and_the_warning_level_are_kept_when_they_are_whole_numbers_in_range():
    got = read_settings("CONTEXT_WINDOW=200000\nCONTEXT_WARN='75'\n", HOME)
    assert (got["CONTEXT_WINDOW"], got["CONTEXT_WARN"]) == ("200000", "75")
    edges = read_settings("CONTEXT_WINDOW=1000\nCONTEXT_WARN=1\n", HOME)
    assert (edges["CONTEXT_WINDOW"], edges["CONTEXT_WARN"]) == ("1000", "1")
    tops = read_settings("CONTEXT_WINDOW=100000000\nCONTEXT_WARN=100\n", HOME)
    assert (tops["CONTEXT_WINDOW"], tops["CONTEXT_WARN"]) == ("100000000", "100")


def test_where_the_transcripts_are_is_a_path_with_home_filled_in():
    assert read_settings("APP_TRANSCRIPTS=~/my claude/projects\n", HOME)["APP_TRANSCRIPTS"] == "/home/sq/my claude/projects"
