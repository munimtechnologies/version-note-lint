#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Pre-registered census 4 (see PREREG-4.md): do the comment-like rules hold up?

Census 3 (GRADING-3.md) found that most false alarms among malformed directive markers
are deliberate comments such as ".. note: don't use 30.0 above". Two rules (R1, R2 in
marker_scan) were written AFTER seeing that data. Census 4 tests them on 60 Python
projects that were not in censuses 2 and 3, read from GitHub source tarballs
(streamed, not stored).

Usage: python census4.py --out-dir /out
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import tarfile
import time
import urllib.request

import marker_scan as ms

PROJECTS = [
    "boto/boto3", "enthought/traits", "saltstack/salt", "jupyter/jupyter_client",
    "ipython/traitlets", "jupyter/nbconvert", "jupyter/nbformat", "ipython/ipykernel",
    "pyqtgraph/pyqtgraph", "pypa/virtualenv", "pypa/twine", "pypa/build", "pypa/wheel",
    "sqlalchemy/mako", "zopefoundation/zope.interface", "python-jsonschema/jsonschema",
    "PyCQA/flake8", "PyCQA/pycodestyle", "PyCQA/bandit", "pyinstaller/pyinstaller",
    "kivy/kivy", "pygame/pygame", "geopandas/geopandas", "pyproj4/pyproj",
    "rasterio/rasterio", "pvlib/pvlib-python", "sunpy/sunpy", "scrapy/scrapy",
    "Supervisor/supervisor", "fabric/fabric", "pyinvoke/invoke", "django/channels",
    "python-telegram-bot/python-telegram-bot", "Rapptz/discord.py", "aio-libs/yarl",
    "aio-libs/multidict", "MagicStack/asyncpg", "coleifer/peewee",
    "pallets-eco/flask-sqlalchemy", "pallets-eco/wtforms", "HypothesisWorks/hypothesis",
    "nedbat/coveragepy", "pytest-dev/pluggy", "pytest-dev/pytest-xdist", "joblib/joblib",
    "dask/distributed", "pyvista/pyvista", "mne-tools/mne-python", "nipy/nibabel",
    "biopython/biopython", "Unidata/MetPy", "numpy/numpydoc", "arviz-devs/arviz",
    "lmfit/lmfit-py", "mpmath/mpmath", "zeromq/pyzmq", "gevent/gevent",
    "python-websockets/websockets", "Kozea/WeasyPrint", "zarr-developers/zarr-python",
]
# The 60 projects of censuses 2 and 3; none may appear above.
EARLIER = {
    "python/cpython", "django/django", "numpy/numpy", "scipy/scipy", "pandas-dev/pandas",
    "matplotlib/matplotlib", "scikit-learn/scikit-learn", "sphinx-doc/sphinx",
    "sqlalchemy/sqlalchemy", "pytest-dev/pytest", "pypa/pip", "pypa/setuptools",
    "python-attrs/attrs", "pallets/flask", "pallets/werkzeug", "pallets/jinja",
    "pallets/click", "celery/celery", "astropy/astropy", "networkx/networkx",
    "pydata/xarray", "sympy/sympy", "ipython/ipython", "python-pillow/Pillow",
    "scikit-image/scikit-image", "statsmodels/statsmodels", "dask/dask",
    "tornadoweb/tornado", "pyca/cryptography", "python/mypy", "twisted/twisted",
    "aio-libs/aiohttp", "psf/requests", "urllib3/urllib3", "python-trio/trio",
    "agronholm/anyio", "psycopg/psycopg", "sqlalchemy/alembic", "pypa/packaging",
    "tox-dev/tox", "pylint-dev/pylint", "marshmallow-code/marshmallow", "bokeh/bokeh",
    "numba/numba", "cython/cython", "h5py/h5py", "shapely/shapely", "pymc-devs/pymc",
    "python-babel/babel", "pygments/pygments", "paramiko/paramiko", "Pylons/pyramid",
    "falconry/falcon", "benoitc/gunicorn", "redis/redis-py",
    "mongodb/mongo-python-driver", "celery/kombu", "pyca/pyopenssl",
    "prompt-toolkit/python-prompt-toolkit", "Textualize/rich",
}
MAX_FILE = 3 * 1024 * 1024
SKIP_PARTS = ("node_modules", ".git")
BAD = ("DROPPED", "RAW_TEXT")
REVIEW_CAP = 40
COMMENT_CAP = 20
MIN_MARKERS = 20000
COLS = ["project", "path", "line", "directive", "family", "cls", "comment_like",
        "in_literal", "test_path", "sphinx_lint", "text"]


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
            with urllib.request.urlopen(req, timeout=300) as r:
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
    """Gate and mechanical predictions; returns (results, reported, default, comment)."""
    ok = [p for p in per if p.get("ok")]
    rep = [r for r in rows if r["cls"] in BAD and not r["in_literal"] and not r["test_path"]]
    nonver = [r for r in rep if r["family"] != "version"]
    default = [r for r in nonver if not r["comment_like"]]
    comment = [r for r in nonver if r["comment_like"]]
    d_projects = sorted({r["project"] for r in default})
    share = (len(comment) / len(nonver)) if nonver else None

    def rate(sel):
        allm = [r for r in rows if not r["in_literal"] and not r["test_path"] and
                sel(r["family"])]
        return allm

    ver_all = rate(lambda f: f == "version")
    nv_all = rate(lambda f: f != "version")
    ver_bad = sum(1 for r in ver_all if r["cls"] in BAD)
    vr = (ver_bad / len(ver_all)) if ver_all else None
    nr = (len(default) / len(nv_all)) if nv_all else None
    gate = {
        "G1_projects_read_ge_90pct": len(ok) >= 0.9 * len(projects),
        "G2_markers_ge_%d" % MIN_MARKERS: len(rows) >= MIN_MARKERS,
    }
    res = {
        "gate": gate,
        "gate_held": all(gate.values()),
        "nonversion_rows": len(nonver),
        "default_rows": len(default),
        "default_projects": d_projects,
        "comment_like_rows": len(comment),
        "P1_held": len(default) >= 15 and len(d_projects) >= 8,
        "P2": "graded by hand on review4.csv (GRADING-4.md)",
        "P3": ("graded by hand on review4-comment.csv (GRADING-4.md)" if len(comment) >= 5
               else "not graded: fewer than 5 comment-like rows"),
        "P4_comment_like_share": share,
        "P4_held": (0.20 <= share <= 0.60) if share is not None else None,
        "P5_version_rate": {"bad": ver_bad, "markers": len(ver_all), "rate": vr},
        "P5_nonversion_default_rate": {"bad": len(default), "markers": len(nv_all),
                                       "rate": nr},
        "P5_held": (vr > nr) if (vr is not None and nr is not None) else None,
        "sphinx_lint_overlap_default": sum(1 for r in default if r["sphinx_lint"]),
        "reported_by_family_class": {
            "%s/%s" % (f, c): sum(1 for r in rep if r["family"] == f and r["cls"] == c)
            for f in ms.FAMILIES for c in BAD},
        "default_by_directive": dict(sorted(
            ((d, sum(1 for r in default if r["directive"] == d))
             for d in {r["directive"] for r in default}), key=lambda kv: (-kv[1], kv[0]))),
        "markers_by_family": {f: sum(1 for r in rows if r["family"] == f)
                              for f in ms.FAMILIES},
    }
    return res, rep, default, comment


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
            key = "%s/%s%s%s" % (r["family"], r["cls"], "_cl" if r["comment_like"] else "",
                                 "_lit" if r["in_literal"] else "")
            counts[key] = counts.get(key, 0) + 1
        rows.extend(markers)
        per.append({"project": slug, "ok": files > 0, "commit": commit, "files": files,
                    "markers": len(markers), "counts": counts})
        log.append("%s: %d files, %d markers" % (slug, files, len(markers)))

    res, rep, default, comment = evaluate(rows, per, projects)
    write_csv(os.path.join(a.out_dir, "findings4.csv"),
              [r for r in rows if r["cls"] != "OK"])
    write_csv(os.path.join(a.out_dir, "reported4.csv"), rep)
    review = review_order(default)[:REVIEW_CAP]
    write_csv(os.path.join(a.out_dir, "review4.csv"), review)
    review_c = review_order(comment)[:COMMENT_CAP]
    write_csv(os.path.join(a.out_dir, "review4-comment.csv"), review_c)

    summary = dict(res)
    summary.update({
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(time.time() - t0, 1),
        "projects_listed": len(projects),
        "projects_read": sum(1 for p in per if p.get("ok")),
        "markers_total": len(rows),
        "review4_size": len(review),
        "review4_comment_size": len(review_c),
        "per_project": per,
        "log": log,
    })
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, sort_keys=True)
    for r in rep[:800]:
        print("REPORT %s %s:%d %s %s %s%s %r" % (
            r["project"], r["path"], r["line"], r["family"], r["directive"], r["cls"],
            " COMMENT_LIKE" if r["comment_like"] else "", r["text"][:90]))
    print("GATE", json.dumps(res["gate"], sort_keys=True))
    print("P1 %d default non-version rows in %d projects; P4 comment-like share %s; "
          "P5 version %s vs non-version default %s" % (
              res["default_rows"], len(res["default_projects"]),
              res["P4_comment_like_share"], res["P5_version_rate"]["rate"],
              res["P5_nonversion_default_rate"]["rate"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
