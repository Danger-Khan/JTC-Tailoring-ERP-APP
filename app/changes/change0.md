# Change log — part 1 of 2

Entries 0–15 of the original per-session log, consolidated into
one file. Each section below is the original `change{N}.md` reproduced
**verbatim**; only the file it lives in changed. Cross-references of the
form "continued in changeN.md" now point at a section of this file or its
sibling rather than a separate file.

Numbering is historical and never reused. New sessions are appended to the
last part as dated bullet points until it reaches ~1000 lines, at which
point the next part begins.

---

<!-- ===== originally change0.md ===== -->

# Change 0 — Urdu translations for order-card terms

**Date:** 2026-09-09

## Summary
Added ~90 Urdu translation entries to `app/lang/ur.py` for every English string
used in `app/services/order_card_service.py`: the 7 garment options, all 15
measurement field labels, all 8 style groups and their option choices, order
and delivery statuses, the 7 validation error messages, and the printed/PDF
receipt text labels.

## Why
The order card (and its underlying service module) only existed in English.
The user asked for Urdu translations for every term used there, as groundwork
for the app displaying in Urdu.

## Files touched
- `app/lang/ur.py` — added `garment_*`, `meas_*`, `style_*`, `status_*`,
  `err_*`, `receipt_*` keys to `TRANSLATIONS`.

## Verification
Visual review of the added dict (balanced braces, consistent
`"key": "value"` entries). Not yet wired into any UI at this point — that
wiring came later (see change 6). No automated test covers this file
directly.

## Note
This was translation-data-only; nothing in the app read these keys yet.

---

<!-- ===== originally change1.md ===== -->

# Change 1 — Debug pass: fixed 4 runtime bugs

**Date:** 2026-09-09

## Summary
Ran a static bug sweep across `app/` and fixed everything confirmed as a real
runtime break:

1. **`app/models/schemas.py`** — `OrderModel`, `InventoryItemModel`,
   `EmployeeModel` didn't accept fields their own routes pass in
   (`priority`/`measurements_snapshot`/`notes`,
   `item_code`/`unit_cost`/`selling_price`/`supplier`,
   `salary`/`cnic`/`current_task`/`specialization`). Every
   create/update call to `POST /api/orders/`, `POST /api/inventory/`, and
   `POST /api/employees/` was throwing an unhandled `TypeError` (500).
   Aligned all three model `__init__`/`to_dict()` methods to the full field
   sets their routes actually send.
2. **`app/routes/finance_routes.py`** — used `datetime.now()` with no
   `datetime` import; `POST /api/finance/expense` crashed with `NameError`
   whenever a caller omitted `date` (the documented default path). Added
   `from datetime import datetime`.
3. **`app/utils/logger.py`** — missing `from typing import List`, which
   crashed the whole Flask app on boot. Added the import.
4. **`app/tests/test_order_workflow.py`** — a stale assertion was checking
   the wrong data; corrected it.

**Flagged but intentionally not changed:** `app/security/auth.py`'s
`verify_token()` accepts any non-empty token as a valid Administrator login
— a real gap between intent and implementation, but changing auth behavior
is a judgment call for the user, not an obvious bug fix.

## Why
User asked to "test run analyze optimize and debug all." A background static
sweep found these; each was verified by direct reproduction before fixing.

## Files touched
- `app/models/schemas.py`
- `app/routes/finance_routes.py`
- `app/utils/logger.py`
- `app/tests/test_order_workflow.py`

## Verification
- Full pytest suite: 12/12 passed.
- GUI smoke test (`app/tests/gui_smoke_test.py`): 23/23 passed.
- End-to-end verification via a real Flask test client hitting the actual
  routes (not just constructing the model classes directly):
  `POST /api/employees/` → 201 with all fields persisted and round-tripped
  correctly; same for `POST /api/inventory/` and `POST /api/orders/`.

---

<!-- ===== originally change2.md ===== -->

# Change 2 — Order card: removed per-order Measurements section (v1)

**Date:** 2026-09-09

## Summary
Removed the "3 · Measurements" input section from the Order Card screen
(`app/views/order_card_view.py`). In its place, added a read-only "Saved
Measurements" block in the Customer Information section that auto-fills from
the selected customer's own record once a customer is chosen.

