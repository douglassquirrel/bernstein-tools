"""conform: list what an existing lobster pair lacks against bernstein's template. Read-only.

PLAN.md (Settled 55) is the specification. Exit codes: 0 nothing missing, 1 something missing,
2 bad arguments or settings, 4 the template cannot be read.
"""

import argparse
import datetime
import json
import os
import re
import shlex

from bernstein import globalfiles
from bernstein.conduct import (
    ProjectRefused,
    conductor_folder,
    discovered,
    locate,
    non_code_folder_in,
    read_conf_file,
    subfolders,
    tools_folders,
    tools_folders_in,
)
from bernstein.newlobster import OUTER_FILES, OUTER_FOLDERS
from bernstein.render import INCLUDE, PLACEHOLDER, TemplateRefused, fill, values_for
from bernstein.settings import SettingsRefused, read_settings

# A template heading with one of these names the pair, so every pair's CLAUDE.md must have it.
PAIR_NAMES = {"NAME", "TOOLS", "SELF", "SISTER"}
# The shared sections whose wording the template fixes; the others carry a date or a project's own lines.
FIXED_WORDING = {"sections/inbox.md", "sections/mail.md", "sections/dreaming.md"}


def hook_has_root(text, root):
    """Whether a hook's JSON text passes this mail root to --root, as one shell word."""
    word = json.dumps(shlex.quote(root), ensure_ascii=False)[1:-1]
    return re.search(rf' --root {re.escape(word)}(?=[\s"])', text) is not None


def sections_of(text):
    """Each "## " section as {heading: its lines}, leaving out blank lines and a closing ---."""
    found, lines = {}, []
    for line in text.splitlines():
        if line.startswith("## "):
            lines = found.setdefault(line, [])
        elif line.strip():
            lines.append(line)
    for lines in found.values():
        while lines and lines[-1] == "---":
            lines.pop()
    return found


def find(name, kind, s):
    """(folder, checkout) for one half, or None."""
    if kind == "code":
        return locate(name, s["CODE_DIR"], tools_folders_in)
    folder = locate(name, s["NON_CODE_DIR"], non_code_folder_in)
    return (folder, folder) if folder else None


def conf_gaps(conf, wanted, empty="a lone claw"):
    """What lobster.conf lacks: the right KIND, SELF and SISTER, and a MODEL and an EFFORT."""
    try:
        settings = read_conf_file(conf)
    except (UnicodeDecodeError, OSError):
        return ["lobster.conf as plain UTF-8 text"]
    gaps = []
    for key, value in wanted.items():
        if (settings.get(key) or "") != value:
            said = f" (it says {settings[key]})" if settings.get(key) else ""
            shown = f"{key}={value}" if value else f"{key}= (empty: {empty})"
            gaps.append(f"{shown} in lobster.conf{said}")
    gaps += [f"{key} in lobster.conf" for key in ("MODEL", "EFFORT") if not settings.get(key)]
    return gaps


def session_of(conf):
    """What a lobster.conf says of SESSION, the kind of session a non-code project runs in: "" for no line."""
    try:
        return read_conf_file(conf).get("SESSION", "")
    except (UnicodeDecodeError, OSError):
        return ""


def session_gaps(conf, kind):
    """What is wrong with the SESSION a lobster.conf names: only a non-code project names one, cowork or code."""
    said = session_of(conf)
    if said and kind != "non-code":
        return [(f"an empty SESSION in lobster.conf (it says SESSION={said}; only a non-code project names its "
                "kind of session)")]
    if said not in ("", "cowork", "code"):
        return [f"SESSION=cowork or SESSION=code in lobster.conf, or no SESSION line (it says SESSION={said})"]
    return []


def claws_of(conf):
    """The further claws a non-code project's lobster.conf names, or none."""
    try:
        return read_conf_file(conf).get("CLAWS", "").split()
    except (UnicodeDecodeError, OSError):
        return []


def folder_gaps(conf, kind, home):
    """What is wrong with the further folders a lobster.conf names in FOLDERS (colons between them)."""
    try:
        named = [part.strip() for part in read_conf_file(conf).get("FOLDERS", "").split(":") if part.strip()]
    except (UnicodeDecodeError, OSError):
        return []
    if named and kind == "code":
        return ["an empty FOLDERS in lobster.conf (a Claude Code session opens in one folder)"]
    gaps = []
    for part in named:
        path = os.path.join(home, part[2:]) if part.startswith("~/") else part
        if not os.path.isabs(path):
            gaps.append(f"a full path for {part} in FOLDERS in lobster.conf (start it with / or ~/)")
        elif not os.path.isdir(path):
            gaps.append(f"the folder {os.path.normpath(path)}, named in FOLDERS in lobster.conf")
    return gaps


