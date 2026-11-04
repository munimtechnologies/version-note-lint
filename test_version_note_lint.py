# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
import contextlib
import io
import os
import tempfile
import unittest

import version_note_lint as vnl


class ClassifyToken(unittest.TestCase):
    def test_versions(self):
        for t in ("3.14", "v2.1", "2.0.0rc1", "1.0b1", "3.14.0a1", "21", "2024.1"):
            self.assertEqual(vnl.classify_token(t), "VERSION", t)

    def test_two_versions_joined_by_slash(self):
        for t in ("2.0/2.3.4", "2.0.14/2.0.22"):
            self.assertEqual(vnl.classify_token(t), "VERSION", t)

    def test_placeholders(self):
        for t in ("next", "A.B", "X.Y", "3.x", "|version|", "NEXT_VERSION", "unreleased",
                  "{version}", "{{", "{{start_version}}", "{%"):
            self.assertEqual(vnl.classify_token(t), "PLACEHOLDER", t)

    def test_punct(self):
        for t in ("1.14.", "1.2.0:", "2.0::", "1.4.48,", "1.2,"):
            self.assertEqual(vnl.classify_token(t), "PUNCT", t)

    def test_other(self):
        for t in ("NumPy", "Python", "Django", "Kombu", "The", ":"):
            self.assertEqual(vnl.classify_token(t), "OTHER", t)


class ScanText(unittest.TestCase):
    def test_numpy_body_as_version(self):
        text = (".. versionchanged::\n"
                "    NumPy 2.1 changed the headers to avoid sharing\n"
                "\nOther.\n")
        notes = vnl.scan_text(text, "array.rst")
        self.assertEqual(len(notes), 1)
        n = notes[0]
        self.assertEqual((n["line"], n["cls"], n["arg"], n["in_literal"]),
                         (1, "BODY_AS_VERSION", "NumPy", False))
        self.assertEqual(n["directive"], "versionchanged")

    def test_missing(self):
        notes = vnl.scan_text(".. versionadded::\n\n   Body.\n", "a.rst")
        self.assertEqual([(n["cls"], n["arg"]) for n in notes], [("MISSING", "")])

    def test_option_line_is_not_an_argument(self):
        notes = vnl.scan_text(".. versionadded::\n   :foo: bar\n", "a.rst")
        self.assertEqual(notes[0]["cls"], "MISSING")

    def test_version_on_next_line_is_fine(self):
        notes = vnl.scan_text(".. versionadded::\n   2.0\n", "a.rst")
        self.assertEqual((notes[0]["cls"], notes[0]["arg"]), ("OK", "2.0"))

    def test_ok_and_other(self):
        notes = vnl.scan_text(".. versionadded:: 2.0\n.. versionchanged:: Python 3.4\n",
                              "a.rst")
        self.assertEqual([(n["cls"], n["arg"]) for n in notes],
                         [("OK", "2.0"), ("OTHER", "Python")])

    def test_sphinx9_and_cpython_names(self):
        text = (".. version-added:: 1.0\n.. deprecated-removed:: 3.12 3.14\n"
                ".. soft-deprecated:: 3.13\n.. version-removed:: Foo\n")
        notes = vnl.scan_text(text, "a.rst")
        self.assertEqual([n["directive"] for n in notes],
                         ["version-added", "deprecated-removed", "soft-deprecated",
                          "version-removed"])
        self.assertEqual([n["cls"] for n in notes], ["OK", "OK", "OK", "OTHER"])

    def test_dropped(self):
        # Tornado's OAuth2Mixin.oauth2_request docstring had the first form (2026-11-03).
        text = (".. versionchanged::: 6.0\n"
                "\n"
                "   The callback argument was removed.\n"
                ".. versionadded: 1.2\n"
                ".. versionadded::1.3\n"
                ".. versionadded  :: 1.4\n"
                ".. versionadded :: 1.5\n")
        notes = vnl.scan_text(text, "auth.py")
        self.assertEqual([(n["line"], n["cls"], n["arg"]) for n in notes],
                         [(1, "DROPPED", "6.0"), (4, "DROPPED", "1.2"),
                          (5, "DROPPED", "1.3"), (6, "DROPPED", "1.4"), (7, "OK", "1.5")])
        self.assertEqual(notes[0]["directive"], "versionchanged")

    def test_raw_text(self):
        notes = vnl.scan_text("..versionadded:: 2.0\n", "a.rst")
        self.assertEqual([(n["cls"], n["arg"]) for n in notes], [("RAW_TEXT", "2.0")])

    def test_docstring_closing_quotes(self):
        text = 'x = property(doc="""Header.\n\n    .. versionadded:: 0.7""",\n)\n'
        notes = vnl.scan_text(text, "response.py")
        self.assertEqual([(n["line"], n["cls"], n["arg"]) for n in notes],
                         [(3, "OK", "0.7")])
        notes = vnl.scan_text(text, "response.rst")
        self.assertEqual([n["cls"] for n in notes], ["OTHER"])

    def test_templated_docstring(self):
        notes = vnl.scan_text("    .. deprecated:: {{ start_version }}\n", "fit.py")
        self.assertEqual([n["cls"] for n in notes], ["PLACEHOLDER"])

    def test_literal_block_is_skipped(self):
        text = ("Example::\n\n    .. versionadded:: Foo\n\nAfter.\n"
                ".. versionadded:: Bar\n")
        notes = vnl.scan_text(text, "a.rst")
        self.assertEqual(len(notes), 2)
        self.assertTrue(notes[0]["in_literal"])
        self.assertEqual([n["line"] for n in vnl.findings(notes)], [6])
        self.assertEqual(len(vnl.findings(notes, include_literal=True)), 2)

    def test_code_block_is_skipped(self):
        notes = vnl.scan_text(".. code-block:: rst\n\n   .. versionadded:: A.B\n", "a.rst")
        self.assertEqual((notes[0]["cls"], notes[0]["in_literal"]), ("PLACEHOLDER", True))

    def test_future_on_branch(self):
        text = ".. versionchanged:: 6.0.6\n.. versionadded:: 5.2.15\n"
        notes = vnl.scan_text(text, "cache.txt", (5, 2))
        self.assertEqual([n["cls"] for n in notes], ["FUTURE", "OK"])
        self.assertEqual([n["cls"] for n in vnl.scan_text(text, "cache.txt")], ["OK", "OK"])

    def test_docstring(self):
        text = 'def f():\n    """Do it.\n\n    .. versionadded:: 1.20.0\n    """\n'
        notes = vnl.scan_text(text, "m.py")
        self.assertEqual([(n["line"], n["cls"]) for n in notes], [(4, "OK")])

    def test_myst(self):
        text = ("```{versionadded} 1.2\nBody\n```\n\n```python\n"
                "```{versionchanged} Foo\n```\n\n```{deprecated}\nBody\n```\n")
        notes = vnl.scan_text(text, "x.md")
        self.assertEqual([(n["cls"], n["arg"]) for n in notes],
                         [("OK", "1.2"), ("MISSING", "")])

    def test_ignore(self):
        notes = vnl.scan_text(".. deprecated:: 1.14.\n.. versionadded:: Foo\n", "a.rst")
        self.assertEqual([n["cls"] for n in vnl.findings(notes)], ["PUNCT", "OTHER"])
        self.assertEqual([n["cls"] for n in vnl.findings(notes, ignore=("PUNCT",))],
                         ["OTHER"])

    def test_parse_branch_version(self):
        self.assertEqual(vnl.parse_branch_version("5.2"), (5, 2))
        with self.assertRaises(ValueError):
            vnl.parse_branch_version("5")


