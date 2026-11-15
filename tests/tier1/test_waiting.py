"""conduct waiting's pure functions: a repository's facts, its line, the messages of a listing."""

import pytest

from bernstein import waiting


def test_a_folder_with_no_git_is_not_a_repository_and_waits():
    assert waiting.repository("/p/x", False) == {
        "folder": "/p/x", "git": False, "remote": None, "upstream": None, "unpushed": None,
        "uncommitted": None, "waiting": True}


def test_a_level_clean_repository_does_not_wait():
    assert waiting.repository("/p/x", True, remote="origin\n", ahead="0\n", status="") == {
        "folder": "/p/x", "git": True, "remote": True, "upstream": True, "unpushed": 0, "uncommitted": 0,
        "waiting": False}


def test_commits_ahead_and_files_changed_or_untracked_are_counted_and_wait():
    repo = waiting.repository("/p/x", True, remote="origin\nbackup\n", ahead="2\n",
                              status=' M a\n?? "new file"\nA  b\n')
    assert (repo["unpushed"], repo["uncommitted"], repo["waiting"]) == (2, 3, True)


def test_one_file_uncommitted_alone_waits_and_commits_ahead_alone_wait():
    assert waiting.repository("/p/x", True, "origin\n", "0\n", "?? a\n")["waiting"] is True
    assert waiting.repository("/p/x", True, "origin\n", "1\n", "")["waiting"] is True


def test_no_remote_means_nothing_to_push_and_waits_only_for_uncommitted_files():
    clean = waiting.repository("/p/x", True, remote="", status="")
    assert clean == {"folder": "/p/x", "git": True, "remote": False, "upstream": None, "unpushed": None,
                     "uncommitted": 0, "waiting": False}
    assert waiting.repository("/p/x", True, remote="\n", status=" M a\n")["waiting"] is True


def test_a_remote_with_no_upstream_branch_waits_as_never_pushed():
    repo = waiting.repository("/p/x", True, remote="origin\n", ahead=None, status="")
    assert (repo["remote"], repo["upstream"], repo["unpushed"], repo["waiting"]) == (True, False, None, True)


@pytest.mark.parametrize("ahead", ["", "two\n", "-1\n", "1 2\n"])
def test_a_count_that_is_not_a_number_is_refused(ahead):
    with pytest.raises(ValueError):
        waiting.repository("/p/x", True, remote="origin\n", ahead=ahead)


@pytest.mark.parametrize("facts, line", [
    ((False,), "/p/a b: not a git repository"),
    ((True, "origin\n", "2\n", ""), "/p/a b: 2 commits not pushed"),
    ((True, "origin\n", "1\n", " M a\n"), "/p/a b: 1 commit not pushed; 1 file uncommitted"),
    ((True, "origin\n", "0\n", " M a\n?? b\n"), "/p/a b: 2 files uncommitted"),
    ((True, "", None, "?? b\n"), "/p/a b: no remote; 1 file uncommitted"),
    ((True, "origin\n", None, ""), "/p/a b: no upstream branch: never pushed"),
    ((True, "origin\n", None, "?? b\n"), "/p/a b: no upstream branch: never pushed; 1 file uncommitted"),
    ((True, "origin\n", "0\n", ""), "/p/a b: nothing waiting"),
    ((True, "", None, ""), "/p/a b: no remote; nothing uncommitted"),
])
def test_a_repository_s_line_says_only_what_there_is_to_say(facts, line):
    assert waiting.repository_line(waiting.repository("/p/a b", *facts)) == line


LISTED = [
    {"id": "m1", "from": "bernstein", "date": "2026-10-18T08:00:00Z", "subject": "Notice: rules", "box": "new",
     "path": "/mail/x/new/m1.md", "headers": True},
    {"id": "m2", "from": "recipes", "date": "2026-10-18T08:05:00Z", "subject": "Re: Request 3", "box": "new"},
]


def test_messages_keeps_the_sender_the_id_the_subject_and_when_it_was_sent():
    assert waiting.messages(LISTED, "unread") == [
        ("bernstein", {"id": "m1", "subject": "Notice: rules", "sent": "2026-10-18T08:00:00Z", "state": "unread"}),
        ("recipes", {"id": "m2", "subject": "Re: Request 3", "sent": "2026-10-18T08:05:00Z", "state": "unread"}),
    ]
    assert waiting.messages([], "claimed") == []


