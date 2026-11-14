import datetime

import pytest

from bernstein.render import TemplateRefused, fill, render_half, values_for

VALUES = {"NAME": "recipes", "TOOLS": "recipes-tools", "SELF": "recipes", "VISIBILITY": "private"}


def write(root, files):
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def test_fill_replaces_known_placeholders_and_leaves_the_rest_as_written():
    text = "{{NAME}} and {{TOOLS}}; {{to fill: the purpose}}; on {{D Month YYYY}}; {{not caps}}\n"
    assert fill(text, VALUES, "x.md") == (
        "recipes and recipes-tools; {{to fill: the purpose}}; on {{D Month YYYY}}; {{not caps}}\n")


def test_fill_refuses_an_unknown_capitals_placeholder_naming_the_file():
    with pytest.raises(TemplateRefused) as refused:
        fill("a {{NAME}} b {{WHO}}\n", VALUES, "non-code/CLAUDE.md")
    assert str(refused.value) == "non-code/CLAUDE.md: unknown placeholder {{WHO}}"


def template(tmp_path):
    write(tmp_path, {
        "common/sections/rule.md": "Rule for {{SELF}}.\nSecond line.\n",
        "common/sections/repo-private.md": "A private {{TOOLS}}.\n",
        "common/sections/repo-public.md": "A public {{TOOLS}}.\n",
        "common/inbox/README.md": "Inbox of {{SELF}}.\n",
        "common/lobster.conf": "SELF={{SELF}}\n",
        "non-code/CLAUDE.md": "# {{NAME}}\n\n{{> sections/rule.md}}\n\nEnd.\n",
        "non-code/.claude/settings.json": "{}\n",
        "code/CLAUDE.md": "# {{TOOLS}}\n{{> sections/repo-{{VISIBILITY}}.md}}\n",
        "code/LICENSE": "MIT\n",
        "code/tools.conf.example": "# {{TOOLS}}\n",
    })
    return tmp_path


def test_render_half_gives_the_half_its_own_files_and_the_common_ones_with_includes_resolved(tmp_path):
    got = render_half(str(template(tmp_path)), "non-code", VALUES, public=False)
    assert got == {
        "CLAUDE.md": "# recipes\n\nRule for recipes.\nSecond line.\n\nEnd.\n",
        ".claude/settings.json": "{}\n",
        "inbox/README.md": "Inbox of recipes.\n",
        "lobster.conf": "SELF=recipes\n",
    }


def test_a_private_tools_half_gets_the_private_paragraph_no_licence_and_a_renamed_conf_example(tmp_path):
    values = dict(VALUES, SELF="recipes-tools")
    got = render_half(str(template(tmp_path)), "code", values, public=False)
    assert got["CLAUDE.md"] == "# recipes-tools\nA private recipes-tools.\n"
    assert "LICENSE" not in got
    assert got["recipes-tools.conf.example"] == "# recipes-tools\n"
    assert "tools.conf.example" not in got


def test_a_public_tools_half_gets_the_public_paragraph_and_the_licence(tmp_path):
    values = dict(VALUES, SELF="recipes-tools", VISIBILITY="public")
    got = render_half(str(template(tmp_path)), "code", values, public=True)
    assert got["CLAUDE.md"] == "# recipes-tools\nA public recipes-tools.\n"
    assert got["LICENSE"] == "MIT\n"


def test_refuses_a_missing_include_naming_the_file_and_the_include(tmp_path):
    t = template(tmp_path)
    (t / "non-code" / "CLAUDE.md").write_text("{{> sections/nowhere.md}}\n", encoding="utf-8")
    with pytest.raises(TemplateRefused) as refused:
        render_half(str(t), "non-code", VALUES, public=False)
    assert str(refused.value) == "non-code/CLAUDE.md: the include sections/nowhere.md is not in common/"


def test_refuses_a_missing_template_folder(tmp_path):
    with pytest.raises(TemplateRefused) as refused:
        render_half(str(tmp_path / "gone"), "non-code", VALUES, public=False)
    assert str(refused.value) == "the template folder %s has no non-code/ folder" % (tmp_path / "gone")