(Note: this display block was itself removed later — see change 5 — once the
user pointed out it duplicated what's already visible on the Customer card.)

## Why
User asked to remove measurements from the order card and use the value
already saved in the customer section instead of re-entering it per order.

## Files touched
- `app/views/order_card_view.py`

## Verification
- Full pytest suite: 12/12 passed.
- GUI smoke test: 23/23 passed (including dark theme, both Add modals).

---

<!-- ===== originally change3.md ===== -->

# Change 3 — Data incident: stray data folder corrupted by my own test scripts, restored

**Date:** 2026-09-09

## Summary
While verifying the change 1 API fixes with ad-hoc Flask test-client scripts,
a pre-existing quirk in this codebase (`app/utils/excel_db.py` imports
`Config` via `from config import Config` rather than `from app.config import
Config`, unlike most other files) meant my attempt to redirect those test
writes to a temp directory didn't fully take effect. The writes landed in a
second, stray `data/` folder at the project root
(`ERP PY APP\data\`, separate from the real one at `app\data\`), overwriting
`employees.xlsx`, `inventory.xlsx`, and `orders.xlsx` there with test data,
and creating a new `system_audit.log`.

The app's real data (`app\data\*.xlsx`, confirmed against what the GUI smoke
test seeds/expects) was never touched.

Restored `data\employees.xlsx`, `data\inventory.xlsx`, and `data\orders.xlsx`
from the pre-test backups that `ExcelDB._backup()` automatically saved into
`data\backups\` before each of my writes, and deleted the stray
`system_audit.log`. Confirmed with user before restoring.

## Why
Transparency: my own testing caused this, so it's logged like any other
change even though it's a data-integrity fix rather than a feature change.

## Files touched (restored, not newly modified)
- `data\employees.xlsx`
- `data\inventory.xlsx`
- `data\orders.xlsx`
- `data\system_audit.log` (deleted — didn't exist before)

## Verification
Read back all three restored files with openpyxl: confirmed 0 rows / blank
headers, matching their true pre-session state (this stray folder was
already unpopulated/unused before my session — the backups prove the
pre-existing content was blank, not that real data was lost).

## Lesson applied going forward
Sandbox live-testing more carefully — verify which `Config`/data-dir a test
script actually resolves to before writing, rather than assuming an override
took effect.

---

<!-- ===== originally change4.md ===== -->

# Change 4 — UI visual-consistency / dark-mode polish pass

**Date:** 2026-09-09

## Summary
Ran a background audit of `app/main_gui.py` for visual-consistency and
dark-mode-safety issues (explicitly excluding `order_card_view.py`, per
user's instruction not to touch that screen's patterns). Fixed the
highest-impact findings, all cosmetic only:

1. Every `tk.Entry` field (login password, customer search, garment/role
   inputs, all Add/Edit modal fields) now themes correctly — previously
   stayed white-on-black regardless of theme.
2. `ttk.Combobox` fields and their dropdown lists now theme correctly
   (status/theme/language/role/staff pickers).
3. Dashboard donut-chart "track" ring now uses the theme border color
   instead of a hardcoded light gray.
4. Edit Customer / Edit Staff dialogs now match the Add dialogs' button
   style (full-width, `cursor="hand2"`, bold font) and label font.
5. Search "Clear" button now has a visible border instead of blending into
   the background in dark mode.
6. Minor sizing consistency: dashboard "Mark Ready" button and the Customer
   Hub search label now match their equivalents elsewhere.

## Why
User asked for a UI polish/consistency pass on the app (excluding the order
card and new customer card's fields/patterns/values, cosmetic changes only
there).

## Files touched
- `app/main_gui.py`

## Verification
- Full pytest suite: 12/12 passed.
- GUI smoke test: 23/23 passed, including explicit dark-theme and both
  Add-modal checks.

## Deferred (lower priority, flagged not done)
Card padding standardization (dashboard vs. settings cards), a formal
button-size tier system, per-column Treeview widths, and confirming/removing
`open_add_order_modal` (looks like dead code superseded by the Order Card
screen).

---

<!-- ===== originally change5.md ===== -->

# Change 5 — Order card: fully removed measurement display; New Customer modal: added Address

**Date:** 2026-09-09

## Summary
Two related fixes:

1. **Order Card** (`app/views/order_card_view.py`): removed the "Saved
   Measurements" read-only display block added in change 2 — it duplicated
   what's already shown on the Customer card, so the user asked for it to
   be dropped from the order card entirely. The underlying behavior is
   unchanged: saving an order still snapshots the selected customer's
   current measurements into `measurements.xlsx` via a new
   `_customer_measurements()` helper that looks the values up directly from
   `self.app.customers`, it just isn't shown on screen anymore.
2. **New Customer modal** (`app/main_gui.py`,
   `open_add_customer_modal`): found and fixed a real gap — the customer
   schema (`cust_headers`) has always included `address` and `created_date`
   columns, but the modal never collected them, so every customer created
   through it silently got a blank address forever. Added an **Address**
   field to the form, and `created_date` now auto-fills to today's date
   (matching how dates are auto-set elsewhere in the app).

## Why
User: "remove the length and sizes from order card it is already there in
new customer card and in new customer card do must add the address and
other details."

## Files touched
- `app/views/order_card_view.py`
- `app/main_gui.py`

## Verification
- Full pytest suite: 12/12 passed.
- GUI smoke test: 23/23 passed.
- Targeted script confirming: no `cust_meas_entries` widgets remain on
  `OrderCardView`; customer info (incl. address) still auto-fills on
  selection; `collect_form()` still supplies all 9 mapped measurements
  sourced from the customer record; a full order save still writes a
  correct measurement snapshot to `measurements.xlsx`.
- Separate targeted script confirming the New Customer modal now saves
  `address` and `created_date` correctly to `customers.xlsx`.

---

<!-- ===== originally change6.md ===== -->

# Change 6 — Full Urdu/English i18n wiring for Order Card + New Customer modal

**Date:** 2026-09-09

## Summary
Previously only the Order Card's title/subtitle actually translated on a
language switch; everything else (section headers, field labels, garment and
style chip text, buttons, dropdowns) and the entire New Customer modal stayed
in English regardless of the selected language. Wired up full translation
for both screens:

- **`app/views/order_card_view.py`** (substantial rewrite): all 6 section
  headers, every field label, all garment chips, all style-group labels and
  their option chips across all 8 groups, and the 3 action buttons now
  re-render via `set_language()`.
  - `ChipGroup`/`ChipCheckGroup` were refactored to separate a chip's
    canonical stored *value* from its displayed *label*, with a new
    `relabel()` method that updates on-screen text without touching the
    selection or the underlying value.
  - New `TranslatedCombobox` wrapper does the same for the Order
    Status / Delivery Status dropdowns.
  - This decoupling matters because `main_gui.py` elsewhere compares status
    strings literally in English (dashboard charts, row coloring, the "Mark
    Ready" quick-action) — translating the *displayed* text without this
    separation would have caused orders saved while in Urdu mode to store
    Urdu status/garment/style text and silently vanish from those
    English-keyed comparisons.
- **`app/main_gui.py`**, `open_add_customer_modal`: now builds using
  `TRANSLATIONS[self.current_lang]` (merged with English fallback) so it
  opens in whichever language is currently active — title, heading,
  Name/Phone/Address labels, all 9 measurement labels (replacing the old
  hardcoded mixed English/Urdu-script hint text), and the Save button.
- **`app/lang/en.py`**: added the English versions of every new key
  (mandatory — the app's language-merge logic does direct `dict[key]`
  lookups, so a key missing from `en.py` would `KeyError` even in English
  mode).
- **`app/lang/ur.py`**: added the remaining `oc_*` (order-card chrome) and
  `nc_*` (new-customer modal) keys not already added in change 0.

## Why
User: "i need this all change to urdu as well when i cange from en to ur,"
referencing screenshots showing the Order Card and New Customer modal
mostly still in English after a language switch.

## Files touched
- `app/views/order_card_view.py`
- `app/main_gui.py`
- `app/lang/en.py`
- `app/lang/ur.py`

## Verification
- Full pytest suite: 12/12 passed.
- GUI smoke test: 23/23 passed.
- A 28-check targeted script covering: EN baseline text/values, switching to
  UR via the real UI control path, every section header/field
  label/chip/button/dropdown showing translated text, selection state
  surviving the relabel, canonical English values still returned by
  `.selected()`/`.get()` while UI is in Urdu, the New Customer modal opening
  in Urdu, a full order save performed while in Urdu mode confirmed to land
  in `orders.xlsx` still in English (garment/status/style columns), and
  switching back to English restoring everything cleanly.

## Explicitly out of scope (flagged, not done)
Validation error messages and the printed/PDF receipt text
(`order_card_service.py`) are not translated — that module is shared
between the desktop GUI and the Flask API, so wiring translation into it
needs more care than the screenshots called for. `ur.py` already has the
Urdu strings ready (`err_*`, `receipt_*`) if this is wanted next. Pashto,
Chinese, and Russian language packs were not updated for the new keys —
they safely fall back to English, consistent with the app's existing
partial-language-pack design.

---

<!-- ===== originally change7.md ===== -->

# Change 7 — Employee section i18n + Assign Task now links real orders

**Date:** 2026-09-09

## Summary
- **Employee section translation** (matching the Order Card/New Customer depth): Print/Edit/Delete buttons, all 6 employee table column headers, and all 3 employee modals (Add Staff, Assign Task, Edit Staff Member) now translate on language switch — titles, field labels, buttons. Added `emp_*`/`tbl_emp_*`/`task_*`/`btn_save_changes` keys to `en.py` + `ur.py`.
- **Assign Task redesigned**: instead of typing free-text, it now shows a dropdown of open (non-Delivered) orders labeled by **customer name** ("ORD-101 — Ayesha Khan (Kameez)"); picking one shows a read-only details panel (garment, status, order/delivery date, currently assigned tailor, total/advance/remaining) and auto-fills an editable task note — same pattern as the order card's customer auto-fill.
- Confirming now links **both** sides: sets the order's `tailor` field (new `_assign_order_tailor()` helper, mirrors the existing `quick_change_order_status()` pattern) and the employee's `current_task`/status (existing `update_employee_task()`, unchanged). Since the Dashboard's Active Orders Ledger reads `self.orders` live, the new tailor assignment shows up there immediately after reload — no dashboard code needed changing.

## Why
User: employee-section translation parity with the other screens, then: "connecting the employee section taking order from customer... by name... pop its details like order card... assign the work to it... linked to the main dashboard."

## Files touched
- `app/main_gui.py` (`apply_language_pack`, `open_add_employee_modal`, `open_assign_task_modal` rewritten, `edit_selected_employee`, new `_assign_order_tailor`)
- `app/lang/en.py`, `app/lang/ur.py`

## Verification
- pytest: 12/12. GUI smoke test: 23/23.
- Targeted script (14 checks, 13 pass — 1 "failure" was my own test's wrong assumption about pre-existing untranslated header casing, not an app bug): EN baseline, all UR translations for buttons/headers/3 modals, EN-restore.
- Targeted script (9/9 checks) for the Assign Task redesign: order dropdown shows customer names, selecting one auto-fills details + task note, saving writes the tailor to `orders.xlsx` and the task/status to `employees.xlsx`, and the Dashboard ledger shows the new tailor after reload.

---

<!-- ===== originally change8.md ===== -->

# Change 8 — Soft-glass UI styling (whole app)

**Date:** 2026-09-09

## Summary
- Retuned `THEMES` (light + dark) in `main_gui.py` to a soft frosted-tint palette: cooler/softer `bg_body`, `bg_header`, `bg_sidebar`, `bg_card`, `bg_chart`, and lower-contrast `border` colors. Added a new `glass_highlight` token per theme for a thin light-catching strip. `text_main`/`text_muted` and the semantic accent colors (PRIMARY/SUCCESS/WARNING/DANGER) were left untouched — legibility and status-color meaning never traded away for looks.
- New `AtelierERPApp._glass_card()` helper: wraps a frosted shell (soft bg + soft border + 2px top highlight strip) around an inner content frame. Returns the inner frame so every caller keeps adding children exactly as before — zero layout/behavior changes. Applied to the 3 dashboard stat tiles, all 4 Settings cards, and the Assign Task modal's order-details box.
- Applied the same treatment to `order_card_view.py`'s centralized `_card()` helper (used by all 6 order-card sections).
- **Bug found + fixed while visually reviewing dark mode**: several `tk.Entry` fields in the order card (Date, Assign Tailor, Total, Advance) had a hardcoded/missing background, making dark-theme text nearly invisible against a stray white field. Also added `readonlybackground` to the read-only fields (Customer ID/Name/Mobile/Address), which Tkinter needs separately from `bg` for `state="readonly"` Entries — fixes an inconsistent gray look in light mode too.
- Fixed `gui_smoke_test.py`'s theme-check assertions, which hardcoded the old hex values; now compare against `gui.THEMES[...]` directly so future palette tweaks won't stale them out.

## Why
User: "do gui improvement i want soft glass morph texture without disturbing any content." Tkinter has no real background blur/transparency, so this is an approximated glass look via color/border choices only, confirmed with the user first (whole-app scope, faux-glass approach) since a literal blur hack would require restructuring cards onto Canvas.

## Files touched
- `app/main_gui.py` (THEMES, new `_glass_card`, 8 call sites)
- `app/views/order_card_view.py` (`_card`, `_row_entry`, `ent_total`/`ent_advance`)
- `app/tests/gui_smoke_test.py` (2 stale assertions)

## Verification
- pytest: 12/12. GUI smoke test: 23/23.
- Actually launched the real app on-screen (not headless) and captured real screenshots via PIL.ImageGrab (DPI-scale-corrected for this machine's 1.25x scaling) — Dashboard, Order Card, and Settings, in both light and dark mode. Visually confirmed the soft-glass cards render correctly and caught the Entry dark-mode bug this way before calling it done.

---

<!-- ===== originally change9.md ===== -->

# Change 9 — Finance view + Dashboard finance card (SQLite-backed)

**Date:** 2026-09-10

## Summary
- New `app/utils/finance_db.py` (`FinanceDB`): a small SQLite database
  (`finance.db`, colocated with whichever data dir `ExcelManager` currently
  points to) holding one `order_finance` row per order — `total`, `paid`,
  `remaining`, `debt`. Orders/customers stay in Excel as the source of
  truth; this table is fully recomputed from live order records on every
  `sync()` call (cheap — one `DELETE` + `executemany` per reload), so it's
  always a mirror, never a second source of truth to keep in sync by hand.
  Totals and per-order rows are read back out with real SQL
  (`SUM(...)`, `ORDER BY`), not recomputed ad hoc in Tkinter code.
- **Definitions** (confirmed with the user before building): `paid` = an
  order's advance/amount collected. `remaining` = unpaid balance on an
  order **not yet delivered** (normal, expected). `debt` = unpaid balance
  on an order that **has been delivered/handed over** (or partially) — the
  customer already has the goods but still owes money, i.e. real
  receivable risk, tracked separately from ordinary WIP `remaining`.
- `main_gui.py`: `reload_all_data()` now calls
  `FinanceDB.sync(self.orders, self.customers)` at the end of every data
  load (login, the 5s auto-refresh loop, every order/customer/employee
  write) — non-fatal on failure so a locked `finance.db` never blocks the
  rest of the app.
- New **Finance** section (new sidebar nav entry, between Employees and
  Settings): 3 glass summary cards (Total Paid / Total Remaining / Total
  Debt) + a per-order ledger table (order, customer, garment, total, paid,
  remaining, debt, status, delivery status), red/orange row-tinted by
  whether that order carries debt or just remaining balance.
- **Dashboard**: new finance snapshot row (3 glass cards, same numbers) added
  directly under the existing WORK DONE / IN PROGRESS / REMAINING row, so
  the money picture is visible without leaving the Dashboard.
- Both the Finance section and Dashboard finance cards are refreshed by one
  shared `refresh_finance_ui()`, called from the existing
  `update_graphics_and_stats()` — no new refresh loop, reuses the app's
  existing "data changed -> repaint" path.
- Full i18n: new `nav_finance`, `dash_fin_*`, `fin_*` keys added to both
  `app/lang/en.py` and `app/lang/ur.py` (nav label, section title/subtitle,
  card titles, table headers) and wired into `apply_language_pack()`.
- New cards use the existing `_glass_card()` helper, so they match the
  soft-glass styling from change8 in both light and dark theme automatically.

## Why
User: "in the apk i need the finance view card. that will need to track the
finance of customer order, the one paid, the one remaining and the one
debt. also need its update on main dashboard card. do manage the
background of the finance and numerical values related to finance in sql
format." Clarified with the user first: debt = delivered-but-unpaid vs.
remaining = still-in-progress-and-unpaid (not the same number shown
twice), and "SQL format" = a real local SQLite database for the finance
figures specifically (not just formatting numbers), while Excel stays the
source of truth for orders/customers everywhere else in the app.

## Files touched
- `app/utils/finance_db.py` (new)
- `app/main_gui.py` (import, `_finance_db_for_current_data`, finance sync
  hook in `reload_all_data`, Dashboard finance row, new
  `build_finance_section`/`refresh_finance_ui`, nav entry, language wiring)
- `app/lang/en.py`, `app/lang/ur.py` (new finance keys)
- `app/tests/gui_smoke_test.py` (second seeded order — Delivered with an
  unpaid balance — plus new checks for the Finance section and its totals)

## Verification
- pytest: 12/12. GUI smoke test: 29/29 (6 new checks: finance section nav,
  finance section visible, total paid/debt/remaining computed correctly
  from two seeded orders — one active+partially paid, one delivered+unpaid
  — and the ledger table row count).
- Actually launched the real app on-screen and screenshotted Dashboard and
  Finance in light mode, dark mode, and Urdu: confirmed the numbers match
  the seeded data (PKR 3,000 paid / 2,000 remaining / 3,000 debt), the
  delivered order's balance lands in the Debt column (not Remaining), the
  Urdu labels and RTL order-ID/customer table render correctly, and both
  themes stay legible.

---

<!-- ===== originally change10.md ===== -->

# Change 10 — Icons added across the UI (chrome only, no field/value changes)

**Date:** 2026-09-10

## Summary
Added emoji icons wherever they fit naturally, matching the style already
used by buttons like `➕ Add Customer` / `🖨️ New Order Card`:

- **Sidebar nav** (all 6 items, incl. the new Finance tab): 📊 Dashboard,
  👥 Customers, 📝 Order Card, 👷 Employees, 💰 Finance, ⚙️ Settings.
- **Dashboard stat cards**: ✅ Work Done, ⏳ In Progress, ⏰ Remaining, plus
  the finance snapshot row: 💵 Total Paid, ⏳ Total Remaining, ⚠️ Total Debt.
- **Finance view** summary cards get the same 💵/⏳/⚠️ treatment.
- **Action buttons** that previously had no icon: Edit (✏️), Delete (🗑️),
  Print Latest Receipt / Print Task Slip (🧾), Save Staff / Save Changes /
  Save Customer / Save Order (💾), Clear Form / Clear search (🧹 / ✖),
  Assign Task submit (✅), Place Order (✅), Login to Dashboard (🔐).
- **Order Card section headers** (chrome only — "1 · Customer Information"
  etc.): 👤 Customer Information, 👕 Garment Type, 🎨 Style Options,
  📝 Special Notes, 🚚 Delivery, 💳 Payment.
- **New Customer modal**: 📋 Register Measurements (window title),
  📏 Customer Profile & Measurements (heading), 💾 Save Customer.
- **Add/Edit Staff and Assign Task modal** titles/headings/buttons.
- Every icon added to a lang-driven string went into **both**
  `app/lang/en.py` and `app/lang/ur.py`, so it survives switching to Urdu
  (icons themselves don't need translating — same emoji, translated text).

**Deliberately left untouched** (per the standing "don't change order
card / new customer card patterns, blanks or values" instruction): the
actual field labels (Name, Mobile Number, Date, etc.), the garment/style
selection chips (Kameez, Shalwar, Baz Button, Normal, ...), and status
values. Icons only went on section headers and action buttons — chrome,
not the form itself. Table column headers were also left plain (no
existing precedent for per-column icons in this app).

## Why
User: "add icons where possible" — a follow-on visual-polish pass after
the soft-glass styling (change8) and the new Finance view (change9).

## Files touched
- `app/lang/en.py`, `app/lang/ur.py` (icon prefixes on ~35 nav/button/
  header/card-title keys)
- `app/main_gui.py` (icon prefixes on the handful of hardcoded button
  strings not sourced from the lang dict: login button, customer
  Edit/Delete/Print Latest Receipt, search Clear, Place Order, the
  customer-edit dialog's Save Changes)
- `app/tests/gui_smoke_test.py` ("english nav restored" now checks
  `"Dashboard" in text` instead of exact equality, since the nav label is
  now `"📊 Dashboard"`)

## Verification
- pytest: 12/12. GUI smoke test: 29/29.
- Launched the real app on-screen and screenshotted Dashboard, Customers,
  Employees, Finance, Order Card, and the New Customer modal: confirmed
  every icon renders correctly (Windows' Segoe UI Symbol/Emoji fallback
  draws them cleanly), buttons stay readable at their existing size, and
  no order-card or new-customer field/value/pattern changed — only
  section headers and action-button chrome gained icons.

---

<!-- ===== originally change11.md ===== -->

# Change 11 — Session persistence, Finance tabs + Add Payment, tri-color accent (part 1 of 2, continued in change12.md)

**Date:** 2026-09-18

## Summary

### 1. Settings/session persistence ("memory/cache file")
New `app/utils/app_state.py` (`AppStateCache`): a small JSON cache file at
`<data_dir>/cache/app_state_cache.json` holding theme, language, the last
open sidebar section, and window geometry. Loaded once at startup (before
the login screen is even shown, so the very first frame already reflects
last session's theme/language) and written back on every change that
matters: theme switch, language switch, section navigation, and on window
close (`WM_DELETE_WINDOW` now runs `on_app_close()`, which saves once more
before destroying, catching anything the per-action saves might have
missed). Closing and reopening the app now reliably lands back on the same
theme, language, section, and window size/position instead of always
resetting to English/Light/Dashboard/default size.

As a side effect of fixing this properly (see the bug note below), a
pre-existing rough edge got fixed too: switching theme used to always snap
the view back to Dashboard, because `build_ui_layout()` hardcoded
`show_section("dashboard")`. It now reopens on `self.current_section`
(tracked by `show_section()` itself), so a theme toggle keeps you exactly
where you were, and that's also the value written to the session cache.

### 2. Finance: Done / Due / Add Payment tabs
The Finance view now has a small tab bar above the ledger table: **All**,
**✅ Done**, **⚠️ Due**, and **➕ Add Payment**.
- **Done** filters to orders that are fully settled (`remaining <= 0`,
  `debt <= 0`, and `total > 0` — the total>0 guard excludes blank/legacy
  rows with no financial data at all from counting as "done").
- **Due** filters to orders carrying any outstanding balance (`remaining >
  0` or `debt > 0`), whether that balance is ordinary work-in-progress
  remaining or delivered-and-unpaid debt.
- **Add Payment** swaps the ledger table out for a small form: a dropdown
  of only the orders that currently have a due balance (labelled with the
  order, customer, and amount due), a payment-amount field, and a
  **💾 Record Payment** button.

New `main_gui.py` methods: `set_finance_tab(tab_key)` (switches which
container is shown and restyles the active tab button),
`_refresh_finance_payment_picker()` (rebuilds the due-orders dropdown from
`FinanceDB.get_rows()`), and `record_finance_payment()` — this increases
the selected order's `advance` field by the entered amount (capped at the
order's `total` so it can never go negative-remaining), recomputes
`remaining` via the existing `order_card_service.compute_remaining()`
helper, and writes the order back to `orders.xlsx` using the same
schema-aware full-row rewrite pattern already used by
`quick_change_order_status()` and `_assign_order_tailor()` (rebuild every
column from `ord_headers`, mutate only the two financial fields). After
saving it reloads all data (which re-syncs `finance.db`) and refreshes the
UI, so the Dashboard finance card, the Finance totals, and the ledger all
update immediately. `refresh_finance_ui()` now also takes the active tab
into account when populating `tree_finance`, instead of always showing
every order.

All four tab labels and the Add Payment form's labels are fully wired
through the existing `en.py`/`ur.py` translation dictionaries and
`apply_language_pack()`, matching the depth of i18n already done for the
rest of the app this session.

### 3. UI appeal and flexibility
- New thin **blue / white / red accent strip** (`_create_accent_strip()`)
  along the very top edge of the window, above the header bar — a small
  brand-color signature drawn from three equal segments, rebuilt on every
  theme switch alongside the rest of the layout. Purely decorative; it
  doesn't touch the header, sidebar, or any content.
- **Sidebar nav hover feedback**: nav buttons now lightly tint
  (`bg_chart`) on mouse-over when they aren't the already-active section,
  and revert on mouse-out — a small "the UI feels alive" touch that costs
  nothing structurally (bound via `<Enter>`/`<Leave>`, no layout change).
- **`self.minsize(1100, 700)`** so the window can be resized more freely
  without its own content starting to clip, and the saved geometry from
  the session cache is applied before the window is ever shown, so a user
  who prefers a bigger or smaller window keeps it every time.

### 4. Bug found and fixed while building the above
While wiring the settings cache, testing surfaced a real bug: `main_gui.py`
originally created `self.app_state = AppStateCache(self.excel_mgr.data_dir)`
**once**, eagerly, in `__init__` — before the GUI test suite (or anything
else) gets a chance to point `self.excel_mgr` at a different data
directory. Every later `.save()` call kept writing to that first-bound
path regardless of what `excel_mgr` later became, which meant the
permanent GUI smoke test was — silently — writing a real
`app/data/cache/app_state_cache.json` file into the actual production data
folder on every run, exactly the class of mistake flagged as a lesson in
an earlier session (change3.md: sandbox test writes more carefully). It
never touched customer/order/employee data and the written values were
always harmless defaults, but it was still the app leaking test state into
real storage.

Fixed by giving `app_state` the same lazy-rebind pattern `finance_db`
already used: a new `_app_state_for_current_data()` method that
(re)creates the `AppStateCache` against whichever directory
`self.excel_mgr.data_dir` currently points to, and every `.save()`/`.load()`
call site now goes through that accessor instead of touching
`self.app_state` directly. A second, smaller issue in the same vein was
also fixed: `AppStateCache.__init__` used to call `os.makedirs()`
immediately on construction (even for a read-only `.load()` that finds
nothing), which alone was enough to leave a stray `cache/` folder behind
in the real data dir the instant the app started — now only `save()`
creates the directory, so a session that never changes a setting never
touches the filesystem at all. The stray file this created during today's
own testing was deleted, and a fresh smoke test run was confirmed to leave
`app/data/` completely untouched afterward.

*(continued in [change12.md](change12.md): Documentation, Why, Files
touched, Verification)*

---

<!-- ===== originally change12.md ===== -->

# Change 12 — Session persistence, Finance tabs + Add Payment, tri-color accent (part 2 of 2, continued from change11.md)

**Date:** 2026-09-18

## Summary (continued)

### 5. Documentation
`app/README.md`, `app/readme.txt`, and `app/readme.me` all rewritten to
match the app as it actually stands today: the Finance section and its
SQLite ledger, the session-persistence cache, the soft-glass theme (in
place of the old "Apple Glass Light" description), the tri-color accent,
and an honest language note (English and Urdu are fully translated;
Pashto/Chinese/Russian are selectable in the picker but currently fall
back to English). `readme.me` also had a leftover line of AI-scaffolding
text at the top ("Here is an updated, comprehensive README.md tailored
specifically for...") removed, and its stale theme-color table updated to
the current soft-glass palette.

## Why
User asked, in one request: (1) persist app settings/memory across
restarts in a cache file, (2) make the UI a little more appealing and
flexible, (3) add Finance tabs "like done, due, add", (4) split any
changelog file that exceeds 1000 words into sequential continuation
files — and, mid-turn, also asked to (5) update all README files and the
smoke test, and (6) work three brand colors — blue, red, white — into the
main theme. Per the standing "auto everything" instruction for this turn,
reasonable calls were made throughout without pausing for clarification
(e.g. Done/Due definitions reused the paid/remaining/debt semantics
already agreed in change9; the tri-color treatment was implemented as a
restrained accent strip rather than recoloring existing semantic colors,
since PRIMARY/DANGER already anchor blue/red and repurposing them for
brand color would have muddied their existing status meaning).

## Files touched
- `app/utils/app_state.py` (new)
- `app/main_gui.py` (session cache load/save + lazy rebind, accent strip,
  nav hover, minsize, Finance tab bar + Add Payment form + filtering,
  `on_app_close`, `build_ui_layout` reopens on last section)
- `app/lang/en.py`, `app/lang/ur.py` (finance tab + Add Payment form keys)
- `app/tests/gui_smoke_test.py` (third seeded order for a clean Done case,
  Finance tab filter checks, Add Payment flow check, session-cache
  round-trip checks)
- `app/README.md`, `app/readme.txt`, `app/readme.me` (full rewrite to
  match current features)

## Verification
- pytest: 12/12. GUI smoke test: 39/39 (10 new checks: three Finance tab
  filters, the Add Payment picker + submit + persisted result, and four
  session-cache checks).
- Confirmed — after the fix — that a full smoke test run leaves
  `app/data/` completely untouched (`Test-Path app/data/cache` is `False`
  before and after).
- Launched the real app on-screen and screenshotted: the tri-color accent
  strip on the Dashboard; the Finance view's Done tab (showing only the
  fully-paid seeded order) and Add Payment tab (showing the one seeded
  order with a due balance, pre-filled and submittable); and a simulated
  reopen — construct a fresh app instance, rebind its session cache to the
  same data dir, reload the saved state, and re-render — which correctly
  came back in Dark theme on the Finance section, confirming the
  persistence mechanism actually drives what's on screen, not just what's
  in the JSON file.

---

<!-- ===== originally change13.md ===== -->

# Change 13 — Remaining button translations wired, monochrome retheme

**Date:** 2026-09-18

## Summary

### 1. Closed remaining translation gaps
User asked for Add/Delete/Remove translations "by their each individual
card" for Staff, Employee, Customer, and the Dashboard/Finance/Settings
cards. Dashboard/Finance/Settings titles and Employee's Edit/Delete/Print
were already wired (change9/change10); the real gaps closed here:
- **Customer section**: Edit, Delete, and Print Latest Receipt buttons
  were hardcoded English regardless of language — now driven by new
  `cust_btn_edit`/`cust_btn_delete`/`cust_btn_receipt` keys, wired at both
  construction time and in `apply_language_pack()`.
- **Settings**: the Garment Types / Employee Roles card titles and their
  Add/Remove buttons were hardcoded too — now `admin_card_garments`,
  `admin_card_roles`, and shared `btn_item_add`/`btn_item_remove` keys
  (four button widgets captured as `self.btn_add_garment`/
  `btn_remove_garment`/`btn_add_role`/`btn_remove_role` so language switch
  can reach them).
- Bigger find while auditing: `btn_add_cust`, `btn_new_card`,
  `btn_assign_task`, `btn_add_emp`, and the Dashboard ledger's table
  headers (`tbl_ord_id`/`tbl_cust`/`tbl_garment`/`tbl_status`/`tbl_tailor`)
  didn't exist in `ur.py` at all — switching to Urdu silently left these
  showing English (the merge-fallback logic masks a missing key instead of
  erroring). Added all of them to `ur.py`.

### 2. Monochrome retheme (from a reference design)
User shared several screenshots of a flat black/white/gray SaaS-style
reference ("Farman Clothes") and asked the app look closer to it, keeping
all content — especially the Order Card — unchanged. Implemented as a
palette/chrome retune, not a content rebuild:
- **`PRIMARY` changed from blue (`#007AFF`) to near-black (`#111214`)**.
  Because `PRIMARY` already drives the nav active pill, primary buttons,
  Treeview/Combobox selection color, and (passed through as a constructor
  arg) the Order Card's selected style chips, this single constant change
  cascades correctly everywhere without touching call sites — nav active
  state and primary CTAs now read as black-on-white, matching the
  reference.
- **`THEMES` light palette retuned** to a flatter, cooler white/gray:
  `bg_body #F7F8FA`, `bg_card #FFFFFF` (pure white, was an off-white
  blue-tinted `#FAFBFF`), `border #E5E7EB`, `text_main #111214`,
  `text_muted #6B7280`, `bg_chart #F3F4F6`. Dark theme similarly moved off
  its navy tint toward true near-black/gray (`bg_body #121212`,
  `bg_card #1E1E21`, `border #333333`).
- **`_glass_card()` (main_gui.py) and `_card()` (order_card_view.py)
  flattened**: removed the 2px "glass_highlight" top strip both drew,
  leaving a plain soft-bordered flat card — closer to the reference's flat
  cards than the previous frosted-glass look. Both keep their exact same
  shell+inner-frame signature, so every existing caller (dashboard tiles,
  settings cards, Finance cards, all 6 order-card sections) needed zero
  changes.
- **`ACCENT_BLUE`/`ACCENT_RED` decoupled from `PRIMARY`/`DANGER`**: the
  tri-color accent strip added earlier this session was tied to those two
  constants; now hardcoded to their original blue/red values directly, so
  it stays a genuine blue/white/red strip regardless of how the main
  palette gets retuned going forward.
- **Order Card deliberately untouched in every other respect**: same
  fields, same labels, same garment/style options, same values, same
  validation — only the shell color/border it sits in changed, per the
  standing "don't change order card patterns/blanks/values" instruction.

### 3. README color tables updated
`app/README.md`, `app/readme.txt`, and `app/readme.me` all updated to
describe "flat monochrome" instead of "soft-glassmorphism" and to list the
new hex values, with a note that the accent strip is intentionally
independent of the retuned Primary/Danger tokens.

## Why
Two follow-on requests in the same sitting as change11/12: (1) "make
translations for the options of like delete add remove staff, employee,
customer, dashboard, finance, settings by their each individual cards" —
closing the specific gaps found; (2) a shared reference-design screenshot
with "make it somehow closely to this gui while keeping the content as it
is specially order card" — a palette/chrome retune rather than a layout
rebuild, since the reference's actual information architecture (client
photo upload, referral source, garment "architecture" picker cards, etc.)
differs from this app's own screens and the user explicitly said to keep
content as-is.

## Files touched
- `app/main_gui.py` (button/label wiring for the translation gaps;
  `PRIMARY`, `THEMES`, `ACCENT_BLUE`/`ACCENT_RED`, `_glass_card`)
- `app/views/order_card_view.py` (`_card()` flattened)
- `app/lang/en.py`, `app/lang/ur.py` (new + backfilled keys)
- `app/README.md`, `app/readme.txt`, `app/readme.me` (palette description)

## Verification
- pytest: 12/12. GUI smoke test: 39/39 (unchanged — palette/wording
  changes don't touch the checks, and `gui_smoke_test.py`'s theme
  assertions already compare against `gui.THEMES[...]` directly rather
  than hardcoded hex, so a palette retune never staled them).
- Launched the real app on-screen and screenshotted Dashboard, Order Card,
  Settings, and Employee in both Light and Dark: confirmed the black
  active-nav pill, flat white cards, and black primary buttons read
  cleanly against the reference direction, the tri-color strip still
  shows true blue/white/red, and the Order Card's fields/values/layout
  are pixel-identical to before except for the new flat card color.

---

<!-- ===== originally change14.md ===== -->

# Change 14 — Reverted retheme colors, added donut circles to Dashboard finance cards

**Date:** 2026-09-18

## Summary
- **Reverted the monochrome retheme from change13**: user clarified the
  reference-design ask was about column/block *layout*, not color — "the
  original coloring was good." Restored `PRIMARY` to blue (`#007AFF`), the
  original soft-glass `THEMES` palette (light + dark), and the
  light-catching `glass_highlight` top strip on cards in both
  `main_gui.py`'s `_glass_card()` and `order_card_view.py`'s `_card()`
  (both had been flattened). `ACCENT_BLUE`/`ACCENT_RED` for the tri-color
  header strip stay hardcoded independently of `PRIMARY`/`DANGER` as
  before — harmless now that they match again, but keeps the strip safe
  from future palette retuning either way. README color tables reverted
  to match. Analyzed the reference screenshots for their actual
  column/block layout patterns (two-column page splits, compound table
  cells, status pills, paired footer utility cards, sidebar profile block,
  segmented card-header tabs, pagination) and reported them back rather
  than guessing which to build next.
- **Added donut circles to the Dashboard's finance snapshot cards**,
  matching the existing Work Done / In Progress / Remaining donuts: each
  of Total Paid / Total Remaining / Total Debt now has a
  `CircularDonutChart` showing that bucket's share of the shop's total
  order value (`paid + remaining + debt`), colored the same as its label
  (green/orange/red). Computed and set in `refresh_finance_ui()` alongside
  the existing PKR labels — no new refresh path.

## Why
Two follow-on corrections/requests: "i mean by the column and blocks not
their coloring the original coloring was good" (color revert), and "the
circles for finance as there for order in dashboard card add them" (donut
parity between the order and finance stat rows).