def required_sections(s, kind, non_code, tools, public, home, claws=(), backlog=False, conductor=None,
                      session=None):
    """(headings, wording) for a half's CLAUDE.md. Headings: every heading of each section the template's
    CLAUDE.md for that half includes from common/sections/, and every heading of its own that names the
    pair. Wording: {heading: lines} of the included sections in FIXED_WORDING, filled. A lone claw has
    non_code None. `conductor` is the folder of the conductor a tools project serves, when its sister is one."""
    values = values_for(non_code, kind, model=s["MODEL"], effort=s["EFFORT"], non_code_dir=s["NON_CODE_DIR"],
                        code_dir=s["CODE_DIR"], mail_root=s["MAIL_ROOT"], lobster_mail=s["LOBSTER_MAIL"],
                        public=public, today=datetime.date.today(), home=home, tools=tools, claws=claws,
                        backlog=backlog, non_code_path=conductor, conductor=bool(conductor), session=session)
    where = f"{kind}/CLAUDE.md"
    with open(os.path.join(s["TEMPLATE"], kind, "CLAUDE.md"), encoding="utf-8") as f:
        raw = f.read()
    headings, wording = [], {}
    for line in raw.splitlines():
        include = INCLUDE.fullmatch(line)
        if include:
            name = fill(include.group(1), values, where)
            section = os.path.join(s["TEMPLATE"], "common", name)
            with open(section, encoding="utf-8") as f:
                text = f.read()
            headings += [fill(h, values, section) for h in text.splitlines() if h.startswith("## ")]
            if name in FIXED_WORDING:
                wording.update(sections_of(fill(text, values, section)))
        elif line.startswith("## ") and set(PLACEHOLDER.findall(line)) & PAIR_NAMES:
            headings.append(fill(line, values, where))
    return headings, wording


def claude_gaps(folder, headings, wording):
    claude = os.path.join(folder, "CLAUDE.md")
    if not os.path.isfile(claude):
        return ["CLAUDE.md"]
    with open(claude, encoding="utf-8", errors="replace") as f:
        text = f.read()
    have = sections_of(text)
    return ([f'the section "{h}" in CLAUDE.md' for h in headings if h not in have]
            + [f'the template\'s wording of the section "{h}" in CLAUDE.md'
               for h, lines in wording.items() if h in have and have[h] != lines])


class StartMends(str):
    """A gap that the project's next conduct start mends by itself: a global file behind the template."""


def global_gaps(rendered, folder):
    """What a project's global files lack. One that is behind is mended by a start only where the project
    keeps every global file: conduct start leaves the files of a project that lacks one as they are."""
    found = globalfiles.state(rendered, folder)
    whole = all(how != "missing" for _rel, how in found)
    gaps = []
    for rel, how in found:
        if how == "missing":
            gaps.append(f"{rel}, one of the template's global files")
        else:
            behind = f"the template's current {rel} (a global file: conduct start brings it up to date)"
            gaps.append(StartMends(behind) if whole else behind)
    return gaps


