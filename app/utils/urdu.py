"""Urdu text that survives being drawn into a PDF.

Three separate things have to go right, and the built-in PDF fonts get
none of them:

  * **Glyphs.** Helvetica has no Arabic script at all. reportlab does not
    fail on a missing glyph -- it quietly substitutes ZapfDingbats, whose
    stand-in for a letter is a filled square, so the order slip printed
    "Length (■■■■■)" for months and every text-level assertion passed.
  * **Joining.** Arabic script is cursive: a letter takes a different shape
    depending on whether it starts, ends, or sits inside a word. Unicode
    stores the abstract letter, so drawing the raw string gives you
    disconnected stumps even with a correct font. `arabic_reshaper` picks
    the presentation form for each position.
  * **Direction.** Urdu runs right to left, and a PDF canvas draws left to
    right. `python-bidi` reorders the string so that drawing it forwards
    puts it on the page backwards, which is to say correctly.

Doing one or two of the three is worse than doing none: a correct font
without shaping and reordering prints isolated letters in reverse, which
looks like a font bug rather than an obvious blank.

Everything here degrades to "not available" rather than raising, and the
callers print romanised labels when it is. A slip with "Shalwar Length"
on it is fine. A slip with five black squares is not.
"""
import os

try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:  # pragma: no cover - exercised by the degraded path
    arabic_reshaper = None
    get_display = None

# Nastaliq first: it is the style Urdu is actually read in, and a Pakistani
# shopkeeper will notice the difference immediately. The Naskh faces below
# are on every Windows install and are a genuine fallback -- readable, just
# not what anyone would choose.
FONT_CANDIDATES = (
    ("JameelNooriNastaleeq", r"C:\Windows\Fonts\Jameel Noori Nastaleeq.ttf"),
    ("NotoNastaliqUrdu", r"C:\Windows\Fonts\NotoNastaliqUrdu-Regular.ttf"),
    ("UrduTypesetting", r"C:\Windows\Fonts\UrduTypesetting.ttf"),
    ("SegoeUI-Urdu", r"C:\Windows\Fonts\segoeui.ttf"),
    ("Arial-Urdu", r"C:\Windows\Fonts\arial.ttf"),
    ("Tahoma-Urdu", r"C:\Windows\Fonts\tahoma.ttf"),
)

# The Arabic script ranges Urdu actually uses.
_ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF),
                  (0xFE70, 0xFEFF))

_registered = None      # font name, or "" once we know there is none
_registered_path = None


def has_arabic(text):
    """True if `text` contains anything that needs shaping."""
    return any(any(low <= ord(ch) <= high for low, high in _ARABIC_RANGES)
               for ch in str(text))


def shaping_available():
    """Whether the two shaping libraries imported."""
    return arabic_reshaper is not None and get_display is not None


def register():
    """Register an Urdu-capable font with reportlab; return its name or "".

    Memoized: the answer cannot change inside a run, and parsing a TTF is
    not free. Tries each candidate and actually checks it has the glyphs --
    a font that exists but covers no Arabic is no use, and finding that out
    at draw time means squares on the paper again.
    """
    global _registered, _registered_path
    if _registered is not None:
        return _registered

    _registered = ""
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:  # pragma: no cover - reportlab is optional here too
        return _registered

    for name, path in FONT_CANDIDATES:
        if not os.path.exists(path):
            continue
        try:
            font = TTFont(name, path)
            # Does it really cover the script? 0x0644 is "lam", in every
            # Urdu word worth printing.
            if 0x0644 not in font.face.charToGlyph:
                continue
            pdfmetrics.registerFont(font)
        except Exception:
            continue
        _registered, _registered_path = name, path
        break
    return _registered


def font_name():
    """The registered font's name, or "" if none could be registered."""
    return register()


def font_path():
    register()
    return _registered_path


def available():
    """True when Urdu can be drawn properly: font AND shaping AND ordering.

    All three or none. Two out of three prints isolated letters backwards,
    which is worse than the romanised fallback because it looks deliberate.
    """
    return bool(register()) and shaping_available()


def shape(text):
    """Turn `text` into the glyph sequence to draw left to right.

    Safe on anything: text with no Arabic comes back unchanged, and if the
    libraries are missing it is returned as-is rather than raising -- the
    caller decides whether to use it by asking available() first.
    """
    text = str(text)
    if not shaping_available() or not has_arabic(text):
        return text
    try:
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def reset_for_tests():
    """Forget the memoized font so a test can exercise the other branch."""
    global _registered, _registered_path
    _registered = None
    _registered_path = None
