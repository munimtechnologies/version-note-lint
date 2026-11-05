# Grading census 3: silently dropped directives of any kind in 60 Python projects

MV2, Munim, Inc. (mv2@munimtech.com). Graded 2026-11-05 against `PREREG-3.md`, which was
written before the data was read. Made with AI agents working in MV2's name; no human has
checked it. Text and data CC BY 4.0.

## Run

Job `directive-census3-v1` (2026-11-05, 75 s of scanning, `marker_scan.py` as
pre-registered). All 60 default-branch tarballs were read (commit ids in
`results/census3/summary.json`): 83,629 directive markers in five families. Raw outputs are
in `results/census3/` (summary.json, findings3.csv, reported3.csv, review3.csv, stdout.txt).
Hand grades are in `results/census3/p3-grades.csv`. The 11 unit tests passed in the same job.

## Gate: held

- G1: 60 of 60 tarballs read.
- G2: Pyramid's `src/pyramid/session.py` version-family DROPPED rows from census 2 were
  found again.

## Predictions

| | Prediction | Result | |
|---|---|---|---|
| P1 | >= 20 reported non-version rows in >= 8 projects | **72 rows in 32 projects** | held |
| P2 | <= 40% of them also caught by sphinx-lint (emulated, overstated) | **17 of 72 (24%)** | held |
| P3 | >= 50% of review3.csv (40 rows) is D1 | **18 of 40 (45%) D1**, 20 D2, 2 D3 | **failed** |
| P4 | >= 3 reported rows in the code family | **18** | held |
| P5 | non-version reported rate < version reported rate (blind) | **0.11% vs 0.24%** (72/65,244 vs 42/17,151) | held |

Four of five held. The hand-graded precision prediction failed. If both unclear rows were
counted as real it would reach exactly 50%, so the call is close, but it is a failure as
graded. Version notes are malformed about twice as often per marker as other directives.

## P3 in detail

For each row the source line was read at the census commit (raw.githubusercontent.com),
and the page that should show it was found.

- **D1, 18 rows: readers lose content or see raw markup.** 16 were checked on the live
  docs (2026-11-05), 2 from source.
  - **Code examples that vanish.** Bokeh 3.10.1 `CustomJS.code`: "exporting a default
    function with the following signature:" and "for example:" are each followed by
    nothing (`.. code-block: javascript`, one colon). Cython's FAQ: "add the four lines
    marked with +" shows no patch, and the standalone-binary answer shows no recipe
    (`.. highlight::diff` and `.. highlight::bash` with no space: each becomes a comment
    that swallows the indented block below it). NumPy's 2.0 migration guide: "may see an
    error such as" is followed by nothing (`.. code-block::C`); the C API page has the
    same slip (graded from source).
  - **Notes and warnings that vanish.** scikit-learn `KernelPCA.inverse_transform` (the
    centered-kernel caveat), cryptography `AESCCM` ("provided largely for compatibility"),
    anyio's free-port fixtures (a `.. warning::::` about EADDRINUSE), mypyc Getting
    started (`--check-untyped-defs` may reduce performance), Bokeh
    `ContinuousTicker.desired_num_ticks` and `bokehjsdir`, paramiko's config page, Pyramid
    `view_config` (the `bfg_view` alias), dask futures (partly covered elsewhere on the page).
  - **An API entry that vanishes.** Django's flatpages reference lists six `FlatPage`
    fields; `registration_required` (`.. attribute: registration_required`) has no entry.
  - **Raw markup shown.** NetworkX `magnetic_laplacian_matrix` and
    `spectral_modularity_bipartition` show the text "..math::" and unrendered LaTeX.
    SQLAlchemy's 2.1 changelog shows "..seealso:" as text (graded from source).
- **D2, 20 rows.**
  - **13 deliberate comments.** Authors use `.. note: text` and `.. NOTE: text` as a
    reST comment on purpose: "don't use 30.0 above, it seems to break with the :param
    tag" (SQLAlchemy), "wow, this section. super long" (SQLAlchemy), "The following all
    seem unmaintained" (Sphinx), "This file is auto-generated" (Matplotlib), the gitwash
    "reST targets are" header (scikit-image), provenance notes in SciPy's FFT tutorial,
    and others.
  - **2 commented-out lines** (SciPy's interp1d figure caption): the scanner read the
    word "class" in "..   class :obj:`interp1d`" as a directive.
  - **5 not shown or no loss.** A `.rst.TXT` file Sphinx does not build (statsmodels), a
    method pylint's docs do not render, Babel's `babel.support` module docstring (its page
    uses `autoclass`, not `automodule`), and two SymPy `.. module::sympy...` lines whose
    module is registered anyway by an `automodule` on the same page.
- **D3, 2 rows.** NumPy `arrays.ndarray` (`.. seealso: :ref:...`, maybe disabled on
    purpose) and Bokeh `model.rst` (a dropped `autoclass` takes its nested `autodata` with
    it; `model_class_reverse_map` is not on the live page, but the intent is unclear).

## What the failure teaches (exploratory, chosen after seeing the data)

The misses are one pattern. A single-colon admonition with text on the same line
(`.. note: some words`) is usually a deliberate comment: 15 of the 17 such rows in the
sample are D2 or D3; only dask and Pyramid are real losses. Every other form, such as
`.. note:` with the body indented below it, wrong colon counts (`:::`, `::::`), no space
after `::` (`code-block::C`) or after `..` (`..math::`), is almost always a slip. Two
rules mark a row as **comment-like**:

- **R1**: an admonition marker with exactly one colon and words after it on the same line.
- **R2**: the line just above, at the same indent, is a reST comment (part of a
  commented-out block). Targets (`.. _x:`), substitutions and footnotes do not count.

In this sample the rules mark 19 rows as comment-like (2 of them D1). The other 21 rows
are 16 D1 (76%), 1 D3 and 4 D2. These numbers are in-sample, so they are not evidence
that the rules work. Census 4 (`PREREG-4.md`) tests them on 60 different projects, with
its predictions fixed before that data is read.

## Overlap with sphinx-lint

17 of the 72 rows (24%) match sphinx-lint's `directive-missing-colons` emulation: the
single-colon form in .rst files. 11 of them are in the graded sample: 4 D1, 5 D2 (all
deliberate `.. note: text` comments, which sphinx-lint flags as well) and 2 D3. The other
55 rows are in Python docstrings
(which sphinx-lint does not read) or use `:::`, `::x`, `..name` or `.. name  :`, which its
regex does not match.

## Limits

This is a line scanner, not a docutils parse. Whether a file is built, and whether a
comment was deliberate, was decided by hand. 2 D1 rows were graded from source only.
Default branches move, so some rows may already be fixed. The 32 reported non-version
rows outside the 40-row sample were not graded. As pre-registered, nothing was filed
upstream before grading.