def gaps_of(name, kind, sister, found, s, conductor=None):
    """What one half lacks, as lines. `conductor` is the folder of the conductor a tools half serves, if any."""
    folder, _checkout = found
    gaps = []
    conf = os.path.join(folder, "lobster.conf")
    if not os.path.isfile(conf):
        gaps.append("lobster.conf")
    else:
        gaps += conf_gaps(conf, {"KIND": kind, "SELF": name, "SISTER": sister})
    if not os.path.isfile(os.path.join(folder, "START-HERE.txt")):
        gaps.append("START-HERE.txt")
    hook = os.path.join(folder, ".claude", "settings.json")
    if not os.path.isfile(hook):
        gaps.append(".claude/settings.json (the lobster-mail start hook)")
    else:
        with open(hook, encoding="utf-8", errors="replace") as f:
            text = f.read()
        if "lobster-mail" not in text or " start --project" not in text.replace('\\"', ""):
            gaps.append("the lobster-mail start hook in .claude/settings.json")
        elif not hook_has_root(text, s["MAIL_ROOT"]):
            gaps.append(f"--root {shlex.quote(s['MAIL_ROOT'])} in the lobster-mail start hook in .claude/settings.json")
    if not os.path.isfile(os.path.join(folder, "inbox", "README.md")):
        gaps.append("inbox/README.md")
    gaps += folder_gaps(conf, kind, s["HOME"]) + session_gaps(conf, kind)
    non_code, tools = (name, sister) if kind == "non-code" else (sister or None, name)
    claws = claws_of(conf) if kind == "non-code" else []
    # a non-code project is checked against the files rendered for the session its lobster.conf names
    session = "code" if kind == "non-code" and session_of(conf) == "code" else None
    for claw in claws:
        if not os.path.isdir(tools_folders(claw, s["CODE_DIR"])[1]):
            gaps.append(f"the claw {claw} in {s['CODE_DIR']} or a folder directly inside it")
    gaps += claude_gaps(folder, *required_sections(s, kind, non_code, tools, found[0] != found[1], s["HOME"], claws,
                                                       globalfiles.keeps_tickets(folder), conductor, session))
    checkout = found[1]
    other = conductor or sister_path(kind, sister, s)
    rendered = globalfiles.renders(s, kind, name, sister, folder, checkout, other, claws, s["HOME"],
                                   datetime.date.today(), conductor=bool(conductor), session=session,
                                   claw_paths={claw: tools_folders(claw, s["CODE_DIR"])[1] for claw in claws})
    gaps += global_gaps(rendered, folder)
    if checkout != folder:
        beside = OUTER_FILES + OUTER_FOLDERS + tuple(r for r in rendered if not r.startswith(OUTER_FOLDERS))
        for rel in dict.fromkeys(beside):
            if os.path.lexists(os.path.join(checkout, rel.rstrip("/"))):
                gaps.append(f"{rel} beside the checkout, not in it ({checkout})")
    if not os.path.isdir(os.path.join(checkout, ".git")):
        gaps.append(f"a git repository in {checkout}")
    if not os.path.isdir(os.path.join(s["MAIL_ROOT"], name)):
        gaps.append(f"the mailbox {name} in {s['MAIL_ROOT']}")
    return gaps


def sister_path(kind, sister, s):
    """Where the other half is, for the template's words: a non-code project's home claw's checkout, or a
    tools project's non-code folder. None when there is none or it cannot be found."""
    if not sister:
        return None
    try:
        found = find(sister, "code" if kind == "non-code" else "non-code", s)
    except ProjectRefused:
        return None
    return found[1] if found else None


def conductor_gaps(name, claw, folder, s):
    """What a conductor lacks. It is outside the template, so only what a conductor has is asked of it: its
    lobster.conf, a CLAUDE.md, a git repository and a mailbox."""
    conf = os.path.join(folder, "lobster.conf")
    gaps = conf_gaps(conf, {"KIND": "conductor", "SELF": name, "SISTER": claw})
    if claws_of(conf):
        gaps.append("an empty CLAWS in lobster.conf (a conductor has one claw, the one SISTER names)")
    gaps += folder_gaps(conf, "code", s["HOME"]) + session_gaps(conf, "conductor")
    if not os.path.isfile(os.path.join(folder, "CLAUDE.md")):
        gaps.append("CLAUDE.md")
    if not os.path.isdir(os.path.join(folder, ".git")):
        gaps.append(f"a git repository in {folder}")
    if not os.path.isdir(os.path.join(s["MAIL_ROOT"], name)):
        gaps.append(f"the mailbox {name} in {s['MAIL_ROOT']}")
    return gaps


def served_conductor(tools, s):
    """The name of the conductor a tools project's lobster.conf names as its sister, or None."""
    try:
        found = find(tools, "code", s)
        sister = read_conf_file(os.path.join(found[0], "lobster.conf")).get("SISTER", "") if found else ""
    except (ProjectRefused, UnicodeDecodeError, OSError):
        return None
    return sister if conductor_folder(sister, s["CODE_DIR"]) else None


def feeler_folder(name, s):
    """The folder of the feeler called name, or None if there is no such feeler."""
    try:
        found = find(name, "non-code", s)
    except ProjectRefused:
        return None
    if found is None:
        return None
    try:
        kind = read_conf_file(os.path.join(found[0], "lobster.conf")).get("KIND")
    except (UnicodeDecodeError, OSError):
        return None
    return found[0] if kind == "feeler" else None


