# Grading 4: the comment-like rules on 60 new projects

MV2, Munim, Inc. (mv2@munimtech.com). Graded 2026-11-06 against `PREREG-4.md`, which was
committed before the census-4 data was read. Made with AI agents working in MV2's name; the
hand grades below were made by those agents and no human has checked them. Code Apache-2.0;
text and data CC BY 4.0.

## Run

Job `directive-census4-v1` ran on 2026-11-05 (20:55-20:59 UTC, 270 s, 0.06 GB peak). All 6
unit tests passed. It read the default branches of 60 Python projects that were not in
censuses 2 and 3; commit ids are in `results/census4/summary.json`.

## Result: gate and all five predictions held

| | Prediction | Result | |
|---|---|---|---|
| G1 | at least 54 of 60 tarballs read | 60 of 60 | held |
| G2 | at least 20,000 markers | 46,881 | held |
| P1 | at least 15 default rows in at least 8 projects | 49 rows in 9 projects | held |
| P2 | at least 60% of `review4.csv` is D1 (hand) | 31 of 40 (77.5%) | held |
| P3 | at most 30% of `review4-comment.csv` is D1 (hand) | 2 of 20 (10%) | held |
| P4 | comment-like rows are 20-60% of reported non-version rows | 30 of 79 (38%) | held |
| P5 | version-note reported rate above other directives' default rate | 0.26% vs 0.15% | held |

P1, P4 and P5 were computed by the job. P2 and P3 were graded by hand; every grade and its
evidence is in `results/census4/p2-grades.csv` and `p3-grades.csv`.

## P2: 31 of 40 default rows are real losses

24 of the 31 D1 rows were confirmed on the live docs sites on 2026-11-06; the other 7 were
checked in the source at the census commit. Examples:

- **Salt** (23 of 25 sampled rows D1). Seven functions in `salt.modules.nxos` (`ping`,
  `check_password`, `get_roles`, `get_user`, `grains`, `grains_refresh`, `sendline`) have
  no CLI example on docs.saltproject.io because each is written `.. code-block: bash`.
  Eight notes in `salt.states.win_iis` (e.g. that `deployed` only checks the site name and
  will not modify an existing site) are written `.. note:` and do not appear; only the one
  correct `.. note::` (in `set_app`) does. Also hidden: the Mako renderer's install command,
  the msgpack renderer's "NOT intended for use in creating sls files by hand" note,
  `system.init`'s runlevel table, two `fileserver` runner notes, `git.latest`'s "bare is
  incompatible with rev" note, `file.replace`'s memory note, `win_wua.set_wu_settings`'s
  read-only note, the proxy-minion grains example (`.. code: python::`) and the
  developer-guide `pip install` command for `tools`.
- **Kivy**: the `keyboard` warning and the `focus_next`/`focus_previous` notes of
  `FocusBehavior` (missing on the 2.3.1 API page), and the `Settings.on_config_change`
  warning.
- **pyqtgraph**: `arrayToQPath` says "The memory format is as follows" and then shows
  nothing.
- **Bandit**: the B108 plugin page has an "Example:" heading with an empty body.
- **PyVista**: the `Color` note on its internal RGBA representation.
- **PyInstaller**: the "This section is still incomplete" note in the testing guide.

The 9 D2 rows: three ffpyplayer provider modules of Kivy that the API docs do not include,
a private dask method, Salt's `noxfile.py`, `salt.utils.templates` (no API page that we
know of; could be D3), two PyInstaller `.. highlight: bash` lines with nothing indented
under them (only highlighting changes), and PyInstaller's deliberate `.. NOTE:` editor
comment at the top of `CHANGES.rst`.

**Caveat that matters.** Salt alone gives 23 of the 31 D1 rows. Without Salt, 8 of 15 rows
are D1 (53%), which would have failed the 60% line. The rules held on this sample, but the
precision depends heavily on which projects are in it; one project that writes
`.. note:` and `.. code-block: bash` by habit dominates. The per-project picture is the
honest one: 9 projects have default rows, and the rows in 6 of them are mostly real losses.

## P3: the comment-like rules skip what they should

18 of the 20 comment-like rows are deliberate comments: 16 are MNE-Python's editor notes
(`.. NOTE: part of this file is included in ...`), one is nibabel's link-target note, and
one (`kivy/tools/kviewer.py`) reads like a slip but is in a module the docs do not build.
Two are real losses the rules skip: Salt's webhook engine hides a
`tls.create_self_signed_cert` command behind `.. note: For making an unsigned key, use the
following command`, and dask distributed's asynchronous guide hides "Blocking operations
like the .compute() method aren't ok to use in ..." (`.. note: Blocking ...`). Both are
exactly the R1 shape, so rule R1 trades these misses for skipping the 18 comments.

## What this says about the tool

- Out of sample, `version-note-lint --all-directives` (default, comment-like rows skipped)
  was right on 31 of 40 sampled rows. In census 3 (in sample) the same rules would have
  given 16 of 21 (76%).
- 42 of the 49 default rows (86%) are outside the pattern of sphinx-lint's
  `directive-missing-colons` as the census models it, mostly because they are in Python
  docstrings (34 of the 40 sampled rows are in `.py` files). This is the gap the tool fills.
- Both P3 misses are R1 rows in built docs. A future rule could keep R1 rows whose text
  ends in a colon or that have an indented body; that idea comes from this data and would
  need a new sample.

## Limits

The scanner reads lines, not a docutils parse. Whether a file is built was decided by hand,
partly from live pages and partly from the project layout. Live pages were read on
2026-11-06 and may be built from a release branch rather than the census commit; for each
live-checked row the slip is present in the source at the census commit and the content is
absent on the live page. Small samples: 40 and 20 rows. Nothing was reported upstream before
this grading.
