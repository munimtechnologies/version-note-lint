#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Pre-registered census 2 for version-note-lint (see PREREG-2.md).

Silently dropped version notes: how often is a versionadded / versionchanged /
deprecated note written with a malformed marker (".. versionchanged::: 6.0",
".. versionadded: 1.2", ".. versionadded::1.2", "..versionadded:: 1.2"), so that
docutils turns it into a comment or plain text? Default branches of 60 Python
projects (the 30 from census 1 plus 30 new ones), streamed from GitHub tarballs and
scanned with version_note_lint 0.1.1.

Usage: python census2.py --out-dir /out
"""
import argparse
import csv
import json
import os
import re
import sys
import time

import census
import version_note_lint as vnl

NEW_PROJECTS = [
    "twisted/twisted", "aio-libs/aiohttp", "psf/requests", "urllib3/urllib3",
    "python-trio/trio", "agronholm/anyio", "psycopg/psycopg", "sqlalchemy/alembic",
    "pypa/packaging", "tox-dev/tox", "pylint-dev/pylint", "marshmallow-code/marshmallow",
    "bokeh/bokeh", "numba/numba", "cython/cython", "h5py/h5py", "shapely/shapely",
    "pymc-devs/pymc", "python-babel/babel", "pygments/pygments", "paramiko/paramiko",
    "Pylons/pyramid", "falconry/falcon", "benoitc/gunicorn", "redis/redis-py",
    "mongodb/mongo-python-driver", "celery/kombu", "pyca/pyopenssl",
    "prompt-toolkit/python-prompt-toolkit", "Textualize/rich",
]
PROJECTS = census.PROJECTS + NEW_PROJECTS
NEW_CLASSES = ("DROPPED", "RAW_TEXT")
SLIP_CLASSES = ("MISSING", "BODY_AS_VERSION", "OTHER")
KNOWN = ("tornadoweb/tornado", "tornado/auth.py", "DROPPED")
V1_FALSE_POSITIVE_FILES = (
    ("pallets/werkzeug", "src/werkzeug/sansio/response.py"),
    ("scikit-image/scikit-image", "src/_skimage2/measure/fit.py"),
)
REVIEW_CAP = 40
COLS = ["project", "sample", "path", "line", "directive", "arg", "cls", "in_literal",
        "test_path", "sphinx_lint", "text"]


def sphinx_lint_would_flag(row):
    """True if sphinx-lint's directive-missing-colons check would also catch the row.

    That check (rst.SEEMS_DIRECTIVE_RE) runs on .rst and .po files only and matches
    '.. <directive>' followed by a character that is not a letter or colon, or by a
    single colon. It does not match '.. name:::', '.. name::1.2' or '..name::'.
    """
    if not row["path"].lower().endswith((".rst", ".po")):
        return False
    return re.match(r"^\.\. " + re.escape(row["directive"]) + r"([^a-z:]|:(?!:))",
                    row["text"]) is not None


def evaluate(rows, per, projects):
    """Gate and predictions from the non-OK rows; returns (results, reported, dropped)."""
    ok = [p for p in per if p.get("ok")]
    rep = [r for r in rows if r["cls"] in vnl.REPORTED and not r["in_literal"] and
           not r["test_path"]]
    dropped = [r for r in rep if r["cls"] in NEW_CLASSES]
    dropped_projects = sorted({r["project"] for r in dropped})
    new_names = set(NEW_PROJECTS)
    slips_new = sorted({r["project"] for r in rep
                        if r["cls"] in SLIP_CLASSES and r["project"] in new_names})
    known = any(r["project"] == KNOWN[0] and r["path"] == KNOWN[1] and r["cls"] == KNOWN[2]
                for r in rep)
    fp = [r for r in rep if (r["project"], r["path"]) in V1_FALSE_POSITIVE_FILES]
    gate = {
        "G1_tornado_dropped_found": known,
        "G2_projects_read_ge_90pct": len(ok) >= 0.9 * len(projects),
    }
    res = {
        "gate": gate,
        "gate_held": all(gate.values()),
        "dropped_rows": len(dropped),
        "dropped_by_class": {c: sum(1 for r in dropped if r["cls"] == c) for c in NEW_CLASSES},
        "dropped_projects": dropped_projects,
        "P1_held": len(dropped) >= 5 and len(dropped_projects) >= 3,
        "P2": "graded by hand on review2.csv (GRADING-2.md)",
        "P3_v1_false_positive_rows": len(fp),
        "P3_held": len(fp) == 0,
        "P4_new_projects_with_slip": slips_new,
        "P4_held": len(slips_new) >= 3,
        "sphinx_lint_overlap": sum(1 for r in dropped if sphinx_lint_would_flag(r)),
        "reported_by_class": {c: sum(1 for r in rep if r["cls"] == c) for c in vnl.REPORTED},
    }
    return res, rep, dropped


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default="/out")
    ap.add_argument("--projects", default="", help="comma list to override (testing)")
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    t0 = time.time()
    log = []
    projects = [p for p in a.projects.split(",") if p] or PROJECTS
    new_names = set(NEW_PROJECTS)
    per, rows = [], []
    for slug in projects:
        try:
            notes, files, commit = census.fetch_project(slug, log)
        except RuntimeError as e:
            per.append({"project": slug, "ok": False, "error": str(e)[:300]})
            log.append("%s: FAILED" % slug)
            continue
        counts = {}
        for n in notes:
            key = n["cls"] + ("_lit" if n["in_literal"] else "")
            counts[key] = counts.get(key, 0) + 1
            if n["cls"] != "OK":
                r = dict(n)
                r["project"] = slug
                r["sample"] = "new" if slug in new_names else "v1"
                r["test_path"] = census.is_test_path(n["path"])
                r["sphinx_lint"] = sphinx_lint_would_flag(r)
                rows.append(r)
        per.append({"project": slug, "ok": files > 0, "commit": commit, "files": files,
                    "notes": len(notes), "counts": counts})
        log.append("%s: %d files, %d notes" % (slug, files, len(notes)))

    res, rep, dropped = evaluate(rows, per, projects)
    write_csv(os.path.join(a.out_dir, "findings2.csv"), rows)
    write_csv(os.path.join(a.out_dir, "reported2.csv"), rep)
    review = census.review_order(dropped)[:REVIEW_CAP]
    write_csv(os.path.join(a.out_dir, "review2.csv"), review)

    summary = dict(res)
    summary.update({
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(time.time() - t0, 1),
        "tool_version": vnl.__version__,
        "projects_listed": len(projects),
        "projects_read": sum(1 for p in per if p.get("ok")),
        "notes_total": sum(p.get("notes", 0) for p in per),
        "review2_size": len(review),
        "per_project": per,
        "log": log,
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, sort_keys=True)
    for r in rep[:500]:
        if r["cls"] != "PUNCT":
            print("REPORT %s %s:%d %s %s %r" % (r["project"], r["path"], r["line"], r["cls"],
                                                r["directive"], r["arg"]))
    print("GATE", json.dumps(res["gate"], sort_keys=True))
    print("P1 %d dropped rows in %d projects; P3 %d; P4 %d new projects; sphinx-lint overlap %d"
          % (res["dropped_rows"], len(res["dropped_projects"]),
             res["P3_v1_false_positive_rows"], len(res["P4_new_projects_with_slip"]),
             res["sphinx_lint_overlap"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
