# version-note-lint

A small checker for Sphinx/reST directives that silently vanish. It started with version
notes (`versionadded`, `versionchanged`, `deprecated`, `versionremoved`, the Sphinx 9
`version-*` spellings, and CPython's `deprecated-removed` / `soft-deprecated`): it checks
their version argument and the directive marker itself. Since 0.2.0, `--all-directives`
also checks the markers of other common directives (note, warning, seealso, code-block,
math, highlight, autoclass, attribute, image, ...). By MV2 of Munim, Inc.
(mv2@munimtech.com). Made with AI agents working in MV2's name. Apache-2.0.

Sphinx prints whatever word comes first after the directive as the version, and docutils
quietly turns a malformed directive into a comment, together with its indented body. So
these slips build without a warning but show readers the wrong thing, or nothing:

```rst
.. versionchanged::
    NumPy 2.1 changed the headers ...
```

renders as "Changed in version NumPy: 2.1 changed the headers ..." (live in NumPy's C API
docs as of 2026-11-03), and

```rst
.. versionchanged::: 6.0

   The ``callback`` argument was removed.
```

renders as nothing at all (live in Tornado's `OAuth2Mixin.oauth2_request` docs as of
2026-11-04). The same goes for other directives: `.. code-block: javascript` (one colon)
hides the code example, `.. highlight::diff` (no space) hides the indented patch below it,
and `..math::` shows raw LaTeX.

What it reports:

| Class | Example | What readers see |
|---|---|---|
| DROPPED | `.. versionchanged::: 6.0`, `.. versionadded: 1.2`, `.. versionadded::1.2` | nothing; docutils reads the note as a comment |
| RAW_TEXT | `..versionadded:: 1.2` | the raw text |
| MISSING | `.. versionadded::` then a blank line | nothing; Sphinx errors and drops the note |
| BODY_AS_VERSION | `.. versionchanged::` with the text on the next line | the first word of the text as the version |
| OTHER | `.. versionadded:: NumPy 1.25`, `.. versionchanged:: The ...` | "Added in version NumPy: 1.25", "Changed in version The: ..." |
| PUNCT | `.. deprecated:: 1.14.`, `.. versionchanged:: 2.0::` | the right version with stray punctuation (minor) |
| FUTURE (`--branch-version X.Y`) | `.. versionchanged:: 6.0.6` on a 5.2 branch | a release the branch's docs are not about |
| DROPPED / RAW_TEXT (`--all-directives`) | `.. note:` + body, `.. warning:::: x`, `.. code-block::C`, `..math::` | nothing, or the raw markup |

Placeholders (`next`, `A.B`, `|version|`, `{version}`, `{{ start_version }}`, ...), two
versions joined by a slash (`2.0/2.3.4`), and notes inside literal blocks or code fences are
not reported. In Python files, a docstring's closing quotes on the same line are ignored.

With `--all-directives`, markers that look like deliberate comments are skipped unless you
add `--include-comment-like`. Authors often write `.. note: don't use 30.0 above` or
`.. NOTE: this file is auto-generated` as a reST comment on purpose. The rules (from the
census-3 grading, `GRADING-3.md`): R1, an admonition with one colon and words on the same
line; R2, a line inside a commented-out block. The version directives are always reported,
because one-colon version notes are slips. Census 4 tested these rules on 60 other
projects: 31 of 40 sampled default reports were real losses, and 18 of 20 skipped
comment-like rows were deliberate comments (`GRADING-4.md`).

sphinx-lint's `directive-missing-colons` already catches `.. versionadded: 1.2` and
`.. note: x` in .rst files. This tool also covers triple and quadruple colons, `::` with no
space after it, `..name::`, and Python docstrings. In census 2, 35 of the 42 dropped or
raw version notes were of these kinds; in census 3, 55 of the 72 other directives were; in
census 4, 42 of the 49 default reports were, mostly docstrings.

## Use

```
pip install git+https://github.com/munimtechnologies/version-note-lint
version-note-lint docs/ src/
version-note-lint --all-directives docs/ src/     # every common directive
version-note-lint --ignore PUNCT docs/ src/       # only what changes the meaning
version-note-lint --branch-version 5.2 docs/      # on a maintenance branch
version-note-lint --json docs/
```

Exit status is 1 when anything is reported. As a pre-commit hook:

```yaml
- repo: https://github.com/munimtechnologies/version-note-lint
  rev: v0.2.0
  hooks:
    - id: version-note-lint
      args: [--ignore, PUNCT]
    # or, for every common directive:
    - id: directive-lint
```

No dependencies; two files (`version_note_lint.py`, `marker_scan.py`), Python 3.9+.

## Census results

- **Census 1** (`PREREG.md`, `GRADING.md`): 30 projects, 14,997 notes. Gate and C1 held;
  C2 and C3 failed. Of 33 flagged rows, 13 (39%) are real reader-visible defects in 4
  projects (NumPy, SQLAlchemy, Celery, Tornado). Another 13 are cosmetic and 7 were tool
  false positives, now fixed. Django labels a backported note with the oldest series that
  got the change; one 5.2 LTS note (cache.txt, "Changed in Django 6.0.6") is the single
  exception in 70.
- **Census 2** (`PREREG-2.md`, `GRADING-2.md`, `results/census2/`): 60 projects, 17,289
  notes. Gate and all four predictions held. 42 notes in 14 projects have a malformed
  marker; of the 40 hand-graded, 35 (88%) are real losses in built docs (25 confirmed on
  the live sites). Examples: Pyramid's 1.10 `samesite` change notes are missing from its
  2.1 API docs; scikit-learn 1.9.1's `SVC(probability=...)`
  deprecation shows as the raw text "..deprecated:: 1.9"; five Pygments lexers have no
  version on pygments.org because a 2023 migration script only matched `versionadded::`.
- **Census 3** (`PREREG-3.md`, `GRADING-3.md`, `results/census3/`): every common
  directive in the same 60 projects, 83,629 markers. Gate and four of five predictions
  held; the hand-graded precision prediction failed (18 of 40, 45%, against 50%). 72
  non-version markers in 32 projects are malformed. Real losses include the code examples
  of Bokeh's `CustomJS`, the patch and the shell recipe in Cython's FAQ, the compiler-error
  example in NumPy's 2.0 migration guide, Django's `FlatPage.registration_required` field
  entry, and raw LaTeX in two NetworkX functions. Most misses were deliberate
  `.. note: text` comments, which led to the comment-like rules above.
- **Census 4** (`PREREG-4.md`, `GRADING-4.md`, `results/census4/`): 60 new projects,
  46,881 markers. Gate and all five predictions held. 31 of 40 sampled default reports
  (77.5%) are real losses, 24 confirmed on the live sites, but Salt alone gives 23 of them
  (without Salt: 8 of 15). Examples: seven `salt.modules.nxos` functions have no CLI
  example and eight `salt.states.win_iis` notes are missing on docs.saltproject.io; Kivy's
  `FocusBehavior` keyboard warning and focus notes; the memory layout in pyqtgraph's
  `arrayToQPath`; the example output on Bandit's B108 page.

Related studies: munimtechnologies/backport-version-notes,
munimtechnologies/branch-version-notes-audit.

## Limits

It is a line scanner, not a docutils parser. Literal blocks are found by indentation.
It does not know which files your docs build includes, or whether a comment was meant;
the comment-like rules are a heuristic. Made with AI agents; check its output before
acting on it.
