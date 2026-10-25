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
<!-- ===== session: 2026-09-28 (d) ===== -->

## 2026-09-28 — Languages section

Audited the language packs and closed the gaps.

**Pashto was effectively broken.** 29 keys against English's 267 — **10.5%
coverage**. Choosing Pashto gave a mirrored RTL layout with a
mostly-*English* interface, which is arguably worse than not offering it.
The pack had also dropped the emoji prefixes the nav buttons and card
headings are laid out around, so the Pashto sidebar had no icons at all.
Rewritten complete: **306/306 keys**, icons restored, day and month names
included.

**Three screens had never been internationalised at all** — no keys existed
for them in any pack, so they were English even in fully-translated Urdu:
- the login screen (both the photo panel and the plain fallback),
- the whole Inventory page — header, toolbar, the four summary tiles, the
  table headings and the Add Item modal,
- the add-order modal's field labels.

44 new English keys, wired through `apply_language_pack` so they follow a
live switch, and translated into Urdu and Pashto. Field values, dropdown
options and defaults were left untouched — labels only.

**Urdu** brought back to 306/306 (it was missing the 39 new keys).

**A guard so this cannot rot again** (`app/tests/test_translations.py`, 9
tests, no Tk):
- every offered language has a pack, and every pack is offered — this is the
  check that would have caught `translations.py` importing `zh` and `ru`
  after those files were deleted, which broke every entry point,
- every pack covers every key,
- no value is left identical to English (bar an explicit allow-list for the
  CPU/RAM/GPU acronyms) — a verbatim copy is an untranslated string wearing
  a translation's clothes,
- `cal_days`/`cal_months` keep their type and length,
- `{placeholder}`s survive translation, since a dropped one raises at
  `.format()` time in that language only,
- leading emoji are preserved, which is exactly how the Pashto pack lost its
  icons unnoticed.

Each guard was mutation-tested: a key dropped, an English string copied in,
an emoji removed, a placeholder deleted and a tuple shortened all make the
relevant test fail.

**Coverage now:** en 306, ur 306, ps 306 — all at 100%.

**Verification:** unit tests **28/28** (was 19; 9 new); GUI smoke 146/146;
screenshotted Pashto across dashboard, inventory, calendar and settings.

**Caveat worth flagging:** the Pashto pack was written in one pass and wants
a read-through by a native speaker, particularly the tailoring vocabulary
(collar, daman, paancha, stitching styles) where the shop's own usage may
differ from the standard term. A note to that effect is in the file header.

---

## Session — the three defects the audit left open

Nothing here is visible in the desktop app; all three were latent, and two of
them could have destroyed live data the first time the Flask side was started
in the wrong way.

**One configuration module instead of two.** `config.py` and `app/config.py`
were byte-identical copies, and `from config import Config` resolved to
whichever one the launcher happened to put on `sys.path` first. Because both
derived `BASE_DIR` from `__file__`, the two copies disagreed about where the
data was: started from the project root the same import statement meant
`<root>/data`, started from `app/` (which is what `Start.bat` does, `cd app &&
pythonw main_gui.py`) it meant `<root>/app/data`. Ten modules import it.
- the root file is now the only real one; `app/config.py` loads it by absolute
  path, under a private module name so it cannot collide with whichever
  spelling of `config` is already in `sys.modules`, and re-exports `Config` —
  both spellings now hand back the same class object,
- the shim also reuses an already-loaded root module rather than executing the
  file twice, so a process that touches both spellings gets one `Config` and
  one read of the signing key,
- `DESKTOP_DATA_DIR` is now a named constant, so code can *check against* the
  desktop's store rather than guess at it,
- `JTC_DATA_DIR` overrides the API's store; `app/tests/conftest.py` uses it to
  keep the suite off both real directories, which it has to do from a conftest
  because `DATA_DIR` is resolved once at import time.

**`SECRET_KEY` is no longer a literal in the repo.** It defaulted to
`'super-secret-atelier-key-change-in-production'`, which signs the Flask
session cookie and now the auth tokens too — anyone holding a copy of the
source could forge either. Absent `SECRET_KEY` in the environment, a random
key is generated once and persisted (mode 0600) beside the data, so restarts
do not invalidate every outstanding session.

**`initialize_database()` no longer creates unreadable workbooks.** It saved a
bare `openpyxl.Workbook()` — a workbook whose one sheet is completely empty.
Everything in `excel_db.py` keys off the header row, so that is not an empty
table, it is a broken one:
- `get_all()` bails on `len(rows) < 2` and returns `[]` no matter what is
  written afterwards,
