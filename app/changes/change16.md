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
