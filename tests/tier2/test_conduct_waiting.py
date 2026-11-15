"""conduct waiting against the stubs: what it prints, what it asks git and lobster-mail, and what it never does."""

import io
import json
import os

import pytest
from conftest import NOW, tree


def mail(ident, sender, subject, date="2026-10-18T08:00:00Z"):
    return {"id": ident, "from": sender, "date": date, "subject": subject, "box": "new", "path": "/x", "headers": True}


def lists(world, box, mailbox, messages):
    """What `lobster-mail list --as mailbox --new|--open --json` prints."""
    with open(os.path.join(world.bin, f"list-{box}-{mailbox}.json"), "w", encoding="utf-8") as f:
        f.write(messages if isinstance(messages, str) else json.dumps(messages))


def a_world(world):
    """A pair, a conductor, a mailbox with no folder, and three repositories that are not lobster projects."""
    w = {}
    w["recipes"] = world.repo(world.project("recipes", "non-code"))
    w["outer"] = world.repo(world.project("recipes-tools", "code", public=True), remote="",
                            changed=[" M DIARY.md", "?? notes.md"])
    w["checkout"] = world.repo(os.path.join(w["outer"], "recipes-tools"), ahead=2)
    w["video"] = world.project("video-tools", "code", under="video", sister="")        # no .git
    w["bernstein"] = world.repo(world.conductor("bernstein", claw="recipes-tools"), changed=["?? scratch.txt"])
    w["halmos-outer"] = world.repo(os.path.join(world.code, "video", "halmos-code"), remote="")
    w["halmos"] = world.repo(os.path.join(w["halmos-outer"], "halmos"), ahead=1, changed=[" M a.py"])
    w["filer"] = world.repo(os.path.join(world.code, "filer"))
    w["notes"] = world.repo(os.path.join(world.non_code, "writing", "nötes"), upstream=False)
    world.mailboxes(["bernstein", "recipes", "recipes-tools", "salads", "video-tools"])
    lists(world, "new", "recipes-tools", [mail("m1", "bernstein", "Notice: your rules changed"),
                                          mail("m2", "recipes-tools", "Handover 2026-10-18")])
    lists(world, "open", "recipes-tools", [mail("m3", "bernstein", "Stop: hand over", "2026-10-17T16:00:00Z"),
                                           mail("m4", "recipes", "Request 5: a tool")])
    lists(world, "new", "salads", [mail("m5", "bernstein", "Start: salads")])
    lists(world, "new", "bernstein", [mail("m6", "recipes-tools", "Re: Request 3: built"),
                                      mail("m7", "bernstein", "Handover 2026-10-18"),
                                      mail("m8", "squirrel", "hello")])
    lists(world, "open", "bernstein", [mail("m9", "recipes-tools", "Request 4: a flag")])
    return w


def test_waiting_prints_a_block_for_each_project_that_waits_the_other_repositories_and_the_totals(world):
    w = a_world(world)
    code, out, err = world.conduct("waiting")
    assert (code, err) == (0, "")
    assert out == (
        "bernstein\n"
        f"  {w['bernstein']}: 1 file uncommitted\n"
        "\n"
        "recipes-tools\n"
        f"  {w['outer']}: no remote; 2 files uncommitted\n"
        f"  {w['checkout']}: 2 commits not pushed\n"
        '  From bernstein, unread: "Notice: your rules changed" (sent 2026-10-18T08:00:00Z)\n'
        '  From bernstein, claimed and not closed: "Stop: hand over" (sent 2026-10-17T16:00:00Z)\n'
        '  To bernstein, unread: "Re: Request 3: built" (sent 2026-10-18T08:00:00Z)\n'
        '  To bernstein, claimed and not closed: "Request 4: a flag" (sent 2026-10-18T08:00:00Z)\n'
        "\n"
        "salads (a mailbox with no project folder)\n"
        '  From bernstein, unread: "Start: salads" (sent 2026-10-18T08:00:00Z)\n'
        "\n"
        "squirrel (no project folder and no mailbox)\n"
        '  To bernstein, unread: "hello" (sent 2026-10-18T08:00:00Z)\n'
        "\n"
        "video-tools\n"
        f"  {w['video']}: not a git repository\n"
        "\n"
        "Other repositories (not lobster projects):\n"
        f"  {w['halmos']}: 1 commit not pushed; 1 file uncommitted\n"
        f"  {w['notes']}: no upstream branch: never pushed\n"
        "\n"
        "Waiting: 3 commits not pushed, 4 files uncommitted, 3 messages from bernstein not dealt with, "
        "3 messages to bernstein not closed, 1 repository never pushed, 1 folder not a git repository.\n"
        "Nothing waiting in 1 project and 2 other repositories.\n"
        "No remote and nothing uncommitted: 1 repository.\n")