def feeler_gaps(name, folder, s):
    """What a feeler lacks: far less than a pair, since it has no tools project, Backlog, inbox or hook."""
    conf = os.path.join(folder, "lobster.conf")
    gaps = conf_gaps(conf, {"KIND": "feeler", "SELF": name, "SISTER": ""}, empty="a feeler has no home claw")
    for rel in ("START-HERE.txt", "CLAUDE.md"):
        if not os.path.isfile(os.path.join(folder, rel)):
            gaps.append(rel)
    gaps += folder_gaps(conf, "feeler", s["HOME"]) + session_gaps(conf, "feeler")
    claws = claws_of(conf)
    for claw in claws:
        if not os.path.isdir(tools_folders(claw, s["CODE_DIR"])[1]):
            gaps.append(f"the claw {claw} in {s['CODE_DIR']} or a folder directly inside it")
    rendered = globalfiles.renders(s, "feeler", name, "", folder, folder, None, claws, s["HOME"], datetime.date.today())
    gaps += global_gaps(rendered, folder)
    if not os.path.isdir(os.path.join(folder, ".git")):
        gaps.append(f"a git repository in {folder}")
    if not os.path.isdir(os.path.join(s["MAIL_ROOT"], name)):
        gaps.append(f"the mailbox {name} in {s['MAIL_ROOT']}")
    return gaps