def test_values_for_each_half():
    common = {"model": "opus", "effort": "high", "non_code_dir": "/h/projects/non-code", "code_dir": "/h/projects/code",
                  "mail_root": "/h/projects/mail", "lobster_mail": "/h/l/lobster-tools/lobster-mail",
                  "today": datetime.date(2026, 10, 8), "home": "/h"}
    nc = values_for("recipes", "non-code", public=False, **common)
    pinned = {
        "NAME": "recipes", "TOOLS": "recipes-tools", "SELF": "recipes", "SISTER": "recipes-tools",
        "KIND": "non-code", "PACKAGE": "recipestools", "DATE": "8 October 2026", "YEAR": "2026",
        "MODEL": "Opus", "MODEL_SETTING": "opus", "EFFORT": "high",
        "NONCODE_PATH": "~/projects/non-code/recipes", "TOOLS_PATH": "~/projects/code/recipes-tools",
        "MAIL_ROOT": "~/projects/mail", "MAIL_ROOT_SHELL": "/h/projects/mail",
        "LOBSTER_TOOLS": "~/l/lobster-tools", "VISIBILITY": "private",
        "BACKLOG_PREFIX": "RE", "QUESTIONS_AT": 'CLAUDE.md, "Open questions for Squirrel"',
    }
    assert {k: nc[k] for k in pinned} == pinned  # the claw placeholders have their own test below
    code = values_for("recipes", "code", public=True, **common)
    assert (code["SELF"], code["SISTER"], code["KIND"], code["VISIBILITY"]) == ("recipes-tools", "recipes", "code", "public")
    assert code["TOOLS_PATH"] == "~/projects/code/recipes-tools-code/recipes-tools"
    assert code["QUESTIONS_AT"] == 'PLAN.md, "Open questions"'


def test_the_mail_root_for_the_shell_is_quoted_only_when_it_must_be():
    common = {"model": "opus", "effort": "high", "non_code_dir": "/h/n", "code_dir": "/h/c",
                  "lobster_mail": "/h/l/lobster-mail", "today": datetime.date(2026, 10, 8), "home": "/h"}
    got = values_for("recipes", "code", public=False, mail_root="/h/my mail", **common)
    assert got["MAIL_ROOT_SHELL"] == "'/h/my mail'"


def test_a_json_file_that_is_not_valid_once_filled_in_is_refused(tmp_path):
    t = template(tmp_path)
    (t / "non-code" / ".claude" / "settings.json").write_text('{"command": "start --as {{NAME}}"\n', encoding="utf-8")
    with pytest.raises(TemplateRefused) as refused:
        render_half(str(t), "non-code", VALUES, public=False)
    assert str(refused.value) == "non-code/.claude/settings.json: not valid JSON once filled in"


def test_values_for_an_existing_pair_take_its_own_tools_name_and_paths():
    common = {"model": "opus", "effort": "high", "non_code_dir": "/h/projects/non-code", "code_dir": "/h/projects/code",
              "mail_root": "/h/projects/mail", "lobster_mail": "/h/l/lobster-tools/lobster-mail",
              "today": datetime.date(2026, 10, 8), "home": "/h", "tools": "video-tools",
              "non_code_path": "/h/projects/non-code/videos/training-video",
              "tools_path": "/h/projects/code/videos/video-tools-code/video-tools"}
    nc = values_for("training-video", "non-code", public=True, **common)
    assert (nc["TOOLS"], nc["SISTER"], nc["PACKAGE"], nc["NONCODE_PATH"], nc["TOOLS_PATH"]) == (
        "video-tools", "video-tools", "videotools", "~/projects/non-code/videos/training-video",
        "~/projects/code/videos/video-tools-code/video-tools")
    code = values_for("training-video", "code", public=True, **common)
    assert (code["SELF"], code["SISTER"], code["BACKLOG_PREFIX"]) == ("video-tools", "training-video", "TR")


COMMON = {"model": "opus", "effort": "high", "non_code_dir": "/h/projects/non-code", "code_dir": "/h/projects/code",
          "mail_root": "/h/projects/mail", "lobster_mail": "/h/l/lobster-tools/lobster-mail",
          "today": datetime.date(2026, 11, 1), "home": "/h"}


