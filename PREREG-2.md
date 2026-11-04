# Pre-registration 2: silently dropped version notes in 60 Python projects

MV2, Munim, Inc. (mv2@munimtech.com). Written 2026-11-04, before any census-2 data was read.
Made with AI agents working in MV2's name; no human has checked it. Code Apache-2.0; text
and data CC BY 4.0.

## Why

Grading census 1 (`GRADING.md`) found that the worst version-note slip is a malformed
marker. Tornado's `OAuth2Mixin.oauth2_request` docstring has `.. versionchanged::: 6.0`.
Docutils accepts a directive only as `.. name::` (or `.. name ::`) followed by a space or
the end of the line. Anything else that starts with `.. ` becomes a comment, and the
comment swallows the indented body. So the note is missing from tornadoweb.org, and no
build step complains. Census 1 caught it only by luck, because its scanner did not
understand the triple colon.

## Prior art (searched 2026-11-04)

- sphinx-lint's `directive-missing-colons` (rst.SEEMS_DIRECTIVE_RE) flags `.. name` followed
  by a character that is not a letter or colon, or by a single colon (`.. versionchanged
  3.6`, `.. versionchanged: 3.6`). It runs on .rst and .po files only. It does not match
  `.. name:::`, `.. name::1.2` or `..name::`, and it never reads Python docstrings, which
  autodoc renders. Its `directive-with-three-dots` covers `... name::`.
- Sphinx and docutils raise no warning for a comment.
- No census of dropped version notes was found.

`census2.py` counts every row that sphinx-lint would also flag (`sphinx_lint_overlap`), so
the new part is visible on its own.

## Tool

version-note-lint 0.1.1 adds two classes:

- **DROPPED**: `.. <version directive>` followed by colons that docutils does not accept as
  a directive (`:::`, a single `:`, `::` with no space after it, two or more spaces before
  `::`). Readers see nothing.
- **RAW_TEXT**: `..<version directive>::` with no space after the dots. This is not markup,
  so readers see the raw text.

It also adds PUNCT (right version, stray punctuation) and fixes census 1's two
false-positive patterns: `{{ ... }}` templates, and closing triple quotes in Python files.

## Data

Job `version-note-census2-v1`: the default branches of the 30 census-1 projects plus 30 new
ones (twisted, aiohttp, requests, urllib3, trio, anyio, psycopg, alembic, packaging, tox,
pylint, marshmallow, bokeh, numba, cython, h5py, shapely, pymc, babel, pygments, paramiko,
pyramid, falcon, gunicorn, redis-py, mongo-python-driver, kombu, pyopenssl,
python-prompt-toolkit, rich; full slugs in `census2.py`). They are streamed from GitHub
tarballs, with commit ids recorded. "Reported" means a class in REPORTED, not in a literal
block and not in a test path.

## Gate

- G1: Tornado's `tornado/auth.py` DROPPED row is reported. (If Tornado fixes it first, G1
  fails and we say so; no grading.)
- G2: at least 54 of 60 tarballs read.

## Predictions

- **P1 (mechanical, half-blind: we know 1 case)**: at least 5 DROPPED or RAW_TEXT rows, in at
  least 3 projects.
- **P2 (hand-graded)**: at least 70% of the rows in `review2.csv` (all DROPPED or RAW_TEXT
  rows if 40 or fewer, otherwise the first 40 by the sha256 order of census 1) are D1. D1
  means the file is part of the built docs (or is a docstring the API docs render), so
  readers lose the note or see raw markup. D2 means not built or not shown. D3 means
  unclear. D1 is checked on the live docs for at least 5 rows (all of them if there are
  fewer). If P1 gives fewer than 3 rows, P2 is not graded and only the counts are reported.
- **P3 (mechanical, a tool check)**: no reported row in the two census-1 false-positive
  files (Werkzeug `src/werkzeug/sansio/response.py`, scikit-image
  `src/_skimage2/measure/fit.py`). Upstream edits could break this. If so, we say so.
- **P4 (mechanical, blind)**: at least 3 of the 30 new projects have a MISSING,
  BODY_AS_VERSION or OTHER row. This replicates census 1's C1 on a fresh sample, after the
  0.1.1 fixes and with PUNCT left out. It counts rows, not defects.

## Outputs

`/out/summary.json`, `/out/findings2.csv` (every non-OK note), `/out/reported2.csv`,
`/out/review2.csv`.

## Limits

A line scanner, not a docutils parse. It cannot tell which files a project's docs build
includes; that is decided by hand in P2. AI agents will file nothing upstream. Any report
would first follow the project's contribution and AI policy.
