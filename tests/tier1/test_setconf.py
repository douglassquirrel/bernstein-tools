"""set-conf's one-line change to the text of a lobster.conf (PLAN.md, "set-conf", Settled 159)."""

import pytest

from bernstein.setconf import Stop, change, setting

CONF = "# written by new-lobster\nKIND=non-code\nSELF=recipes\nSISTER=recipes-tools\nMODEL=opus\nEFFORT=high\n"


@pytest.mark.parametrize("before, key, value, after, was, now", [
    (CONF, "SISTER", "menus-tools", CONF.replace("SISTER=recipes-tools", "SISTER=menus-tools"),
     "SISTER=recipes-tools", "SISTER=menus-tools"),                                    # a line in the middle
    ("MODEL=opus\nEFFORT=high\n", "MODEL", "fable", "MODEL=fable\nEFFORT=high\n", "MODEL=opus", "MODEL=fable"),
    (CONF, "EFFORT", "max", CONF[:-5] + "max\n", "EFFORT=high", "EFFORT=max"),         # the last line
    (CONF[:-1], "EFFORT", "max", CONF[:-5] + "max", "EFFORT=high", "EFFORT=max"),      # ... with no line end
    ("KIND=code\r\nMODEL=opus\r\nEFFORT=high\r\n", "MODEL", "fable", "KIND=code\r\nMODEL=fable\r\nEFFORT=high\r\n",
     "MODEL=opus", "MODEL=fable"),
    ("KIND=code\rMODEL=opus\rEFFORT=high\r", "MODEL", "fable", "KIND=code\rMODEL=fable\rEFFORT=high\r",
     "MODEL=opus", "MODEL=fable"),
    ("KIND=code\nMODEL=opus\r\nEFFORT=high", "MODEL", "fable", "KIND=code\nMODEL=fable\r\nEFFORT=high",
     "MODEL=opus", "MODEL=fable"),                                                     # mixed endings stay mixed
])
def test_a_setting_the_file_has_is_changed_where_it_stands_and_every_other_byte_stays(before, key, value, after,
                                                                                    was, now):
    got = change(before, key, value)
    assert (got.text, got.was, got.now, len(got.on_lines)) == (after, was, now, 1)


def test_what_stands_before_the_equals_sign_is_kept_and_the_whole_rest_of_the_line_is_the_value():
    before = "KIND=non-code\n  FOLDERS =  ~/old one  # was elsewhere\t\nMODEL=opus\n"
    got = change(before, "FOLDERS", "~/models/kokoro")
    assert got.text == "KIND=non-code\n  FOLDERS =~/models/kokoro\nMODEL=opus\n"
    assert (got.was, got.now) == ("  FOLDERS =  ~/old one  # was elsewhere\t", "  FOLDERS =~/models/kokoro")


def test_comments_stay_and_a_commented_out_setting_is_not_taken_for_the_setting():
    before = ("# FOLDERS=~/never\n#FOLDERS=~/nor this\n  # FOLDERS=~/nor this\nKIND=non-code\n"
              "# the folders, FOLDERS=a:b\nFOLDERS=~/old\n# after\nXFOLDERS=~/other\nFOLDERS_TOO=~/other\n")
    got = change(before, "FOLDERS", "~/new")
    assert got.text == before.replace("\nFOLDERS=~/old\n", "\nFOLDERS=~/new\n")
    assert (got.was, got.now, got.on_lines) == ("FOLDERS=~/old", "FOLDERS=~/new", [6])


@pytest.mark.parametrize("value", [
    "~/My Drive/modèles:/Volumes/Big Disk/voices", "a 'quoted' \"value\"", "$HOME/`id`/$(id)", "back\\slash\\n",
    "</script><b>", "KEY=inside=twice", "# not a comment", "café and café", "%s {} {{to fill}}", "\\1\\g<0>",
])
def test_a_value_is_data_whatever_is_in_it(value):
    got = change("KIND=non-code\nFOLDERS=old\nMODEL=opus\n", "FOLDERS", value)
    assert got.text == "KIND=non-code\nFOLDERS=" + value + "\nMODEL=opus\n"
    assert got.now == "FOLDERS=" + value


@pytest.mark.parametrize("before, after", [
    ("KIND=non-code\nMODEL=opus\n", "KIND=non-code\nMODEL=opus\nFOLDERS=~/new\n"),
    ("KIND=non-code\r\nMODEL=opus\r\n", "KIND=non-code\r\nMODEL=opus\r\nFOLDERS=~/new\r\n"),
    ("KIND=non-code\rMODEL=opus\r", "KIND=non-code\rMODEL=opus\rFOLDERS=~/new\r"),
    ("KIND=non-code\nMODEL=opus", "KIND=non-code\nMODEL=opus\nFOLDERS=~/new\n"),          # no final line end
    ("KIND=non-code\r\nMODEL=opus", "KIND=non-code\r\nMODEL=opus\r\nFOLDERS=~/new\r\n"),
    ("MODEL=opus", "MODEL=opus\nFOLDERS=~/new\n"),                                        # one line, no ending
    ("", "FOLDERS=~/new\n"),
    ("# FOLDERS=~/commented\nMODEL=opus\n\n", "# FOLDERS=~/commented\nMODEL=opus\n\nFOLDERS=~/new\n"),
])
def test_a_setting_the_file_lacks_is_added_as_the_last_line_ending_as_the_files_first_line_ends(before, after):
    got = change(before, "FOLDERS", "~/new")
    assert (got.text, got.was, got.now, got.on_lines) == (after, None, "FOLDERS=~/new", [])