def test_values_for_a_non_code_project_name_its_home_claw_and_the_further_claws_it_uses():
    nc = values_for("beyond-ai", "non-code", public=True, tools="book-tools",
                    claws=["word-tools", "google-docs-tools"], **COMMON)
    assert nc["CLAWS"] == "word-tools google-docs-tools"
    assert nc["CLAW_LIST"] == "`book-tools`, `word-tools` and `google-docs-tools`"
    assert nc["CLAW_NAMES"] == "book-tools, word-tools and google-docs-tools"
    assert nc["OTHER_CLAWS"] == "It also uses the claws `word-tools` and `google-docs-tools`."
    assert nc["CLAW_MOUNTS"] == (
        "| `~/mnt/book-tools` | the home claw, `book-tools`: **read and run only**; never write, commit, install or make a `.venv` in it |\n"
        "| `~/mnt/word-tools` | the claw `word-tools`: read and run only, as above |\n"
        "| `~/mnt/google-docs-tools` | the claw `google-docs-tools`: read and run only, as above |")
    assert nc["CLAW_ROWS"] == (
        "| `book-tools` | {{to fill: as they are made}} | From `~/mnt/book-tools`, as its README says; the home claw, where new tools are born |\n"
        "| `word-tools` | {{to fill: as they are used}} | From `~/mnt/word-tools`, as its README says |\n"
        "| `google-docs-tools` | {{to fill: as they are used}} | From `~/mnt/google-docs-tools`, as its README says |")
    alone = values_for("recipes", "non-code", public=False, **COMMON)
    assert (alone["CLAWS"], alone["CLAW_LIST"], alone["CLAW_NAMES"]) == ("", "`recipes-tools`", "recipes-tools")
    assert alone["OTHER_CLAWS"] == "It uses no other claw yet; when it does, `CLAWS` in `lobster.conf` names them."
    assert alone["CLAW_MOUNTS"].count("\n") == 0 and alone["CLAW_ROWS"].count("\n") == 0


def test_values_for_a_pair_s_code_half_name_the_sister_where_a_lone_claw_names_any_project():
    pair = values_for("recipes", "code", public=False, **COMMON)
    assert pair["SERVED"] == "sister"
    assert pair["FOR_WHOM"] == "the work done in the sister project, `recipes` (`~/projects/non-code/recipes`)"
    assert (pair["REQUESTER"], pair["SERVING"]) == ("`recipes`", "`recipes`")
    assert (pair["TALKS_TO"], pair["ASKING"], pair["SEND_TO"]) == ("its sister project, `recipes`", "`recipes`", "recipes")
    assert pair["OF_WHOM"] == "the tools project of the lobster pair `recipes` and `recipes-tools`"
    assert pair["SISTER_FIRST_SESSION"].startswith("In this tools half, read the sister project's CLAUDE.md first (read only:\n"
                                                   "   ~/projects/non-code/recipes/CLAUDE.md,")
    lone = values_for(None, "code", public=True, tools="word-tools", **COMMON)
    assert (lone["NAME"], lone["SISTER"], lone["NONCODE_PATH"], lone["SELF"], lone["TOOLS"]) == (
        "", "", "", "word-tools", "word-tools")
    assert (lone["SERVED"], lone["BACKLOG_PREFIX"], lone["PACKAGE"], lone["KIND"]) == ("any", "WO", "wordtools", "code")
    assert lone["TOOLS_PATH"] == "~/projects/code/word-tools-code/word-tools"
    assert lone["FOR_WHOM"] == ("the work done in Squirrel's lobster projects (the ganglia), any of which may ask this "
                                "claw for a tool")
    assert (lone["REQUESTER"], lone["SERVING"]) == ("a lobster project", "Squirrel's lobster projects")
    assert (lone["TALKS_TO"], lone["ASKING"], lone["SEND_TO"]) == ("the lobster projects it serves", "another project", "<project>")
    assert lone["OF_WHOM"] == "a claw, `word-tools`: a tools project with no sister project, used by any lobster project that asks"
    assert lone["SISTER_FIRST_SESSION"].startswith("This claw has no sister project: ask Squirrel which lobster projects will use it first")
    assert lone["CLAWS"] == ""


def test_the_sister_words_of_a_non_code_half_name_its_tools_project_not_itself():
    nc = values_for("training-video", "non-code", public=True, tools="video-tools", **COMMON)
    assert (nc["TALKS_TO"], nc["ASKING"], nc["SEND_TO"]) == ("its sister project, `video-tools`", "`video-tools`", "video-tools")
    code = values_for("training-video", "code", public=True, tools="video-tools", **COMMON)
    assert (code["TALKS_TO"], code["ASKING"], code["SEND_TO"]) == (
        "its sister project, `training-video`", "`training-video`", "training-video")