@pytest.mark.parametrize("listed", [
    {"id": "m1"}, "text", None, [["m1"]], [{"id": "m1", "from": "x", "date": "d"}],
    [{"id": "m1", "from": 3, "date": "d", "subject": "s"}], [{"id": "m1", "from": "x", "date": "d", "subject": None}],
])
def test_a_listing_that_is_not_lobster_mail_s_shape_is_refused(listed):
    with pytest.raises(ValueError):
        waiting.messages(listed, "unread")


def repo(folder, *facts):
    return waiting.repository(folder, *(facts or (True, "origin\n", "0\n", "")))


def msg(ident, subject, state, sent="2026-10-18T08:00:00Z"):
    return {"id": ident, "subject": subject, "sent": sent, "state": state}


def test_a_project_waits_for_a_repository_or_a_message_either_way_and_for_nothing_else():
    quiet = waiting.project("recipes", ["/p/recipes"], True, [repo("/p/recipes")])
    assert quiet == {"name": "recipes", "folders": ["/p/recipes"], "mailbox": True,
                     "repositories": [repo("/p/recipes")], "from_bernstein": [], "to_bernstein": [],
                     "waiting": False}
    assert waiting.project("recipes", ["/p/recipes"], True, [repo("/p/recipes", True, "o\n", "1\n", "")])["waiting"]
    assert waiting.project("recipes", ["/p/recipes"], True, [repo("/p/recipes")],
                           from_bernstein=[msg("m1", "Notice: x", "unread")])["waiting"]
    assert waiting.project("recipes", ["/p/recipes"], True, [repo("/p/recipes")],
                           to_bernstein=[msg("m2", "Re: x", "claimed")])["waiting"]
    assert not waiting.project("salads", [], True, [])["waiting"]           # a mailbox with no folder: a note only
    assert not waiting.project("recipes", ["/p/recipes"], False, [repo("/p/recipes")])["waiting"]   # no mailbox


def a_report():
    tools = waiting.project(
        "recipes-tools", ["/p/code/recipes-tools-code"], True,
        [repo("/p/code/recipes-tools-code", True, "", None, " M DIARY.md\n?? x\n?? y\n"),
         repo("/p/code/recipes-tools-code/recipes-tools", True, "origin\n", "2\n", ""),
         repo("/p/code/recipes-tools-code/extra")],
        from_bernstein=[msg("m1", "Notice: your rules changed", "unread"),
                        msg("m2", "Stop: hand over", "claimed", "2026-10-17T16:00:00Z")],
        to_bernstein=[msg("m3", "Re: Request 3: built", "unread"), msg("m4", "Request 4: a flag", "claimed")])
    quiet = waiting.project("recipes", ["/p/non-code/recipes"], True, [repo("/p/non-code/recipes")])
    local = waiting.project("pastry", ["/p/non-code/pastry"], True, [repo("/p/non-code/pastry", True, "", None, "")])
    salads = waiting.project("salads", [], True, [], from_bernstein=[msg("m5", "Start: salads", "unread")])
    soups = waiting.project("soups", ["/p/non-code/soups"], False,
                            [repo("/p/non-code/soups", False), repo("/p/non-code/soups/x", True, "o\n", None, "")])
    stranger = waiting.project("squirrel", [], False, [], to_bernstein=[msg("m6", "hello", "unread")])
    others = [repo("/p/code/halmos", True, "origin\n", "1\n", "?? a\n"), repo("/p/code/filer"),
              repo("/p/code/scatter", True, "", None, "")]
    return waiting.report("/p/mail", [local, quiet, tools, salads, soups, stranger], others)


def test_the_report_counts_everything_once():
    data = a_report()
    assert sorted(data) == ["other_repositories", "projects", "root", "totals"]
    assert data["root"] == "/p/mail"
    assert [p["name"] for p in data["projects"]] == ["pastry", "recipes", "recipes-tools", "salads", "soups",
                                                     "squirrel"]
    assert data["totals"] == {
        "projects": 6, "projects_waiting": 4, "other_repositories": 3, "other_repositories_waiting": 1,
        "commits_not_pushed": 3, "never_pushed": 1, "files_uncommitted": 4, "not_git": 1,
        "from_bernstein": 3, "to_bernstein": 3, "no_remote_nothing_uncommitted": 2}