def test_waiting_json_gives_everything_as_data_the_projects_with_nothing_waiting_too(world):
    w = a_world(world)
    code, out, err = world.conduct("waiting", "--json")
    assert (code, err) == (0, "")
    said = json.loads(out)
    assert sorted(said) == ["other_repositories", "projects", "root", "totals"]
    assert said["root"] == world.mail
    by_name = {p["name"]: p for p in said["projects"]}
    assert list(by_name) == ["bernstein", "recipes", "recipes-tools", "salads", "squirrel", "video-tools"]
    assert by_name["recipes"] == {
        "name": "recipes", "folders": [w["recipes"]], "mailbox": True, "from_bernstein": [], "to_bernstein": [],
        "waiting": False,
        "repositories": [{"folder": w["recipes"], "git": True, "remote": True, "upstream": True, "unpushed": 0,
                          "uncommitted": 0, "waiting": False}]}
    tools = by_name["recipes-tools"]
    assert [(r["folder"], r["remote"], r["unpushed"], r["uncommitted"]) for r in tools["repositories"]] == [
        (w["outer"], False, None, 2), (w["checkout"], True, 2, 0)]
    assert tools["from_bernstein"] == [
        {"id": "m1", "subject": "Notice: your rules changed", "sent": "2026-10-18T08:00:00Z", "state": "unread"},
        {"id": "m3", "subject": "Stop: hand over", "sent": "2026-10-17T16:00:00Z", "state": "claimed"}]
    assert [(m["id"], m["state"]) for m in tools["to_bernstein"]] == [("m6", "unread"), ("m9", "claimed")]
    assert (by_name["salads"]["folders"], by_name["salads"]["mailbox"]) == ([], True)
    assert (by_name["squirrel"]["folders"], by_name["squirrel"]["mailbox"]) == ([], False)
    assert by_name["bernstein"]["from_bernstein"] == by_name["bernstein"]["to_bernstein"] == []
    assert [(r["folder"], r["waiting"]) for r in said["other_repositories"]] == [
        (w["filer"], False), (w["halmos-outer"], False), (w["halmos"], True), (w["notes"], True)]
    assert said["totals"] == {
        "projects": 6, "projects_waiting": 5, "other_repositories": 4, "other_repositories_waiting": 2,
        "commits_not_pushed": 3, "never_pushed": 1, "files_uncommitted": 4, "not_git": 1,
        "from_bernstein": 3, "to_bernstein": 3, "no_remote_nothing_uncommitted": 1}