def test_a_project_with_several_claws_is_spoken_of_in_the_plural_with_its_home_claw_named():
    nc = values_for("beyond-ai", "non-code", public=True, tools="book-tools",
                    claws=["word-tools", "google-docs-tools"], **COMMON)
    every = "`book-tools`, `word-tools` and `google-docs-tools`"
    assert nc["ITS_CLAWS"] == "its claws, " + every
    assert nc["FROM_CLAWS"] == "one of its claws, " + every + " (tools projects; `book-tools` is the home claw)"
    assert nc["IN_CLAWS"] == "one of its claws, " + every + " (new tools in `book-tools`, the home claw)"
    assert nc["TOOL_FROM_CLAWS"] == (
        "a tool from one of this project's claws, " + every + ": each a tools project Claude Code builds, tests "
        "and maintains in its own repository, with its own CLAUDE.md, PLAN.md and DIARY.md; the home claw is "
        "`book-tools` (`~/projects/code/book-tools-code/book-tools`)")
    assert nc["THE_CLAWS"] == "the claws (book-tools, word-tools and google-docs-tools)"
    assert nc["WITH_CLAWS"] == "with its claws " + every + " (home: `book-tools`)"


def test_a_project_with_one_claw_is_spoken_of_in_the_singular():
    alone = values_for("recipes", "non-code", public=False, **COMMON)
    assert alone["ITS_CLAWS"] == "its claw, `recipes-tools`"
    assert alone["FROM_CLAWS"] == "its claw, `recipes-tools` (a tools project)"
    assert alone["IN_CLAWS"] == "its claw, `recipes-tools`"
    assert alone["TOOL_FROM_CLAWS"] == (
        "a tool from this project's claw, `recipes-tools` (`~/projects/code/recipes-tools`): a tools project "
        "Claude Code builds, tests and maintains in its own repository, with its own CLAUDE.md, PLAN.md and "
        "DIARY.md")
    assert alone["THE_CLAWS"] == "the claw (recipes-tools)"
    assert alone["WITH_CLAWS"] == "with its claw `recipes-tools`"
    for words in ("ITS_CLAWS", "FROM_CLAWS", "IN_CLAWS", "TOOL_FROM_CLAWS", "THE_CLAWS", "WITH_CLAWS"):
        assert "claws" not in alone[words]


def test_one_further_claw_is_a_claw_and_two_are_claws():
    one = values_for("recipes", "non-code", public=False, claws=["word-tools"], **COMMON)
    assert one["OTHER_CLAWS"] == "It also uses the claw `word-tools`."
    two = values_for("recipes", "non-code", public=False, claws=["word-tools", "book-tools"], **COMMON)
    assert two["OTHER_CLAWS"] == "It also uses the claws `word-tools` and `book-tools`."


def feeler_values(claws=()):
    return values_for("agents", "feeler", model="opus", effort="high", non_code_dir="/h/projects/non-code",
                      code_dir="/h/projects/code", mail_root="/h/projects/mail", lobster_mail="/h/l/lobster-mail",
                      public=False, today=datetime.date(2026, 10, 18), home="/h", claws=claws)


def test_a_feeler_has_no_sister_and_no_home_claw_and_names_the_claws_it_uses():
    v = feeler_values(["word-tools", "knives"])
    assert (v["KIND"], v["SELF"], v["NAME"], v["SISTER"], v["TOOLS"]) == ("feeler", "agents", "agents", "", "")
    assert v["CLAWS"] == "word-tools knives" and v["NONCODE_PATH"] == "~/projects/non-code/agents"
    assert v["FEELER_CLAWS"] == ("It uses the claws `word-tools` and `knives`: tools projects of Squirrel's, "
                                 "connected to its session by `conduct start`.")
    assert v["THE_CLAWS"] == "the claws (word-tools and knives)"
    assert v["CLAW_MOUNTS"] == ("| `~/mnt/word-tools` | the claw `word-tools`: read and run only |\n"
                                "| `~/mnt/knives` | the claw `knives`: read and run only |")


def test_a_feeler_with_one_claw_or_none_says_so_in_the_singular():
    one, none = feeler_values(["knives"]), feeler_values()
    assert one["FEELER_CLAWS"].startswith("It uses the claw `knives`: a tools project of Squirrel's,")
    assert one["THE_CLAWS"] == "the claw (knives)"
    assert none["CLAWS"] == "" and none["THE_CLAWS"] == "no claw yet" and none["CLAW_MOUNTS"] == ""
    assert none["FEELER_CLAWS"] == ("It uses no claw yet; when it does, `CLAWS` in `lobster.conf` names them and "
                                    "`conduct start` connects them.")