- `delete_record()` raises `ValueError` looking for the id column,
- and the self-heal path in `save_record()` used `sheet.append()`, which on a
  workbook *loaded from disk* lands on row 2 while row 1 stays blank — after
  which every field mapped through row 1 resolved to `None` and each record
  was stored as **a row of empty strings**. Silent, total loss of the first
  writes into any table.

The fix gives each table its header row (`TABLE_SCHEMAS`, mirroring the
`to_dict()` order in `app/models/schemas.py`), writes it to row 1 explicitly,
repairs an existing headerless workbook, and leaves any workbook that already
has a header row alone — even one whose columns differ, because reshaping
somebody's data is not initialisation's job.

It also now **refuses to run against the desktop store**. Both sides define
tables called `customers`, `orders`, `inventory` and `employees`, and the
columns differ in every one of them — the desktop's customers sheet is
`(id, name, phone, length, sleeve, shoulder…)` while the API's `CustomerModel`
is `(id, name, phone, chest, waist, length, sleeves, created_at)`. Pointing the
API at `app/data/` would have written the API's schema straight over live
customer records. This is not hypothetical: `app/data/users.xlsx` is still
headerless from the one time `initialize_database()` ran with `app/` on
`sys.path`. (Left as-is — nothing in the desktop app reads it, and live-data
files are not ours to delete.)

**`verify_token()` is now an actual check.** It was:

    return {"username": "admin", "role": "Administrator"} if token else None

Any non-empty string — `"x"`, `"null"`, `"undefined"`, a guess — authenticated
as an administrator, which defeated `@requires_auth` on all twenty protected
routes. Tokens are now signed with `itsdangerous.URLSafeTimedSerializer`,
salted so one cannot be swapped in for any other value signed with the same
key, and expire after 12 hours. `issue_token()` is handed out by `/api/auth/
login`, which previously returned nothing a client could use — because
anything at all would have worked.

While in there: `requires_auth` now stashes the verified identity on `flask.g`
and `requires_role` reads it. Without that, a token-authenticated administrator
fell through to `requires_role`'s session lookup, defaulted to `Viewer`, and
got a 403 on every route that also checks a role.

**Tests** — `app/tests/test_config_and_auth.py`, 23 of them, no server:
both import spellings resolving to one object; `app/config.py` having no
`Config` of its own; the two stores staying distinct; the signing key not
being a shipped constant; headers landing in row 1; a headerless workbook
being repaired; an existing header row surviving; initialisation refusing the
desktop store; records keeping their values instead of blanks; and, for the
token, rejection of arbitrary strings, non-strings, a tampered payload
(base64-decoded, role rewritten, original signature kept), a token signed with
another key, one signed under another salt, and an expired one — plus the
decorators as a route meets them, including a `Viewer` token being refused a
role-gated route.

All five defects were mutation-tested: re-introducing each one fails exactly
the tests that name it. (The first attempt at that proved nothing — the
mutation script truncated each file before reading it back, since
`io.open(p, "w")` truncates the moment it is evaluated. Rerun correctly.)

**Verification:** unit tests **51/51** (was 28; 23 new); GUI smoke 146/146;
desktop app launched and screenshotted to confirm the config change does not
touch it — it reaches its data through `excel_manager.py`, which computes the
path from its own `__file__` and never consults `Config`.

**One behaviour change worth knowing:** the audit log is now one file at
`<root>/data/system_audit.log` rather than following whichever config copy the
launcher picked. It was already split across both directories.

---

## Session — the order slip printed the wrong measurements

Everything here is about the piece of paper the tailor cuts from, plus the
name printed at the top of it.

**The slip reprinted an old order with today's measurements.** Every order
save snapshots its measurements and styles into `measurements.xlsx` and
`styles.xlsx`, keyed by `order_id` — that is what the order card's own
comment says it is for. Nothing ever read those sheets back. The ledger's
"Print Order PDF" pulled the numbers out of `customers.xlsx` instead, which
keeps only whatever was entered last.

So: measure a customer, take an order, re-measure them later (the Customer
Hub is the single place measurements are edited), then reprint the first
order. It came out with the new numbers on it, and the cloth gets cut to
them. Silent — the slip looks perfectly normal.

- `load_measurements()` / `load_styles()` read a snapshot back by order id,
- `measurements_for_order()` prefers the snapshot and returns whether it got
  one, so the slip can say where the numbers came from,
