#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""version-note-lint: check the version argument of Sphinx version notes.

Sphinx's versionadded / versionchanged / deprecated / versionremoved directives
(and their Sphinx 9 spellings version-added, version-changed, version-deprecated,
version-removed, plus CPython's deprecated-removed and soft-deprecated) take the
version as their FIRST argument. Sphinx prints whatever word comes first after
"Added in version" / "Changed in version". Three mistakes are invisible in the
rst source but visible to readers:

  MISSING          ".. versionchanged::" followed by a blank line: no version at
                   all (Sphinx reports an error and drops the note).
  BODY_AS_VERSION  ".. versionchanged::" with the text starting on the very next
                   line: docutils takes the first word of that text as the version,
                   so "NumPy 2.1 changed the headers" renders as
                   "Changed in version NumPy: 2.1 changed the headers".
  OTHER            the first word after "::" is not a version number, for example
                   ".. versionadded:: Python 3.4" or ".. versionadded:: 1.2,".

With --branch-version X.Y it also reports FUTURE notes: a version later than the
branch (for example "versionchanged:: 6.0.6" in the docs of a 5.2 maintenance
branch). Placeholders such as "next" (CPython) or "A.B" (docs about docs) are
counted but not reported. Notes inside literal blocks and code fences are skipped.

Usage:
  version-note-lint [--branch-version X.Y] [--json] PATH [PATH ...]
Exit status 1 when anything is reported, else 0.
"""
import argparse
import json
import os
import re
import sys

__version__ = "0.1.0"

DIRECTIVES = (
    "deprecated-removed", "soft-deprecated", "versionadded", "versionchanged",
    "versionremoved", "deprecated", "version-added", "version-changed",
    "version-deprecated", "version-removed",
)
_ALT = "|".join(re.escape(d) for d in DIRECTIVES)
RST_RE = re.compile(r"^[ \t]*\.\.[ \t]+(?P<d>" + _ALT + r")::(?P<rest>.*)$")
MYST_RE = re.compile(r"^[ \t]*(?:`{3,}|:{3,})\{(?P<d>" + _ALT + r")\}(?P<rest>.*)$")
DIRECTIVE_LINE_RE = re.compile(r"^[ \t]*\.\.[ \t]+[\w:.-]+::")
CODE_DIRECTIVE_RE = re.compile(
    r"^[ \t]*\.\.[ \t]+(?:code-block|code|sourcecode|parsed-literal|doctest|testcode|"
    r"testoutput|testsetup|testcleanup|ipython|jupyter-execute|prompt)::", re.I)
FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")

VERSION_TOKEN_RE = re.compile(
    r"^v?\d+(?:\.\d+)*(?:[-.]?(?:a|b|c|rc|alpha|beta|dev|post|pre)\.?\d*)*$", re.I)
PLACEHOLDER_RE = re.compile(
    r"^(?:next|next-version|unreleased|upcoming|tbd|tba|main|master|dev|development|"
    r"future|x\.y(?:\.z)?|a\.b(?:\.c)?|n\.n(?:\.n)?|\d+(?:\.\d+)*\.[x*]|"
    r"\|[^|]+\||\{[^}]*\}|\$\{[^}]*\}|@[a-z_]+@|[a-z0-9_]*version[a-z0-9_]*)$", re.I)
MAJOR_MINOR_RE = re.compile(r"^v?(\d+)\.(\d+)", re.I)

REPORTED = ("MISSING", "BODY_AS_VERSION", "OTHER", "FUTURE")
EXTENSIONS = (".rst", ".txt", ".inc", ".py", ".pyi", ".pyx", ".pxd", ".md")


def classify_token(tok):
    """'VERSION', 'PLACEHOLDER' or 'OTHER' for the first argument word."""
    if VERSION_TOKEN_RE.match(tok):
        return "VERSION"
    if PLACEHOLDER_RE.match(tok):
        return "PLACEHOLDER"
    return "OTHER"


def parse_branch_version(s):
    m = re.match(r"^(\d+)\.(\d+)$", s.strip())
    if not m:
        raise ValueError("branch version must look like X.Y, got %r" % s)
    return (int(m.group(1)), int(m.group(2)))


def _indent(line):
    e = line.expandtabs(8)
    return len(e) - len(e.lstrip())


def _cls_for(tok, branch_version):
    kind = classify_token(tok)
    if kind == "PLACEHOLDER":
        return "PLACEHOLDER"
    if kind == "OTHER":
        return "OTHER"
    if branch_version is not None:
        m = MAJOR_MINOR_RE.match(tok)
        if m and (int(m.group(1)), int(m.group(2))) > tuple(branch_version):
            return "FUTURE"
    return "OK"


def scan_text(text, path="", branch_version=None):
    """Every version note in `text` as a dict.

    Keys: path, line (1-based), directive, arg (first argument word, or the first
    word of the next line for BODY_AS_VERSION, or ''), cls (OK, PLACEHOLDER,
    MISSING, BODY_AS_VERSION, OTHER, FUTURE), in_literal (bool), text.
    """
    lines = text.splitlines()
    md = path.lower().endswith(".md")
    notes = []
    lit_base = None
    lit_seen = False
    fences = []  # markdown: stack of (kind, fence char), kind "code" or "directive"
    for i, line in enumerate(lines):
        stripped = line.strip()
        ind = _indent(line)
        in_lit = False
        if md:
            fm = FENCE_RE.match(line)
            if fm:
                info = fm.group(2).strip()
                ch = fm.group(1)[0]
                if fences and fences[-1][0] == "code":
                    if not info and ch == fences[-1][1]:
                        fences.pop()
                    continue
                if info.startswith("{"):
                    fences.append(("directive", ch))
                elif info:
                    fences.append(("code", ch))
                    continue
                else:
                    if fences:
                        fences.pop()
                    else:
                        fences.append(("code", ch))
                    continue
            elif fences and fences[-1][0] == "code":
                in_lit = True
        else:
            if lit_base is not None:
                if not stripped:
                    in_lit = lit_seen
                elif ind > lit_base:
                    in_lit = True
                    lit_seen = True
                else:
                    lit_base = None
                    lit_seen = False
        m = (MYST_RE if md else RST_RE).match(line)
        if m:
            rest = m.group("rest").strip()
            if rest:
                tok = rest.split()[0]
                cls = _cls_for(tok, branch_version)
            elif md:
                tok, cls = "", "MISSING"
            else:
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if nxt and not nxt.startswith(":"):
                    tok = nxt.split()[0]
                    cls = _cls_for(tok, branch_version)
                    if cls == "OTHER":
                        cls = "BODY_AS_VERSION"
                else:
                    tok, cls = "", "MISSING"
            notes.append({"path": path, "line": i + 1, "directive": m.group("d"),
                          "arg": tok, "cls": cls, "in_literal": in_lit,
                          "text": stripped[:200]})
        if not md and not in_lit and stripped:
            if CODE_DIRECTIVE_RE.match(line) or (
                    stripped.endswith("::") and not DIRECTIVE_LINE_RE.match(line)):
                lit_base = ind
                lit_seen = False
    return notes


def findings(notes, include_literal=False):
    return [n for n in notes if n["cls"] in REPORTED and
            (include_literal or not n["in_literal"])]


def iter_files(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in (".git", "node_modules",
                                                              ".tox", ".venv", "build"))
                for f in sorted(files):
                    if f.lower().endswith(EXTENSIONS):
                        yield os.path.join(root, f)
        else:
            yield p


MESSAGES = {
    "MISSING": "version note has no version (Sphinx needs it as the first argument)",
    "BODY_AS_VERSION": "no version on the directive line; Sphinx will show %r as the version",
    "OTHER": "first argument %r is not a version number; Sphinx will show it as the version",
    "FUTURE": "version %r is later than this branch (%s)",
}


def describe(n, branch_version=None):
    msg = MESSAGES[n["cls"]]
    if n["cls"] == "MISSING":
        return msg
    if n["cls"] == "FUTURE":
        return msg % (n["arg"], "%d.%d" % tuple(branch_version))
    return msg % n["arg"]


def main(argv=None):
    ap = argparse.ArgumentParser(prog="version-note-lint", description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--branch-version", default=None,
                    help="X.Y of a maintenance branch; report notes naming a later release")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)
    bv = parse_branch_version(a.branch_version) if a.branch_version else None
    out = []
    for path in iter_files(a.paths):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            print("%s: cannot read: %s" % (path, e), file=sys.stderr)
            continue
        out.extend(findings(scan_text(text, path, bv)))
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        for n in out:
            print("%s:%d: %s: %s" % (n["path"], n["line"], n["cls"], describe(n, bv)))
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
