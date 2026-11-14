"""A facts file: what a command did in each project, for a notice to say (PLAN.md, "notice", Settled 162).

JSON, one block a project: {"recipes": {"KEPT": "/path", "WHEN": "14 November 2026, 11:47Z"}}. A fact's name
is written in capitals and underscores, as its place in a notice's body is ({{KEPT}}), and its value is text.
"""


import json
import os
import re

from bernstein.render import MONTHS

NAME = re.compile(r"[A-Z_]+")
OWN = ("PROJECT", "FOLDER")       # the two places notice fills in itself


class FactsRefused(ValueError):
    """A facts file cannot be used; the message says where and why."""


def read(text, where):
    """{project: {NAME: value}} from a facts file's text; FactsRefused if it is not one."""
    try:
        data = json.loads(text)
    except ValueError:
        raise FactsRefused(f"{where} is not JSON")
    if not isinstance(data, dict):
        raise FactsRefused(f"{where} is not a facts file: it must be one JSON object, with a block for each project")
    for project, block in data.items():
        if not isinstance(block, dict):
            raise FactsRefused(f"{where}: the block for {project} must be a JSON object of facts")
        for name, value in block.items():
            if name in OWN:
                raise FactsRefused(f"{where}: {project}'s block gives {name}, which notice fills in itself")
            if not NAME.fullmatch(name):
                raise FactsRefused(f"{where}: {project}'s fact {name!r} must be named in capitals and underscores, "
                                   "as its place in a notice is written")
            if not isinstance(value, str):
                raise FactsRefused(f"{where}: {project}'s fact {name} must be text, in quotation marks")
    return data


def text_of(facts):
    """A facts file's text."""
    return json.dumps(facts, indent=1, ensure_ascii=False) + "\n"


def when(now):
    """A moment as a notice says it: 14 November 2026, 11:47Z."""
    return f"{now.day} {MONTHS[now.month - 1]} {now.year}, {now:%H:%M}Z"


def held(path):
    """The facts in the file at path, none if there is no such file; FactsRefused if it is not a facts file."""
    if not os.path.lexists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return read(f.read(), path)
    except UnicodeDecodeError:
        raise FactsRefused(f"{path} is not plain UTF-8 text")
    except OSError as why:
        raise FactsRefused(f"{path} cannot be read ({why.strerror})")


def record(path, project, block):
    """Add one project's block to the facts file at path, or replace it there, keeping every other block."""
    facts = held(path)
    facts[project] = dict(block)
    with open(path + ".new", "w", encoding="utf-8") as f:
        f.write(text_of(facts))
    os.replace(path + ".new", path)


HELP = ("write what was done in each project to this facts file, for notice --facts (made if it is not there; "
        "a project's block is added or replaced)")


def refusal(path):
    """Why the file at path cannot take facts, or None: asked before a command does anything."""
    folder = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(folder):
        return f"--facts-to {path}: the folder {folder} is not there: make it first"
    try:
        held(path)
    except FactsRefused as why:
        return f"--facts-to {path} is there already and is not a facts file ({why})"
    return None


def unwritten(path, project, block):
    """Record a block; None, or why it could not be written (the command's own change is made by then)."""
    try:
        record(path, project, block)
    except (OSError, FactsRefused) as why:
        return (f"the change was made, but the facts for a notice could not be written to {path} "
                f"({getattr(why, 'strerror', None) or why})")
    return None