- `styles_for_order()` does the same for the style choices,
- an order with no snapshot (anything predating the order card) still prints,
  from the profile, labelled "(from customer profile)" rather than passed off
  as the order's own,
- a snapshot of all zeros counts as no snapshot: that is an order nobody
  measured, not a customer measured at zero,
- a row whose `order_id` went missing no longer answers to every lookup made
  with a blank id.

**Two style choices were collected and then thrown away.** `sleeve_type` and
`shalwar_type` — Full/Half, Churidar/Patiala — have no column in
`orders.xlsx`, so they were written to `styles.xlsx` and read by nothing.
The tailor never saw them. Both now print, on the PDF and on the text
receipt.

**The Urdu measurement labels were printing as black squares.** `Length
(لبادی)` and the eight beside it: the built-in Helvetica has no Urdu glyphs,
and reportlab does not fail on that — it silently substitutes ZapfDingbats,
whose stand-in for a letter is a filled square. The slip has been printing
`Length (■■■■■)`. Every text-level assertion passed the whole time, which is
why the smoke test now checks that nothing on the page needs a glyph the
font hasn't got.

Labels now come from the order card's own `MEASUREMENT_FIELDS`, so this slip
and the one the order card prints say the same words. **Real Urdu on the PDF
is still to do** — it needs an embedded Nastaliq font plus
`arabic-reshaper`/`python-bidi` for letter joining and right-to-left order;
neither is installed, and doing half of it prints isolated letters backwards.
Not silently dropped, just not pretended at.

**The text receipt ran off the roll.** Its dividers are drawn at 40
characters and `center()` does not truncate, so `Daman : Round Daman
Stitch : 1. Single Stitch` (47) and the footer (42) wrapped mid-value on an
80mm printer. One style per line now, each label padded to a fixed width,
every line 40 characters or fewer.

**One spelling of the shop's name.** It had drifted into three. The sidebar,
the receipts and the confirmation SMS said "Jhagra Creation & Fabrics"; the
window title said "Jhagra Textile & Clothing — Atelier Ledger"; and the API's
`InvoiceEngine` still carried the starter template's "ATELIER TAILORING &
DESIGN STUDIO" over a "+92 300 1234567" that belongs to nobody — on a
document that goes to a customer.

`app/services/shop_identity.py` is now the only place it is written down, and
everything that prints or displays it reads from there: the window title, the
two PDF mastheads, the text receipt, the task slip, the API invoice (text and
HTML), the CLI help, the server banner, the backup filename prefix. Address
and phone are deliberately empty — a made-up phone number on a receipt is
worse than none — and the masthead skips whatever is blank, so filling them
in is all it takes. `AtelierERPApp` is `JhagraERPApp`; the migrator's default
database name is `jtq_database.db`.

**Tests** — `app/tests/test_order_reprint.py` (13) drives a real
`ExcelManager` on a temp directory: the reprint regression itself, two orders
by one customer keeping separate measurements, the profile fallback and its
flag, the all-zero snapshot, the orphaned row, the sleeve/shalwar round trip,
and the legacy column map being a genuine inverse of `customer_row` (it was
spelled out longhand in three files; one constant now).
`app/tests/test_shop_identity.py` (16) greps the source files rather than only
the constants, because the failure mode is somebody typing the name inline
again, and covers the receipt content the masthead change sits on top of.
The GUI smoke test gained six checks around the PDF, including the dingbat
one and a width check on the fallback note.

All six defects mutation-tested: re-introducing each fails exactly the tests
that name it. The dingbat mutation is the instructive one — it fails one
check out of 154, and every assertion about the text on the page still
passes.

**Verification:** unit tests **82/82** (was 51); GUI smoke **154/154** (was
146); both slip PDFs rendered and read back operator by operator to confirm
the snapshot numbers, the two extra styles, no substituted glyphs and no
column collision; dashboard screenshotted.

---

## Session — barcode, machine health, Urdu on paper, motion

- **`barcode_service.py` did not produce a barcode.** Three independent
  reasons, each fatal alone: no modulo-103 check symbol (mandatory — every
  conformant scanner rejects the label without it); a pattern table shifted
  by the ASCII offset, so `'0'` carried the pattern for *space* and every
  character would have read back as a different one; 39 of ~95 characters
  covered, with the rest falling back to `111111`; and two entries that were
  not 11 modules, so not symbols at all (its space was `211213`, 10 modules).
- Replaced with the full 106-symbol table, the check symbol, a **decoder**,
  and a real 10-module quiet zone (it left 10 *pixels*). The decoder is the
  point: it is how you prove the encoder is right rather than plausible.