def test_of_a_setting_written_twice_the_last_is_changed_as_that_is_the_one_read():
    before = "FOLDERS=~/first\nKIND=non-code\nFOLDERS = ~/second\nMODEL=opus\n"
    got = change(before, "FOLDERS", "~/new")
    assert got.text == "FOLDERS=~/first\nKIND=non-code\nFOLDERS =~/new\nMODEL=opus\n"
    assert (got.was, got.now, got.on_lines) == ("FOLDERS = ~/second", "FOLDERS =~/new", [1, 3])


@pytest.mark.parametrize("before, key, value", [
    ("KIND=non-code\nFOLDERS=~/same\n", "FOLDERS", "~/same"),
    ("KIND=non-code\nFOLDERS =  ~/same \t\r\n", "FOLDERS", "~/same"),      # as read: the spaces round it dropped
    ("FOLDERS=~/other\nFOLDERS=~/same\n", "FOLDERS", "~/same"),            # the last is the one read
    ("KIND=non-code\nCLAWS=\n", "CLAWS", ""),
    ("KIND=non-code\n", "CLAWS", ""),                                       # no line reads as an empty one
    ("", "FOLDERS", ""),
])
def test_a_setting_that_already_reads_as_that_value_is_no_change(before, key, value):
    assert change(before, key, value) is None


def test_an_earlier_line_with_the_value_does_not_make_it_the_value_read():
    got = change("FOLDERS=~/same\nFOLDERS=~/other\n", "FOLDERS", "~/same")
    assert got.text == "FOLDERS=~/same\nFOLDERS=~/same\n" and got.on_lines == [1, 2]


@pytest.mark.parametrize("argument, key, value", [
    ("FOLDERS=~/models/kokoro", "FOLDERS", "~/models/kokoro"),
    ("CLAWS=", "CLAWS", ""),
    ("CLAWS=word-tools video-tools", "CLAWS", "word-tools video-tools"),
    (" MODEL = fable \t", "MODEL", "fable"),
    ("EFFORT=xhigh", "EFFORT", "xhigh"),
    ("SISTER=a=b", "SISTER", "a=b"),
    ("FOLDERS=~/My Drive/modèles:/Volumes/Big Disk", "FOLDERS", "~/My Drive/modèles:/Volumes/Big Disk"),
])
def test_the_argument_is_a_key_and_a_value_split_at_the_first_equals_sign(argument, key, value):
    assert setting(argument) == (key, value)


@pytest.mark.parametrize("argument", ["FOLDERS", "", "=~/models", " =x", "~/models/kokoro"])
def test_an_argument_that_is_not_key_equals_value_is_a_bad_argument(argument):
    with pytest.raises(Stop) as stopped:
        setting(argument)
    assert stopped.value.code == 2
    assert stopped.value.message == (f"{argument!r} is not KEY=VALUE: give the setting and its new value, as in "
                                     "FOLDERS=~/models/voices (set-conf --help shows the form)")


@pytest.mark.parametrize("argument, why", [
    ("KIND=code", "KIND and SELF say what a project is, and set-conf never changes them"),
    ("SELF=menus", "KIND and SELF say what a project is, and set-conf never changes them"),
    ("PACE=eager", "set-conf does not know the setting PACE: it sets SISTER, CLAWS, FOLDERS, MODEL, EFFORT or SESSION"),
    ("folders=~/x", "set-conf does not know the setting folders: it sets SISTER, CLAWS, FOLDERS, MODEL, EFFORT or SESSION"),
    ("# MODEL=x", "set-conf does not know the setting # MODEL: it sets SISTER, CLAWS, FOLDERS, MODEL, EFFORT or SESSION"),
    ("FOLDERS=~/a\nKIND=code", "the value for FOLDERS has a line break in it: a setting is one line"),
    ("FOLDERS=~/a\rb", "the value for FOLDERS has a line break in it: a setting is one line"),
    ("MODEL=opus\r\n", "the value for MODEL has a line break in it: a setting is one line"),
])
def test_a_setting_it_does_not_change_or_a_value_with_a_line_break_is_refused(argument, why):
    with pytest.raises(Stop) as stopped:
        setting(argument)
    assert (stopped.value.code, stopped.value.message) == (3, why + "; nothing was changed")


@pytest.mark.parametrize("text", [
    CONF, CONF[:-1], "A=1\r\nB=2\r\n", "A=1\rB=2\r", "A=1\n\nB=2\r\n\rC=3", "", "\n", "A=1\x0bB=2\x0cC=3 D=4\n",
])
def test_the_lines_are_the_lines_conduct_reads_and_join_back_to_the_same_text(tmp_path, text):
    from bernstein import conduct
    from bernstein.setconf import lines_of
    path = tmp_path / "lobster.conf"
    path.write_bytes(text.encode("utf-8"))
    lines = lines_of(text)
    assert "".join(line + end for line, end in lines) == text
    assert conduct.conf_settings(line for line, _end in lines) == conduct.read_conf_file(str(path))
    with open(str(path), encoding="utf-8") as f:
        assert [line for line, _end in lines] == [line.rstrip("\n") for line in f]
