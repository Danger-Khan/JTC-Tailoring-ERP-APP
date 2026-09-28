# Change log — part 2 of 2

Entries 16–19 of the original per-session log, consolidated into
one file. Each section below is the original `change{N}.md` reproduced
**verbatim**; only the file it lives in changed. Cross-references of the
form "continued in changeN.md" now point at a section of this file or its
sibling rather than a separate file.

Numbering is historical and never reused. New sessions are appended to the
last part as dated bullet points until it reaches ~1000 lines, at which
point the next part begins.

---

<!-- ===== originally change16.md ===== -->

# Change 16 — Brand imagery, translucent rounded surfaces, fullscreen mode

**Date:** 2026-09-28

*Continued in [change17.md](change17.md) — production calendar and inventory.*

## Summary

### Brand images (`app/utils/assets.py`, new)
`app/Images/` holds three shop photos: the round illuminated sign (twice —
a wide shot and a tight crop) and the owner at the counter. They are now
used throughout the app.

Two Tk limits shaped the whole module:

- `tk.PhotoImage` reads only GIF/PNG/PPM **and trusts the file extension**.
  These files have been renamed by hand more than once and are currently
  `.png` holding JPEG bytes, so Tk's own loader would reject them. Everything
  goes through Pillow, which sniffs the real format. Files are resolved by
  name-stem, case-insensitively, so renaming them again will not break it.
- Tk widgets have no per-widget opacity. Anything that looks translucent is
  an opaque image that Pillow blended against the theme colour first.

`AssetStore` exposes `circle()` (round crop matted onto a flat colour),
`backdrop()` (cover-fit, blurred, blended toward a colour), `panel()`
(frosted card with a round emblem composited in), `average_color()`, and
`window_icon()`. Every accessor returns `None` rather than raising when
Pillow is missing or the folder has moved, so the app still starts with its
plain text chrome. Images are cached on the store (Tk blanks a widget the
moment the last Python reference to its image is dropped) and the cache is
cleared on theme switch, since each one is flattened against a specific
surface colour.

**Where they appear:** the sign is the window icon (via `iconphoto(True, …)`,
which also covers the login dialog and every modal, unlike `iconbitmap`) and
the sidebar logo; the owner photo is the login backdrop, the sidebar
background, and a faint watermark behind each page.

### Translucency
- **Login** is now the owner photo full-bleed with a frosted panel over it.
  The headings are canvas text, not labels, because a `tk.Label` would punch
  an opaque rectangle through the photo. The logo is composited *into* the
  panel image — stacking a separately-matted circle on top left it sitting
  in a visible square of the wrong shade, which is what the first attempt
  looked like.
- **Pages** get the owner photo blended behind them at
  `PAGE_BACKDROP_OPACITY`, visible in the gutters between cards. Rebuilt on
  resize, debounced and snapped to a 24px grid so dragging the window edge
  does not re-blur a full-size photo on every pixel.
- **The sidebar's empty region** below the nav gets a stronger blend — it is
  the one area large enough for the photo to actually read rather than just
  add texture.
- **Cards** are frosted by tinting every surface colour toward the photo's
  average (`CARD_FROST`). This is a tint, not see-through, and deliberately
  so: a card cannot show an image behind it when each of its child labels
  paints its own opaque rectangle. Sharing the backdrop's colour cast is what
  the eye actually reads as translucency. `bg_body`, `border`, `neu_light`
  and `neu_shadow` are excluded — tinting the edges toward the surfaces they
  outline flattened every card into the page on the first pass.
- **`WINDOW_ALPHA`** gives real window-level translucency, but only just:
  at 0.97 the desktop behind the window was legible straight through the
  dashboard, so it sits at 0.99. Set it to 1.0 to switch off.

### Rounded corners
A `tk.Frame` is always a hard rectangle, so the design's `--radius-card: 16px`
could not be built from frames at all. `_neu_card` and `_neu_well` are now
canvases with the rounded shape drawn on them and the content frame placed
inside, inset far enough that its square corners stay within the curve. The
canvas paints itself in its **parent's** background colour, which is what
makes the cut corners read as empty space rather than chips of the wrong
shade. Both helpers still return the inner frame, so every existing caller
was untouched. Depth is an offset copy of the shape underneath, standing in
for `--shadow-out`.

### Display mode
The app now opens **fullscreen** by default (`-fullscreen`: no title bar,
covers the taskbar — not `zoomed`, which would leave the shell chrome on
screen). Settings has a Display Mode card; F11 toggles and Esc always drops
back to windowed, since a real fullscreen window with no title bar is hard
to escape otherwise. The choice persists in the session cache.

`windowed_geometry` is tracked separately and updated only while actually
windowed: `self.geometry()` reports the whole screen while fullscreen is
set, so reading it on the way out would permanently overwrite the size to
come back to.

