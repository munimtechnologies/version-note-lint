#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Pre-registered census 3 (see PREREG-3.md): silently dropped DIRECTIVES of any kind.

Census 2 found 42 version notes in 14 of 60 Python projects whose marker docutils
silently turns into a comment or plain text. Census 3 asks the same question for
every common directive (note, warning, seealso, code-block, testcode, autoclass,
image, ...) in the same 60 projects, read from GitHub source tarballs (streamed,
not stored) and scanned with marker_scan.

Usage: python census3.py --out-dir /out
"""
import argparse
import csv
import hashlib
import io
import json
import os
import sys
import tarfile
import time
import urllib.request

import marker_scan as ms

PROJECTS = [
    "python/cpython", "django/django", "numpy/numpy", "scipy/scipy",
    "pandas-dev/pandas", "matplotlib/matplotlib", "scikit-learn/scikit-learn",
    "sphinx-doc/sphinx", "sqlalchemy/sqlalchemy", "pytest-dev/pytest", "pypa/pip",
    "pypa/setuptools", "python-attrs/attrs", "pallets/flask", "pallets/werkzeug",
    "pallets/jinja", "pallets/click", "celery/celery", "astropy/astropy",
    "networkx/networkx", "pydata/xarray", "sympy/sympy", "ipython/ipython",
    "python-pillow/Pillow", "scikit-image/scikit-image", "statsmodels/statsmodels",
    "dask/dask", "tornadoweb/tornado", "pyca/cryptography", "python/mypy",
    "twisted/twisted", "aio-libs/aiohttp", "psf/requests", "urllib3/urllib3",
    "python-trio/trio", "agronholm/anyio", "psycopg/psycopg", "sqlalchemy/alembic",
    "pypa/packaging", "tox-dev/tox", "pylint-dev/pylint", "marshmallow-code/marshmallow",
    "bokeh/bokeh", "numba/numba", "cython/cython", "h5py/h5py", "shapely/shapely",
    "pymc-devs/pymc", "python-babel/babel", "pygments/pygments", "paramiko/paramiko",
    "Pylons/pyramid", "falconry/falcon", "benoitc/gunicorn", "redis/redis-py",
    "mongodb/mongo-python-driver", "celery/kombu", "pyca/pyopenssl",
    "prompt-toolkit/python-prompt-toolkit", "Textualize/rich",
]
MAX_FILE = 3 * 1024 * 1024
SKIP_PARTS = ("node_modules", ".git")
BAD = ("DROPPED", "RAW_TEXT")
KNOWN = ("Pylons/pyramid", "src/pyramid/session.py", "version", "DROPPED")
REVIEW_CAP = 40
COLS = ["project", "path", "line", "directive", "family", "cls", "in_literal", "test_path",
        "sphinx_lint", "text"]


def relpath(member_name):
    return member_name.split("/", 1)[1] if "/" in member_name else ""


def wanted(rel, size):
    if not rel or size > MAX_FILE:
        return False
    if any(p in SKIP_PARTS for p in rel.split("/")):
        return False
    return rel.lower().endswith(ms.EXTENSIONS)


def is_test_path(rel):
    parts = rel.split("/")
    return (any(p in ("test", "tests", "testing") for p in parts[:-1]) or
            parts[-1].startswith("test_"))


def scan_tarball(fileobj):
    """Scan a .tar.gz stream; return (markers, files_read, commit)."""
    rows, files = [], 0
    with tarfile.open(fileobj=fileobj, mode="r|gz") as tf:
        for m in tf:
            if not m.isfile():
                continue
            rel = relpath(m.name)
            if not wanted(rel, m.size):
                continue
            f = tf.extractfile(m)
            if f is None:
                continue
            text = f.read().decode("utf-8", "replace")
            files += 1
            rows.extend(ms.scan_text(text, rel))
        commit = (tf.pax_headers or {}).get("comment", "")
    return rows, files, commit


def fetch_project(slug, log, tries=3):
    url = "https://github.com/%s/archive/HEAD.tar.gz" % slug
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mv2-directive-census"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return scan_tarball(r)
        except Exception as e:  # network or archive error: retry
            last = e
            log.append("%s try %d failed: %s" % (slug, k + 1, e))
            time.sleep(5 * (k + 1))
    raise RuntimeError("%s: %s" % (slug, last))


def review_order(rows):
    """Deterministic pre-registered order for hand review."""
    return sorted(rows, key=lambda r: hashlib.sha256(
        ("%s:%s:%d" % (r["project"], r["path"], r["line"])).encode()).hexdigest())


def evaluate(rows, per, projects):
    """Gate and predictions; returns (results, reported, nonversion)."""
    ok = [p for p in per if p.get("ok")]
    rep = [r for r in rows if r["cls"] in BAD and not r["in_literal"] and not r["test_path"]]
    nonver = [r for r in rep if r["family"] != "version"]
    nv_projects = sorted({r["project"] for r in nonver})
    overlap = sum(1 for r in nonver if r["sphinx_lint"])
    code_rows = [r for r in nonver if r["family"] == "code"]
    known = any(r["project"] == KNOWN[0] and r["path"] == KNOWN[1] and
                r["family"] == KNOWN[2] and r["cls"] == KNOWN[3] for r in rep)

    def rate(fam_pred):
        allm = [r for r in rows if not r["in_literal"] and not r["test_path"] and
                fam_pred(r["family"])]
        bad = [r for r in allm if r["cls"] in BAD]
        return len(bad), len(allm), (len(bad) / len(allm) if allm else None)

    vb, vn, vr = rate(lambda f: f == "version")
    nb, nn, nr = rate(lambda f: f != "version")
    gate = {
        "G1_projects_read_ge_90pct": len(ok) >= 0.9 * len(projects),
        "G2_pyramid_session_version_dropped_found": known,
    }
    res = {
        "gate": gate,
        "gate_held": all(gate.values()),
        "nonversion_rows": len(nonver),
        "nonversion_projects": nv_projects,
        "P1_held": len(nonver) >= 20 and len(nv_projects) >= 8,
        "P2_sphinx_lint_overlap": overlap,
        "P2_overlap_share": (overlap / len(nonver)) if nonver else None,
        "P2_held": (overlap / len(nonver) <= 0.40) if nonver else None,
        "P3": "graded by hand on review3.csv (GRADING-3.md)",
        "P4_code_family_rows": len(code_rows),
        "P4_held": len(code_rows) >= 3,
        "P5_version_rate": {"bad": vb, "markers": vn, "rate": vr},
        "P5_nonversion_rate": {"bad": nb, "markers": nn, "rate": nr},
        "P5_held": (nr < vr) if (vr is not None and nr is not None) else None,
        "reported_by_family_class": {
            "%s/%s" % (f, c): sum(1 for r in rep if r["family"] == f and r["cls"] == c)
            for f in ms.FAMILIES for c in BAD},
        "nonversion_by_directive": dict(sorted(
            ((d, sum(1 for r in nonver if r["directive"] == d))
             for d in {r["directive"] for r in nonver}), key=lambda kv: (-kv[1], kv[0]))),
        "markers_by_family": {f: sum(1 for r in rows if r["family"] == f)
                              for f in ms.FAMILIES},
    }
    return res, rep, nonver


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
    per, rows = [], []
    for slug in projects:
        try:
            markers, files, commit = fetch_project(slug, log)
        except RuntimeError as e:
            per.append({"project": slug, "ok": False, "error": str(e)[:300]})
            log.append("%s: FAILED" % slug)
            continue
        counts = {}
        for r in markers:
            r["project"] = slug
            r["test_path"] = is_test_path(r["path"])
            r["sphinx_lint"] = ms.sphinx_lint_would_flag(r)
            key = "%s/%s%s" % (r["family"], r["cls"], "_lit" if r["in_literal"] else "")
            counts[key] = counts.get(key, 0) + 1
        rows.extend(markers)
        per.append({"project": slug, "ok": files > 0, "commit": commit, "files": files,
                    "markers": len(markers), "counts": counts})
        log.append("%s: %d files, %d markers" % (slug, files, len(markers)))

    res, rep, nonver = evaluate(rows, per, projects)
    write_csv(os.path.join(a.out_dir, "findings3.csv"),
              [r for r in rows if r["cls"] != "OK"])
    write_csv(os.path.join(a.out_dir, "reported3.csv"), rep)
    review = review_order(nonver)[:REVIEW_CAP]
    write_csv(os.path.join(a.out_dir, "review3.csv"), review)

    summary = dict(res)
    summary.update({
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(time.time() - t0, 1),
        "projects_listed": len(projects),
        "projects_read": sum(1 for p in per if p.get("ok")),
        "markers_total": len(rows),
        "review3_size": len(review),
        "per_project": per,
        "log": log,
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, sort_keys=True)
    for r in rep[:600]:
        print("REPORT %s %s:%d %s %s %s %r" % (r["project"], r["path"], r["line"],
                                               r["family"], r["directive"], r["cls"],
                                               r["text"][:90]))
    print("GATE", json.dumps(res["gate"], sort_keys=True))
    print("P1 %d non-version rows in %d projects; P2 overlap %s; P4 %d code rows; "
          "P5 version %s vs non-version %s" % (
              res["nonversion_rows"], len(res["nonversion_projects"]),
              res["P2_overlap_share"], res["P4_code_family_rows"],
              res["P5_version_rate"]["rate"], res["P5_nonversion_rate"]["rate"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
