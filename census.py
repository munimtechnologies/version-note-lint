#!/usr/bin/env python3
# Copyright 2026 Munim, Inc. (MV2, mv2@munimtech.com)
# Licensed under the Apache License, Version 2.0 (Apache-2.0). See LICENSE.
# Made with AI agents working in MV2's name.
"""Pre-registered census for version-note-lint (see PREREG.md).

Part A: the default branch of 30 Sphinx-documented Python projects, read from GitHub's
source tarballs (streamed, not stored), scanned with version_note_lint.scan_text.
Part B: Django's final release tags since 3.0 (bare clone in the data volume): which
version label do version notes carry when they first appear after a series' X.Y.0?

Usage: python census.py --data-dir /data --out-dir /out
"""
import argparse
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import time
import urllib.request

import version_note_lint as vnl

PROJECTS = [
    "python/cpython", "django/django", "numpy/numpy", "scipy/scipy",
    "pandas-dev/pandas", "matplotlib/matplotlib", "scikit-learn/scikit-learn",
    "sphinx-doc/sphinx", "sqlalchemy/sqlalchemy", "pytest-dev/pytest", "pypa/pip",
    "pypa/setuptools", "python-attrs/attrs", "pallets/flask", "pallets/werkzeug",
    "pallets/jinja", "pallets/click", "celery/celery", "astropy/astropy",
    "networkx/networkx", "pydata/xarray", "sympy/sympy", "ipython/ipython",
    "python-pillow/Pillow", "scikit-image/scikit-image", "statsmodels/statsmodels",
    "dask/dask", "tornadoweb/tornado", "pyca/cryptography", "python/mypy",
]
MAX_FILE = 3 * 1024 * 1024
SKIP_PARTS = ("node_modules", ".git")
DJANGO_URL = "https://github.com/django/django.git"
DJANGO_TAG_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?$")
DJANGO_GREP = (r"^[[:space:]]*\.\.[[:space:]]+(versionadded|versionchanged|deprecated|"
               r"versionremoved)::")
KNOWN_NUMPY = ("numpy/numpy", "doc/source/reference/c-api/array.rst", "BODY_AS_VERSION")
REVIEW_CAP = 60


def relpath(member_name):
    return member_name.split("/", 1)[1] if "/" in member_name else ""


def wanted(rel, size):
    if not rel or size > MAX_FILE:
        return False
    parts = rel.split("/")
    if any(p in SKIP_PARTS for p in parts):
        return False
    return rel.lower().endswith(vnl.EXTENSIONS)


def scan_tarball(fileobj):
    """Scan a .tar.gz stream; return (notes, files_read, commit)."""
    notes, files = [], 0
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
            notes.extend(vnl.scan_text(text, rel))
        commit = (tf.pax_headers or {}).get("comment", "")
    return notes, files, commit


def fetch_project(slug, log, tries=3):
    url = "https://github.com/%s/archive/HEAD.tar.gz" % slug
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mv2-version-note-census"})
            with urllib.request.urlopen(req, timeout=180) as r:
                return scan_tarball(r)
        except Exception as e:  # network or archive error: retry
            last = e
            log.append("%s try %d failed: %s" % (slug, k + 1, e))
            time.sleep(5 * (k + 1))
    raise RuntimeError("%s: %s" % (slug, last))


def is_test_path(rel):
    parts = rel.split("/")
    return (any(p in ("test", "tests") for p in parts[:-1]) or
            parts[-1].startswith("test_"))


def review_order(rows):
    """Deterministic pre-registered order for hand review."""
    return sorted(rows, key=lambda r: hashlib.sha256(
        ("%s:%s:%d" % (r["project"], r["path"], r["line"])).encode()).hexdigest())


# ---------------------------------------------------------------- Django tags

