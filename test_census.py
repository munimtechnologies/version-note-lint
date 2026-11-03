# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
import io
import tarfile
import unittest

import census


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


class Helpers(unittest.TestCase):
    def test_relpath_and_wanted(self):
        self.assertEqual(census.relpath("numpy-abc/doc/a.rst"), "doc/a.rst")
        self.assertTrue(census.wanted("doc/a.rst", 10))
        self.assertTrue(census.wanted("docs/topics/cache.txt", 10))
        self.assertFalse(census.wanted("doc/a.png", 10))
        self.assertFalse(census.wanted("web/node_modules/x.md", 10))
        self.assertFalse(census.wanted("doc/big.rst", census.MAX_FILE + 1))
        self.assertFalse(census.wanted("", 1))

    def test_is_test_path(self):
        self.assertTrue(census.is_test_path("tests/roots/test-root/markup.txt"))
        self.assertTrue(census.is_test_path("Lib/test/data.txt"))
        self.assertTrue(census.is_test_path("pkg/test_x.py"))
        self.assertFalse(census.is_test_path("doc/source/testing.rst"))
        self.assertFalse(census.is_test_path("docs/topics/testing/overview.txt"))
        self.assertFalse(census.is_test_path("Doc/library/test.rst"))

    def test_parse_grep_line(self):
        ref = "refs/tags/5.2.15"
        line = ref + ":docs/topics/cache.txt:1412:.. versionchanged:: 6.0.6"
        self.assertEqual(census.parse_grep_line(line, ref),
                         ("docs/topics/cache.txt", 1412, ".. versionchanged:: 6.0.6"))
        self.assertIsNone(census.parse_grep_line("other:x:1:y", ref))

    def test_note_from_content(self):
        self.assertEqual(census.note_from_content("   .. versionchanged:: 6.0.6"),
                         ("versionchanged", "6.0.6", "6.0.6"))
        self.assertEqual(census.note_from_content(".. versionadded::"),
                         ("versionadded", "", ""))
        self.assertIsNone(census.note_from_content("text"))

    def test_label_relation(self):
        self.assertEqual(census.label_relation("6.0.6", (5, 2)), ("newer", True))
        self.assertEqual(census.label_relation("5.2.15", (5, 2)), ("own", True))
        self.assertEqual(census.label_relation("5.2", (5, 2)), ("own", False))
        self.assertEqual(census.label_relation("4.2", (5, 2)), ("older", False))
        self.assertEqual(census.label_relation("A.B", (5, 2)), ("unparsed", False))

    def test_review_order_is_deterministic(self):
        rows = [{"project": "p", "path": "a.rst", "line": i} for i in range(5)]
        a = census.review_order(rows)
        b = census.review_order(list(reversed(rows)))
        self.assertEqual(a, b)
        self.assertEqual(len(a), 5)

    def test_scan_tarball(self):
        buf = make_tar({
            "numpy-abc123/doc/source/reference/c-api/array.rst":
                ".. versionchanged::\n    NumPy 2.1 changed the headers\n",
            "numpy-abc123/numpy/core.py":
                '"""Doc.\n\n.. versionadded:: 2.0\n"""\n',
            "numpy-abc123/logo.png": "not text",
        })
        notes, files, commit = census.scan_tarball(buf)
        self.assertEqual(files, 2)
        self.assertEqual(commit, "abc123")
        got = sorted((n["path"], n["cls"]) for n in notes)
        self.assertEqual(got, [("doc/source/reference/c-api/array.rst", "BODY_AS_VERSION"),
                               ("numpy/core.py", "OK")])


if __name__ == "__main__":
    unittest.main()
