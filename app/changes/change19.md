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
