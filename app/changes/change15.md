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