## Files touched
- `app/main_gui.py` (`THEMES`, `PRIMARY`, `_glass_card`, Dashboard finance
  card donuts, `refresh_finance_ui` percentage calc)
- `app/views/order_card_view.py` (`_card()` highlight strip restored)
- `app/README.md`, `app/readme.txt`, `app/readme.me` (color table revert)

## Verification
- pytest: 12/12. GUI smoke test: 39/39 (unaffected — palette/donut
  additions don't touch any check, and the theme checks already compare
  against `gui.THEMES[...]` directly).
- Screenshotted the real running Dashboard: confirmed the blue nav/accent
  colors are back, and the three finance cards now show partial donut
  rings (Paid ~33% green, Remaining ~67% orange, Debt 0% on the seeded
  data) exactly like the order status row above them.

---

<!-- ===== originally change15.md ===== -->

# Change 15 — Ported the JTC web app's neumorphic design system into the Tkinter GUI

**Date:** 2026-09-28

## Summary

The user pointed at their Base44 web app (`jtc-erp-app.base44.app`) and asked
for the desktop UI to look like it. The published URL is not live yet and the
editor preview needs their login, so the design was taken instead from the
source they pasted: `index.css`, `tailwind.config.js`, and the `Dashboard`,
`Customers`, `CustomerDetail`, `Tailors` and `SettingsPage` components.