class Cli(unittest.TestCase):
    def run_main(self, args):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = vnl.main(args)
        return code, buf.getvalue()

    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "good.rst")
            bad = os.path.join(d, "bad.rst")
            with open(good, "w", encoding="utf-8") as f:
                f.write(".. versionadded:: 1.0\n")
            with open(bad, "w", encoding="utf-8") as f:
                f.write(".. versionchanged::\n    NumPy 2.1 changed it\n")
            self.assertEqual(self.run_main([good])[0], 0)
            code, out = self.run_main([d])
            self.assertEqual(code, 1)
            self.assertIn("bad.rst:1: BODY_AS_VERSION", out)
            self.assertIn("'NumPy'", out)
            code, out = self.run_main(["--branch-version", "0.9", good])
            self.assertEqual(code, 1)
            self.assertIn("FUTURE", out)

    def test_ignore_flag_and_dropped_message(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "a.rst")
            with open(p, "w", encoding="utf-8") as f:
                f.write(".. deprecated:: 1.14.\n")
            code, out = self.run_main([p])
            self.assertEqual(code, 1)
            self.assertIn("PUNCT", out)
            self.assertEqual(self.run_main(["--ignore", "punct", p])[0], 0)
            q = os.path.join(d, "b.py")
            with open(q, "w", encoding="utf-8") as f:
                f.write('def f():\n    """X.\n\n    .. versionchanged::: 6.0\n    """\n')
            code, out = self.run_main([q])
            self.assertEqual(code, 1)
            self.assertIn("b.py:4: DROPPED", out)
            self.assertIn(".. versionchanged:: VERSION", out)


if __name__ == "__main__":
    unittest.main()
