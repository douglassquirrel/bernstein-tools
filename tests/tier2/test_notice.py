"""notice: one notice to several projects, each with its own facts, sent as bernstein (PLAN.md, Settled 162)."""

import datetime
import hashlib
import io
import json
import os
import subprocess
import sys

import pytest
from conftest import tree, write_tree

NOW = datetime.datetime(2026, 10, 18, 9, 40, tzinfo=datetime.timezone.utc)
SUBJECT = "Notice: your Backlog was moved"
BODY = ("To {{PROJECT}}, from bernstein.\n\nOn {{WHEN}} your unused backlog/ was moved to\n{{KEPT}}\nin {{FOLDER}}. "
        "Nothing else changed; {{to fill: nothing}}.\n")
ID = "2026-10-18-0940-bernstein-to-{}"


def notice(world, *argv):
    from bernstein import notice as command
    out, err = io.StringIO(), io.StringIO()
    env = {"PATH": world.bin + os.pathsep + "/usr/bin:/bin", "HOME": world.home, "BERNSTEIN_CONF": world.conf}
    code = command.main(list(argv), env=env, today=NOW, out=out, err=err, sleep=lambda seconds: None)
    return code, out.getvalue(), err.getvalue()


def three(world, tmp_path, body=BODY, facts=None):
    """Three projects with mailboxes and nobody on duty, a body and a facts file: (folders, arguments)."""
    at = {"recipes": world.project("recipes", "non-code"), "recipes-tools": world.project("recipes-tools", "code"),
          "menus": world.project("menus", "non-code", under="eat")}
    world.duty({name: None for name in at})
    if facts is None:
        facts = {name: {"KEPT": f"{folder}/_to_delete/backlog-removed-2026-10-18-0940/backlog",
                        "WHEN": "18 October 2026, 09:40Z"} for name, folder in at.items()}
    write_tree(str(tmp_path), {"body.md": body, "facts.json": json.dumps(facts)})
    return at, ("--subject", SUBJECT, "--body", str(tmp_path / "body.md"), "--facts", str(tmp_path / "facts.json"))


def sends(world):
    return [c for c in world.calls() if c["prog"] == "lobster-mail" and c["args"][:1] == ["send"]]


def body_for(name, folder):
    return (f"To {name}, from bernstein.\n\nOn 18 October 2026, 09:40Z your unused backlog/ was moved to\n"
            f"{folder}/_to_delete/backlog-removed-2026-10-18-0940/backlog\nin {folder}. Nothing else changed; "
            "{{to fill: nothing}}.\n")


def test_each_project_gets_one_message_as_bernstein_with_its_own_facts_filled_in(world, tmp_path):
    at, args = three(world, tmp_path)
    before = {name: tree(folder) for name, folder in at.items()}
    code, out, err = notice(world, *args, "recipes", "recipes-tools", "menus")
    assert (code, err) == (0, "")
    assert out == (f"Sent to recipes: {ID.format('recipes')}\n"
                   f"Sent to recipes-tools: {ID.format('recipes-tools')}\n"
                   f"Sent to menus: {ID.format('menus')}\n"
                   f"Sent 3 notices as bernstein, subject \"{SUBJECT}\".\n")
    assert [(c["args"], c["stdin"]) for c in sends(world)] == [
        (["send", "--as", "bernstein", "--to", name, "--subject", SUBJECT, "--root", world.mail, "--json", "-"],
         body_for(name, at[name])) for name in ("recipes", "recipes-tools", "menus")]
    assert {name: tree(folder) for name, folder in at.items()} == before
    assert {c["prog"] for c in world.calls()} == {"lobster-mail"}
    assert {c["args"][0] for c in world.calls()} == {"duty", "list", "send"}


def test_dry_run_prints_every_notice_whole_and_the_real_run_then_sends_those_bytes(world, tmp_path):
    at, args = three(world, tmp_path)
    order = ("menus", "recipes-tools", "recipes")
    code, out, err = notice(world, "--dry-run", *args, *order)
    assert (code, err) == (0, "")
    assert out == "".join(f"Would send to {name}, as bernstein, subject \"{SUBJECT}\":\n\n{body_for(name, at[name])}\n"
                          for name in order) + "Dry run: nothing was sent.\n"
    assert sends(world) == []
    assert notice(world, *args, *order)[0] == 0
    assert [c["args"][4] for c in sends(world)] == list(order)
    for call in sends(world):
        assert f"\n\n{call['stdin']}\n" in out