## Files touched
- `app/utils/assets.py` (new), `app/utils/app_state.py` (`display_mode`)
- `app/main_gui.py` (asset wiring, login, sidebar, rounded surfaces, frost,
  display mode)
- `app/README.md`, `app/readme.txt`, `app/readme.me`
- `app/tests/gui_smoke_test.py`

## Verification
- Unit tests 12/12; GUI smoke test 58/58 (see change17 for the full count).
- Screenshotted the running app: login over the owner photo, sidebar logo and
  owner block, rounded frosted cards, and the photo showing through gutters
  and the sidebar, in both light and dark.

---

<!-- ===== originally change17.md ===== -->

# Change 17 — Production calendar and inventory summary

**Date:** 2026-09-28

*Continued from [change16.md](change16.md) — brand imagery, translucency,
rounded surfaces, fullscreen.*

## Summary

Two new sidebar sections, both built on the existing Excel-backed patterns.

### 📅 Production Calendar
A month grid of what is due when, derived entirely from each order's
existing `delivery_date` column — no new storage, and read-only, since it is
a planning view over orders that already exist rather than another place to
create them.

- Day cells are inset wells showing the date, a count pill, and the first
  three customers due that day (`+N more` beyond that). Today is picked out
  in the primary colour; days outside the month recede but stay visible so
  the grid keeps its shape.
- The count pill is terracotta when the day is already past and amber when
  it is still ahead.
- Prev / next / Today navigation, plus a stat strip: **Due This Month**,
  **Due In 7 Days**, **Overdue**.
- `_parse_date()` accepts the handful of formats that actually turn up in a
  hand-typed sheet (`%Y-%m-%d`, `%d-%m-%Y`, `%d/%m/%Y`, `%Y/%m/%d`,
  `%m/%d/%Y`) and returns `None` for anything it cannot read, rather than
  throwing on one bad cell and taking the whole view down.

### 📦 Inventory
A new `inventory.xlsx` (`id, item, category, quantity, unit, reorder_level,
updated`), read in `reload_all_data()` alongside the other sheets — a missing
file just means nothing has been stocked yet.

- **Summary strip**: Items Tracked, Total Units, Low Stock, Out Of Stock.
  "Low" means at or below the item's own reorder level; rows are tinted to
  match (tan for low, brick red for empty).
- **Stock In / Stock Out** adjust the selected item by a typed amount and
  stamp `updated`. Quantity is floored at zero — a shop cannot hold −3 metres
  of cloth.
- **Add Item** modal and admin-gated delete, both using the same
  append/write-all rewrite pattern as customers and orders.
- `_inventory_level()` tolerates blank or non-numeric cells the way the rest
  of the sheet handling does.

## Why
"add production calender, inventory summary".

## Files touched
- `app/main_gui.py` (both sections, nav entries, `inv_headers`, inventory
  loading in `reload_all_data`, refresh hooks)
- `app/lang/en.py`, `app/lang/ur.py` (`nav_calendar`, `nav_inventory`)
- `app/tests/gui_smoke_test.py`, `app/tests/test_excel_manager.py` (new)
- `app/excel_manager.py` (`ensure_file` header repair)
- `app/README.md`, `app/readme.txt`, `app/readme.me`

## Bug found and fixed
The calendar's "skip delivered orders" test was
`"deliver" in delivery_status.lower()` — but the sheet stores **"Not
Delivered"**, which contains the substring. Every undelivered order was
therefore hidden from the calendar: the grid rendered correctly but every
cell and every counter was empty. Caught by screenshotting the page rather
than by the tests, because the first version of the check
(`all(... for o in buckets)`) passed vacuously on an empty result.

Fixed with `_is_delivered()`, which anchors at the start of the string and
also checks the `status` column. The smoke check now asserts the exact set of
bucketed order IDs, so it cannot pass on an empty result again, plus a direct
assertion that `"Not Delivered"` reads as still-due.

## Second bug found and fixed
`app/data/inventory.xlsx` already existed in the real data dir (dated July),
holding **zero rows** — no header row at all. `ExcelManager.ensure_file()`
returned early whenever the file existed, so it never repaired that: the
first `append_record()` would drop its row into row 1, the next
`read_records()` would read that row back as the header, and the user's
first inventory item would have silently vanished.

`ensure_file()` now also repairs an existing workbook whose first row is
blank, writing the headers into it. That helps every sheet, not just
inventory. Covered by a new `app/tests/test_excel_manager.py` (4 tests),
including a direct reproduction of the found-on-disk state.