def git(gitdir, args, ok=(0,)):
    r = subprocess.run(["git", "--git-dir", gitdir] + args, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode not in ok:
        raise RuntimeError("git %s failed (%d): %s" % (" ".join(args[:3]), r.returncode,
                                                       r.stderr[-300:]))
    return r.stdout


def ensure_django(data_dir, log):
    gitdir = os.path.join(data_dir, "django.git")
    if os.path.isdir(gitdir):
        try:
            git(gitdir, ["fetch", "--prune", "--quiet", "origin",
                         "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*"])
            log.append("fetched django")
        except RuntimeError as e:
            log.append("django fetch failed, using cached copy: %s" % e)
    else:
        r = subprocess.run(["git", "clone", "--bare", "--quiet", DJANGO_URL, gitdir],
                           capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("clone failed: " + r.stderr[-300:])
        log.append("cloned django")
    return gitdir


def parse_grep_line(line, ref):
    """'<ref>:<path>:<n>:<content>' -> (path, n, content) or None."""
    prefix = ref + ":"
    if not line.startswith(prefix):
        return None
    parts = line[len(prefix):].split(":", 2)
    if len(parts) != 3 or not parts[1].isdigit():
        return None
    return parts[0], int(parts[1]), parts[2]


def note_from_content(content):
    m = vnl.RST_RE.match(content)
    if not m:
        return None
    rest = m.group("rest").strip()
    return m.group("d"), rest, (rest.split()[0] if rest else "")


def label_relation(tok, series):
    """'own', 'older', 'newer' or 'unparsed' for a label against a series (A, B)."""
    m = re.match(r"^v?(\d+)\.(\d+)(?:\.(\d+))?", tok)
    if not m:
        return "unparsed", False
    lab = (int(m.group(1)), int(m.group(2)))
    micro = m.group(3) is not None and int(m.group(3)) > 0
    if lab == series:
        return "own", micro
    return ("older" if lab < series else "newer"), micro


def django_tags_part(data_dir, log, min_series=(3, 0)):
    gitdir = ensure_django(data_dir, log)
    tags = {}
    for t in git(gitdir, ["tag", "--list"]).split():
        m = DJANGO_TAG_RE.match(t)
        if m:
            v = (int(m.group(1)), int(m.group(2)), int(m.group(3) or 0))
            if v[:2] >= min_series:
                tags[t] = v
    series = sorted({v[:2] for v in tags.values()})
    rows, listed, scanned = [], 0, 0
    for s in series:
        st = sorted([t for t, v in tags.items() if v[:2] == s], key=lambda t: tags[t])
        x0 = [t for t in st if tags[t][2] == 0]
        if not x0:
            log.append("django %d.%d: no X.Y.0 tag" % s)
            continue
        seen = None
        for t in st:
            listed += 1
            ref = "refs/tags/" + t
            try:
                out = git(gitdir, ["grep", "-n", "-I", "-E", DJANGO_GREP, ref, "--",
                                   "docs/*.txt"], ok=(0, 1))
            except RuntimeError as e:
                log.append("tag %s failed: %s" % (t, e))
                continue
            scanned += 1
            keys = {}
            for line in out.splitlines():
                p = parse_grep_line(line, ref)
                if not p:
                    continue
                n = note_from_content(p[2])
                if not n:
                    continue
                keys.setdefault((p[0], n[0], n[1]), p[1])
            if seen is None:
                seen = set(keys)  # the X.Y.0 tag
                continue
            for k in sorted(set(keys) - seen):
                tok = k[2].split()[0] if k[2] else ""
                rel, micro = label_relation(tok, s)
                rows.append({"series": "%d.%d" % s, "first_tag": t, "path": k[0],
                             "line": keys[k], "directive": k[1], "args": k[2],
                             "relation": rel, "micro_label": micro})
            seen |= set(keys)
    return rows, listed, scanned


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="/data")
    ap.add_argument("--out-dir", default="/out")
    ap.add_argument("--projects", default="", help="comma list to override (testing)")
    ap.add_argument("--skip-django-tags", action="store_true")
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(a.data_dir, exist_ok=True)
    t0 = time.time()
    log = []
    projects = [p for p in a.projects.split(",") if p] or PROJECTS
    per, finding_rows = [], []
    for slug in projects:
        try:
            notes, files, commit = fetch_project(slug, log)
        except RuntimeError as e:
            per.append({"project": slug, "ok": False, "error": str(e)[:300]})
            continue
        counts = {}
        for n in notes:
            key = n["cls"] + ("_lit" if n["in_literal"] else "")
            counts[key] = counts.get(key, 0) + 1
            if n["cls"] != "OK":
                row = dict(n)
                row["project"] = slug
                finding_rows.append(row)
        rep = sum(1 for n in vnl.findings(notes))
        per.append({"project": slug, "ok": files > 0, "commit": commit, "files": files,
                    "notes": len(notes), "reported": rep, "counts": counts})
        log.append("%s: %d files, %d notes, %d reported" % (slug, files, len(notes), rep))

    cols = ["project", "path", "line", "directive", "arg", "cls", "in_literal", "text"]
    with open(os.path.join(a.out_dir, "findings.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in finding_rows:
            w.writerow(r)
    flagged = [r for r in finding_rows if r["cls"] in ("MISSING", "BODY_AS_VERSION", "OTHER")
               and not r["in_literal"]]
    reported = [r for r in flagged if not is_test_path(r["path"])]
    in_tests = len(flagged) - len(reported)
    order = review_order(reported)
    review = order if len(order) <= REVIEW_CAP else order[:REVIEW_CAP]
    with open(os.path.join(a.out_dir, "review_set.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in review:
            w.writerow(r)

    dj_rows, dj_listed, dj_scanned = ([], 0, 0)
    if not a.skip_django_tags:
        try:
            dj_rows, dj_listed, dj_scanned = django_tags_part(a.data_dir, log)
        except RuntimeError as e:
            log.append("django tags part failed: %s" % e)
    with open(os.path.join(a.out_dir, "django_backport_notes.csv"), "w", newline="",
              encoding="utf-8") as f:
        dc = ["series", "first_tag", "path", "line", "directive", "args", "relation",
              "micro_label"]
        w = csv.DictWriter(f, fieldnames=dc)
        w.writeheader()
        for r in dj_rows:
            w.writerow(r)

    ok_projects = [p for p in per if p.get("ok")]
    projects_with_finding = sorted({r["project"] for r in reported})
    known = any(r["project"] == KNOWN_NUMPY[0] and r["path"] == KNOWN_NUMPY[1] and
                r["cls"] == KNOWN_NUMPY[2] for r in reported)
    c3_pool = [r for r in dj_rows if r["micro_label"]]
    c3_own = [r for r in c3_pool if r["relation"] == "own"]
    gate = {
        "G1_numpy_known_body_as_version": known,
        "G2_projects_read_ge_90pct": len(ok_projects) >= 0.9 * len(projects),
        "G3_django_tags_scanned_ge_90pct": (dj_scanned >= 0.9 * dj_listed) if dj_listed else False,
    }
    summary = {
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(time.time() - t0, 1),
        "tool_version": vnl.__version__,
        "gate": gate,
        "gate_held": all(gate.values()),
        "projects_read": len(ok_projects),
        "projects_listed": len(projects),
        "notes_total": sum(p.get("notes", 0) for p in per),
        "reported_outside_literal": len(reported),
        "flagged_in_test_paths": in_tests,
        "reported_by_class": {c: sum(1 for r in reported if r["cls"] == c)
                              for c in ("MISSING", "BODY_AS_VERSION", "OTHER")},
        "C1_projects_with_finding": len(projects_with_finding),
        "C1_held": len(projects_with_finding) >= 5,
        "C1_projects": projects_with_finding,
        "C2": "graded by hand on review_set.csv (GRADING.md)",
        "review_set_size": len(review),
        "C3_pool_micro_labelled": len(c3_pool),
        "C3_own": len(c3_own),
        "C3_share_own": (len(c3_own) / len(c3_pool)) if c3_pool else None,
        "C3_graded": len(c3_pool) >= 5,
        "C3_held": (len(c3_own) / len(c3_pool) >= 0.8) if len(c3_pool) >= 5 else None,
        "django_tags_listed": dj_listed,
        "django_tags_scanned": dj_scanned,
        "django_backport_notes": len(dj_rows),
        "django_relation_counts": {k: sum(1 for r in dj_rows if r["relation"] == k)
                                   for k in ("own", "older", "newer", "unparsed")},
        "per_project": per,
        "log": log,
    }
    with open(os.path.join(a.out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1, sort_keys=True)
    for r in reported[:400]:
        print("REPORT %s %s:%d %s %s %r" % (r["project"], r["path"], r["line"], r["cls"],
                                            r["directive"], r["arg"]))
    for r in dj_rows:
        if r["micro_label"] or r["relation"] == "newer":
            print("DJANGO %s %s %s:%d %s:: %s %s" % (r["series"], r["first_tag"], r["path"],
                                                    r["line"], r["directive"], r["args"],
                                                    r["relation"]))
    print("GATE", json.dumps(gate, sort_keys=True))
    print("C1 %d projects; reported %d; C3 %d/%d own" % (
        len(projects_with_finding), len(reported), len(c3_own), len(c3_pool)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
