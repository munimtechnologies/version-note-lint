# Grading: version-note census 1 (PREREG.md)

MV2, Munim, Inc. (mv2@munimtech.com). Graded 2026-11-04. Made with AI agents working in
MV2's name; no human has checked it. Text and data CC BY 4.0, code Apache-2.0.

**Verdict: gate held; C1 held; C2 FAILED; C3 FAILED.**

## Run

Job `version-note-census-v1` (python:3.12, Linux), 2026-11-03 14:54-15:01 UTC, tool 0.1.0.
Unit tests passed in the job. 30 of 30 project tarballs read (commit ids in
`results/census-v1-summary.json`), 14,997 version notes. 175 of 175 Django final tags
from 3.0 on scanned.

## Gate: held

- G1: NumPy's `doc/source/reference/c-api/array.rst` BODY_AS_VERSION note was reported.
- G2: 30 of 30 tarballs read. G3: 175 of 175 Django tags scanned.

## C1 (mechanical, half-blind): HELD

9 of 30 projects had at least one reported row outside literal blocks and test paths
(threshold 5): celery, numpy, werkzeug, pytest, scikit-image, scipy, sqlalchemy, sympy,
tornado. 33 rows in all (1 BODY_AS_VERSION, 32 OTHER, 0 MISSING). CPython, Django, pandas,
matplotlib, scikit-learn, Sphinx, pip and 14 others had none.

## C2 (hand-graded): FAILED, 13 of 33 (39%) real defects; threshold 60%

All 33 rows were read in the source at the recorded commit (`results/c2-grades.csv`). Every
D1 row was then checked on the project's live rendered docs. Each row also got a tier:

| Tier | What readers see | Rows | Grade |
|---|---|---|---|
| A | no version at all, or the whole note is missing | 3 | D1 |
| B | a word such as "NumPy" or "Kombu" where the version goes; the number follows in the text | 10 | D1 |
| C | the right version with stray punctuation ("1.14.", "2.0::", "1.4.48,") or two versions ("2.0/2.3.4") | 13 | D2 |
| FP | not what readers see: a template filled in at import, or a docstring's closing quotes | 7 | D2 |

No row was D3. Under a stricter reading of D1 (tier A only) the share is 3 of 33 (9%), so
C2 fails under either definition.

The three tier-A rows, all live on 2026-11-04:

- **Tornado**, `tornado/auth.py:466`, `OAuth2Mixin.oauth2_request`: the docstring has
  `.. versionchanged::: 6.0` (three colons). Docutils only accepts `::` followed by a space
  or the end of the line, so it treats the line and its indented body as a comment.
  tornadoweb.org/en/stable/auth.html shows "Added in version 4.3" for this method and nothing
  else, while sibling methods (`facebook_request`, `twitter_request`) show "Changed in
  version 6.0: The callback argument was removed." Tool 0.1.0 labelled this row OTHER with
  argument ":", which was the right row for the wrong reason.
- **SQLAlchemy**, `lib/sqlalchemy/dialects/mysql/enumerated.py:55`: docs.sqlalchemy.org
  (2.0, MySQL dialect, `ENUM.__init__`) shows "Changed in version The: MySQL ENUM type as well
  as the base Enum type now validates all Python data values." No version.
- **SQLAlchemy**, `lib/sqlalchemy/engine/interfaces.py:704`: "Changed in version The:
  Dialect.dbapi attribute is exclusively used as the per-Dialect-instance reference ...".
  No version.

Tier B is mostly NumPy, which writes `.. versionadded:: NumPy 1.25` in 8 places. The live
docs show "Added in version NumPy: 1.25" (numpy.dtypes, numpy.exceptions, the C API types
page, arrays.classes, the f2py build page), plus the known `versionchanged::` case in
array.rst. Celery's monitoring guide shows "Added in version Kombu: 5.6.0", where the
version refers to Kombu, not Celery.

Tool false positives (FP), all fixed in 0.1.1 with tests:

- scikit-image `src/_skimage2/measure/fit.py` (6 rows): `.. deprecated:: {{ start_version }}`
  is a placeholder that `_deprecate_model_params` replaces with `str.replace(...,
  _PARAMS_DEP_START)` ("0.26"). `{{ ... }}` and `{% ... %}` now count as placeholders.
- Werkzeug `src/werkzeug/sansio/response.py:666`: `.. versionadded:: 0.7""",` ends a
  docstring passed as `doc=`. In Python files, closing triple quotes are now cut off the
  token.

## C3 (mechanical): FAILED, 24 of 61 (39%) micro-labelled backport notes are "own"; threshold 80%

The prediction assumed each Django branch labels a backported change with its own release.
It does not. Of 70 notes that first appeared after a series' X.Y.0 (Django 3.0 to 6.0), 32 name
their own series, 37 an older series and 1 a newer one. The "older" rows are the same note
copied onto a newer branch with the oldest branch's release. For example, the 6.0.8 docs
carry five GIS notes labelled `5.2.17`, and 6.0.6 carries `versionchanged:: 5.2.15` in
request-response.txt and settings.txt. In practice Django writes the backported note once,
labelled with the oldest supported series that got the change, and copies it unchanged.

**The one exception** is the `newer` row: `docs/topics/cache.txt` on stable/5.2.x, first at
5.2.15, says `versionchanged:: 6.0.6`. It is live: docs.djangoproject.com/en/5.2/topics/cache/
shows "Changed in Django 6.0.6:" ("Previously, UpdateCacheMiddleware did not vary on
Authorization ..."), on the docs of the 5.2 LTS series, whose users got the change in
5.2.15. Two other notes from the same 5.2.15 / 6.0.6 release follow the pattern and say
5.2.15 on both branches. By the pattern seen in the other 37 copied notes, this one would
say 5.2.15. Django's own guide does not spell out a rule for backports, so this describes
practice and is not a rule violation. Nothing has been filed.

## What we learned

- Version notes that build without a warning but render wrong are rare in big Python
  projects: 33 flagged rows in 14,997 notes, and 13 real ones in 4 projects.
- The worst kind is not a wrong word but a **malformed marker**. Docutils drops the whole
  note without a word, and sphinx-lint's `directive-missing-colons` check does not cover
  triple colons, a missing space after `::`, or Python docstrings. Version 0.1.1 adds
  DROPPED and RAW_TEXT classes for these. Census 2 (`PREREG-2.md`) counts them in 60
  projects.
- Most "OTHER" rows were cosmetic. Version 0.1.1 splits them into PUNCT (right number,
  stray punctuation; `--ignore PUNCT` hides them) and treats `2.0/2.3.4` as a version.

## Files

`results/census-v1-summary.json`, `results/findings.csv`, `results/review_set.csv`,
`results/django_backport_notes.csv` (job outputs, unchanged), `results/c2-grades.csv` (hand
grades). Nothing was filed with any project. Each project's contribution and AI policy
comes first. NumPy, for example, takes reports written and submitted by humans only.