## Verification
- Unit tests: **16/16** (was 12; 4 new in `test_excel_manager.py`).
- GUI smoke test: **58/58** (was 45 at the start of this sitting). New checks
  cover: fullscreen-by-default and both toggle directions, display mode
  persisting to the session cache, inventory loading from its own sheet, the
  summary counting low/out/units correctly, calendar bucketing (exact ID
  set), `"Not Delivered"` handling, date-format parsing, grid rendering, and
  month navigation. The inventory seed deliberately includes one healthy,
  one low and one empty item so every summary bucket is non-zero.
- Screenshotted both new sections against seeded data: the calendar showing
  3 due this month / 2 due in 7 days / 4 overdue with the right days pilled
  red vs amber, and inventory showing 5 items / 182 units / 2 low / 1 out
  with the matching rows tinted.
- One screenshot-harness fix along the way: leaving fullscreen, the window
  manager restores the previous rect *asynchronously* and clobbered a
  geometry set before it had settled, so captures were being cropped from a
  negative X offset. The capture helper now re-asserts geometry each time.

---

<!-- ===== originally change18.md ===== -->

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

---

<!-- ===== originally change19.md ===== -->

# Change 19 — Right-to-left Urdu layout, quick theme/language controls

**Date:** 2026-09-28

*Continued from [change18.md](change18.md) — version control and the
off-screen window fix.*

## Summary

### Reading direction is now a first-class layout property
Urdu and Pashto are Arabic-script and read right-to-left, so selecting one
mirrors the whole app rather than only swapping the wording: the sidebar moves
to the right edge, nav and headings anchor to the right, toolbars and stat
strips reverse, table columns read from the right, typed text is
right-aligned, and the status pill's dot leads its text from the other side.

Tk has no direction property — a widget is packed to a literal side and
anchored to a literal compass point — so mirroring means mirroring those
arguments. Five helpers (`_side`, `_anchor`, `_justify`, `_pad`, `_columns`,
plus `_grid_col` and `_text_align`) do that centrally, and 162 layout call
sites now route through them. They are no-ops in a left-to-right language, so
the English layout is unchanged.

Notes on the parts that are not a simple flip:

- **Tables** mirror via `displaycolumns`, never by reordering `columns` —
  `columns` is the order every `insert(values=…)` supplies its tuple in, so
  reversing it would silently file each value under the wrong heading. A
  smoke check inserts a probe row and asserts every cell still reads back
  under its own column.
- **Canvas item anchors are not mirrored.** `create_image`/`create_window`
  place relative to an absolute canvas coordinate, so anchoring `"ne"` at
  x=0 hangs the item off the left edge.
- **Grid column indices are mirrored only in the calendar.** The New Customer
  modal and the Order Card are laid out on a grid too, but their field
  positions are off-limits, so they get mirrored `sticky` and right-aligned
  input without their columns being renumbered.
- **A direction change rebuilds the body**, the same way a theme change
  already does, because packed sides cannot be flipped after the fact.
  Same-direction switches still just re-label in place.

### Quick theme and language controls
Two chips at the foot of the sidebar: the current theme (click to flip) and
the current language (click for a menu of the five packs, ticked, with RTL
ones marked). Both also answer to **Ctrl+T** and **Ctrl+G**, for when a modal
has focus. `set_theme()` is now the single path every theme control shares.

### More Urdu
The pack was already complete for what was wired up; the gap was strings that
had never been routed through it. Now translated: the Mark Ready button and
its context-menu twin, the empty-ledger line, the whole Display Mode card,
the theme and display combobox *values*, the order statuses shown in the
ledger, and the production calendar — title, subtitle, Today, the three
workload captions, the weekday row and the month names.

Order statuses are translated **for display only**. The workbook keeps its
English values, because reports, the finance tabs and every status test match
on them — switching language must never rewrite what is stored.

## Bugs found and fixed

**The Settings page hid its own theme and language controls.** The Theme,
Display Mode and Language cards were packed `fill=BOTH` inside a row that does
not expand. `_rounded_surface` only grows a canvas to fit its content when
pack is not already stretching it vertically, so all three kept their
placeholder `height=1` and collapsed to a sliver — the controls existed, but
could not be seen or clicked. This is why they were asked for.

**A theme change silently reverted the UI to English.** Widgets are built with
English text and translated afterwards, but `build_ui_layout()` never re-ran
the language pass. Pick Urdu, switch to Dark Mode, and every label came back
English while `current_lang` still said `ur`.

**The display-mode and theme handlers matched on English substrings**
(`"Full" in …`, `"Dark" in …`), which appear in none of the translated values.
Both now compare against the generated label, keeping the substring as a
fallback.

**`calendar.month_name` follows the C locale**, so the month heading was
English in every pack. Month and weekday names now come from the language
pack.

