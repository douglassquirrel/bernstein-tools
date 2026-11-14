"""Stubs on PATH for new-lobster's external programs, and a run() that drives main().

Each stub is a small shell script that records its arguments and working folder in calls.log (read back
by World.calls()). A stub
fails when its name is listed in the file `fail` in the stub folder, as `name`, `name:verb` (only that
first argument) or `name:verb:code` (that exit code; 1 otherwise). The lobster-mail stub's
`duty status --all --json` prints the JSON in `duty.json` (default: no mailboxes), and its `check` prints
the text in `check.json` (default: `[]`, no new mail); its `list --new` and `list --open` print
`list-new.json` and `list-open.json` (default: `[]`), or `list-new-<mailbox>.json` where there is one for the
mailbox named by `--as`; its `send --json` prints an id made from the recipient; its `read ... ID` prints the
file `read-ID.txt` if there is one. The conduct stub's
`status` prints the text in `status.json` (default: no mailboxes); its other verbs print "conduct stub: "
and their first two arguments, and a `--brief FILE` is read into the call's record as `brief`.
"""

import datetime
import io
import json
import os
import shlex
import textwrap

import pytest

from bernstein import newlobster

# A shell script, not Python: a stub is started thousands of times in a run of the suite, and /bin/sh starts
# in about a quarter of the time. Every program it runs is named by its full path, so that it still works
# when a test's PATH holds the stubs alone. The log is NUL-separated pairs (key, value), one record a call:
# prog, cwd, arg (once for each argument), then stdin and brief when there are any, then end.
STUB = textwrap.dedent(r"""        #!/bin/sh
        set -f
        here={bin}
        name=${{0##*/}}
        last=; prev=; brief=; as=; to=; json=
        for a in "$@"; do
            [ "$prev" = --brief ] && brief=$a
            [ "$prev" = --as ] && as=$a
            [ "$prev" = --to ] && to=$a
            [ "$a" = --json ] && json=1
            last=$a; prev=$a
        done
        {{
            printf 'prog\0%s\0cwd\0%s\0' "$name" "$(pwd -P)"
            for a in "$@"; do printf 'arg\0%s\0' "$a"; done
            if [ "$last" = - ]; then printf 'stdin\0'; /bin/cat; printf '\0'; fi
            if [ "$name" = conduct ] && [ -n "$brief" ] && [ "$last" != --brief ]; then
                printf 'brief\0'; /bin/cat "$brief"; printf '\0'
            fi
            printf 'end\0.\0'
        }} >> "$here/calls.log"
        if [ -f "$here/fail" ]; then
            for rule in $(/bin/cat "$here/fail"); do
                prog=${{rule%%:*}}; rest=${{rule#"$prog"}}; rest=${{rest#:}}
                verb=${{rest%%:*}}; code=${{rest#"$verb"}}; code=${{code#:}}
                if [ "$prog" = "$name" ] && {{ [ -z "$verb" ] || [ "$verb" = "${{1-}}" ]; }}; then
                    echo "$name: stub failure" >&2
                    exit "${{code:-1}}"
                fi
            done
        fi
        none='{{"root": "", "mailboxes": [], "skipped": []}}'
        show() {{ if [ -f "$here/$1" ]; then /bin/cat "$here/$1"; echo; else echo "$2"; fi; }}
        case "$name" in
        lobster-mail)
            if [ "${{1-}}" = duty ] && [ "${{2-}}" = status ] && [ "${{3-}}" = --all ]; then show duty.json "$none"; fi
            if [ "${{1-}}" = check ]; then show check.json "[]"; fi
            if [ "${{1-}}" = list ]; then
                box=new
                for a in "$@"; do [ "$a" = --open ] && box=open; done
                if [ -f "$here/list-$box-$as.json" ]; then /bin/cat "$here/list-$box-$as.json"; echo
                else show "list-$box.json" "[]"
                fi
            fi
            if [ "${{1-}}" = send ] && [ -n "$json" ]; then
                printf '{{"id": "2026-10-18-0940-bernstein-to-%s", "to": "%s"}}\n' "$to" "$to"
            fi
            if [ "${{1-}}" = read ] && [ -f "$here/read-$last.txt" ]; then /bin/cat "$here/read-$last.txt"; fi ;;
        conduct)
            if [ "${{1-}}" = status ]; then
                if [ -f "$here/status.json" ]; then /bin/cat "$here/status.json"; else printf '%s' "$none"; fi
            elif [ $# -ge 2 ]; then echo "conduct stub: $1 $2"
            else echo "conduct stub: ${{1-}}"
            fi ;;
        python3)
            if [ "${{1-}}" = -m ] && [ "${{2-}}" = venv ]; then
                /bin/mkdir -p "$3/bin" && /bin/cp "$0" "$3/bin/pip" && /bin/chmod 755 "$3/bin/pip"
            fi ;;
        esac
        exit 0
        """)