def test_a_body_with_no_places_needs_no_facts_and_one_with_only_the_two_of_its_own_needs_no_file(world, tmp_path):
    at, _args = three(world, tmp_path, body="The same for everyone.\n")
    code, out, err = notice(world, "--subject", "Notice: x", "--body", str(tmp_path / "body.md"), "recipes", "menus")
    assert (code, err) == (0, "") and [c["stdin"] for c in sends(world)] == ["The same for everyone.\n"] * 2
    write_tree(str(tmp_path), {"own.md": "{{PROJECT}} is at {{FOLDER}}.\n"})
    code, out, err = notice(world, "--subject", "Notice: y", "--body", str(tmp_path / "own.md"), "recipes-tools")
    assert (code, err) == (0, "")
    assert sends(world)[-1]["stdin"] == f"recipes-tools is at {at['recipes-tools']}.\n"
    assert out.endswith("Sent 1 notice as bernstein, subject \"Notice: y\".\n")


def refused(world, *argv, code=3):
    """Run it for real and as a dry run: the same refusal both times, nothing printed, nothing sent."""
    said = set()
    for run in (argv, ("--dry-run",) + argv):
        got, out, err = notice(world, *run)
        assert (got, out) == (code, "")
        assert err.startswith("notice: ") and err.endswith("\n")
        said.add(err[len("notice: "):-1])
    assert sends(world) == [] and len(said) == 1
    return said.pop()


def test_a_project_with_no_mailbox_stops_the_run_with_nothing_sent_even_to_those_in_order(world, tmp_path):
    _at, args = three(world, tmp_path)
    world.duty({"recipes": None, "menus": None})                               # recipes-tools has no mailbox
    assert refused(world, *args, "recipes", "recipes-tools", "menus") == (
        f"there is no mailbox recipes-tools in {world.mail}; nothing was sent")


def test_a_place_in_the_body_with_no_fact_for_some_project_stops_the_run(world, tmp_path):
    at, args = three(world, tmp_path)
    facts = str(tmp_path / "facts.json")
    with open(facts) as f:
        given = json.load(f)
    del given["menus"]["WHEN"]
    del given["recipes-tools"]
    with open(facts, "w") as f:
        json.dump(given, f)
    assert refused(world, *args, "recipes", "menus") == (
        f"the body has the place {{{{WHEN}}}}, and {facts} gives menus no fact WHEN; nothing was sent")
    assert refused(world, *args, "recipes", "recipes-tools", "menus") == (
        f"the body has the place {{{{WHEN}}}}, and {facts} has no block for recipes-tools; nothing was sent")
    assert refused(world, "--subject", SUBJECT, "--body", str(tmp_path / "body.md"), "recipes") == (
        "the body has the place {{WHEN}}, and no facts file was given (--facts) to fill it for recipes; nothing "
        "was sent")
    os.makedirs(os.path.join(world.mail, "lodger"))
    world.duty({"recipes": None, "lodger": None})                              # a mailbox whose project has no folder
    with open(facts, "w") as f:
        json.dump({"recipes": given["recipes"], "lodger": given["recipes"]}, f)
    assert refused(world, *args, "recipes", "lodger") == (
        f"the body has the place {{{{FOLDER}}}}, and lodger has no folder in {world.non_code} or {world.code}, or a "
        "folder directly inside either; nothing was sent")
    assert tree(at["recipes"]) == {"lobster.conf": tree(at["recipes"])["lobster.conf"],
                                   "START-HERE.txt": b"Start recipes.\n"}


def test_facts_for_a_project_that_is_not_named_and_an_empty_body_or_subject_stop_the_run(world, tmp_path):
    _at, args = three(world, tmp_path)
    assert refused(world, *args, "recipes", "menus") == (
        f"{tmp_path}/facts.json has a block for recipes-tools, which is not among the projects named; nothing "
        "was sent")
    write_tree(str(tmp_path), {"empty.md": " \n\t\n"})
    assert refused(world, "--subject", SUBJECT, "--body", str(tmp_path / "empty.md"), "recipes") == (
        f"the body {tmp_path}/empty.md is empty; nothing was sent")
    assert refused(world, "--subject", "  ", "--body", str(tmp_path / "body.md"), "recipes") == (
        "the subject is empty; nothing was sent")
    assert world.calls() == []                                                 # all three before anything is asked


