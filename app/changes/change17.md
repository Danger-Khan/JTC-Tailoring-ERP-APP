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
