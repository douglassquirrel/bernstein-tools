"""new-lobster --check-template's pure parts: the ways, what is left in a rendered file, and the report."""

from bernstein import checktemplate


def test_there_are_23_ways_each_named_by_its_kind_and_what_applies():
    assert [w.name for w in checktemplate.ways()] == [
        "non-code", "non-code,public", "non-code,tickets", "non-code,public,tickets",
        "non-code,claws", "non-code,public,claws", "non-code,tickets,claws", "non-code,public,tickets,claws",
        "code", "code,public", "code,tickets", "code,public,tickets",
        "claw", "claw,public", "claw,tickets", "claw,public,tickets",
        "conductor-claw", "conductor-claw,public", "conductor-claw,tickets", "conductor-claw,public,tickets",
        "feeler", "feeler,claw", "feeler,claws"]


def test_a_way_says_which_half_it_renders_and_with_what():
    by_name = {w.name: w for w in checktemplate.ways()}
    w = by_name["non-code,public,tickets,claws"]
    assert (w.half, w.public, w.backlog, w.claws, w.lone, w.conductor) == (
        "non-code", True, True, ("first-tools", "second-tools"), False, False)
    assert (by_name["claw"].half, by_name["claw"].lone, by_name["claw"].conductor) == ("code", True, False)
    assert (by_name["conductor-claw,tickets"].conductor, by_name["conductor-claw,tickets"].backlog) == (True, True)
    assert by_name["code"].claws == () and not by_name["code"].lone
    assert [by_name[n].claws for n in ("feeler", "feeler,claw", "feeler,claws")] == [
        (), ("first-tools",), ("first-tools", "second-tools")]


def test_a_to_fill_gap_is_counted_and_is_not_a_leftover():
    text = "# Title\n\n{{to fill: the purpose}}\nand {{to fill: the brief}} here, {{to fill: more}}\n"
    assert checktemplate.gaps(text) == 3
    assert checktemplate.leftovers(text) == []
    assert checktemplate.gaps("no gap: {{TO FILL}} {to fill: x}\n") == 0


def test_any_other_double_brace_is_a_leftover_with_its_line_number_once_a_line():
    text = ("fine\nSee {{Name}} and {{other}} here\n{{to fill: ok}} but {{> sections/x.md}} is not\n"
            "{{ }}\nclosing }} alone is fine\n   {{indented}}   \n")
    assert checktemplate.leftovers(text) == [
        (2, "See {{Name}} and {{other}} here"), (3, "{{to fill: ok}} but {{> sections/x.md}} is not"),
        (4, "{{ }}"), (6, "{{indented}}")]


def test_the_report_lists_the_template_each_way_its_notes_and_faults_and_a_last_line():
    data = {"template": "/t/lobster", "version": "18 October 2026 (2)", "global_files": ["RULES.md", "inbox/README.md"],
            "faults": [],
            "ways": [{"way": "non-code", "files": 6, "to_fill": 1, "notes": [], "faults": []},
                     {"way": "code,public", "files": None, "to_fill": 0, "notes": [],
                      "faults": ["code/CLAUDE.md: the include sections/repo-public.md is not in common/"]},
                     {"way": "feeler", "files": 5, "to_fill": 2, "notes": ["does not get inbox/README.md"],
                      "faults": ["CLAUDE.md: {{ left in line 3: See {{Name}}", "another"]}]}
    assert checktemplate.text(data) == (
        "Template: /t/lobster\nVersion: 18 October 2026 (2)\nGlobal files: RULES.md, inbox/README.md\n\n"
        "non-code: 6 files, 1 to fill\n"
        "code,public: cannot be rendered\n"
        "  fault: code/CLAUDE.md: the include sections/repo-public.md is not in common/\n"
        "feeler: 5 files, 2 to fill; does not get inbox/README.md\n"
        "  fault: CLAUDE.md: {{ left in line 3: See {{Name}}\n"
        "  fault: another\n\n"
        "3 ways: 3 faults in 2 ways.\n")


def test_a_clean_report_says_so_and_names_what_the_template_lacks():
    data = {"template": "/t", "version": "", "global_files": [], "faults": ["common/global-files: ../x is not a path inside a project"],
            "ways": [{"way": "feeler", "files": 1, "to_fill": 0, "notes": [], "faults": []}]}
    assert checktemplate.text(data) == (
        "Template: /t\nVersion: none (the template has no common/version)\nGlobal files: none\n"
        "  fault: common/global-files: ../x is not a path inside a project\n\n"
        "feeler: 1 file, 0 to fill\n\n1 way: 1 fault in the template itself.\n")
    data["faults"] = []
    assert checktemplate.text(data).endswith("feeler: 1 file, 0 to fill\n\n1 way: all render clean.\n")
