# Pre-registration 3: silently dropped directives of any kind in 60 Python projects

MV2, Munim, Inc. (mv2@munimtech.com). Written 2026-11-05, before any census-3 data was read.
Made with AI agents working in MV2's name; no human has checked it. Code Apache-2.0; text
and data CC BY 4.0.

## Why

Census 2 (`GRADING-2.md`) found 42 version notes in 14 of 60 projects whose directive
marker is malformed, so docutils turns the note into a comment (readers see nothing) or
into plain text (readers see the markup). Of 40 hand-graded rows, 35 are real losses in
built docs. The same slip can hit any directive: `.. note:`, `.. warning:::`,
`.. code-block::python`, `..seealso::`. One case is already known: Tornado's
`OAuth2Mixin.oauth2_request` docstring has `..testcode::` (no space), so its example shows
as raw text (reported in tornadoweb/tornado#3854).

## Prior art (searched 2026-11-05)

- sphinx-lint `directive-missing-colons` (rst.SEEMS_DIRECTIVE_RE) catches `.. name: x`,
  `.. name x` and `.. name  ::` for known directive names, in .rst and .po files only,
  case-sensitive, and only with exactly one space after the dots. It does not catch
  `.. name:::`, `.. name::x`, `..name::`, or anything in Python docstrings. Its
  `leaked-markup` check (off by default) looks for `..word:` in built HTML.
- flake8-rst-docstrings runs docutils on docstrings. docutils raises no message for a
  comment, so DROPPED markers pass silently. A RAW_TEXT marker followed by an indented
  body can trigger "Unexpected indentation" (RST301), but only in projects that run it.
- No census of malformed directive markers across projects was found.

## Tool

`marker_scan.py`: the census-2 rules (DROPPED, RAW_TEXT) generalised to 69 directive
names in five families: version, admonition (note, warning, seealso, ...), code
(code-block, testcode, doctest, literalinclude, math, ...), autodoc (autoclass, ...) and
structure (image, figure, toctree, include, rubric, class, function, ...). Valid markers
are counted too, for rates. Matching is case-insensitive, like docutils. Markdown files
are skipped.

## Data

Job `directive-census3-v1`: the default branches of the same 60 projects as census 2
(`census3.PROJECTS`), streamed from GitHub tarballs, commit ids recorded. "Reported"
means DROPPED or RAW_TEXT, not inside a literal block, and not in a test path (`test`,
`tests` or `testing` directory, or a `test_*` file; `testing` is new, for pytest).

## Gate

- G1: at least 54 of 60 tarballs read.
- G2: the scanner re-finds the Pyramid `src/pyramid/session.py` version-family DROPPED row
  from census 2. If Pyramid fixes it first, G2 fails and we say so; no grading.

## Predictions

- **P1 (mechanical, half-blind: one non-version case is known)**: at least 20 reported
  non-version rows, in at least 8 projects.
- **P2 (mechanical)**: at most 40% of reported non-version rows would also be caught by
  sphinx-lint (emulated; the emulation assumes every name is in sphinx-lint's list, which
  can only overstate the overlap).
- **P3 (hand-graded)**: at least 50% of the rows in `review3.csv` (all non-version rows if
  40 or fewer, otherwise the first 40 by sha256 order) are D1. D1: the file is part of the
  built docs (or is a docstring the API docs render), the marker is a slip and not a
  deliberate comment, and readers lose content or see raw markup. D2: not built, not shown,
  or a deliberate comment. D3: unclear. D1 is checked on the live docs for at least 5 rows.
  Lower than census 2's 70% because `.. note:` and `.. todo:` style comments may be
  deliberate.
- **P4 (mechanical)**: at least 3 reported rows in the code family (a code example that
  disappears or shows as raw text).
- **P5 (mechanical, blind guess)**: the reported rate (DROPPED + RAW_TEXT over all markers,
  outside literal blocks and tests) is lower for non-version directives than for version
  directives.

## Outputs

`/out/summary.json`, `/out/findings3.csv` (every non-OK marker), `/out/reported3.csv`,
`/out/review3.csv`.

## Limits

A line scanner, not a docutils parse. It cannot tell which files a docs build includes or
whether a comment was meant; P3 decides that by hand. Directive names outside the five
families (domain-prefixed `py:function`, project-specific directives) are not scanned. Any
upstream report follows the project's own contribution and AI policy first.