- The table was **generated from `explore/barcode-rs`**, not retyped — typing
  106 six-digit patterns twice is how you end up with two different tables —
  and a test asserts the two stay identical. Cross-checked both ways: the
  Python and Rust encoders emit byte-identical widths for every sample, and
  each decodes the other's output.
- Tests check the symbology's own invariants rather than trusting the
  transcription: 11 modules per symbol, **bars totalling an even number of
  modules** (catches a transposed digit pair, which a plain sum does not),
  no duplicate rows, no element over 4 modules, and three published bit
  patterns matched exactly.

- **CPU and RAM showed a dash because psutil was never installed.** It is
  declared in `requirements.txt`; the import is deliberately guarded so a
  missing optional dependency greys out one card instead of stopping the
  app — right for the shop, useless for noticing. There is now a test that
  every declared dependency actually imports.
- **CPU then read a steady 0%.** `cpu_percent(interval=None)` reports load
  since the *previous* call, so the first is always 0.0 and the rest depend
  on when the cache happened to expire. It samples a real window now, which
  it can afford because the GUI already runs the probe off the Tk thread.
  Confirmed it tracks: 4.6% idle, 14.2% under a busy loop.
- The **GPU row showed a bare load percentage**, which reads as broken on an
  idle counter machine; it shows VRAM beside it (`0% · 0.0/4G`). The probe
  itself was always fine — it finds the Quadro M2000M.
- The five readouts are now a **two-column grid**, roughly half the height of
  five stacked rows, leaving the sidebar headroom at windowed sizes.
- Worth recording: the strip *looked* clipped in a screenshot, and it was
  not. The grab ignored this machine's 1.25 display scaling, so the image
  was short by a quarter. Measured the widget geometry before changing
  anything — the layout was fine all along.

- **Urdu reaches the printed slip for the first time.** The terms were in
  the code and never rendered: Helvetica has no Arabic script, and reportlab
  does not fail on a missing glyph — it substitutes ZapfDingbats, whose
  stand-in for a letter is a filled square. The slip printed
  `Length (■■■■■)` and every text-level assertion passed.
- `app/utils/urdu.py` does all three things that have to be right — a font
  with the glyphs, `arabic-reshaper` for cursive joining, `python-bidi` for
  right-to-left order. Any two of the three is worse than none: it prints
  isolated letters backwards, which looks deliberate. Falls back to
  romanised labels when any part is unavailable.
- Font: Nastaliq if present, else Segoe UI / Arial / Tahoma (Naskh —
  readable, not what an Urdu reader would choose). No Nastaliq face on this
  machine. The shop's own terms are **restored exactly as they were
  written** (لبادی for length, واشن for daman, بائی پا for paancha);
  several are regional rather than standard Urdu, and that is the
  shopkeeper's vocabulary, not ours to quietly correct. Nobody has ever
  seen them on paper, so they are worth a native speaker's eye now.
- Column positions measured, not eyeballed: the first attempt overlapped the
  Urdu with "Shalwar Length:" and truncated it.

- **Motion.** `app/utils/animate.py`: pages settle upward into place on a
  section change, dialogs fade up. Tk has no per-widget opacity — a frame is
  opaque, full stop — so only `Toplevel` can really fade and in-page content
  moves instead. Bound on the Toplevel class, so every dialog gets it and
  any future one comes along free.
- Every runner writes its final value as its last act, so a cancelled or
  destroyed animation cannot strand a card half-tinted or a page 18px low.
  Switchable off in Settings for slower counter machines.
- **The flag had to move out of module globals.** This file is reachable as
  both `utils.animate` and `app.utils.animate` depending on how the app was
  started (`Start.bat` does `cd app`), and Python makes those two modules
  with two sets of globals — so switching motion off through one spelling
  left the other animating. Exactly the trap the duplicate `config.py` fell
  into. It surfaced as the smoke test's layout checks failing *intermittently*
  against an animation nobody thought was running. The flag now lives on one
  process-wide object, and a test loads the module under a third name to
  prove it.
- The smoke test runs with motion off, because it asserts layout and a
  section entering is transiently offset by design; one block at the end
  turns it on deliberately and checks every section settles flush.

**Verification:** unit tests **143** (was 82); GUI smoke **162/162**, run
three times over to confirm the flakiness was gone; both slip PDFs
re-rendered and read back operator by operator (no ZapfDingbats, font
embedded, no column collision); Urdu shaping rendered to an image and
checked by eye; sidebar and Settings screenshotted with the health strip on.

---