def test_waiting_only_reads_three_git_verbs_and_two_of_lobster_mail_s_and_writes_nothing(world):
    w = a_world(world)
    before = tree(world.home)
    assert world.conduct("waiting")[0] == 0
    assert world.conduct("waiting", "--json")[0] == 0
    assert tree(world.home) == before
    calls = world.calls()
    git = [(c["args"], c["cwd"]) for c in calls if c["prog"] == "git"]
    assert {tuple(args) for args, _ in git} == {
        ("remote",), ("rev-list", "--count", "@{u}..HEAD"), ("--no-optional-locks", "status", "--porcelain")}
    real = os.path.realpath
    assert [args[0] for args, cwd in git if cwd == real(w["checkout"])][:3] == ["remote", "rev-list",
                                                                                 "--no-optional-locks"]
    assert [args[0] for args, cwd in git if cwd == real(w["outer"])][:2] == ["remote", "--no-optional-locks"]
    assert real(w["video"]) not in {cwd for _, cwd in git}      # not a repository: git is not run there
    assert {cwd for _, cwd in git} == {real(w[k]) for k in ("recipes", "outer", "checkout", "bernstein",
                                                            "halmos-outer", "halmos", "filer", "notes")}
    mail_calls = [c["args"] for c in calls if c["prog"] == "lobster-mail"]
    assert {tuple(args[:2]) if args[0] == "duty" else (args[0],) for args in mail_calls} == {
        ("duty", "status"), ("list",)}
    listed = sorted((args[2], args[3]) for args in mail_calls[: len(mail_calls) // 2] if args[0] == "list")
    assert listed == sorted((box, flag) for box in ("bernstein", "recipes", "recipes-tools", "salads",
                                                    "video-tools") for flag in ("--new", "--open"))
    assert {c["prog"] for c in calls} == {"git", "lobster-mail"}


def test_with_nothing_waiting_it_says_so_in_two_lines(world):
    world.repo(world.project("recipes", "non-code"))
    world.repo(world.project("recipes-tools", "code"))
    world.mailboxes(["recipes", "recipes-tools"])
    assert world.conduct("waiting") == (0, ("Waiting: nothing.\nNothing waiting in 2 projects and 0 other "
                                            "repositories.\n"), "")


def test_a_project_with_no_mailbox_is_said_so_and_its_mail_is_not_asked_for(world):
    folder = world.repo(world.project("recipes", "non-code"), changed=["?? a"])
    world.mailboxes([])
    code, out, err = world.conduct("waiting")
    assert (code, err) == (0, "")
    assert out.startswith(f"recipes (no mailbox)\n  {folder}: 1 file uncommitted\n\n")
    assert [c["args"][:2] for c in world.calls() if c["prog"] == "lobster-mail"] == [["duty", "status"]]


def test_a_project_in_two_places_has_both_folders_in_its_block(world):
    one = world.repo(world.project("recipes-tools", "code"), ahead=1)
    two = world.repo(world.project("recipes-tools", "code", under="old"), changed=[" M a"])
    world.mailboxes(["recipes-tools"])
    code, out, err = world.conduct("waiting")
    assert (code, err) == (0, "")
    assert out.startswith(f"recipes-tools\n  {two}: 1 file uncommitted\n  {one}: 1 commit not pushed\n\n")


def test_a_public_project_whose_checkout_is_not_there_has_its_outer_folder_alone(world):
    outer = world.repo(world.project("recipes-tools", "code", public=True), remote="", changed=["?? a"])
    os.rmdir(os.path.join(outer, "recipes-tools"))
    world.mailboxes(["recipes-tools"])
    code, out, err = world.conduct("waiting", "--json")
    assert (code, err) == (0, "")
    assert [r["folder"] for r in json.loads(out)["projects"][0]["repositories"]] == [outer]


def test_a_lobster_project_and_a_repository_are_not_looked_into_for_other_repositories(world):
    project = world.repo(world.project("recipes", "non-code"))
    world.repo(os.path.join(project, "vendored"), ahead=5)
    plain = world.repo(os.path.join(world.code, "group", "plain"), ahead=1)
    world.repo(os.path.join(plain, "inside"), ahead=7)
    world.repo(os.path.join(world.code, "group", "deep", "deeper"), ahead=9)      # two folders down: not found
    top = world.repo(os.path.join(world.code, "top"), ahead=2)
    world.repo(os.path.join(top, "inside"), ahead=11)                             # inside a repository: not found
    world.mailboxes(["recipes"])
    code, out, err = world.conduct("waiting", "--json")
    assert (code, err) == (0, "")
    said = json.loads(out)
    assert [r["folder"] for r in said["other_repositories"]] == [plain, top]
    assert said["totals"]["commits_not_pushed"] == 3


def test_subjects_and_folder_names_are_data(world):
    odd = 'It\'s "quoted" \\ back\nnew line $HOME `x` </script> é 日本'
    folder = world.repo(os.path.join(world.code, "it's $HOME `x` é"), changed=['?? "a b"'])
    world.repo(world.project("recipes", "non-code"))
    world.mailboxes(["recipes"])
    lists(world, "new", "recipes", [mail("m1", "bernstein", odd)])
    code, out, err = world.conduct("waiting")
    assert (code, err) == (0, "")
    assert ('  From bernstein, unread: "It\'s \\"quoted\\" \\\\ back\\nnew line $HOME `x` </script> é 日本"'
            " (sent 2026-10-18T08:00:00Z)\n") in out
    assert f"  {folder}: 1 file uncommitted\n" in out
    code, out, err = world.conduct("waiting", "--json")
    said = json.loads(out)
    assert said["projects"][0]["from_bernstein"][0]["subject"] == odd
    assert said["other_repositories"][0]["folder"] == folder


@pytest.mark.parametrize("fail, message", [
    ("git:remote", "git remote in {folder} failed (exit 1)\n  git: stub failure"),
    ("git:--no-optional-locks", "git status in {folder} failed (exit 1)\n  git: stub failure"),
    ("git:rev-list:1", "git rev-list in {folder} failed (exit 1)\n  git: stub failure"),
    ("lobster-mail:duty", "lobster-mail duty status --all failed (exit 1)\n  lobster-mail: stub failure"),
    ("lobster-mail:list:3", "lobster-mail list --new for recipes failed (exit 3)\n  lobster-mail: stub failure"),
])
def test_a_program_that_fails_stops_the_report_with_exit_4_and_prints_none_of_it(world, fail, message):
    folder = world.repo(world.project("recipes", "non-code"), ahead=1)
    world.mailboxes(["recipes"])
    world.fail(fail)
    code, out, err = world.conduct("waiting")
    assert (code, out, err) == (4, "", "conduct: " + message.format(folder=folder) + "\n")


@pytest.mark.parametrize("what, text, message", [
    ("rev-list", "many\n", "git rev-list --count in {folder} did not print a number"),
    ("duty", "not json", "lobster-mail duty status --all --json did not print the expected JSON"),
    ("list", "not json", "lobster-mail list --new --json did not print the expected JSON for recipes"),
    ("list", '{"id": "m1"}', "lobster-mail list --new --json did not print the expected JSON for recipes"),
    ("list", '[{"id": "m1", "from": "bernstein"}]',
     "lobster-mail list --new --json did not print the expected JSON for recipes"),
])
def test_output_that_is_not_what_was_expected_stops_the_report_with_exit_4(world, what, text, message):
    folder = world.repo(world.project("recipes", "non-code"))
    world.mailboxes(["recipes"])
    if what == "rev-list":
        with open(os.path.join(folder, ".git", "stub-rev-list"), "w") as f:
            f.write(text)
    elif what == "duty":
        with open(os.path.join(world.bin, "duty.json"), "w") as f:
            f.write(text)
    else:
        lists(world, "new", "recipes", text)
    code, out, err = world.conduct("waiting", "--json")
    assert (code, out, err) == (4, "", "conduct: " + message.format(folder=folder) + "\n")


def test_git_that_cannot_be_run_is_exit_4_and_no_traceback(world):
    from bernstein import conduct
    folder = world.repo(world.project("recipes", "non-code"))
    world.mailboxes(["recipes"])
    os.remove(os.path.join(world.bin, "git"))
    out, err = io.StringIO(), io.StringIO()
    env = {"PATH": world.bin, "HOME": world.home, "BERNSTEIN_CONF": world.conf}    # the stubs alone: no git at all
    code = conduct.main(["waiting"], env=env, today=NOW, out=out, err=err, sleep=lambda seconds: None)
    assert (code, out.getvalue()) == (4, "")
    assert err.getvalue() == f"conduct: git remote in {folder} could not be run (No such file or directory)\n"


def test_waiting_takes_no_project_and_no_other_flag(world):
    code, out, err = world.conduct("waiting", "recipes")
    assert (code, out) == (2, "")
    assert err == "conduct: unrecognized arguments: recipes (conduct --help shows the form)\n"
    code, out, err = world.conduct("waiting", "--all")
    assert (code, out, err) == (2, "", "conduct: unrecognized arguments: --all (conduct --help shows the form)\n")
    assert world.calls() == []


def test_help_shows_waiting(world):
    code, out, err = world.conduct("--help")
    assert (code, err) == (0, "")
    assert "conduct waiting [--json]\n" in out
    code, out, err = world.conduct("waiting", "--help")
    assert (code, err) == (0, "")
    assert "it reads only" in " ".join(out.split())