@pytest.mark.parametrize("change, said", [
    (("--subject", "two\nlines"), "the subject must be one line"),
    (("--body", "{tmp}/gone.md"), "the body {tmp}/gone.md cannot be read (No such file or directory)"),
    (("--body", "{tmp}/latin.md"), "the body {tmp}/latin.md is not plain UTF-8 text"),
    (("--facts", "{tmp}/gone.json"), "the facts file {tmp}/gone.json cannot be read (No such file or directory)"),
    (("--facts", "{tmp}/body.md"), "{tmp}/body.md is not JSON"),
    (("--keep", "{tmp}/body.md"), "--keep {tmp}/body.md is not a folder: make it first"),
    (("--keep", "{tmp}/nowhere"), "--keep {tmp}/nowhere is not a folder: make it first"),
])
def test_arguments_that_cannot_be_used_are_exit_2_before_anything_is_asked_or_sent(world, tmp_path, change, said):
    _at, args = three(world, tmp_path)
    (tmp_path / "latin.md").write_bytes("café\n".encode("latin-1"))
    flag, value = change[0], change[1].format(tmp=tmp_path)
    given = list(args)
    if flag in given:
        given[given.index(flag) + 1] = value
    else:
        given += [flag, value]
    assert refused(world, *given, "recipes", "recipes-tools", "menus", code=2) == (
        said.format(tmp=tmp_path) + " (notice --help shows the form)")
    assert world.calls() == []


def test_a_project_named_twice_no_project_and_a_missing_subject_or_body_are_exit_2(world, tmp_path):
    _at, args = three(world, tmp_path)
    assert refused(world, *args, "recipes", "menus", "recipes", code=2) == (
        "recipes is named twice (notice --help shows the form)")
    assert refused(world, *args, code=2) == (
        "the following arguments are required: PROJECT (notice --help shows the form)")
    assert refused(world, "--body", args[3], "recipes", code=2) == (
        "the following arguments are required: --subject (notice --help shows the form)")
    assert refused(world, "--subject", SUBJECT, "recipes", code=2) == (
        "the following arguments are required: --body (notice --help shows the form)")
    code, out, err = notice(world, "--help")
    assert (code, err) == (0, "") and "usage: notice [-h] [--dry-run] --subject TEXT --body FILE" in out
    assert "--facts FILE" in out and "--keep DIR" in out and "PROJECT [PROJECT ...]" in out


def test_quotes_dollars_backslashes_accents_and_markup_in_a_fact_or_the_subject_are_data(world, tmp_path):
    odd = "it's $HOME `id` $(id) \\n \"q\" </script> café café {{PROJECT}} %s"
    _at, args = three(world, tmp_path, body="Kept: {{KEPT}}\n", facts={"recipes": {"KEPT": odd}})
    subject = "Notice: it's \"$HOME\" `id` \\ </script> café"
    given = ["--subject", subject] + list(args[2:])
    code, out, err = notice(world, *given, "recipes")
    assert (code, err) == (0, "")
    sent = sends(world)[0]
    assert sent["stdin"] == f"Kept: {odd}\n" and sent["args"][sent["args"].index("--subject") + 1] == subject
    code, out, err = notice(world, "--dry-run", *given, "recipes")
    assert out.startswith(f"Would send to recipes, as bernstein, subject \"{subject}\":\n\nKept: {odd}\n\n")


def test_the_command_file_runs_as_a_program(world):
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    done = subprocess.run([sys.executable, os.path.join(here, "notice"), "--help"], capture_output=True,
                          text=True, check=False, env={"PATH": "/usr/bin:/bin", "HOME": world.home})
    assert done.returncode == 0 and "usage: notice" in done.stdout


def waits_unread(world, project, ident, body, subject=SUBJECT, sender="bernstein"):
    """Make the stub say this message waits unread in the project's mailbox, as lobster-mail lists and prints it."""
    path = os.path.join(world.bin, f"list-new-{project}.json")
    listed = []
    if os.path.exists(path):
        with open(path) as f:
            listed = json.load(f)
    listed.append({"id": ident, "from": sender, "date": "2026-10-18T08:00:00Z", "subject": subject, "box": "new"})
    with open(path, "w") as f:
        json.dump(listed, f)
    with open(os.path.join(world.bin, f"read-{ident}.txt"), "w", encoding="utf-8", newline="") as f:
        f.write(f"From: {sender}\nTo: {project}\nDate: 2026-10-18T08:00:00Z\nSubject: {subject}\nId: {ident}\n"
                f"Body-SHA-256: {hashlib.sha256(body.encode('utf-8')).hexdigest()}\n\n{body}")


