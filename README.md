# version-note-lint

A small checker for Sphinx version notes (`versionadded`, `versionchanged`, `deprecated`,
`versionremoved`, the Sphinx 9 `version-*` spellings, and CPython's `deprecated-removed` /
`soft-deprecated`). It checks the version argument and the directive marker itself. By MV2
of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name. Apache-2.0.

Sphinx prints whatever word comes first after the directive as the version, and docutils
quietly turns a malformed directive into a comment. So these slips build without a warning
but show readers the wrong thing, or nothing:

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
2026-11-04).

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

Placeholders (`next`, `A.B`, `|version|`, `{version}`, `{{ start_version }}`, ...), two
versions joined by a slash (`2.0/2.3.4`), and notes inside literal blocks or code fences are
not reported. In Python files, a docstring's closing quotes on the same line are ignored.

sphinx-lint's `directive-missing-colons` already catches `.. versionadded: 1.2` and
`.. versionadded 1.2` in .rst files. This tool also covers triple colons, `::` with no
space after it, `..name::`, and Python docstrings. In census 2, 35 of the 42 dropped or
raw notes were of these kinds.

## Use

```
pip install git+https://github.com/munimtechnologies/version-note-lint
version-note-lint docs/ src/
version-note-lint --ignore PUNCT docs/ src/       # only what changes the meaning
version-note-lint --branch-version 5.2 docs/      # on a maintenance branch
version-note-lint --json docs/
```

Exit status is 1 when anything is reported. As a pre-commit hook:

```yaml
- repo: https://github.com/munimtechnologies/version-note-lint
  rev: v0.1.1
  hooks:
    - id: version-note-lint
      args: [--ignore, PUNCT]
```

No dependencies; one file (`version_note_lint.py`), Python 3.9+.

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
- **Census 3** (`PREREG-3.md`, `marker_scan.py`, `census3.py`): the same question for every
  common directive (note, warning, seealso, code-block, testcode, autoclass, image, ...)
  in the same 60 projects. Pre-registered 2026-11-05; results will be in `GRADING-3.md`.

Related studies: munimtechnologies/backport-version-notes,
munimtechnologies/branch-version-notes-audit.

## Limits

It is a line scanner, not a docutils parser. Literal blocks are found by indentation.
It does not know which files your docs build includes. Made with AI agents; check its
output before acting on it.
