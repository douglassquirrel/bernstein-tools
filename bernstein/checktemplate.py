"""new-lobster --check-template: does the template render every way the commands can render it?

PLAN.md ("`new-lobster --check-template`") is the specification. It reads the template and writes nothing.
Exit codes: 0 every way renders clean, 4 any fault, 2 bad arguments or settings.
"""

import argparse
import datetime
import os
from collections import namedtuple

from bernstein.conduct import conf_settings
from bernstein.globalfiles import declared
from bernstein.render import TemplateRefused, render_half, values_for, version
from bernstein.settings import SettingsRefused, read_settings

# session: for a non-code way, the kind of session it is rendered for ("code" is a Claude Code session on the
# Mac, and the way's name has the word mac); None for every other way.
Way = namedtuple("Way", "name half public backlog claws lone conductor session")

NAME, TOOLS, FURTHER = "example", "example-tools", ("first-tools", "second-tools")
GAP = "{{to fill:"


def ways():
    """Every way the commands can render the template, each with the name the report gives it."""
    found = []

    def add(kind, half, public=False, backlog=False, claws=(), lone=False, conductor=False, session=None):
        words = [kind] + [word for word, on in (("mac", session == "code"), ("public", public),
                                                ("tickets", backlog)) if on]
        if claws:
            words.append("claws" if len(claws) > 1 else "claw")
        found.append(Way(",".join(words), half, public, backlog, tuple(claws), lone, conductor, session))

    for session in ("cowork", "code"):
        for claws in ((), FURTHER):
            for backlog in (False, True):
                for public in (False, True):
                    add("non-code", "non-code", public, backlog, claws, session=session)
    for kind, lone, conductor in (("code", False, False), ("claw", True, False), ("conductor-claw", False, True)):
        for backlog in (False, True):
            for public in (False, True):
                add(kind, "code", public, backlog, lone=lone, conductor=conductor)
    for claws in ((), FURTHER[:1], FURTHER):
        add("feeler", "feeler", claws=claws)
    return found


def gaps(text):
    """How many "to fill" gaps a rendered file leaves for a project's first session."""
    return text.count(GAP)


def leftovers(text):
    """[(line number, the line)] for each line of a rendered file with a {{ that does not open a "to fill"
    gap: a placeholder or an include that was never filled."""
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        at = line.find("{{")
        while at != -1 and line.startswith(GAP, at):
            at = line.find("{{", at + 2)
        if at != -1:
            found.append((number, line.strip()))
    return found


def counted(n, one, many=None):
    return f"{n} {one if n == 1 else many or one + 's'}"


def text(data):
    """The report: the template, a line a way with its notes and its faults beneath, and a last line."""
    lines = [f"Template: {data['template']}",
             f"Version: {data['version'] or 'none (the template has no common/version)'}",
             f"Global files: {', '.join(data['global_files']) or 'none'}"]
    lines += [f"  fault: {fault}" for fault in data["faults"]]
    lines.append("")
    for way in data["ways"]:
        if way["files"] is None:
            said = "cannot be rendered"
        else:
            said = f"{counted(way['files'], 'file')}, {way['to_fill']} to fill"
        lines.append(f"{way['way']}: " + "; ".join([said] + way["notes"]))
        lines += [f"  fault: {fault}" for fault in way["faults"]]
    lines.append("")
    in_ways = sum(len(way["faults"]) for way in data["ways"])
    bad = sum(1 for way in data["ways"] if way["faults"])
    said = []
    if in_ways:
        said.append(f"{counted(in_ways, 'fault')} in {counted(bad, 'way')}")
    if data["faults"]:
        said.append(f"{counted(len(data['faults']), 'fault')} in the template itself")
    lines.append(f"{counted(len(data['ways']), 'way')}: {', and '.join(said) or 'all render clean'}.")
    return "".join(line + "\n" for line in lines)


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def render(way, template, s, home, day):
    """One way's files, {path: text}, rendered as new-lobster and conduct render them, for invented names."""
    usual = {"model": s["MODEL"], "effort": s["EFFORT"], "non_code_dir": s["NON_CODE_DIR"],
             "code_dir": s["CODE_DIR"], "mail_root": s["MAIL_ROOT"], "lobster_mail": s["LOBSTER_MAIL"],
             "today": day, "home": home}
    if way.half == "feeler":
        values = values_for(NAME, "feeler", public=False, claws=way.claws, **usual)
    elif way.lone:
        values = values_for(None, "code", public=way.public, tools=TOOLS, backlog=way.backlog, **usual)
    elif way.conductor:
        values = values_for(NAME, "code", public=way.public, tools=TOOLS, backlog=way.backlog, conductor=True,
                            non_code_path=os.path.join(s["CODE_DIR"], NAME + "-code"), **usual)
    else:
        values = values_for(NAME, way.half, public=way.public, claws=way.claws, backlog=way.backlog,
                            session=way.session, **usual)
    try:
        return render_half(template, way.half, values, way.public)
    except UnicodeDecodeError:
        raise TemplateRefused(f"a file in {way.half}/ or common/ is not plain UTF-8 text")


