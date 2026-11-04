#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""version-note-lint: check the version argument of Sphinx version notes.

Sphinx's versionadded / versionchanged / deprecated / versionremoved directives
(and their Sphinx 9 spellings version-added, version-changed, version-deprecated,
version-removed, plus CPython's deprecated-removed and soft-deprecated) take the
version as their FIRST argument. Sphinx prints whatever word comes first after
"Added in version" / "Changed in version". These mistakes build without a
warning but are visible to readers (or make the note vanish):

  MISSING          ".. versionchanged::" followed by a blank line: no version at
                   all (Sphinx reports an error and drops the note).
  BODY_AS_VERSION  ".. versionchanged::" with the text starting on the very next
                   line: docutils takes the first word of that text as the version,
                   so "NumPy 2.1 changed the headers" renders as
                   "Changed in version NumPy: 2.1 changed the headers".
  OTHER            the first word after "::" is not a version number, for example
                   ".. versionadded:: Python 3.4" or ".. versionchanged:: The ...".
  DROPPED          the directive marker is malformed (".. versionchanged::: 6.0",
                   ".. versionadded: 1.2", ".. versionadded::1.2"), so docutils reads
                   the whole note, body included, as a comment: readers see nothing.
  RAW_TEXT         no space after the dots ("..versionadded:: 1.2"): not markup at
                   all, so readers see the raw text.
  PUNCT            a version with trailing punctuation ("1.14.", "2.0::", "1.4.48,"):
                   readers get the right number with stray punctuation. Minor; hide
                   with --ignore PUNCT.

With --branch-version X.Y it also reports FUTURE notes: a version later than the
branch (for example "versionchanged:: 6.0.6" in the docs of a 5.2 maintenance
branch). Placeholders such as "next" (CPython), "A.B" (docs about docs) or
"{{ start_version }}" (templated docstrings) are counted but not reported.
Notes inside literal blocks and code fences are skipped.

Usage:
  version-note-lint [--branch-version X.Y] [--ignore CLS[,CLS]] [--json] PATH [PATH ...]
Exit status 1 when anything is reported, else 0.
"""
import argparse
import json
import os
import re
import sys

__version__ = "0.1.1"

DIRECTIVES = (
    "deprecated-removed", "soft-deprecated", "versionadded", "versionchanged",
    "versionremoved", "deprecated", "version-added", "version-changed",
    "version-deprecated", "version-removed",
)
_ALT = "|".join(re.escape(d) for d in DIRECTIVES)
# Loose match kept for callers of 0.1.0 (census.py uses it on git grep output).
RST_RE = re.compile(r"^[ \t]*\.\.[ \t]+(?P<d>" + _ALT + r")::(?P<rest>.*)$")
# What docutils accepts as a directive: ".. name::" or ".. name ::" (one optional
# space), then whitespace or the end of the line.
VALID_RE = re.compile(r"^[ \t]*\.\.[ \t]+(?P<d>" + _ALT + r") ?::(?P<rest>(?:[ \t].*)?)$")
# Explicit markup that names a version directive but is not a valid directive:
# docutils turns it into a comment (and swallows the indented body with it).
DROPPED_RE = re.compile(r"^[ \t]*\.\.[ \t]+(?P<d>" + _ALT + r")(?P<sep>[ \t]*:+)(?P<rest>.*)$")
# No space after the dots: not explicit markup, so it renders as plain text.
RAW_RE = re.compile(r"^[ \t]*\.\.(?P<d>" + _ALT + r")[ \t]*:+(?P<rest>.*)$")
MYST_RE = re.compile(r"^[ \t]*(?:`{3,}|:{3,})\{(?P<d>" + _ALT + r")\}(?P<rest>.*)$")
DIRECTIVE_LINE_RE = re.compile(r"^[ \t]*\.\.[ \t]+[\w:.-]+::")
CODE_DIRECTIVE_RE = re.compile(
    r"^[ \t]*\.\.[ \t]+(?:code-block|code|sourcecode|parsed-literal|doctest|testcode|"
    r"testoutput|testsetup|testcleanup|ipython|jupyter-execute|prompt)::", re.I)
FENCE_RE = re.compile(r"^[ \t]*(`{3,}|~{3,})(.*)$")

_V = r"v?\d+(?:\.\d+)*(?:[-.]?(?:a|b|c|rc|alpha|beta|dev|post|pre)\.?\d*)*"
VERSION_TOKEN_RE = re.compile(r"^" + _V + r"$", re.I)
MULTI_VERSION_RE = re.compile(r"^" + _V + r"(?:/" + _V + r")+$", re.I)
PUNCT_RE = re.compile(r"^" + _V + r"[.,:;]+$", re.I)
PLACEHOLDER_RE = re.compile(
    r"^(?:next|next-version|unreleased|upcoming|tbd|tba|main|master|dev|development|"
    r"future|x\.y(?:\.z)?|a\.b(?:\.c)?|n\.n(?:\.n)?|\d+(?:\.\d+)*\.[x*]|"
    r"\|[^|]+\||\{[^}]*\}|\{\{.*|\{%.*|\$\{[^}]*\}|@[a-z_]+@|"
    r"[a-z0-9_]*version[a-z0-9_]*)$", re.I)
MAJOR_MINOR_RE = re.compile(r"^v?(\d+)\.(\d+)", re.I)
PY_QUOTES_RE = re.compile(r"\"\"\"|'''")

CLASSES = ("OK", "PLACEHOLDER", "MISSING", "BODY_AS_VERSION", "OTHER", "FUTURE",
           "DROPPED", "RAW_TEXT", "PUNCT")
REPORTED = ("MISSING", "BODY_AS_VERSION", "OTHER", "FUTURE", "DROPPED", "RAW_TEXT", "PUNCT")
EXTENSIONS = (".rst", ".txt", ".inc", ".py", ".pyi", ".pyx", ".pxd", ".md")
PY_EXTENSIONS = (".py", ".pyi", ".pyx", ".pxd")


def classify_token(tok):
    """'VERSION', 'PLACEHOLDER', 'PUNCT' or 'OTHER' for the first argument word."""
    if VERSION_TOKEN_RE.match(tok) or MULTI_VERSION_RE.match(tok):
        return "VERSION"
    if PLACEHOLDER_RE.match(tok):
        return "PLACEHOLDER"
    if PUNCT_RE.match(tok):
        return "PUNCT"
    return "OTHER"


def parse_branch_version(s):
    m = re.match(r"^(\d+)\.(\d+)$", s.strip())
    if not m:
        raise ValueError("branch version must look like X.Y, got %r" % s)
    return (int(m.group(1)), int(m.group(2)))


def _indent(line):
    e = line.expandtabs(8)
    return len(e) - len(e.lstrip())


def _clean_tok(tok, py):
    """In Python source, cut a docstring's closing quotes off the token."""
    if py:
        tok = PY_QUOTES_RE.split(tok)[0]
    return tok


def _cls_for(tok, branch_version):
    if not tok:
        return "MISSING"
    kind = classify_token(tok)
    if kind != "VERSION":
        return kind
    if branch_version is not None:
        m = MAJOR_MINOR_RE.match(tok)
        if m and (int(m.group(1)), int(m.group(2))) > tuple(branch_version):
            return "FUTURE"
    return "OK"


def scan_text(text, path="", branch_version=None):
    """Every version note in `text` as a dict.

    Keys: path, line (1-based), directive, arg (first argument word, or the first
    word of the next line for BODY_AS_VERSION, or ''), cls (one of CLASSES),
    in_literal (bool), text.
    """
    lines = text.splitlines()
    low = path.lower()
    md = low.endswith(".md")
    py = low.endswith(PY_EXTENSIONS)
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
        kind = None
        if md:
            m = MYST_RE.match(line)
            if m:
                kind = "ok"
        else:
            m = VALID_RE.match(line)
            if m:
                kind = "ok"
            else:
                m = DROPPED_RE.match(line)
                if m:
                    kind = "dropped"
                else:
                    m = RAW_RE.match(line)
                    if m:
                        kind = "raw"
        if m:
            rest = m.group("rest").strip()
            if kind == "dropped" or kind == "raw":
                tok = _clean_tok(rest.split()[0], py) if rest else ""
                cls = "DROPPED" if kind == "dropped" else "RAW_TEXT"
            elif rest:
                tok = _clean_tok(rest.split()[0], py)
                cls = _cls_for(tok, branch_version)
            elif md:
                tok, cls = "", "MISSING"
            else:
                nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if nxt and not nxt.startswith(":"):
                    tok = _clean_tok(nxt.split()[0], py)
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


def findings(notes, include_literal=False, ignore=()):
    return [n for n in notes if n["cls"] in REPORTED and n["cls"] not in ignore and
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


def describe(n, branch_version=None):
    c = n["cls"]
    if c == "MISSING":
        return "version note has no version (Sphinx needs it as the first argument)"
    if c == "BODY_AS_VERSION":
        return ("no version on the directive line; Sphinx will show %r as the version"
                % n["arg"])
    if c == "OTHER":
        return ("first argument %r is not a version number; Sphinx will show it as the "
                "version" % n["arg"])
    if c == "FUTURE":
        return "version %r is later than this branch (%s)" % (
            n["arg"], "%d.%d" % tuple(branch_version))
    if c == "DROPPED":
        return ("malformed directive marker; docutils reads this note as a comment and "
                "readers never see it (write '.. %s:: VERSION')" % n["directive"])
    if c == "RAW_TEXT":
        return ("no space after '..'; this is not a directive and renders as plain text "
                "(write '.. %s:: VERSION')" % n["directive"])
    if c == "PUNCT":
        return "version %r has trailing punctuation; Sphinx shows it as written" % n["arg"]
    return c


def main(argv=None):
    ap = argparse.ArgumentParser(prog="version-note-lint", description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--branch-version", default=None,
                    help="X.Y of a maintenance branch; report notes naming a later release")
    ap.add_argument("--ignore", default="",
                    help="comma-separated classes not to report, e.g. PUNCT")
    ap.add_argument("--json", action="store_true", help="print findings as JSON")
    ap.add_argument("--version", action="version", version=__version__)
    a = ap.parse_args(argv)
    bv = parse_branch_version(a.branch_version) if a.branch_version else None
    ignore = tuple(c.strip().upper() for c in a.ignore.split(",") if c.strip())
    bad = [c for c in ignore if c not in REPORTED]
    if bad:
        ap.error("unknown class(es) for --ignore: %s" % ", ".join(bad))
    out = []
    for path in iter_files(a.paths):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            print("%s: cannot read: %s" % (path, e), file=sys.stderr)
            continue
        out.extend(findings(scan_text(text, path, bv), ignore=ignore))
    if a.json:
        print(json.dumps(out, indent=1))
    else:
        for n in out:
            print("%s:%d: %s: %s" % (n["path"], n["line"], n["cls"], describe(n, bv)))
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main())