### Design tokens (`main_gui.py`)
- Replaced the soft-glass `THEMES` palette with the web app's neumorphic
  tokens: one warm-grey canvas (`#EBE7E2` light / `#2A2927` dark) with
  surfaces a shade lighter on top (`#EEEAE6` / `#323130`), `--app-line`
  borders, and the four-level text ramp (`text_main` / `text_muted` /
  `text_3` / `text_4`). The existing key NAMES were kept, so all ~1800
  lines of `self.colors[...]` lookups — including `order_card_view.py`'s —
  picked up the new look with no call-site churn.
- Accents taken verbatim from the brand palette: sage `#2ECC8A`, terracotta
  `#FF8077`, blush `#F9AEBE`, lavender `#C9B3F5`, tan `#C4996A`, gauge amber
  `#FFCB6E`, destructive `#BD3228`. `PRIMARY` is now the design's dark
  neumorphic pill `#3A3A3A` (`.btn-dark-neu`).
- `FONT_FAMILY` resolves to the design's DM Sans when installed and
  otherwise stays on the platform UI face; the check needs a live Tk root,
  so it runs once in `__init__`.

### Neumorphic primitives
Tkinter has no `box-shadow`, so each CSS shadow is rebuilt from thin frames:
- `_neu_card()` (`.neu-raised` / `--shadow-out`): lit top edge, shadowed
  bottom edge. `_glass_card()` now forwards to it, keeping its old padding
  defaults so no existing card changed size.
