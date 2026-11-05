# Pre-registration 4: do the comment-like rules hold up on 60 new projects?

MV2, Munim, Inc. (mv2@munimtech.com). Written 2026-11-05, before any census-4 data was read.
Made with AI agents working in MV2's name; no human has checked it. Code Apache-2.0; text
and data CC BY 4.0.

## Why

Census 3 (`GRADING-3.md`) scanned 83,629 directive markers in 60 Python projects. Its
hand-graded precision prediction failed: 18 of 40 malformed non-version markers (45%) were
real losses in built docs, against a predicted 50% or more. Most false alarms were
deliberate comments written as `.. note: some words`. After seeing that data, two rules
were added to `marker_scan.py` to mark a DROPPED marker as **comment-like**:

- **R1**: an admonition (note, warning, seealso, ...) with exactly one colon and words
  after it on the same line.
- **R2**: the line just above, at the same indent, is a reST comment (a commented-out
  block); targets, substitutions, footnotes, citations and directive markers do not count.

On the census-3 sample the rules mark 19 of 40 rows. The remaining 21 rows are 76% D1.
That number is in-sample and was used to write the rules, so it is not evidence. Census 4
tests the rules on data they were not built from.

## Data

Job `directive-census4-v1`: the default branches of 60 Python projects with Sphinx/reST
docs that were NOT in censuses 2 and 3 (`census4.PROJECTS`; a test checks there is no
overlap), streamed from GitHub tarballs, commit ids recorded. The scanner is
`marker_scan.py` as published with version-note-lint 0.2.0. "Reported" means DROPPED or
RAW_TEXT, not inside a literal block, and not in a test path. "Default" rows are reported
non-version rows that are not comment-like (what `version-note-lint --all-directives`
prints).

## Gate

- G1: at least 54 of 60 tarballs read.
- G2: at least 20,000 markers scanned (census 3 had 83,629).

## Predictions

- **P1 (mechanical)**: at least 15 default rows, in at least 8 projects.
- **P2 (hand-graded, the main test)**: at least 60% of `review4.csv` is D1. `review4.csv`
  holds all default rows if there are 40 or fewer, otherwise the first 40 in sha256 order.
  The D1/D2/D3 definitions are census 3's. D1: the file is part of the built docs (or is
  a docstring the API docs render), the marker is a slip and not a deliberate comment, and
  readers lose content or see raw markup. D2: not built, not shown, no reader loss, or a
  deliberate comment. D3: unclear. D1 is checked on the live docs for at least 5 rows.
- **P3 (hand-graded)**: at most 30% of `review4-comment.csv` is D1. That file holds all
  comment-like rows if there are 20 or fewer, otherwise the first 20 in sha256 order. If
  there are fewer than 5 comment-like rows, P3 is not graded and we say so.
- **P4 (mechanical)**: comment-like rows are 20% to 60% of all reported non-version rows
  (census 3: about 26 of 72, 36%, counted by hand from its report lines; the rules were
  not run on census 3).
- **P5 (mechanical)**: the reported rate of version notes is higher than the default rate
  of the other directives (census 3: 0.24% vs about 0.07%).

## Outputs

`/out/summary.json`, `/out/findings4.csv` (every non-OK marker), `/out/reported4.csv`,
`/out/review4.csv`, `/out/review4-comment.csv`.

## Limits

This is a line scanner, not a docutils parse. It cannot tell which files a docs build
includes, so P2 and P3 decide that by hand. Some of the new projects may write few reST
docs; G2 guards against a census too small to say anything. Nothing is filed upstream
before grading; any later report follows the project's contribution and AI policy first.
