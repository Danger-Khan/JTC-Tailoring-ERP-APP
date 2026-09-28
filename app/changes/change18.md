# Change 18 — Version control, dependency pinning, off-screen window fix

**Date:** 2026-09-28

*Continued from [change17.md](change17.md) — production calendar and inventory.*

## Summary

A repo-readiness pass over the whole project, plus two defects the analysis
sweep turned up.

### Bug: a saved window position could strand the sidebar off-screen
`app_state_cache.json` held `geometry: "1536x793+-164+54"` — a negative X
origin. Restored verbatim on the way out of fullscreen, that slices 164px off
the left of the window, and the left of this window is the sidebar: the brand
lockup and every nav button.

The value came from the window manager itself. Leaving fullscreen, Windows
restores the previous rect *asynchronously*, and a geometry read back before
it settles reports the in-between position — which the app then dutifully
saved.

`_sane_geometry()` now clamps a restored geometry string against the screen:
size capped to the display (and floored at 800x600), origin pulled back inside
it. It runs both on load and in `_remember_windowed_geometry()`, so a bad rect
can neither be restored nor re-saved.

Two deliberate limits:
- Only the `+X+Y` form is rewritten. Tk also accepts `-X-Y`, which measures
  from the right/bottom edge rather than being a negative coordinate;
  reinterpreting that as an origin would move a deliberately-placed window.
  Note Tk spells a negative origin `+-164`, so the sign lives inside the
  capture group — parsing it as a plain signed int raises `ValueError`.
- Clamping to the primary screen means a window parked on a second monitor
  comes back on the main one. That is the trade: this runs on a single
  shop-counter machine, where a chopped-off sidebar is a real failure and a
  window returning to the main display is a shrug.

Unparseable and size-only strings are passed through to Tk untouched.

### Bug: a smoke check that flapped on developer state
`check("starts in fullscreen by default", ...)` asserted a *default* while the
app restores a *saved preference*, so it passed or failed depending on how the
app had last been closed — it failed on the first run of this sitting purely
because of leftover screenshot-harness state. Same flaw as the theme check
fixed in an earlier sitting.

Split into the two halves that are actually contracts: the default with
nothing saved (checked against a cache path that was never written), and the
window agreeing with whatever mode was restored. Verified deterministic by
running the suite with the live cache set to `fullscreen` and to `windowed`.

### `requirements.txt` (new)
There was no dependency manifest — a clone was not installable. The list is
derived from the actual imports in the tree (AST scan, not guesswork), pinned
to the versions this build is verified against, and split into the desktop
app's five packages and the optional Flask API's four. `app/setup.sh` listed
extras the app never imports (pandas, numpy, gunicorn, python-dotenv,
requests) and omitted `psutil`, which it does.

### `.gitignore` (new)
Most importantly, **`app/data/` and `data/` are not tracked**. They hold the
running business — real customer names and phone numbers, order history, the
finance ledger, the session cache. That is user data, not source. A fresh
clone recreates the folder on first launch: `ExcelManager.__init__` makes its
data dir and `ensure_file()` writes the header row into each sheet (the repair
path added in change17).

Also excluded: both in-tree virtualenvs (`.venv`, `.venv-1` — ~1.8M lines of
vendored code), `__pycache__`, `.pytest_cache`, `desktop.ini`, and
`.claude/settings.local.json`.

### `.gitattributes` (new)
The tree mixes LF and CRLF, which would otherwise produce whole-file diffs on
every cross-platform edit. Text normalized to LF in the repo, checked out
native; images and workbooks marked binary; `*.sh` forced to LF so bash does
not reject it.

### Repository initialised
`git init` on `main`, 95 files in the first commit, 8,350 lines of project
Python. Git's `safe.directory` guard had to be satisfied first: this drive
carries an owner SID from a different Windows install, so every git command
failed with "dubious ownership" until the path was allowed.

## Why
"continue and analyze all once done and then git push all the code".

## Files touched
- `app/main_gui.py` (`_sane_geometry()`, `import re`, geometry restore and
  remember paths)
- `app/tests/gui_smoke_test.py` (deterministic display-mode checks, four new
  geometry-clamp checks)
- `.gitignore`, `.gitattributes`, `requirements.txt` (all new)

## Verification
- Unit tests: **19/19**.
- GUI smoke test: **64/64** (was 58; +6 net). Deterministic with the live
  cache set either way.
- `_sane_geometry()` exercised against the real poisoned value, an oversized
  rect, a fully off-screen rect, the edge-relative form, a size-only string,
  a sub-minimum size, and garbage.
- Every package in `requirements.txt` confirmed importable.
- `git add -A` staged 95 files with **no** `app/data/`, `data/` or `.venv`
  leakage.
- `python -m compileall` clean across the project.

## Not done
The push itself. The supplied token returns **401 Bad Credentials** from
`api.github.com/user` under both the `Bearer` and legacy `token` schemes,
while an unauthenticated call to the same host returns 200 — so it is the
credential, not the network. The commit is ready locally; it needs a valid
token and a target repo.
