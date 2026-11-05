# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
import io
import tarfile
import unittest

import census3
import marker_scan as ms


def make_tar(files, comment="abc123"):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.PAX_FORMAT,
                      pax_headers={"comment": comment}) as tf:
        for name, text in files.items():
            data = text.encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf


def one(line, path="doc/a.rst"):
    rows = ms.scan_text(line + "\n", path)
    return [(r["directive"], r["family"], r["cls"]) for r in rows]


class MarkerScan(unittest.TestCase):
    def test_valid_forms(self):
        self.assertEqual(one(".. note:: shown"), [("note", "admonition", "OK")])
        self.assertEqual(one(".. Note:: shown"), [("note", "admonition", "OK")])
        self.assertEqual(one(".. note ::"), [("note", "admonition", "OK")])
        self.assertEqual(one(".. code-block:: python"), [("code-block", "code", "OK")])
        self.assertEqual(one(".. deprecated-removed:: 3.3 3.21"),
                         [("deprecated-removed", "version", "OK")])
        self.assertEqual(one(".. deprecated:: 3.3"), [("deprecated", "version", "OK")])

    def test_dropped_forms(self):
        self.assertEqual(one(".. note: hidden"), [("note", "admonition", "DROPPED")])
        self.assertEqual(one(".. warning::: x"), [("warning", "admonition", "DROPPED")])
        self.assertEqual(one(".. code-block::python"), [("code-block", "code", "DROPPED")])
        self.assertEqual(one(".. note  :: x"), [("note", "admonition", "DROPPED")])
        self.assertEqual(one("    .. versionchanged::: 6.0", "tornado/auth.py"),
                         [("versionchanged", "version", "DROPPED")])

    def test_raw_text(self):
        self.assertEqual(one("..warning:: x"), [("warning", "admonition", "RAW_TEXT")])
        self.assertEqual(one('        ..testcode::', "tornado/auth.py"),
                         [("testcode", "code", "RAW_TEXT")])

    def test_not_markers(self):
        self.assertEqual(one(".. notes: x"), [])
        self.assertEqual(one(".. _note: https://example.org"), [])
        self.assertEqual(one(".. |x| image:: y.png"), [])
        self.assertEqual(one("... note:: x"), [])
        self.assertEqual(one(".. note: x", "README.md"), [])

    def test_literal_blocks(self):
        rows = ms.scan_text("Example::\n\n    .. note: x\n\nback\n.. note: y\n", "a.rst")
        self.assertEqual([(r["line"], r["cls"], r["in_literal"]) for r in rows],
                         [(3, "DROPPED", True), (6, "DROPPED", False)])
        rows = ms.scan_text(".. code-block:: rst\n\n   ..note:: x\n", "a.rst")
        self.assertEqual([(r["line"], r["cls"], r["in_literal"]) for r in rows],
                         [(1, "OK", False), (3, "RAW_TEXT", True)])

    def test_sphinx_lint_emulation(self):
        f = ms.sphinx_lint_would_flag

        def row(path, text, d="note"):
            return {"path": path, "text": text, "directive": d}
        self.assertTrue(f(row("doc/a.rst", ".. note: x")))
        self.assertTrue(f(row("doc/a.rst", ".. note  :: x")))
        self.assertFalse(f(row("doc/a.rst", ".. note::: x")))
        self.assertFalse(f(row("doc/a.rst", ".. Note: x")))
        self.assertFalse(f(row("src/a.py", ".. note: x")))
        self.assertFalse(f(row("doc/a.rst", ".. code-block::python", "code-block")))