def test_a_project_that_already_has_this_very_notice_unread_is_passed_over_and_not_sent_it_twice(world, tmp_path):
    at, args = three(world, tmp_path)
    waits_unread(world, "recipes", "m-earlier", body_for("recipes", at["recipes"]))
    waits_unread(world, "menus", "m-other-words", body_for("menus", at["menus"]) + "A last line that differs.\n")
    waits_unread(world, "menus", "m-other-subject", body_for("menus", at["menus"]), subject="Notice: another")
    waits_unread(world, "menus", "m-other-sender", body_for("menus", at["menus"]), sender="recipes")
    code, out, err = notice(world, "--dry-run", *args, "recipes", "recipes-tools", "menus")
    assert (code, err) == (0, "")
    assert out.startswith("recipes already has this notice unread (m-earlier): it is passed over.\n"
                          f"Would send to recipes-tools, as bernstein, subject \"{SUBJECT}\":\n")
    assert f"Would send to menus, as bernstein, subject \"{SUBJECT}\":\n" in out and "Would send to recipes," not in out
    code, out, err = notice(world, *args, "recipes", "recipes-tools", "menus")
    assert (code, err) == (0, "")
    assert out == ("recipes already has this notice unread (m-earlier): it is passed over.\n"
                   f"Sent to recipes-tools: {ID.format('recipes-tools')}\n"
                   f"Sent to menus: {ID.format('menus')}\n"
                   f"Sent 2 notices as bernstein, subject \"{SUBJECT}\"; 1 project already had it.\n")
    assert [c["args"][4] for c in sends(world)] == ["recipes-tools", "menus"]
    reads = [c["args"] for c in world.calls() if c["args"][:1] == ["read"]]
    assert sorted(a[-1] for a in reads) == ["m-earlier", "m-earlier", "m-other-words", "m-other-words"]
    assert all(a[:5] == ["read", "--as", a[2], "--root", world.mail] for a in reads)


def test_when_every_project_already_has_it_nothing_is_sent_and_the_exit_is_0(world, tmp_path):
    at, args = three(world, tmp_path)
    for name in at:
        waits_unread(world, name, "m-" + name, body_for(name, at[name]))
    code, out, err = notice(world, *args, *at)
    assert (code, err) == (0, "")
    assert out.endswith("Nothing was sent: every project named already has this notice unread.\n")
    assert out.count("it is passed over") == 3 and sends(world) == []


def test_keep_writes_each_notice_as_sent_with_its_id_and_never_over_a_file(world, tmp_path):
    at, args = three(world, tmp_path)
    kept = tmp_path / "requests"
    kept.mkdir()
    code, out, err = notice(world, "--dry-run", *args, "--keep", str(kept), *at)
    assert (code, err) == (0, "") and os.listdir(kept) == []
    assert out.endswith(f"Dry run: nothing was sent. Each notice sent would be kept in {kept}.\n")
    code, out, err = notice(world, *args, "--keep", str(kept), *at)
    assert (code, err) == (0, "")
    assert f"Sent to recipes: {ID.format('recipes')} (kept as {kept}/{ID.format('recipes')}.md)\n" in out
    assert tree(str(kept)) == {
        ID.format(name) + ".md": (f"From: bernstein\nTo: {name}\nSubject: {SUBJECT}\nId: {ID.format(name)}\n\n"
                                  + body_for(name, at[name])).encode("utf-8") for name in at}
    code, out, err = notice(world, *args, "--keep", str(kept), *at)             # the stub gives the same ids again
    assert code == 4 and out == f"Sent to recipes: {ID.format('recipes')}\n"
    assert err == (f"notice: the notice to recipes was sent ({ID.format('recipes')}), but its copy could not be kept "
                   f"as {kept}/{ID.format('recipes')}.md (File exists). Sent: recipes. Not attempted: recipes-tools, "
                   "menus. Nothing is sent twice by naming only those not attempted\n")
    assert len(sends(world)) == 4