def check(template, s, home, today):
    """Everything the check says, as data: the template, and each way with its notes and its faults."""
    faults = []
    try:
        names = declared(template)
    except TemplateRefused as why:
        names, faults = [], [str(why)]
    found = []
    for way in ways():
        entry = {"way": way.name, "files": None, "to_fill": 0, "notes": [], "faults": []}
        found.append(entry)
        try:
            rendered = render(way, template, s, home, today)
            later = render(way, template, s, home, today + datetime.timedelta(days=40))
        except TemplateRefused as why:
            entry["faults"].append(str(why))
            continue
        entry["files"] = len(rendered)
        entry["to_fill"] = sum(gaps(text) for text in rendered.values())
        for rel in sorted(rendered):
            entry["faults"] += [f"{rel}: {{{{ left in line {number}: {line}"
                                for number, line in leftovers(rendered[rel])]
        entry["faults"] += [f"{rel} is a global file and reads differently on another day: use "
                            "{{TEMPLATE_VERSION}} in it, not {{DATE}}"
                            for rel in names if rel in rendered and rendered[rel] != later[rel]]
        if way.session == "code" and conf_settings(rendered["lobster.conf"].splitlines()).get("SESSION") != "code":
            entry["faults"].append("lobster.conf does not say SESSION=code, so new-lobster --session code cannot "
                                   "make a project from this template: add the line SESSION={{SESSION}} to "
                                   "common/lobster.conf")
        lacking = [rel for rel in names if rel not in rendered]
        if lacking:
            entry["notes"].append("does not get " + ", ".join(lacking))
    return {"template": template, "version": version(template), "global_files": names, "faults": faults,
            "ways": found}


def show(way_name, rel, template, s, home, today, out):
    """Print one file as one way renders it, and nothing else."""
    by_name = {way.name: way for way in ways()}
    if way_name not in by_name:
        raise Stop(2, f"there is no way called {way_name}; the ways are: {', '.join(by_name)}")
    try:
        rendered = render(by_name[way_name], template, s, home, today)
    except TemplateRefused as why:
        raise Stop(4, f"the template cannot be used: {why}")
    if rel not in rendered:
        raise Stop(2, f"the way {way_name} has no file {rel}; its files are: {', '.join(sorted(rendered))}")
    out.write(rendered[rel])


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SettingsRefused(message)


def parser():
    p = Parser(prog="new-lobster --check-template", add_help=False)
    p.add_argument("--check-template", action="store_true")
    p.add_argument("--template", metavar="DIR")
    p.add_argument("--show", nargs=2, metavar=("WAY", "FILE"))
    return p


def main(argv, env, today, out, err):
    """Run new-lobster --check-template; return its exit code."""
    try:
        path = env.get("BERNSTEIN_CONF") or os.path.join(env["HOME"], ".bernstein.conf")
        conf = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                conf = f.read()
        try:
            s = read_settings(conf, env["HOME"])
        except SettingsRefused as why:
            raise Stop(2, f"{path}: {why}")
        try:
            a = parser().parse_args(argv)
        except SettingsRefused as why:
            raise Stop(2, f"{why} (new-lobster --help shows the form)")
        template = a.template or s["TEMPLATE"]
        if not os.path.isdir(template):
            raise Stop(4, f"the template cannot be used: the template folder {template} is not there")
        if a.show:
            show(a.show[0], a.show[1], template, s, env["HOME"], today, out)
            return 0
        data = check(template, s, env["HOME"], today)
        out.write(text(data))
        return 4 if data["faults"] or any(way["faults"] for way in data["ways"]) else 0
    except Stop as stopped:
        err.write(f"new-lobster: {stopped.message}\n")
        return stopped.code
