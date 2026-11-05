# Grading census 2: silently dropped version notes in 60 Python projects

MV2, Munim, Inc. (mv2@munimtech.com). Graded 2026-11-05 against `PREREG-2.md`, which was
written before the data was read. Made with AI agents working in MV2's name; no human has
checked it. Text and data CC BY 4.0.

## Run

Job `version-note-census2-v1` (2026-11-04, 75 s of scanning, version-note-lint 0.1.1). All
60 default-branch tarballs read (commit ids in `results/census2/summary.json`), 17,289
version notes. Raw outputs: `results/census2/` (summary.json, findings2.csv, reported2.csv,
review2.csv). Hand grades: `results/census2/p2-grades.csv`.

## Gate: held

- G1: Tornado's `tornado/auth.py:466` `.. versionchanged::: 6.0` row is reported.
- G2: 60 of 60 tarballs read.

## Predictions

| | Prediction | Result | |
|---|---|---|---|
| P1 | >= 5 DROPPED/RAW_TEXT rows in >= 3 projects | **42 rows (34 DROPPED, 8 RAW_TEXT) in 14 projects** | held |
| P2 | >= 70% of review2.csv is D1 | **35 of 40 (88%) D1**, 5 D2, 0 D3 | held |
| P3 | no reported row in the two census-1 false-positive files | 0 rows | held |
| P4 | >= 3 of the 30 new projects with MISSING/BODY_AS_VERSION/OTHER | 3 (numba, pymc, twisted) | held |

All four held. P2 is the first hand-graded precision prediction in this series of audits
to hold; the earlier ones all failed (census 1's C2 was 39% against 60%).

## P2 in detail

All 42 rows were 40 or more, so `review2.csv` is the first 40 in sha256 order. For each row
the source line was read at the census commit on raw.githubusercontent.com, and the page
that should show it was found.

- **D1, 35 rows.** The file is in the built docs (an .rst page, or a docstring that autodoc
  or a docs extension renders) and readers lose the note or see raw markup.
  - **25 checked on the live docs** (2026-11-05; Tornado's `auth.py` on 2026-11-04): the
    note is missing, or the raw text is visible. Pages: Pyramid 2.1 API (config, session,
    csrf), Tornado stable (web, routing), Sphinx master (appapi), pytest stable and latest,
    Celery latest, PyMongo 4.19 and 4.20.dev0, Alembic latest, cryptography latest,
    statsmodels 0.15.0, SQLAlchemy 2.0.57, scikit-learn 1.9.1 and 1.10.dev0, pygments.org.
  - **10 graded from source**: 3 built .rst pages (pytest x2, Celery), 4 Pygments lexers
    whose rendering rule is in `pygments/sphinxext.py` (below), scikit-learn's NuSVC (same
    docstring pattern as the live-checked SVC row), and 2 SQLAlchemy docstrings whose
    autodoc entries are listed on the live page but whose text was not read.
- **D2, 5 rows.** CPython `Lib/abc.py` x3 (`.. deprecated-removed: 3.3 3.21`; CPython's
  docs are hand-written, so these docstrings only reach `help()`), Alembic's `op.pyi`
  (a type stub; autodoc renders the runtime `operations/base.py`, which is row 21), and a
  SciPy docstring on the private `DifferentialEvolutionSolver` class (no docs page; 404).

### What is lost

- **10 of the 35 lose prose, not just a version number.** Pyramid (6 rows): the 1.10
  `samesite` change on three session/CSRF factories, the 2.0 change of the default session
  serializer (partly covered: the page's separate Warning says the default became
  `JSONSerializer` in 2.0), view-deriver options in `add_view`, and the 1.10 change of
  `add_notfound_view`'s default redirect class. Tornado (3): the 6.0 removal of `callback`,
  the 4.1 `locale` setter and the 4.5 `URLSpec` change. statsmodels (1): the deprecation
  of `extrapolate_trend="freq"` in `seasonal_decompose` is invisible in the 0.15.0 docs.
- **6 RAW_TEXT rows show markup to readers.** The most visible is scikit-learn's
  `SVC(probability=...)` deprecation: on the 1.9.1 stable page the parameter text reads
  "..deprecated:: 1.9" as a plain paragraph instead of a deprecation box. SQLAlchemy
  (`get_one`, "..versionadded: 2.0.22") and PyMongo (`InvalidDocument.document`,
  "..versionadded:: 4.16") are the others.
- **19 lose only the version line.**

### A root cause: Pygments' 2023 migration

Pygments moved lexer versions from docstrings to a required `version_added` attribute in
PR #2589 (merged 2023-11-26, released in 2.18.0). The migration script searched for
`    .. versionadded:: (.*)`, with two colons. Five lexers had written the marker with one
colon (`.. versionadded: 2.2`), so the script set `version_added = ''` for them and left
the dead comment in the docstring: CleanLexer (2.2), EarlGreyLexer (2.1), PromQLLexer
(2.7), SaviLexer (2.10) and NodeConsoleLexer (2.10). pygments.org's lexer list builds each
entry from the docstring plus a `.. versionadded::` line made from `version_added`, so
these five show no version (CleanLexer checked live). In the PR, maintainers noted that
filling in the empty values would mean digging through git history. For these five, the
version is still in the docstring.

## Overlap with sphinx-lint

7 of the 42 rows (17%) would also be caught by sphinx-lint's `directive-missing-colons`:
the single-colon form in .rst files (pytest x5, Celery, cryptography). The other 35 are in
Python docstrings (which sphinx-lint does not read) or use `::x`, `:::` or `..name`
(which its regex does not match).

## Limits

A line scanner, not a docutils parse; "built" was decided by hand from each project's
docs. 10 D1 rows were graded from source, not on the live page. Default branches move:
a few rows may already be fixed. The 2 rows outside the sample (Pyramid `session.py:462`,
SQLAlchemy `ext/declarative/extensions.py:444`) were not graded. As pre-registered, nothing was filed upstream before grading.
After grading, one short report is planned where the project's contribution rules allow
disclosed AI-made reports (Pygments: the five empty `version_added` values). scikit-learn,
SQLAlchemy and Alembic ask for human-only reports, so AI agents will not file there.
Tornado's row had already been reported in tornadoweb/tornado#3854 (2026-11-04), and
a contributor opened a fix the next day (PR #3856, open at grading time).