def test_a_send_that_fails_stops_the_run_naming_what_was_sent_and_what_was_not_attempted(world, tmp_path, monkeypatch):
    from bernstein import conduct
    _at, args = three(world, tmp_path)
    real, sent = conduct.run, []

    def second_send_fails(argv, env, what, stdin=None, also_fine=()):
        if argv[1] == "send":
            sent.append(argv[argv.index("--to") + 1])
            if len(sent) == 2:
                raise conduct.Stop(4, f"{what} failed (exit 1)\n  disk full")
        return real(argv, env, what, stdin=stdin, also_fine=also_fine)
    monkeypatch.setattr(conduct, "run", second_send_fails)
    code, out, err = notice(world, *args, "recipes", "recipes-tools", "menus")
    assert code == 4 and out == f"Sent to recipes: {ID.format('recipes')}\n"
    assert err == ("notice: lobster-mail send to recipes-tools failed (exit 1)\n  disk full\n"
                   f"  Sent before it: recipes ({ID.format('recipes')}). Not sent: recipes-tools. Not attempted: menus. "
                   "Nothing is sent twice by naming only those not sent\n")
    assert sent == ["recipes", "recipes-tools"]


def test_a_message_delivered_without_bernsteins_own_copy_counts_as_sent_and_is_never_sent_again(world, tmp_path):
    _at, args = three(world, tmp_path)
    world.fail("lobster-mail:send:7")
    code, out, err = notice(world, *args, "recipes", "recipes-tools", "menus")
    assert code == 0 and len(sends(world)) == 3
    assert out == ("Sent to recipes: its id is not known\nSent to recipes-tools: its id is not known\n"
                   "Sent to menus: its id is not known\n"
                   f"Sent 3 notices as bernstein, subject \"{SUBJECT}\".\n")
    assert err.count("reached") == 3 and err.startswith(
        "notice: the notice reached recipes, but bernstein's own copy of it could not be kept (lobster-mail exit 7); "
        "it was not sent again\n  lobster-mail: stub failure\n")


def test_a_listing_that_cannot_be_had_is_exit_4_and_nothing_is_sent(world, tmp_path):
    at, args = three(world, tmp_path)
    world.fail("lobster-mail:duty")
    code, out, err = notice(world, *args, *at)
    assert (code, out) == (4, "") and err == ("notice: lobster-mail duty status --all failed (exit 1)\n  lobster-mail: "
                                              "stub failure\n  nothing was sent\n")
    world.fail("lobster-mail:list")
    code, out, err = notice(world, *args, *at)
    assert (code, out) == (4, "") and err == ("notice: lobster-mail list --new for recipes failed (exit 1)\n  "
                                              "lobster-mail: stub failure\n  nothing was sent\n")
    world.fail()
    with open(os.path.join(world.bin, "list-new-menus.json"), "w") as f:
        f.write('{"not": "a list"}')
    code, out, err = notice(world, *args, *at)
    assert (code, out) == (4, "") and err == ("notice: lobster-mail list --new for menus did not print the expected "
                                              "JSON\n  nothing was sent\n")
    assert sends(world) == []


def test_a_bad_settings_line_a_project_in_two_places_and_an_answer_with_no_id_are_each_handled(world, tmp_path):
    at, args = three(world, tmp_path, body="{{PROJECT}} at {{FOLDER}}.\n", facts={})
    os.makedirs(os.path.join(world.code, "recipes"))
    assert refused(world, *args[:4], "recipes") == (
        f"the body has the place {{{{FOLDER}}}}, and recipes is in two places, {at['recipes']} and {world.code}/recipes: "
        "keep one, or rename the other; nothing was sent")
    os.rmdir(os.path.join(world.code, "recipes"))
    world.write_conf("EFFORT=extreme\n")
    assert refused(world, *args[:4], "recipes", code=2) == (
        f"{world.conf}: line 7: EFFORT must be one of low, medium, high, xhigh, max (notice --help shows the form)")
    world.write_conf("")
    with open(os.path.join(world.bin, "lobster-mail")) as f:
        stub = f.read()
    with open(os.path.join(world.bin, "lobster-mail"), "w") as f:
        f.write(stub.replace("printf '{\"id\": \"2026-10-18-0940-bernstein-to-%s\", \"to\": \"%s\"}\\n' \"$to\" \"$to\"",
                             "echo Sent"))
    code, out, err = notice(world, *args[:4], "recipes")
    assert (code, err) == (0, "") and out.startswith("Sent to recipes: its id is not known\n")