def test_the_text_has_a_block_for_each_project_that_waits_then_the_others_the_totals_and_the_rest():
    assert waiting.text(a_report()) == (
        "recipes-tools\n"
        "  /p/code/recipes-tools-code: no remote; 3 files uncommitted\n"
        "  /p/code/recipes-tools-code/recipes-tools: 2 commits not pushed\n"
        '  From bernstein, unread: "Notice: your rules changed" (sent 2026-10-18T08:00:00Z)\n'
        '  From bernstein, claimed and not closed: "Stop: hand over" (sent 2026-10-17T16:00:00Z)\n'
        '  To bernstein, unread: "Re: Request 3: built" (sent 2026-10-18T08:00:00Z)\n'
        '  To bernstein, claimed and not closed: "Request 4: a flag" (sent 2026-10-18T08:00:00Z)\n'
        "\n"
        "salads (a mailbox with no project folder)\n"
        '  From bernstein, unread: "Start: salads" (sent 2026-10-18T08:00:00Z)\n'
        "\n"
        "soups (no mailbox)\n"
        "  /p/non-code/soups: not a git repository\n"
        "  /p/non-code/soups/x: no upstream branch: never pushed\n"
        "\n"
        "squirrel (no project folder and no mailbox)\n"
        '  To bernstein, unread: "hello" (sent 2026-10-18T08:00:00Z)\n'
        "\n"
        "Other repositories (not lobster projects):\n"
        "  /p/code/halmos: 1 commit not pushed; 1 file uncommitted\n"
        "\n"
        "Waiting: 3 commits not pushed, 4 files uncommitted, 3 messages from bernstein not dealt with, "
        "3 messages to bernstein not closed, 1 repository never pushed, 1 folder not a git repository.\n"
        "Nothing waiting in 2 projects and 2 other repositories.\n"
        "No remote and nothing uncommitted: 2 repositories.\n")


def test_with_nothing_waiting_the_text_is_the_totals_and_the_count_alone():
    data = waiting.report("/p/mail", [waiting.project("recipes", ["/p/recipes"], True, [repo("/p/recipes")])],
                          [repo("/p/code/filer")])
    assert waiting.text(data) == "Waiting: nothing.\nNothing waiting in 1 project and 1 other repository.\n"
    assert waiting.text(waiting.report("/p/mail", [], [])) == (
        "Waiting: nothing.\nNothing waiting in 0 projects and 0 other repositories.\n")


def test_the_totals_line_leaves_out_never_pushed_and_not_git_when_there_are_none_and_keeps_the_four_counts():
    one = waiting.project("recipes", ["/p/recipes"], True, [repo("/p/recipes", True, "o\n", "1\n", "")])
    assert waiting.text(waiting.report("/p/mail", [one], [])).splitlines()[-2:] == [
        ("Waiting: 1 commit not pushed, 0 files uncommitted, 0 messages from bernstein not dealt with, "
         "0 messages to bernstein not closed."),
        "Nothing waiting in 0 projects and 0 other repositories."]


def test_a_subject_is_data_and_is_shown_as_json_quotes_it_on_one_line():
    odd = 'It\'s "quoted" \\ back\nnew line $HOME `x` </script> é 日本'
    p = waiting.project("recipes", ["/p/recipes"], True, [], from_bernstein=[msg("m1", odd, "unread")])
    lines = waiting.text(waiting.report("/p/mail", [p], [])).splitlines()
    assert lines[1] == ('  From bernstein, unread: "It\'s \\"quoted\\" \\\\ back\\nnew line $HOME `x` </script> é 日本"'
                        " (sent 2026-10-18T08:00:00Z)")
    assert lines[2:4] == ["", ("Waiting: 0 commits not pushed, 0 files uncommitted, 1 message from bernstein not "
                               "dealt with, 0 messages to bernstein not closed.")]