class Census3(unittest.TestCase):
    def test_projects(self):
        self.assertEqual(len(census3.PROJECTS), 60)
        self.assertEqual(len(set(census3.PROJECTS)), 60)

    def test_paths(self):
        self.assertTrue(census3.is_test_path("testing/a.py"))
        self.assertTrue(census3.is_test_path("src/test_a.py"))
        self.assertFalse(census3.is_test_path("doc/a.rst"))
        self.assertTrue(census3.wanted("doc/a.rst", 10))
        self.assertFalse(census3.wanted("doc/a.md", 10))
        self.assertFalse(census3.wanted("x/node_modules/a.rst", 10))

    def test_scan_tarball(self):
        buf = make_tar({
            "pyramid-abc/src/pyramid/session.py":
                'def f():\n    """Doc.\n\n    .. versionadded: 1.5a3\n\n'
                '    .. note:: fine\n\n    ..warning:: shown raw\n    """\n',
            "pyramid-abc/README.md": ".. note: ignored\n",
        })
        rows, files, commit = census3.scan_tarball(buf)
        self.assertEqual(files, 1)
        self.assertEqual(commit, "abc123")
        self.assertEqual([(r["line"], r["family"], r["cls"]) for r in rows],
                         [(4, "version", "DROPPED"), (6, "admonition", "OK"),
                          (8, "admonition", "RAW_TEXT")])

    def test_evaluate(self):
        def r(project, path, fam, d, cls, text, lit=False, test=False, sl=False):
            return {"project": project, "path": path, "line": 1, "family": fam,
                    "directive": d, "cls": cls, "in_literal": lit, "test_path": test,
                    "sphinx_lint": sl, "text": text}
        rows = [
            r("Pylons/pyramid", "src/pyramid/session.py", "version", "versionadded",
              "DROPPED", ".. versionadded: 1.5a3"),
            r("Pylons/pyramid", "src/pyramid/a.py", "version", "versionadded", "OK", ""),
            r("a/b", "doc/x.rst", "admonition", "note", "DROPPED", ".. note: x", sl=True),
            r("a/b", "src/y.py", "code", "testcode", "RAW_TEXT", "..testcode::"),
            r("a/b", "doc/z.rst", "admonition", "note", "OK", ""),
            r("a/b", "doc/z.rst", "admonition", "note", "OK", ""),
            r("a/b", "doc/z.rst", "admonition", "note", "OK", ""),
            r("a/b", "doc/z.rst", "admonition", "note", "OK", ""),
            r("a/b", "doc/l.rst", "admonition", "note", "DROPPED", ".. note: l", lit=True),
            r("a/b", "tests/t.py", "admonition", "note", "DROPPED", ".. note: t", test=True),
        ]
        projects = ["Pylons/pyramid", "a/b"]
        per = [{"project": p, "ok": True} for p in projects]
        res, rep, nonver = census3.evaluate(rows, per, projects)
        self.assertTrue(res["gate_held"])
        self.assertEqual(len(rep), 3)
        self.assertEqual(res["nonversion_rows"], 2)
        self.assertEqual(res["nonversion_projects"], ["a/b"])
        self.assertFalse(res["P1_held"])
        self.assertEqual(res["P2_sphinx_lint_overlap"], 1)
        self.assertEqual(res["P2_overlap_share"], 0.5)
        self.assertFalse(res["P2_held"])
        self.assertEqual(res["P4_code_family_rows"], 1)
        self.assertFalse(res["P4_held"])
        self.assertEqual(res["P5_version_rate"], {"bad": 1, "markers": 2, "rate": 0.5})
        self.assertEqual(res["P5_nonversion_rate"], {"bad": 2, "markers": 6,
                                                     "rate": 2 / 6})
        self.assertTrue(res["P5_held"])
        self.assertEqual(res["nonversion_by_directive"], {"note": 1, "testcode": 1})
        self.assertEqual(res["reported_by_family_class"]["admonition/DROPPED"], 1)

    def test_gate_fails_without_known_case(self):
        res, _, _ = census3.evaluate([], [{"project": "a/b", "ok": True}], ["a/b"])
        self.assertFalse(res["gate"]["G2_pyramid_session_version_dropped_found"])
        self.assertFalse(res["gate_held"])
        self.assertIsNone(res["P2_held"])
        self.assertIsNone(res["P5_held"])


if __name__ == "__main__":
    unittest.main()
