"""Small motion helpers for the Tk UI.

Tkinter has no animation of any kind, and two of the obvious approaches do
not work here:

  * **Opacity.** There is no per-widget alpha. A `tk.Frame` is opaque, full
    stop. Only a `Toplevel` has `-alpha`, which is why dialogs get a real
    fade and in-page cards get movement instead.
  * **Transforms.** Nothing scales or translates a widget. Movement has to
    come from the geometry manager, which means re-packing with a changing
    pad -- cheap, but it reflows, so it is only safe on a container that is
    being shown or hidden anyway.

So: dialogs fade, sections rise into place, and cards can be tinted in a
staggered sweep. Everything is driven by `widget.after`, on the Tk thread,
because Tkinter is not thread-safe.

Three rules, all learned the hard way on this codebase:

  * **Never leave the UI mid-animation.** Every runner writes the final
    value as its last step, so a cancelled or destroyed animation cannot
    strand a card at 40% opacity or 7 pixels low.
  * **Never raise into the event loop.** A `TclError` from a widget that
    was destroyed between frames must end the animation quietly, not
    surface as a traceback over the till.
  * **Be switchable off.** `set_enabled(False)` makes every helper apply
    the final state immediately. A shop counter PC is not always fast, and
    motion is the first thing to drop.
"""
import tkinter as tk

# Roughly 60fps. Tk's after() resolution makes anything finer a lie.
FRAME_MS = 16

_enabled = True


def set_enabled(on):
    """Turn all motion on or off. Off applies final states instantly."""
    global _enabled
    _enabled = bool(on)


def enabled():
    return _enabled


def ease_out_cubic(t):
    """Fast at the start, settling at the end.

    The right curve for something arriving: it covers most of the distance
    immediately, so the UI feels responsive rather than slow, and eases out
    so it does not stop dead.
    """
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


def _alive(widget):
    try:
        return bool(widget.winfo_exists())
    except tk.TclError:
        return False


def run(widget, duration_ms, step, done=None, ease=ease_out_cubic):
    """Call `step(value)` with 0.0..1.0 over `duration_ms`, then `done()`.

    `step` is always called with exactly 1.0 as its last value, including
    when motion is disabled or the duration is zero -- callers rely on that
    to set the final state, so there is one code path and no chance of a
    half-finished layout.
    """
    if not _alive(widget):
        return

    if not _enabled or duration_ms <= 0:
        _safe(step, 1.0)
        if done:
            done()
        return

    frames = max(1, int(duration_ms / FRAME_MS))
    state = {"frame": 0}

    def tick():
        if not _alive(widget):
            return
        state["frame"] += 1
        progress = state["frame"] / float(frames)
        if progress >= 1.0:
            _safe(step, 1.0)
            if done:
                done()
            return
        _safe(step, ease(progress))
        widget.after(FRAME_MS, tick)

    _safe(step, ease(0.0))
    widget.after(FRAME_MS, tick)


def _safe(fn, value):
    """A widget destroyed between frames ends the animation, quietly."""
    try:
        fn(value)
    except tk.TclError:
        pass


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

def fade_in_window(window, duration_ms=140, final_alpha=1.0):
    """Fade a Toplevel up from transparent.

    `-alpha` is the one real opacity Tk exposes, and it is per-window. On
    Windows it is cheap; where the window manager ignores it the attribute
    call raises and this becomes an immediate show, which is the right
    fallback.
    """
    if not _alive(window):
        return
    try:
        window.attributes("-alpha", 0.0 if _enabled else final_alpha)
    except tk.TclError:
        return  # no alpha here; the window is simply shown

    def step(t):
        window.attributes("-alpha", final_alpha * t)

    run(window, duration_ms, step)


# ---------------------------------------------------------------------------
# In-page content
# ---------------------------------------------------------------------------

def slide_in(widget, pack_opts=None, distance=18, duration_ms=190):
    """Let a just-packed widget settle upward into place.

    Implemented as a shrinking top pad rather than a moving coordinate,
    because the sections here are packed, not placed, and mixing geometry
    managers on the same parent is how you get a blank page. The pad is
    restored to whatever it was, so the resting layout is untouched.
    """
    if not _alive(widget):
        return

    base = pack_opts.get("pady", 0) if pack_opts else 0
    top, bottom = base if isinstance(base, (tuple, list)) else (base, base)

    def step(t):
        widget.pack_configure(pady=(int(top + distance * (1.0 - t)), bottom))

    run(widget, duration_ms, step)


def tint_in(widget, from_color, to_color, duration_ms=200, delay_ms=0,
            apply=None):
    """Fade a widget's background from `from_color` to `to_color`.

    Stands in for the opacity Tk will not give a frame: starting a card at
    the page's own background and bringing it up to the card colour reads
    as the card fading in, as long as both are flat.

    `apply` lets a caller redirect the colour somewhere other than the
    widget's own `bg` -- the rounded cards here are canvas polygons, so
    their fill is set by redrawing, not by configuring a frame.
    """
    if not _alive(widget):
        return

    setter = apply or (lambda color: widget.configure(bg=color))

    if not _enabled:
        _safe(lambda _t: setter(to_color), 1.0)
        return

    start, end = _rgb(from_color, widget), _rgb(to_color, widget)
    if start is None or end is None:
        _safe(lambda _t: setter(to_color), 1.0)
        return

    def step(t):
        setter(_hex(tuple(
            int(round(start[i] + (end[i] - start[i]) * t)) for i in range(3))))

    if delay_ms > 0:
        _safe(lambda _t: setter(from_color), 0.0)
        widget.after(delay_ms, lambda: run(widget, duration_ms, step))
    else:
        run(widget, duration_ms, step)


def stagger(widgets, action, gap_ms=45, limit=10):
    """Run `action(widget, delay_ms)` over `widgets`, each a beat later.

    Capped at `limit`: past about ten the sweep stops reading as one motion
    and starts reading as the page being slow. Everything after the cap is
    given the last delay rather than being skipped, so nothing is left in
    its starting state.
    """
    for index, widget in enumerate(widgets):
        action(widget, gap_ms * min(index, limit))


# ---------------------------------------------------------------------------

def _rgb(color, widget):
    """A Tk colour name or #rrggbb as (r, g, b) 0-255."""
    if not color:
        return None
    text = str(color).strip()
    if text.startswith("#") and len(text) == 7:
        try:
            return (int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16))
        except ValueError:
            return None
    try:
        # winfo_rgb resolves names ("white", "grey20") but returns 16-bit.
        return tuple(c // 256 for c in widget.winfo_rgb(text))
    except tk.TclError:
        return None


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, c)) for c in rgb)