- `_neu_well()` (`.neu-inset-sm` / `--shadow-in`): darker fill, shadow along
  the top edge — the inverse, so a block reads recessed.
- `StatusPill`: a canvas-drawn capsule with a leading `.pip` dot, since Tk
  labels cannot round their corners.
- `_avatar()`, `_stat_tile()`, `_page_header()`, `_primary_button()`,
  `_toolbar_button()`, `_search_row()`, `_section_label()`.
- `_track()` fakes the design's wide letter-spacing on small uppercase
  captions by weaving thin spaces between characters. It is skipped for
  non-ASCII text so Urdu is never pulled apart into disconnected letters.

### Layout
- **Top bar removed.** `create_header()` and `_create_accent_strip()` are
  gone; the brand lockup, the accent trio (now sage/blush/lavender rather
  than blue/white/red, to sit on the warm canvas) and the live clock all
  moved into the sidebar card. The active nav item is now a recessed well
  (`.nav-active`) instead of a solid fill.
- **Dashboard** rebuilt to the web layout: page header with a light-weight
  title and a long-form live date line, one primary action on the right; all
  three order gauges sharing a single card with the reading printed inside
  each ring; a counter-tile row (Total Orders / Customers / Tailors On Duty);
  the finance snapshot row; and the ledger.
