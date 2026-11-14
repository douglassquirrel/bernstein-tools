"""new-lobster sets Backlog up only when asked (PLAN.md, Settled 147): a project keeps tickets or it does not."""

import os

from conftest import tree, write_tree

TICKETS = {"non-code/RULES.md": "Rules of {{SELF}}.\n{{> sections/tickets-{{BACKLOG}}.md}}\n",
           "code/RULES.md": "Rules of {{SELF}}.\n{{> sections/tickets-{{BACKLOG}}.md}}\n",
           "common/sections/tickets-yes.md": "Tickets: ids `{{BACKLOG_PREFIX}}-nnn`.\n",
           "common/sections/tickets-no.md": "No tickets here.\n"}


def programs(world):
    return [c["prog"] for c in world.calls()]


def adds(world):
    return [c["args"] for c in world.calls() if c["prog"] == "git" and c["args"][:1] == ["add"]]


def test_a_new_pair_keeps_no_tickets_unless_asked_backlog_is_not_run_and_its_rules_say_so(world):
    write_tree(world.template, TICKETS)
    code, out, err = world.run("--dry-run", "recipes")
    assert (code, err) == (0, "")
    assert (f"Then: git init -b main in each repository; lobster-mail init recipes and recipes-tools in {world.mail}; "
            "a first commit in each; the tools' .venv.\n") in out
    code, _out, err = world.run("recipes")
    assert code == 0, err
    assert "backlog" not in programs(world)
    assert all("backlog" not in args for args in adds(world)) and len(adds(world)) == 2
    nc, tools = os.path.join(world.non_code, "recipes"), os.path.join(world.code, "recipes-tools")
    assert tree(nc)["RULES.md"] == b"Rules of recipes.\nNo tickets here.\n"
    assert tree(tools)["RULES.md"] == b"Rules of recipes-tools.\nNo tickets here.\n"


def test_a_new_pair_asked_to_keep_tickets_gets_backlog_in_both_halves_and_rules_that_say_so(world):
    write_tree(world.template, TICKETS)
    code, out, err = world.run("--dry-run", "--backlog", "recipes")
    assert (code, err) == (0, "")
    assert (f"Then: git init -b main in each repository; backlog init in each half; lobster-mail init recipes and "
            f"recipes-tools in {world.mail}; a first commit in each; the tools' .venv.\n") in out
    code, _out, err = world.run("--backlog", "recipes")
    assert code == 0, err
    nc, tools = os.path.join(world.non_code, "recipes"), os.path.join(world.code, "recipes-tools")
    assert [(c["args"][1], c["cwd"]) for c in world.calls() if c["prog"] == "backlog"] == [
        ("recipes", nc), ("recipes-tools", tools)]
    assert [args[-1] for args in adds(world)] == ["backlog", "backlog"]
    assert tree(nc)["RULES.md"] == b"Rules of recipes.\nTickets: ids `RE-nnn`.\n"
    assert tree(tools)["RULES.md"] == b"Rules of recipes-tools.\nTickets: ids `RE-nnn`.\n"


def test_a_new_claw_keeps_no_tickets_unless_asked(world):
    write_tree(world.template, TICKETS)
    code, out, _err = world.run("--claw", "--dry-run", "knives")
    assert code == 0 and (f"Then: git init -b main; lobster-mail init knives in {world.mail}; a first commit; "
                          "the .venv.\n") in out
    code, _out, err = world.run("--claw", "knives")
    assert code == 0, err
    assert "backlog" not in programs(world)
    assert tree(os.path.join(world.code, "knives"))["RULES.md"] == b"Rules of knives.\nNo tickets here.\n"
    code, out, _err = world.run("--claw", "--backlog", "--dry-run", "forks")
    assert code == 0 and "Then: git init -b main; backlog init; lobster-mail init forks in " in out
    code, _out, err = world.run("--claw", "--backlog", "forks")
    assert code == 0, err
    assert programs(world).count("backlog") == 1
    assert tree(os.path.join(world.code, "forks"))["RULES.md"] == b"Rules of forks.\nTickets: ids `FO-nnn`.\n"


def test_a_feeler_is_never_given_tickets_and_a_render_takes_the_flag(world, tmp_path):
    code, _out, err = world.run("--feeler", "--backlog", "agents")
    assert code == 2
    assert err == ("new-lobster: --backlog cannot be used with --feeler: a feeler keeps no tickets "
                   "(new-lobster --help shows the form)\n")
    assert os.listdir(world.non_code) == [] and world.calls() == []
    write_tree(world.template, TICKETS)
    for flags, said in (((), b"No tickets here.\n"), (("--backlog",), b"Tickets: ids `RE-nnn`.\n")):
        into = str(tmp_path / ("render" + "".join(flags)))
        code, _out, err = world.run("--render-into", into, *flags, "recipes")
        assert code == 0, err
        assert tree(into)["non-code/RULES.md"] == b"Rules of recipes.\n" + said
        assert tree(into)["code/RULES.md"] == b"Rules of recipes-tools.\n" + said
    assert "--backlog" in world.run("--help")[1]