class Stop(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Stop(2, f"{message} (conform --help shows the form)")


def parser():
    p = Parser(prog="conform", description="List what an existing lobster pair, or a lone claw (a tools project "
               "with no non-code half), lacks against bernstein's lobster-project template. Reads only; changes nothing.")
    p.add_argument("project", nargs="?", help="the non-code project's name; or, alone, a lone claw's or a "
                   "feeler's; or a conductor's, with its claw")
    p.add_argument("tools", nargs="?", help="the non-code project's home tools project")
    p.add_argument("--all", action="store_true", help="every lobster project the settings can find, each checked "
                   "once in the form that fits it; gaps that a conduct start mends are counted apart")
    p.add_argument("--json", action="store_true", help="with --all: print what was found as JSON")
    return p


def lone_or(non_code, tools, s):
    """The sister a home claw's lobster.conf should name: the non-code project, unless the claw says it is a
    lone claw (an empty SISTER), which serves this project among others and is checked as one."""
    try:
        found = find(tools, "code", s)
    except ProjectRefused:
        return non_code
    if found is None:
        return non_code
    conf = os.path.join(found[0], "lobster.conf")
    if not os.path.isfile(conf):
        return non_code
    try:
        settings = read_conf_file(conf)
    except (UnicodeDecodeError, OSError):
        return non_code
    return "" if "SISTER" in settings and not settings["SISTER"] else non_code


def half(name, kind, folder=None, state="checked", why=None, gaps=()):
    """One half of a check, as data: state is "checked", "not found", "cannot be checked" or "see above"."""
    return {"name": name, "kind": kind, "folder": folder, "state": state, "why": why, "gaps": list(gaps)}


def halves_of(project, tools, s, seen=(), later=()):
    """The halves of one check, each as it is made: a pair's two, a conductor and its claw, a lone claw or a
    feeler. A half whose name is in seen was checked before, and is only said to be; one in later is
    listed further down, as something that cannot be checked."""
    elsewhere = {name: "see below" for name in later}
    elsewhere.update({name: "see above" for name in seen})
    feeler = feeler_folder(project, s)
    if feeler and tools:
        raise Stop(2, f"{project} is a feeler, which has no tools project: give its name alone")
    if feeler:
        try:
            gaps = feeler_gaps(project, feeler, s)
        except (TemplateRefused, OSError) as why:
            raise Stop(4, f"the template cannot be read: {why}")
        yield half(project, "feeler", feeler, gaps=gaps)
        return
    conductor = conductor_folder(project, s["CODE_DIR"])
    if conductor and not tools:
        raise Stop(2, f"{project} is a conductor: give its claw too, as in conform {project} {project}-tools")
    if not tools and served_conductor(project, s):
        raise Stop(2, f"{project} is the claw of the conductor {served_conductor(project, s)}: check them "
                      f"together, conform {served_conductor(project, s)} {project}")
    if conductor:
        yield (half(project, "conductor", state=elsewhere[project]) if project in elsewhere else
               half(project, "conductor", conductor, gaps=conductor_gaps(project, tools, conductor, s)))
        todo = ((tools, "code", project),)
    else:
        todo = ((project, "non-code", tools), (tools, "code", lone_or(project, tools, s))) if tools else (
            (project, "code", ""),)
    for name, kind, sister in todo:
        if name in elsewhere:
            yield half(name, kind, state=elsewhere[name])
            continue
        base = s["CODE_DIR"] if kind == "code" else s["NON_CODE_DIR"]
        try:
            found = find(name, kind, s)
            why = f"{name} is not in {base} or a folder directly inside it"
        except ProjectRefused as refused:
            found, why = None, str(refused)
        if found is None:
            yield half(name, kind, state="not found", why=why)
            continue
        try:
            gaps = gaps_of(name, kind, sister, found, s, conductor if kind == "code" else None)
        except globalfiles.ProjectUnreadable:
            yield half(name, kind, found[0], state="unfinished")      # its first line is printed, as ever
            raise
        except (TemplateRefused, OSError) as why:
            yield half(name, kind, found[0], state="unfinished")
            raise Stop(4, f"the template cannot be read: {why}")
        yield half(name, kind, found[0], gaps=gaps)


def text_of(h):
    """A half as conform prints it."""
    if h["state"] == "not found":
        return f"{h['name']} ({h['kind']}): not found\n  {h['why']}\n"
    head = f"{h['name']} ({h['kind']}): {h['folder']}\n"
    if h["state"] == "unfinished":
        return head
    return head + ("".join(f"  missing: {g}\n" for g in h["gaps"]) or "  in line\n")


def report(a, s, out):
    """Write the report; return the number of things missing."""
    total = 0
    try:
        for h in halves_of(a.project, a.tools, s):
            out.write(text_of(h))
            total += 1 if h["state"] == "not found" else len(h["gaps"])
            a.feeler = h["kind"] == "feeler"
    except globalfiles.ProjectUnreadable as why:
        raise Stop(4, str(why))
    return total


KINDS = ("non-code", "code", "feeler", "conductor")


def sorted_out(found):
    """({name: (kind, sister)} for the projects that can be checked, {name: why} for those that cannot)."""
    known, cannot = {}, {}
    for name in sorted(found):
        folders = [folder for folder, _placed in found[name]]
        if len(folders) > 1:
            count = {2: "two", 3: "three"}.get(len(folders), str(len(folders)))
            cannot[name] = (f"{name} is in {count} places, {', '.join(folders[:-1])} and {folders[-1]}: keep one, "
                            "or rename the other")
            continue
        conf = os.path.join(folders[0], "lobster.conf")
        try:
            settings = read_conf_file(conf)
        except UnicodeDecodeError:
            cannot[name] = f"{conf} is not plain UTF-8 text: save it again as UTF-8"
            continue
        except OSError as why:
            cannot[name] = f"{conf} cannot be read ({why.strerror}): check its permissions"
            continue
        kind, sister = settings.get("KIND", found[name][0][1]), settings.get("SISTER", "")
        if kind not in KINDS:
            cannot[name] = f"{conf} says KIND={kind}: it must be code, non-code, feeler or conductor"
        elif kind == "non-code" and not sister:
            cannot[name] = f"{conf} names no SISTER, the tools project a non-code project works with"
        elif kind == "conductor" and not sister:
            cannot[name] = f"{conf} names no SISTER, the claw a conductor works with"
        else:
            known[name] = (kind, sister)
    return known, cannot


def survey(s):
    """Everything conform --all says, as data: each project checked once, in the form that fits it."""
    found = discovered(s)
    known, cannot = sorted_out(found)
    units = [(name, sister) for kind in ("non-code", "conductor") for name, (k, sister) in known.items() if k == kind]
    units += [(name, None) for name, (kind, _sister) in known.items() if kind == "feeler"]
    second = {tools for _name, tools in units}
    units += [((sister, name) if sister else (name, None)) for name, (kind, sister) in known.items()
              if kind == "code" and name not in second]
    blocks, seen = [], set()
    for project, tools in units:
        block = []
        try:
            for h in halves_of(project, tools, s, seen, cannot):
                block.append(h)         # noqa: PERF402 (one at a time: what came before a failure is kept)
        except globalfiles.ProjectUnreadable as why:
            block[-1] = dict(block[-1], kind=None, folder=None, state="cannot be checked", why=str(why))
        except Stop as stopped:
            if stopped.code != 2:       # only a pair that cannot be one is the project's own fault
                raise
            block = [half(tools or project, None, state="cannot be checked", why=stopped.message)]
        seen.update(h["name"] for h in block)
        blocks.append(block)
    blocks += [[half(name, None, state="cannot be checked", why=why)] for name, why in cannot.items()]
    for block in blocks:
        for h in block:
            h["gaps"] = [{"missing": str(g), "start_mends": isinstance(g, StartMends)} for g in h["gaps"]]
    halves = [h for block in blocks for h in block]
    gaps = [g for h in halves for g in h["gaps"]]
    return {
        "blocks": blocks,
        "mailboxes_without_a_project": [os.path.basename(box) for box in subfolders(s["MAIL_ROOT"])
                                        if os.path.basename(box) not in found],
        "totals": {"projects": len(found),
                   "nothing_mends": sum(1 for g in gaps if not g["start_mends"])
                   + sum(1 for h in halves if h["state"] == "not found"),
                   "a_start_mends": sum(1 for g in gaps if g["start_mends"]),
                   "cannot_be_checked": sum(1 for h in halves if h["state"] == "cannot be checked")},
    }


def counted(n, one, many=None):
    return f"{n} {one if n == 1 else many or one + 's'}"


def survey_text(data, s):
    """What survey found, as conform --all prints it: a block a check, then the totals."""
    totals = data["totals"]
    if not totals["projects"]:
        return (f"No lobster project in {s['NON_CODE_DIR']} or {s['CODE_DIR']}, or a folder directly inside "
                "either.\n")
    lines = []
    for block in data["blocks"]:
        for h in block:
            if h["state"] == "cannot be checked":
                lines.append(f"{h['name']}: cannot be checked\n  {h['why']}\n")
            elif h["state"] == "not found":
                lines.append(f"{h['name']} ({h['kind']}): not found\n  {h['why']}\n")
            elif h["state"] != "checked":
                lines.append(f"{h['name']} ({h['kind']}): {h['state']}\n")
            else:
                lines.append(f"{h['name']} ({h['kind']}): {h['folder']}\n" + ("".join(
                    f"  {'a start mends' if g['start_mends'] else 'missing'}: {g['missing']}\n" for g in h["gaps"])
                    or "  in line\n"))
        lines.append("\n")
    lines += [f"{box}: a mailbox in {s['MAIL_ROOT']} with no lobster project\n"
              for box in data["mailboxes_without_a_project"]]
    nothing, mends, cannot = totals["nothing_mends"], totals["a_start_mends"], totals["cannot_be_checked"]
    if not (nothing or mends or cannot):
        said = ["all in line"]
    else:
        said = [f"{counted(nothing, 'thing')} to bring into line" if nothing else "nothing to bring into line"]
        if mends:
            said.append(f"{mends} {'more ' if nothing else ''}that a conduct start mends")
        if cannot:
            said.append(f"{counted(cannot, 'project')} that could not be checked")
    return "".join(lines) + f"{counted(totals['projects'], 'project')}: {', '.join(said)}.\n"


def main(argv, env, out, err):
    """Run conform; return its exit code."""
    if argv[:1] in (["-h"], ["--help"]):
        out.write(parser().format_help())
        return 0
    try:
        path = env.get("BERNSTEIN_CONF") or os.path.join(env["HOME"], ".bernstein.conf")
        text = ""
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                text = f.read()
        try:
            s = read_settings(text, env["HOME"])
        except SettingsRefused as why:
            raise Stop(2, f"{path}: {why}")
        s["HOME"] = env["HOME"]
        a = parser().parse_args(argv)
        if a.all and a.project:
            raise Stop(2, "--all checks every project: name none with it (conform --help shows the form)")
        if a.json and not a.all:
            raise Stop(2, "--json goes with --all (conform --help shows the form)")
        if a.all:
            data = survey(s)
            out.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n" if a.json else survey_text(data, s))
            return 1 if data["totals"]["nothing_mends"] or data["totals"]["cannot_be_checked"] else 0
        if not a.project:
            raise Stop(2, "the following arguments are required: project (conform --help shows the form)")
        total = report(a, s, out)
    except Stop as stopped:
        err.write(f"conform: {stopped.message}\n")
        return stopped.code
    if total:
        out.write(f"{total} thing{'s' if total != 1 else ''} to bring into line.\n")
        return 1
    out.write("Both halves are in line.\n" if a.tools else "The feeler is in line.\n" if getattr(a, "feeler", False)
              else "The claw is in line.\n")
    return 0
