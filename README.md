# version-note-lint

A small checker for the version argument of Sphinx version notes (`versionadded`,
`versionchanged`, `deprecated`, `versionremoved`, the Sphinx 9 `version-*` spellings, and
CPython's `deprecated-removed` / `soft-deprecated`). By MV2 of Munim, Inc.
(mv2@munimtech.com). Made with AI agents working in MV2's name. Apache-2.0.

Sphinx prints whatever word comes first after the directive as the version. So these slips
build without a warning but show readers the wrong thing:

```rst
.. versionchanged::
    NumPy 2.1 changed the headers ...
```

renders as "Changed in version NumPy: 2.1 changed the headers ..." (this exact case is live
in NumPy's C API docs as of 2026-11-03).

What it reports:

| Class | Example | What readers see |
|---|---|---|
| MISSING | `.. versionadded::` then a blank line | nothing; Sphinx errors and drops the note |
| BODY_AS_VERSION | `.. versionchanged::` with the text on the next line | the first word of the text as the version |
| OTHER | `.. versionadded:: Python 3.4` | "Added in version Python: 3.4" |
| FUTURE (`--branch-version X.Y`) | `.. versionchanged:: 6.0.6` on a 5.2 branch | a release the branch's docs are not about |

Placeholders (`next`, `A.B`, `|version|`, ...) and notes inside literal blocks or code fences
are not reported.

## Use

```
pip install git+https://github.com/munimtechnologies/version-note-lint
version-note-lint docs/ src/
version-note-lint --branch-version 5.2 docs/      # on a maintenance branch
version-note-lint --json docs/
```

Exit status is 1 when anything is reported. As a pre-commit hook:

```yaml
- repo: https://github.com/munimtechnologies/version-note-lint
  rev: v0.1.0
  hooks:
    - id: version-note-lint
```

No dependencies; one file (`version_note_lint.py`), Python 3.9+.

## Census

`PREREG.md` pre-registers a census of 30 Python projects' default branches and of Django's
release tags (`census.py`, job `version-note-census-v1`). Results will be in `GRADING.md`.
Related studies: munimtechnologies/backport-version-notes,
munimtechnologies/branch-version-notes-audit.

## Limits

It is a line scanner, not a docutils parser. Literal blocks are found by indentation.
It does not know which files your docs build includes. Made with AI agents; check its
output before acting on it.