## Files touched
- `app/main_gui.py` (direction helpers, 162 mirrored call sites, quick
  controls, `set_theme`/`set_language`, `_status_label`, calendar mirroring
  and translation, Settings row fix)
- `app/lang/en.py`, `app/lang/ur.py` (22 new keys, incl. weekday and month
  tuples)
- `app/tests/gui_smoke_test.py`

## Verification
- Unit tests **19/19**; GUI smoke **98/98** (was 83 mid-sitting, 64 before).
- New checks cover: the mirror helpers in both directions (including that
  `_anchor("center")` is not mangled to `"cwntwr"`), sidebar and nav position,
  column reversal *with* value integrity, input alignment, the calendar's
  weekday row moving Monday to the rightmost column and back, Settings
  controls being mapped with real height, translated combobox selections
  still applying, and the theme-change/language regression.
- Screenshotted every section in Urdu, light and dark, against seeded data —
  which is what caught the empty-card bug the property assertions all missed.

---

<!-- ===== session: 2026-09-28 (c) ===== -->

## 2026-09-28 — Instruction-file backlog

Worked through the `instructions.txt` notes left around the project.

**Fixed first — the app would not start.** `app/lang/translations.py` still
did `from . import en, ur, ps, zh, ru` after `zh.py` and `ru.py` were deleted.
Every entry point died on import. Now `from . import en, ur, ps`; both
remaining non-English packs are RTL, which the mirrored layout already covers.

**Machine health readout** (`app/services/system_monitor.py`, new)
- Internet (TCP to a public resolver, not an HTTP fetch), CPU, RAM, disk and
  GPU. GPU shells out to `nvidia-smi` and gives up quietly on anything else.
- Every probe memoized through the `memoize_with_ttl` already in
  `utils/performance.py`; never raises; returns `None` per probe and renders
  as a dash, so an unavailable reading is still information.
- Off by default, toggled in Settings, shown as a strip at the foot of the
  sidebar.
- Probing runs on a worker; **the worker never touches Tk.** Calling
  `self.after()` from it silently failed to deliver and left every row
  reading "—". It now only assigns a dict, and the main thread reads it.
- Dropped the strip's "MACHINE" caption for a hairline: the sidebar's
  vertical budget is tight and the GPU row was being clipped.

**Admin password** (`app/utils/admin_password.py`, new)
- Login no longer compares against a literal in the source. bcrypt hash kept
  in the session cache; an empty hash means "never changed" and the factory
  password still works, so an update cannot lock the owner out.
- A malformed stored hash reads as "wrong password", never a crash on the
  login screen.
- Settings card warns in red while the install is still on the default.

**Command bar** (optional, Ctrl+K)
- Slide-up strip, `place()`d over the page so opening it does not shove
  every section upward.
- Routes offline first — sections, theme, language, display mode — including
  the translated nav words, so an Urdu user can type Urdu.
- A custom API endpoint is consulted only for a phrase nothing local matches;
  absent or failing, it is a quiet no-op. Key stored in plain JSON, and the
  dialog says so.

**Finance delete**
- `FinanceDB.delete_row()` plus an admin-gated, confirmed button.
- The confirmation says plainly that the order survives and the line returns
  on the next sync — the ledger is rebuilt from orders, and "delete" must not
  read as a promise it cannot keep. Verified both halves.
- Extracted `_repaint_finance_table()` so the delete repaints from the table
  instead of re-syncing (which would write the row back before it was seen).

**Cards link to the page they summarise**
- `_link_card()` binds the whole subtree, not just the outer frame: a card is
  mostly covered by its own labels, and a click on the number would otherwise
  do nothing. Hand cursor as the affordance.
- All ten stat tiles wired — dashboard, calendar, inventory.

**Services that existed but were never wired up** (per
`app/services/instructions.txt`, "use the already in the application")
- `NotificationService` → WhatsApp button on Customers, building a
  pre-written message from the customer's latest order. It only opens a
  draft; nothing sends without the owner pressing send.
- `GarmentCalculator` → fabric estimate, taking the garment from the
  customer's most recent order.
- Made the notifier's logger import defensive — it reached for `config`,
  which resolves to a different data directory depending on entry point.
- Fixed stale "Atelier" branding in its message text.

**Translations:** 44 new keys in English and Urdu, all wired through
`apply_language_pack` (the new cards are built in English and re-labelled,
like everything else here).

**Verification:** 19/19 unit tests; GUI smoke **146/146** (was 98).
Screenshotted Settings, the monitor strip, the command bar, Finance and
Customers in English and Urdu, light and dark.

**Changelog consolidation:** `change0.md`–`change19.md` merged into two
~1000-line parts per `app/changes/Instructions.txt`. Every original entry is
reproduced verbatim and was diff-checked against a backup before the
originals were removed.

---
