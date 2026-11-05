#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""marker_scan: malformed reST directive markers for ANY common directive.

docutils accepts a directive only as ".. name::" or ".. name ::" followed by a space
or the end of the line. Anything else that starts with ".. " becomes a comment, and
the comment swallows the indented body with it. ".." with no space after it is not
markup at all, so readers see the raw text. Neither case gives a build warning.

  DROPPED   ".. note: x", ".. warning::: x", ".. code-block::python",
            ".. note  :: x" (two spaces): a comment; readers see nothing.
  RAW_TEXT  "..note:: x": plain text; readers see the markup.
  OK        a valid marker (counted, for rates).

version_note_lint covers only the version directives; this module is the
generalisation used by census 3 (PREREG-3.md). It is a line scanner, not a parser.
"""
import re

FAMILIES = {
    "version": ("deprecated-removed", "soft-deprecated", "versionadded", "versionchanged",
                "versionremoved", "deprecated", "version-added", "version-changed",
                "version-deprecated", "version-removed"),
    "admonition": ("attention", "caution", "danger", "error", "hint", "important", "note",
                   "tip", "warning", "admonition", "seealso"),
    "code": ("code-block", "sourcecode", "code", "literalinclude", "doctest", "testcode",
             "testoutput", "testsetup", "testcleanup", "parsed-literal", "math",
             "highlight"),
    "autodoc": ("autoclass", "autofunction", "automethod", "automodule", "autoattribute",
                "autodata", "autoexception", "autosummary", "autoproperty"),
    "structure": ("image", "figure", "rubric", "topic", "sidebar", "toctree", "include",
                  "only", "glossary", "contents", "raw", "csv-table", "list-table", "table",
                  "centered", "hlist", "currentmodule", "module", "function", "class",
                  "method", "attribute", "data", "exception", "decorator", "classmethod",
                  "staticmethod"),
}
FAMILY_OF = {n: f for f, names in FAMILIES.items() for n in names}
NAMES = sorted(FAMILY_OF, key=len, reverse=True)
_ALT = "|".join(re.escape(n) for n in NAMES)

VALID_RE = re.compile(r"^[ \t]*\.\.[ \t]+(?P<d>" + _ALT + r") ?::(?:[ \t].*)?$", re.I)
DROPPED_RE = re.compile(r"^[ \t]*\.\.[ \t]+(?P<d>" + _ALT + r")(?P<sep>[ \t]*:+)(?P<rest>.*)$",
                        re.I)
RAW_RE = re.compile(r"^[ \t]*\.\.(?P<d>" + _ALT + r")[ \t]*:+(?P<rest>.*)$", re.I)
DIRECTIVE_LINE_RE = re.compile(r"^[ \t]*\.\.[ \t]+[\w:.-]+::")
CODE_DIRECTIVE_RE = re.compile(
    r"^[ \t]*\.\.[ \t]+(?:code-block|code|sourcecode|parsed-literal|doctest|testcode|"
    r"testoutput|testsetup|testcleanup|ipython|jupyter-execute|prompt)::", re.I)
EXTENSIONS = (".rst", ".txt", ".inc", ".py", ".pyi", ".pyx", ".pxd")


def _indent(line):
    e = line.expandtabs(8)
    return len(e) - len(e.lstrip())


def scan_text(text, path=""):
    """Every directive marker in `text` for the names in FAMILIES.

    Returns dicts with keys path, line (1-based), directive (lower case), family,
    cls ("OK", "DROPPED" or "RAW_TEXT"), in_literal (bool), text (stripped line).
    Markdown and other files not in EXTENSIONS return [].
    """
    if not path.lower().endswith(EXTENSIONS):
        return []
    out = []
    lit_base = None
    lit_seen = False
    for i, line in enumerate(text.splitlines()):
        stripped = line.strip()
        ind = _indent(line)
        in_lit = False
        if lit_base is not None:
            if not stripped:
                in_lit = lit_seen
            elif ind > lit_base:
                in_lit = True
                lit_seen = True
            else:
                lit_base = None
                lit_seen = False
        cls = None
        m = VALID_RE.match(line)
        if m:
            cls = "OK"
        else:
            m = DROPPED_RE.match(line)
            if m:
                cls = "DROPPED"
            else:
                m = RAW_RE.match(line)
                if m:
                    cls = "RAW_TEXT"
        if m:
            d = m.group("d").lower()
            out.append({"path": path, "line": i + 1, "directive": d,
                        "family": FAMILY_OF[d], "cls": cls, "in_literal": in_lit,
                        "text": stripped[:200]})
        if not in_lit and stripped:
            if CODE_DIRECTIVE_RE.match(line) or (
                    stripped.endswith("::") and not DIRECTIVE_LINE_RE.match(line)):
                lit_base = ind
                lit_seen = False
    return out


def sphinx_lint_would_flag(row):
    """True if sphinx-lint's directive-missing-colons would also catch the row.

    Emulates rst.SEEMS_DIRECTIVE_RE: .rst/.po files only, exactly '.. ' then a
    lower-case directive name, then a character that is neither a letter nor a colon,
    or a single colon. Assumes every name here is in sphinx-lint's directive list,
    which can only overstate the overlap.
    """
    if not row["path"].lower().endswith((".rst", ".po")):
        return False
    return re.match(r"^\.\. " + re.escape(row["directive"]) + r"([^a-z:]|:(?!:))",
                    row["text"]) is not None