- **Ledger** is now a list of inset rows — order number, a compound
  customer / garment / tailor cell, and a status pill — instead of a grid.
  `tree_orders` is kept but never packed: it remains the data and selection
  model, so the toolbar button, the context menu, `generate_order_pdf` and
  the smoke test all kept working unchanged, and the visible list is drawn
  from the same rows (single source of truth). Clicking a row mirrors the
  selection into it.
- **Finance** cards each gained a donut showing that bucket's share of the
  grand total, with the percentage printed inside the ring.
- **Customer Hub / Staff** headers were overcrowded — five buttons packed
  beside the subtitle, and the leftmost ones were visibly clipped. Both now
  use `_page_header()` (stacked title + subtitle, one primary action right)
  with secondary actions on their own toolbar row, search as an inset well,
  and the table inside a raised card.
- Treeview chrome retuned: headings sit on a recessed well in muted
  lettering, and the finance row tints moved off the old maroon/orange onto
  the warm palette.

## Why
"can you make ui like this" + the pasted web source, then "donut shape in
finance, also remove the top bar and adjust it to the side bar".

This supersedes change13's monochrome attempt and change14's revert: the
earlier correction was that a *black/white* retune was wrong, not that the
app had to keep the blue soft-glass palette. The source the user sent makes
the intended palette explicit — warm neumorphic with pastel accents.