def read_calls(path):
    """The stubs' log as [{"prog", "args", "cwd"} and "stdin" or "brief" when the call had one]."""
    with open(path, "rb") as f:
        fields = f.read().decode("utf-8").split("\0")
    calls, entry = [], None
    for key, value in zip(fields[0::2], fields[1::2]):
        if key == "prog":
            entry = {"prog": value, "args": []}
        elif key == "arg":
            entry["args"].append(value)
        elif key == "end":
            calls.append(entry)
        else:
            entry[key] = value
    return calls


TEMPLATE = {
    "README.md": "The test template.\n",
    "common/sections/rule.md": "Rule for {{SELF}}, sister {{SISTER}}.\n",
    "common/sections/repo-private.md": "{{TOOLS}} is private.\n",
    "common/sections/repo-public.md": "{{TOOLS}} is public.\n",
    "common/inbox/README.md": "Inbox of {{SELF}}.\n",
    "common/lobster.conf": "KIND={{KIND}}\nMODEL={{MODEL_SETTING}}\nEFFORT={{EFFORT}}\n",
    "non-code/CLAUDE.md": "# {{NAME}}\n\n{{> sections/rule.md}}\n\n{{to fill: the purpose}}\n",
    "non-code/START-HERE.txt": "Start {{NAME}} on {{DATE}}.\n",
    "non-code/.gitignore": "inbox/*\n",
    "code/CLAUDE.md": "# {{TOOLS}}\n{{> sections/repo-{{VISIBILITY}}.md}}\n",
    "code/START-HERE.txt": "Start {{TOOLS}}.\n",
    "code/PLAN.md": "Plan for {{TOOLS}}.\n",
    "code/pyproject.toml": "addopts = \"--cov={{PACKAGE}}\"\n",
    "code/requirements-dev.txt": "pytest\n",
    "code/tools.conf.example": "# ~/.{{TOOLS}}.conf\n",
    "code/LICENSE": "MIT {{YEAR}}\n",
}


def write_tree(root, files):
    for rel, text in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)


def tree(root):
    """Every file under root, with its bytes."""
    found = {}
    for here, _, names in os.walk(root):
        for n in names:
            p = os.path.join(here, n)
            with open(p, "rb") as f:
                found[os.path.relpath(p, root)] = f.read()
    return found


# conduct's clock: the date for every verb, and the time of day for a dream's finish time.
NOW = datetime.datetime(2026, 10, 18, 9, 40, tzinfo=datetime.timezone.utc)


