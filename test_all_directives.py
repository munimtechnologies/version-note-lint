# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Tests for version-note-lint --all-directives and marker_scan's comment_like rules."""
import contextlib
import io
import json
import os
import tempfile
import unittest

import marker_scan as ms
import version_note_lint as vnl

DOC = "\n".join([
    "Title",                                         # 1
    "=====",                                         # 2
    "",                                              # 3
    ".. note:",                                      # 4  DROPPED (slip)
    "   Hidden body.",                               # 5
    "",                                              # 6
    ".. NOTE: an author comment, not for readers",   # 7  DROPPED, comment-like (R1)
    "",                                              # 8
    "..warning:: shown raw",                         # 9  RAW_TEXT
    "",                                              # 10
    ".. code-block::python",                         # 11 DROPPED
    "",                                              # 12
    "   x = 1",                                      # 13
    "",                                              # 14
    ".. versionadded: 1.2",                          # 15 DROPPED (version family)
    "",                                              # 16
    "Example::",                                     # 17
    "",                                              # 18
    "    .. note: inside literal",                   # 19 in a literal block
    "",
])


def cl(text, path="doc/a.rst"):
    return [(r["line"], r["directive"], r["cls"], r["comment_like"])
            for r in ms.scan_text(text, path)]


class CommentLike(unittest.TestCase):
    def test_r1_admonition_with_words(self):
        self.assertEqual(cl(".. note: don't use 30.0 above\n"),
                         [(1, "note", "DROPPED", True)])
        self.assertEqual(cl(".. NOTE:  wow, this section\n"),
                         [(1, "note", "DROPPED", True)])

    def test_r1_does_not_apply(self):
        self.assertEqual(cl(".. note:\n   body\n"), [(1, "note", "DROPPED", False)])
        self.assertEqual(cl(".. note:;\n   body\n"), [(1, "note", "DROPPED", False)])
        self.assertEqual(cl(".. warning:::: It is possible\n"),
                         [(1, "warning", "DROPPED", False)])
        self.assertEqual(cl(".. attribute: registration_required\n"),
                         [(1, "attribute", "DROPPED", False)])
        self.assertEqual(cl(".. code-block: python\n"),
                         [(1, "code-block", "DROPPED", False)])
        self.assertEqual(cl(".. versionadded: 2.2\n"),
                         [(1, "versionadded", "DROPPED", False)])

    def test_r2_commented_out_block(self):
        text = ("..   :caption: One-dimensional interpolation using the\n"
                "..             class :obj:`interp1d` with\n")
        self.assertEqual(cl(text), [(2, "class", "DROPPED", True)])
        self.assertEqual(cl(".. some comment\n.. code-block::python\n"),
                         [(2, "code-block", "DROPPED", True)])

    def test_r2_does_not_apply(self):
        self.assertEqual(cl(".. _sec:\n.. code-block::python\n"),
                         [(2, "code-block", "DROPPED", False)])
        self.assertEqual(cl(".. versionadded: 1.2\n.. versionchanged: 1.3\n"),
                         [(1, "versionadded", "DROPPED", False),
                          (2, "versionchanged", "DROPPED", False)])
        self.assertEqual(cl(".. some comment\n\n.. code-block::python\n"),
                         [(3, "code-block", "DROPPED", False)])
        self.assertEqual(cl(".. some comment\n   .. code-block::python\n"),
                         [(2, "code-block", "DROPPED", False)])

    def test_ok_and_raw_are_never_comment_like(self):
        self.assertEqual(cl(".. some comment\n.. note:: fine\n..note:: raw\n"),
                         [(2, "note", "OK", False), (3, "note", "RAW_TEXT", False)])


class AllDirectivesCli(unittest.TestCase):
    def run_main(self, args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = vnl.main(args)
        return code, buf.getvalue()

    def write(self, d, name, text):
        p = os.path.join(d, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(text)
        return p

    def test_default_reports_only_version_notes(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, "a.rst", DOC)
            code, out = self.run_main(["--json", p])
            self.assertEqual(code, 1)
            self.assertEqual([(n["line"], n["cls"]) for n in json.loads(out)],
                             [(15, "DROPPED")])

    def test_all_directives(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, "a.rst", DOC)
            code, out = self.run_main(["--all-directives", "--json", p])
            self.assertEqual(code, 1)
            self.assertEqual([(n["line"], n["directive"], n["cls"])
                              for n in json.loads(out)],
                             [(4, "note", "DROPPED"), (9, "warning", "RAW_TEXT"),
                              (11, "code-block", "DROPPED"),
                              (15, "versionadded", "DROPPED")])

    def test_include_comment_like(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, "a.rst", DOC)
            code, out = self.run_main(["--all-directives", "--include-comment-like",
                                       "--json", p])
            self.assertEqual([n["line"] for n in json.loads(out)], [4, 7, 9, 11, 15])

    def test_ignore_and_messages(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, "a.rst", DOC)
            code, out = self.run_main(["--all-directives", "--ignore", "RAW_TEXT", p])
            self.assertEqual(code, 1)
            self.assertIn("a.rst:4: DROPPED: malformed '.. note' marker", out)
            self.assertIn("(write '.. note::')", out)
            self.assertIn("(write '.. versionadded:: VERSION')", out)
            self.assertNotIn("a.rst:9:", out)
            code, out = self.run_main(["--all-directives", "--ignore", "DROPPED", p])
            self.assertIn("a.rst:9: RAW_TEXT: no space after '..'", out)
            self.assertIn("(write '.. warning::')", out)

    def test_docstring_and_clean_file(self):
        with tempfile.TemporaryDirectory() as d:
            q = self.write(d, "m.py", 'def f():\n    """Doc.\n\n    ..math::\n\n'
                                      '        x = 1\n    """\n')
            code, out = self.run_main(["--all-directives", q])
            self.assertEqual(code, 1)
            self.assertIn("m.py:4: RAW_TEXT", out)
            good = self.write(d, "g.rst", ".. note::\n   fine\n\n.. versionadded:: 1.0\n")
            self.assertEqual(self.run_main(["--all-directives", good])[0], 0)

    def test_markdown_is_not_scanned_for_other_directives(self):
        with tempfile.TemporaryDirectory() as d:
            p = self.write(d, "a.md", ".. note: x\n")
            self.assertEqual(self.run_main(["--all-directives", p])[0], 0)

    def test_version(self):
        self.assertEqual(vnl.__version__, "0.2.0")


if __name__ == "__main__":
    unittest.main()
