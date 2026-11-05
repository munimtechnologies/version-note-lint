# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
import io
import tarfile
import unittest

import census4
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


def r(project, fam, d, cls, cl=False, lit=False, test=False, sl=False, path="doc/x.rst",
      line=1):
    return {"project": project, "path": path, "line": line, "family": fam, "directive": d,
            "cls": cls, "comment_like": cl, "in_literal": lit, "test_path": test,
            "sphinx_lint": sl, "text": ""}


class Census4(unittest.TestCase):
    def test_projects_are_new(self):
        self.assertEqual(len(census4.PROJECTS), 60)
        self.assertEqual(len(set(census4.PROJECTS)), 60)
        self.assertEqual(len(census4.EARLIER), 60)
        lower_earlier = {p.lower() for p in census4.EARLIER}
        self.assertEqual([p for p in census4.PROJECTS if p.lower() in lower_earlier], [])

    def test_scan_tarball_marks_comment_like(self):
        buf = make_tar({
            "proj-abc/doc/a.rst": (".. note: an author comment\n\n.. note:\n   body\n\n"
                                   ".. code-block::python\n\n   x = 1\n"),
            "proj-abc/README.md": ".. note: ignored\n",
        })
        rows, files, commit = census4.scan_tarball(buf)
        self.assertEqual(files, 1)
        self.assertEqual(commit, "abc123")
        self.assertEqual([(x["line"], x["directive"], x["cls"], x["comment_like"])
                          for x in rows],
                         [(1, "note", "DROPPED", True), (3, "note", "DROPPED", False),
                          (6, "code-block", "DROPPED", False)])

    def test_evaluate(self):
        rows = [r("a/b", "admonition", "note", "DROPPED", line=1),
                r("a/b", "admonition", "note", "DROPPED", cl=True, line=2),
                r("a/b", "code", "math", "RAW_TEXT", sl=True, line=3),
                r("a/b", "admonition", "note", "DROPPED", lit=True, line=4),
                r("a/b", "admonition", "note", "DROPPED", test=True, line=5),
                r("a/b", "admonition", "note", "OK", line=6),
                r("a/b", "version", "versionadded", "DROPPED", line=7),
                r("a/b", "version", "versionadded", "OK", line=8)]
        per = [{"project": "a/b", "ok": True}]
        res, rep, default, comment = census4.evaluate(rows, per, ["a/b"])
        self.assertTrue(res["gate"]["G1_projects_read_ge_90pct"])
        self.assertFalse(res["gate"]["G2_markers_ge_20000"])
        self.assertFalse(res["gate_held"])
        self.assertEqual(len(rep), 4)
        self.assertEqual(res["nonversion_rows"], 3)
        self.assertEqual(res["default_rows"], 2)
        self.assertEqual(res["comment_like_rows"], 1)
        self.assertEqual(res["default_projects"], ["a/b"])
        self.assertFalse(res["P1_held"])
        self.assertAlmostEqual(res["P4_comment_like_share"], 1 / 3)
        self.assertTrue(res["P4_held"])
        self.assertEqual(res["P5_version_rate"], {"bad": 1, "markers": 2, "rate": 0.5})
        self.assertEqual(res["P5_nonversion_default_rate"],
                         {"bad": 2, "markers": 4, "rate": 0.5})
        self.assertFalse(res["P5_held"])
        self.assertEqual(res["sphinx_lint_overlap_default"], 1)
        self.assertEqual(res["default_by_directive"], {"math": 1, "note": 1})
        self.assertEqual(res["P3"], "not graded: fewer than 5 comment-like rows")

    def test_empty(self):
        res, rep, default, comment = census4.evaluate([], [], ["a/b"])
        self.assertFalse(res["gate_held"])
        self.assertIsNone(res["P4_held"])
        self.assertIsNone(res["P5_held"])

    def test_review_order_is_deterministic(self):
        rows = [r("a/b", "admonition", "note", "DROPPED", line=k) for k in range(1, 30)]
        self.assertEqual(census4.review_order(rows), census4.review_order(rows[::-1]))

    def test_marker_scan_rules(self):
        rows = ms.scan_text("..   :caption: x\n..             class :obj:`y` with\n",
                            "doc/a.rst")
        self.assertEqual([(x["directive"], x["comment_like"]) for x in rows],
                         [("class", True)])


if __name__ == "__main__":
    unittest.main()
