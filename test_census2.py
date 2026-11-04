# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
import unittest

import census
import census2
from test_census import make_tar


def row(project, path, cls, text, directive="versionadded", test_path=False,
        in_literal=False, line=1):
    return {"project": project, "path": path, "line": line, "directive": directive,
            "arg": "", "cls": cls, "in_literal": in_literal, "test_path": test_path,
            "text": text}


class Census2(unittest.TestCase):
    def test_projects(self):
        self.assertEqual(len(census2.NEW_PROJECTS), 30)
        self.assertEqual(len(census2.PROJECTS), 60)
        self.assertEqual(len(set(census2.PROJECTS)), 60)

    def test_sphinx_lint_overlap(self):
        f = census2.sphinx_lint_would_flag
        self.assertTrue(f(row("p", "doc/a.rst", "DROPPED", ".. versionadded: 1.2")))
        self.assertTrue(f(row("p", "doc/a.rst", "DROPPED", ".. versionadded  :: 1.2")))
        self.assertFalse(f(row("p", "doc/a.rst", "DROPPED", ".. versionadded::: 1.2")))
        self.assertFalse(f(row("p", "doc/a.rst", "DROPPED", ".. versionadded::1.2")))
        self.assertFalse(f(row("p", "src/a.py", "DROPPED", ".. versionadded: 1.2")))

    def test_scan_tornado_like_docstring(self):
        buf = make_tar({
            "tornado-abc/tornado/auth.py":
                'def f():\n    """Fetch.\n\n    .. versionadded:: 4.3\n\n'
                '    .. versionchanged::: 6.0\n\n       Removed.\n    """\n',
        })
        notes, files, commit = census.scan_tarball(buf)
        self.assertEqual([(n["path"], n["line"], n["cls"]) for n in notes],
                         [("tornado/auth.py", 4, "OK"), ("tornado/auth.py", 6, "DROPPED")])

    def test_evaluate(self):
        rows = [
            row("tornadoweb/tornado", "tornado/auth.py", "DROPPED",
                ".. versionchanged::: 6.0", directive="versionchanged"),
            row("psf/requests", "docs/a.rst", "DROPPED", ".. versionadded: 1.2"),
            row("psf/requests", "tests/t.rst", "DROPPED", ".. versionadded: 1.3",
                test_path=True),
            row("twisted/twisted", "src/x.py", "OTHER", ".. versionadded:: Twisted 1.0"),
            row("pallets/werkzeug", "src/werkzeug/sansio/response.py", "PUNCT",
                ".. versionadded:: 0.7,"),
            row("psf/requests", "docs/b.rst", "OTHER", ".. versionadded:: Foo",
                in_literal=True),
        ]
        projects = ["tornadoweb/tornado", "psf/requests", "twisted/twisted",
                    "pallets/werkzeug"]
        per = [{"project": p, "ok": True} for p in projects]
        res, rep, dropped = census2.evaluate(rows, per, projects)
        self.assertTrue(res["gate_held"])
        self.assertEqual(res["dropped_rows"], 2)
        self.assertEqual(res["dropped_projects"], ["psf/requests", "tornadoweb/tornado"])
        self.assertFalse(res["P1_held"])
        self.assertEqual(res["P3_v1_false_positive_rows"], 1)
        self.assertFalse(res["P3_held"])
        self.assertEqual(res["P4_new_projects_with_slip"], ["twisted/twisted"])
        self.assertFalse(res["P4_held"])
        self.assertEqual(res["sphinx_lint_overlap"], 1)
        self.assertEqual(len(rep), 4)

    def test_gate_fails_without_known_case(self):
        per = [{"project": "a/b", "ok": True}]
        res, _, _ = census2.evaluate([], per, ["a/b"])
        self.assertFalse(res["gate"]["G1_tornado_dropped_found"])
        self.assertFalse(res["gate_held"])


if __name__ == "__main__":
    unittest.main()