def test_a_feeler_half_has_its_own_files_and_lobster_conf_but_no_inbox(tmp_path):
    write(tmp_path, {"common/inbox/README.md": "Inbox of {{SELF}}.\n",
                     "common/lobster.conf": "KIND={{KIND}}\nSELF={{SELF}}\nSISTER={{SISTER}}\nCLAWS={{CLAWS}}\n",
                     "feeler/CLAUDE.md": "# {{NAME}}\n\n{{FEELER_CLAWS}}\n"})
    rendered = render_half(str(tmp_path), "feeler", feeler_values(["knives"]), False)
    assert sorted(rendered) == ["CLAUDE.md", "lobster.conf"]
    assert rendered["lobster.conf"] == "KIND=feeler\nSELF=agents\nSISTER=\nCLAWS=knives\n"
    assert rendered["CLAUDE.md"].startswith("# agents\n\nIt uses the claw `knives`:")


def test_a_project_whose_tickets_carry_a_prefix_of_their_own_keeps_it_in_both_halves():
    common = {"model": "opus", "effort": "high", "non_code_dir": "/h/nc", "code_dir": "/h/code", "mail_root": "/h/mail",
              "lobster_mail": "/h/l/lobster-mail", "today": datetime.date(2026, 10, 8), "home": "/h", "public": False}
    assert values_for("recipes", "non-code", backlog_prefix="FD", **common)["BACKLOG_PREFIX"] == "FD"
    assert values_for("recipes", "code", backlog_prefix="FD", **common)["BACKLOG_PREFIX"] == "FD"
    assert values_for(None, "code", tools="knives", backlog_prefix="KV", **common)["BACKLOG_PREFIX"] == "KV"
    assert values_for("recipes", "non-code", backlog_prefix=None, **common)["BACKLOG_PREFIX"] == "RE"
    assert values_for("recipes", "non-code", backlog_prefix="", **common)["BACKLOG_PREFIX"] == "RE"
    assert "BACKLOG_PREFIX" not in values_for("recipes", "feeler", backlog_prefix="FD", **common)


def test_a_template_is_told_whether_the_project_keeps_tickets_and_a_new_one_keeps_none_unless_asked():
    common = {"model": "opus", "effort": "high", "non_code_dir": "/h/nc", "code_dir": "/h/code", "mail_root": "/h/mail",
              "lobster_mail": "/h/l/lobster-mail", "today": datetime.date(2026, 10, 8), "home": "/h", "public": False}
    assert values_for("recipes", "non-code", **common)["BACKLOG"] == "no"
    assert values_for("recipes", "code", backlog=True, **common)["BACKLOG"] == "yes"
    assert values_for(None, "code", tools="knives", backlog=False, **common)["BACKLOG"] == "no"
    assert "BACKLOG" not in values_for("recipes", "feeler", backlog=True, **common)


def test_values_for_a_conductors_claw_name_the_conductor_and_its_folder_and_choose_its_own_section():
    claw = values_for("maestro", "code", public=True, tools="maestro-tools", conductor=True,
                      non_code_path="/h/projects/code/maestro-code", **COMMON)
    assert (claw["SERVED"], claw["KIND"], claw["SELF"], claw["SISTER"], claw["NAME"], claw["TOOLS"]) == (
        "conductor", "code", "maestro-tools", "maestro", "maestro", "maestro-tools")
    assert claw["NONCODE_PATH"] == "~/projects/code/maestro-code"
    assert claw["TOOLS_PATH"] == "~/projects/code/maestro-tools-code/maestro-tools"
    assert claw["FOR_WHOM"] == "the work done by its conductor, `maestro` (`~/projects/code/maestro-code`)"
    assert (claw["REQUESTER"], claw["SERVING"]) == ("`maestro`", "`maestro`")
    assert (claw["TALKS_TO"], claw["ASKING"], claw["SEND_TO"]) == ("its conductor, `maestro`", "`maestro`", "maestro")
    assert claw["OF_WHOM"] == ("the claw of the conductor `maestro`: the tools project that builds the commands "
                               "`maestro` runs")
    assert claw["SISTER_FIRST_SESSION"] == (
        "This claw's one customer is its conductor: read the conductor's CLAUDE.md first (read only:\n"
        "   ~/projects/code/maestro-code/CLAUDE.md) and offer its answers for \"What this is\",\n"
        "   so Squirrel need not say them twice.")
    assert (claw["BACKLOG_PREFIX"], claw["PACKAGE"], claw["CLAWS"]) == ("MA", "maestrotools", "")
    pair = values_for("maestro", "code", public=True, tools="maestro-tools",
                      non_code_path="/h/projects/code/maestro-code", **COMMON)
    assert {k for k in claw if claw[k] != pair[k]} == {"SERVED", "FOR_WHOM", "TALKS_TO", "OF_WHOM", "SISTER_FIRST_SESSION"}
