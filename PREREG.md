# Pre-registration: malformed and mislabelled version notes in 30 Python projects

MV2, Munim, Inc. (mv2@munimtech.com). Written 2026-11-03, before any census data was read.
Made with AI agents working in MV2's name; no human has checked it. Code Apache-2.0; text
and data CC BY 4.0.

## Why

Sphinx's `versionadded`, `versionchanged`, `deprecated` and `versionremoved` directives take
the version as their first argument and print it after "Added in version" / "Changed in
version". Two earlier MV2 studies (munimtechnologies/branch-version-notes-audit,
munimtechnologies/backport-version-notes) read these notes for *which* version they name.
Grading the second one turned up a different kind of slip, about *whether* they name one at
all. In NumPy's `doc/source/reference/c-api/array.rst` (main, read 2026-11-03), a
`.. versionchanged::` has no argument, and its text starts on the next line. Docutils then
takes the first word of the text as the version, so numpy.org/doc/stable shows "Changed in
version NumPy: 2.1 changed the headers to avoid sharing the table outside of a single shared
object/dll". Nothing in the build flags it.

## Prior art (searched 2026-11-03)

- sphinx-lint (sphinx-contrib, from CPython's rstlint.py): its 29 checkers (checkers.py on
  main) cover directive syntax (three dots, missing `::`), roles, backticks and whitespace.
  None checks the arguments of version directives.
- Sphinx itself only errors when no argument at all can be found. It accepts any first word.
- Django ticket #20104 (2013) fixed Django's own version directive mishandling its
  arguments. The `deprecated` library's issue #40 is about generating notes without a version.
- No tool or census checking version-note arguments across projects was found (web, GitHub,
  PyPI searches for versionadded lint / pre-commit / checker).

So `version-note-lint` (this repository) is, as far as we can find, the first checker for
this, and this census is the first count of these slips across projects.

## Tool

`version_note_lint.py` (v0.1.0) classifies every version note it finds in .rst, .txt, .inc,
.py, .pyi, .pyx, .pxd and MyST .md files:

- **OK**: the first argument word is a version number (`3.14`, `v2.1`, `2.0.0rc1`, `21`).
- **PLACEHOLDER**: `next`, `A.B`, `X.Y`, `3.x`, `|version|`, `NEXT_VERSION`, `unreleased`
  and similar. Counted, not reported.
- **MISSING**: no argument, and a blank line follows (Sphinx errors and drops the note).
- **BODY_AS_VERSION**: no argument on the directive line, and the text starts on the next line
  with a word that is not a version. That word renders as the version.
- **OTHER**: the first argument word is not a version (`Python 3.4`, `1.2,`, `NumPy`).
- **FUTURE** (only with `--branch-version X.Y`): a version later than the branch.

Notes inside rst literal blocks (`::` paragraphs, `code-block` and similar directives) and
inside Markdown code fences are marked `in_literal` and not reported. Unit tests:
`test_version_note_lint.py`, `test_census.py`.

## Data

Job `version-note-census-v1` (Linux, python:3.12):

- **Part A**: the default branch of 30 projects, read from `github.com/<org>/<repo>/archive/
  HEAD.tar.gz` (commit id from the tarball header, recorded): python/cpython, django/django,
  numpy/numpy, scipy/scipy, pandas-dev/pandas, matplotlib/matplotlib,
  scikit-learn/scikit-learn, sphinx-doc/sphinx, sqlalchemy/sqlalchemy, pytest-dev/pytest,
  pypa/pip, pypa/setuptools, python-attrs/attrs, pallets/flask, pallets/werkzeug,
  pallets/jinja, pallets/click, celery/celery, astropy/astropy, networkx/networkx,
  pydata/xarray, sympy/sympy, ipython/ipython, python-pillow/Pillow,
  scikit-image/scikit-image, statsmodels/statsmodels, dask/dask, tornadoweb/tornado,
  pyca/cryptography, python/mypy. Files over 3 MB are skipped.
- **Part B**: every final Django release tag from 3.0 on (bare clone). For each series, a
  note (path, directive, argument) that is absent at X.Y.0 and first appears at a later tag
  is a *backport-added* note. Its label is *own* (same A.B as the series), *older* or
  *newer*, and *micro* if it names a third number above 0 (`5.2.15`).

"Reported rows" below means MISSING, BODY_AS_VERSION or OTHER, not in a literal block, and
not in a test path (a directory named `test` or `tests`, or a file named `test_*`). Test-path
rows are counted separately.

## Gate (all must hold before anything is graded)

- G1: Part A reports the known NumPy case (`doc/source/reference/c-api/array.rst`,
  BODY_AS_VERSION). If NumPy fixes it before the job runs, G1 fails and we say so; no
  grading.
- G2: at least 27 of the 30 tarballs are read.
- G3: at least 90% of Django tags from 3.0 on are scanned.

## Predictions

- **C1 (mechanical, half-blind)**: at least 5 of the 30 projects have one or more reported
  rows. (We know NumPy has one. We have not looked at any other project.)
- **C2 (hand-graded)**: at least 60% of the reviewed rows are real defects. Review set: all
  reported rows if there are 60 or fewer, otherwise the first 60 in the pre-set order
  (sha256 of `project:path:line`, `review_set.csv`). Labels, read in the source at the
  recorded commit:
  - D1 real defect: the file is part of the project's built docs (or a docstring that the
    API docs render), and readers see a wrong or missing version.
  - D2 not a defect for readers: not built into docs, example text, vendored code, or a
    project-specific directive that takes other arguments.
  - D3 unclear.
  C2 holds if D1 / (D1 + D2 + D3) >= 0.6.
- **C3 (mechanical)**: among backport-added Django notes with a micro label, at least 80%
  are *own*. This asks whether Django's `versionchanged:: 6.0.6` on stable/5.2.x (the
  CVE-2026-35193 backport; 5.2's own fix is 5.2.15) is a one-off or how Django labels
  backports. If the pool has fewer than 5 notes, C3 is not graded and is reported as counts.

## Outputs

`/out/summary.json` (gate, C1, C3, per-project counts, commits), `/out/findings.csv` (every
non-OK note, with `in_literal`), `/out/review_set.csv`, `/out/django_backport_notes.csv`.

## Limits

- A line scanner, not a docutils parse. Literal-block detection is by indentation.
  Directives in .py comments are ignored; docstrings are scanned as text.
- "Is the file built into the docs?" is decided by hand in C2, not by the tool.
- Projects with custom version directives (Django's renders "Changed in Django X.Y") follow
  Sphinx's argument rule, but their output wording differs.
- AI agents will file nothing upstream. Any report would first follow the project's
  contribution and AI policy (NumPy's, for example, needs a human to write and submit it).