class World:
    def __init__(self, base):
        self.home = os.path.join(base, "home sq")          # a space, on purpose
        self.bin = os.path.join(base, "bin")
        self.template = os.path.join(base, "tmpl")
        self.non_code = os.path.join(self.home, "projects", "non-code")
        self.code = os.path.join(self.home, "projects", "code")
        self.mail = os.path.join(self.home, "projects", "mail")
        for d in (self.home, self.bin, self.non_code, self.code, self.mail):
            os.makedirs(d, exist_ok=True)
        write_tree(self.template, TEMPLATE)
        for prog in ("git", "backlog", "lobster-mail", "python3", "open", "conduct"):
            p = os.path.join(self.bin, prog)
            with open(p, "w") as f:
                f.write(STUB.format(bin=shlex.quote(self.bin)))
            os.chmod(p, 0o755)
        self.conf = os.path.join(base, "bernstein.conf")
        self.write_conf("")

    def write_conf(self, extra):
        with open(self.conf, "w") as f:
            f.write("TEMPLATE={}\nNON_CODE_DIR={}\nCODE_DIR={}\nMAIL_ROOT={}\nLOBSTER_MAIL={}\nPYTHON={}\n{}".format(self.template, self.non_code, self.code, self.mail,
                       os.path.join(self.bin, "lobster-mail"), os.path.join(self.bin, "python3"), extra))

    def fail(self, *progs):
        with open(os.path.join(self.bin, "fail"), "w") as f:
            f.write(" ".join(progs))

    def mailboxes(self, names, skipped=()):
        with open(os.path.join(self.bin, "duty.json"), "w") as f:
            json.dump({"root": self.mail, "mailboxes": [{"mailbox": n, "duty": None} for n in names],
                       "skipped": list(skipped)}, f)

    def duty(self, boxes):
        """Set the duty listing: {mailbox: None (nobody), "fresh", "stale", "changing" or "handed over"}."""
        listing = []
        for name, state in boxes.items():
            duty = None
            if state in ("fresh", "stale"):
                duty = {"mailbox": name, "holder": "mac", "since": "2026-10-18T09:00:00Z",
                        "last_beat": "2026-10-18T09:30:00Z", "stale": state == "stale", "minutes": 3}
            listing.append({"mailbox": name, "duty": duty, "new": 0, "open": 0,
                            "handover_waiting": state == "handed over", "duty_changing": state == "changing"})
        with open(os.path.join(self.bin, "duty.json"), "w") as f:
            json.dump({"root": self.mail, "mailboxes": listing, "skipped": []}, f)

    def listing(self, entries, skipped=()):
        """Set the duty listing to these mailbox entries, as lobster-mail would print them."""
        with open(os.path.join(self.bin, "duty.json"), "w") as f:
            json.dump({"root": self.mail, "mailboxes": entries, "skipped": list(skipped)}, f)

    def waiting(self, messages):
        """Set the new mail `lobster-mail check --json` lists: (sender, date, subject) each, or the raw text."""
        text = messages if isinstance(messages, str) else json.dumps(
            [{"id": f"m{i}", "from": who, "date": date, "subject": subject, "box": "new"}
             for i, (who, date, subject) in enumerate(messages)])
        with open(os.path.join(self.bin, "check.json"), "w") as f:
            f.write(text)

    def boxed(self, box, messages):
        """Set what `lobster-mail list --new` or `--open --json` prints: (id, sender, subject) each, or the raw text."""
        text = messages if isinstance(messages, str) else json.dumps(
            [{"id": ident, "from": who, "date": "2026-10-18T08:00:00Z", "subject": subject, "box": box}
             for ident, who, subject in messages])
        with open(os.path.join(self.bin, f"list-{box}.json"), "w") as f:
            f.write(text)

    def project(self, name, kind, public=False, under="", sister=None, claws=()):
        """A project folder with its lobster.conf, as new-lobster makes it, perhaps in a subfolder. A code
        project with sister "" is a lone claw; a non-code project's claws are its further claws."""
        if kind == "non-code":
            folder = os.path.join(self.non_code, under, name)
            sister = name + "-tools" if sister is None else sister
        else:
            sister = name[: -len("-tools")] if sister is None else sister
            base = os.path.join(self.code, under)
            folder = os.path.join(base, name + "-code") if public else os.path.join(base, name)
        os.makedirs(os.path.join(folder, name) if public else folder, exist_ok=True)
        with open(os.path.join(folder, "lobster.conf"), "w") as f:
            f.write(f"KIND={kind}\nSELF={name}\nSISTER={sister}\nMODEL=opus\nEFFORT=high\n")
            if claws:
                f.write("CLAWS={}\n".format(" ".join(claws)))
        with open(os.path.join(folder, "START-HERE.txt"), "w") as f:
            f.write(f"Start {name}.\n")
        return folder

    def conductor(self, name, claw=None, under="", outer=True, extra=""):
        """A conductor's folder in the code folder (<name>-code/, or <name>/ without outer): its lobster.conf,
        a CLAUDE.md and a git repository, and no START-HERE.txt, for it is outside the template. claw is
        what its SISTER names (default <name>-tools); the claw itself is laid down with project()."""
        folder = os.path.join(self.code, under, name + "-code" if outer else name)
        claw = name + "-tools" if claw is None else claw
        write_tree(folder, {"lobster.conf": f"KIND=conductor\nSELF={name}\nSISTER={claw}\nMODEL=fable\nEFFORT=xhigh\n"
                                            + extra,
                            "CLAUDE.md": "The conductor's own rules.\n", ".git/HEAD": "ref: refs/heads/main\n"})
        return folder

    def conduct(self, *argv, sleep=None):
        from bernstein import conduct
        out, err = io.StringIO(), io.StringIO()
        env = {"PATH": self.bin + os.pathsep + "/usr/bin:/bin", "HOME": self.home, "BERNSTEIN_CONF": self.conf}
        code = conduct.main(list(argv), env=env, today=NOW, out=out, err=err,
                            sleep=sleep or (lambda seconds: None))
        return code, out.getvalue(), err.getvalue()

    def status(self, text):
        """What the conduct stub prints for status --json (default: no mailboxes)."""
        with open(os.path.join(self.bin, "status.json"), "w") as f:
            f.write(text)

    def podium(self, *argv, **injected):
        """Run podium's main against the conduct stub. Without serve= it serves nothing and returns at once."""
        from bernstein import podium
        out, err = io.StringIO(), io.StringIO()
        env = {"PATH": self.bin + os.pathsep + "/usr/bin:/bin", "HOME": self.home, "BERNSTEIN_CONF": self.conf}
        injected.setdefault("conduct", os.path.join(self.bin, "conduct"))
        injected.setdefault("token", "tok-en")
        injected.setdefault("serve", lambda server: None)
        injected.setdefault("clock", lambda: NOW)
        code = podium.main(list(argv), env=env, out=out, err=err, **injected)
        return code, out.getvalue(), err.getvalue()

    def conform(self, *argv):
        from bernstein import conform
        out, err = io.StringIO(), io.StringIO()
        env = {"PATH": self.bin + os.pathsep + "/usr/bin:/bin", "HOME": self.home, "BERNSTEIN_CONF": self.conf}
        code = conform.main(list(argv), env=env, out=out, err=err)
        return code, out.getvalue(), err.getvalue()

    def local_history(self, *argv, path=None):
        """Run local-history's main. path= replaces PATH (the stubs alone, to make a program truly missing)."""
        from bernstein import localhistory
        out, err = io.StringIO(), io.StringIO()
        env = {"PATH": path or self.bin + os.pathsep + "/usr/bin:/bin", "HOME": self.home,
               "BERNSTEIN_CONF": self.conf}
        code = localhistory.main(list(argv), env=env, out=out, err=err)
        return code, out.getvalue(), err.getvalue()

    def outer(self, name, lobster=True, files=None):
        """The folder around a public checkout: its own files, the checkout (a folder with a .git), and
        things that are left out of a local history. Without lobster=True it has no lobster.conf."""
        folder = os.path.join(self.code, name + "-code")
        laid = {"CLAUDE.md": "rules\n", "DIARY.md": "a diary of some length\n", name + "/.git/HEAD": "ref\n",
                name + "/code.py": "pass\n", "_to_delete/old.md": "old\n", ".venv/bin/pip": "x\n",
                "inbox/README.md": "inbox\n", "inbox/sample.dat": "real data\n"}
        if lobster:
            laid["lobster.conf"] = f"KIND=code\nSELF={name}\nSISTER=\nMODEL=opus\nEFFORT=high\n"
        laid.update(files or {})
        write_tree(folder, laid)
        return folder

    def calls(self):
        p = os.path.join(self.bin, "calls.log")
        return read_calls(p) if os.path.exists(p) else []

    def run(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        env = {"PATH": self.bin + os.pathsep + "/usr/bin:/bin", "HOME": self.home, "BERNSTEIN_CONF": self.conf}
        code = newlobster.main(list(argv), env=env, today=datetime.date(2026, 10, 18), out=out, err=err)
        return code, out.getvalue(), err.getvalue()


@pytest.fixture
def world(tmp_path):
    return World(str(tmp_path))