## Files touched
- `app/main_gui.py` (palette, primitives, dashboard, ledger, finance,
  customer, employee, sidebar, ttk styles, language pack)
- `app/lang/en.py`, `app/lang/ur.py` (`dash_new_order`, `dash_total_orders`,
  `dash_customers`, `dash_on_duty`, `dash_unassigned`)
- `app/tests/gui_smoke_test.py` (6 new checks)
- `app/README.md`, `app/readme.txt`, `app/readme.me`

## Verification
- Unit tests: 12/12. GUI smoke test: **45/45** (was 39) — new checks cover
  the palette tokens, the removed top bar, one ledger row per order, ledger
  click driving `tree_orders` selection, the counter tiles, and the finance
  donuts. One new check initially failed by pinning the palette to `light`;
  the app restores whichever theme was last saved, so it now compares
  against `THEMES[app.current_theme]`.
- Screenshotted the real running app (seeded temp data dir, window forced
  topmost so the capture is the app and not the editor behind it) across
  Dashboard / Customers / Staff / Finance / Settings in light, plus the
  Dashboard in dark. Confirmed on screen: warm canvas with raised cards, the
  three gauges in one card with readings inside the rings, counter tiles,
  finance donuts with percentages, inset ledger rows with status pills, the
  sidebar carrying brand + accent strip + clock, and no top bar.

---

