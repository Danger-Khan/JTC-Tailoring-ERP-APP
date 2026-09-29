"""Code 128 (subset B) barcodes for order tickets.

What was here before rendered something barcode-shaped that no scanner would
read. Three independent reasons, each fatal on its own:

  * **No check symbol.** Code 128 requires a modulo-103 checksum symbol
    between the data and the stop pattern. It is not optional; a conformant
    scanner rejects the symbol without it. The old code emitted
    ``[START] + patterns + [STOP]`` and stopped there.
  * **The pattern table was shifted by the ASCII offset.** In set B a
    character's value is its ASCII code minus 32, so ``"0"`` is value 16. The
    old table gave ``"0"`` the pattern ``212222``, which is value *0* -- the
    space. It simply assigned the first 39 patterns to ``0-9`` then ``A-Z``
    in order, so every character encoded as a different character.
  * **Two of its patterns were not symbols.** Every Code 128 symbol is six
    elements totalling exactly 11 modules. Its space was ``211213`` (10) and
    any character outside its 39-entry table fell back to ``111111`` (6).
    Lowercase, ``/``, ``:`` and ``#`` all hit that fallback.

``decode()`` exists so this can be tested rather than asserted: encode,
decode, and get the same string back. ``app/tests/test_barcode.py`` also
round-trips every printable ASCII character and cross-checks the table
against the symbology's own invariants.

The table is transcribed from the symbology and verified in the tests, not
trusted -- see ``explore/barcode-rs`` for the same table in Rust, which is
where this one was generated from.
"""

# Element widths for symbol values 0..=105, as "bar space bar space bar space".
PATTERNS = (
    "212222", "222122", "222221", "121223", "121322",  # 0-4
    "131222", "122213", "122312", "132212", "221213",  # 5-9
    "221312", "231212", "112232", "122132", "122231",  # 10-14
    "113222", "123122", "123221", "223211", "221132",  # 15-19
    "221231", "213212", "223112", "312131", "311222",  # 20-24
    "321122", "321221", "312212", "322112", "322211",  # 25-29
    "212123", "212321", "232121", "111323", "131123",  # 30-34
    "131321", "112313", "132113", "132311", "211313",  # 35-39
    "231113", "231311", "112133", "112331", "132131",  # 40-44
    "113123", "113321", "133121", "313121", "211331",  # 45-49
    "231131", "213113", "213311", "213131", "311123",  # 50-54
    "311321", "331121", "312113", "312311", "332111",  # 55-59
    "314111", "221411", "431111", "111224", "111422",  # 60-64
    "121124", "121421", "141122", "141221", "112214",  # 65-69
    "112412", "122114", "122411", "142112", "142211",  # 70-74
    "241211", "221114", "413111", "241112", "134111",  # 75-79
    "111242", "121142", "121241", "114212", "124112",  # 80-84
    "124211", "411212", "421112", "421211", "212141",  # 85-89
    "214121", "412121", "111143", "111341", "131141",  # 90-94
    "114113", "114311", "411113", "411311", "113141",  # 95-99
    "114131", "311141", "411131", "211412", "211214",  # 100-104
    "211232",                                          # 105
)

START_A = 103
START_B = 104
START_C = 105

# The one seven-element pattern: 13 modules, because it carries the
# terminating bar.
STOP = "2331112"

MODULES_PER_SYMBOL = 11

# Code 128 needs at least 10 modules of clear space either side. Without it a
# scanner cannot find the start of the symbol however good the bars are. The
# old code left 10 *pixels*.
QUIET_ZONE_MODULES = 10


class BarcodeError(ValueError):
    """Raised rather than encoding something a scanner would misread."""


def checksum(start_and_data):
    """``(start + sum(position * value)) mod 103``, positions from 1."""
    total = start_and_data[0]
    for position, value in enumerate(start_and_data[1:], start=1):
        total += position * value
    return total % 103


def encode(data):
    """Symbol values for `data`: start, the data, the check symbol.

    Subset B covers printable ASCII (32..126). Anything else raises instead
    of being silently mangled -- an order ticket that scans as the wrong
    order is worse than one that does not scan.
    """
    if not data:
        raise BarcodeError("nothing to encode")

    values = [START_B]
    for index, char in enumerate(str(data)):
        code = ord(char)
        if not 32 <= code <= 126:
            raise BarcodeError(
                "character %r at position %d is not in Code 128 set B "
                "(printable ASCII 32..126)" % (char, index))
        values.append(code - 32)

    values.append(checksum(values))
    return values


def widths(values):
    """Element widths for `values`, as a digit string, stop included."""
    return "".join(PATTERNS[v] for v in values) + STOP


def bits(width_digits):
    """Module bit string, bars 1 and spaces 0.

    Every Code 128 symbol starts with a bar, so elements simply alternate.
    """
    out = []
    for index, digit in enumerate(width_digits):
        out.append(("1" if index % 2 == 0 else "0") * int(digit))
    return "".join(out)


def decode(width_digits):
    """Read a barcode back from its element widths.

    Verifies the check symbol, which is the whole point: it is what tells
    you the encoder was right rather than merely plausible.
    """
    digits = [d for d in str(width_digits) if d.isdigit()]
    if len(digits) < 6 + 6 + len(STOP):
        raise BarcodeError("too short to be a barcode")

    body_len = len(digits) - len(STOP)
    if body_len % 6:
        raise BarcodeError(
            "%d width digits is not a whole number of symbols "
            "(6 each, plus %d for the stop)" % (len(digits), len(STOP)))
    if "".join(digits[body_len:]) != STOP:
        raise BarcodeError("does not end with the stop pattern")

    lookup = {pattern: value for value, pattern in enumerate(PATTERNS)}
    values = []
    for index in range(0, body_len, 6):
        pattern = "".join(digits[index:index + 6])
        if pattern not in lookup:
            total = sum(int(c) for c in pattern)
            why = ("totals %d modules, and every symbol is %d"
                   % (total, MODULES_PER_SYMBOL)) if total != MODULES_PER_SYMBOL else (
                  "is 11 modules but is not one of the %d Code 128 patterns" % len(PATTERNS))
            raise BarcodeError(
                "symbol %d has widths %s, which %s" % (index // 6, pattern, why))
        values.append(lookup[pattern])

    if values[0] not in (START_A, START_B, START_C):
        raise BarcodeError("does not begin with a start symbol")

    expected = checksum(values[:-1])
    if values[-1] != expected:
        raise BarcodeError(
            "check symbol is %d, should be %d "
            "(scanners reject the whole barcode on this)" % (values[-1], expected))

    return "".join(chr(v + 32) for v in values[1:-1])


def _escape(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def generate_svg(code_text, width=300, height=80):
    """An SVG barcode for `code_text`, `width` pixels wide including the
    quiet zones on both sides.

    The module width is derived from `width` so the whole symbol, quiet
    zones included, fits the space asked for -- a barcode drawn to the edge
    of its box does not scan.
    """
    values = encode(code_text)
    width_digits = widths(values)

    bar_modules = sum(int(d) for d in width_digits)
    total_modules = bar_modules + QUIET_ZONE_MODULES * 2
    module = float(width) / total_modules
    quiet = QUIET_ZONE_MODULES * module

    text_height = 14.0
    bar_height = max(float(height) - text_height - 4.0, 10.0)

    bars = []
    x = quiet
    for index, digit in enumerate(width_digits):
        element = int(digit) * module
        if index % 2 == 0:
            bars.append(
                '<rect x="%.3f" y="0" width="%.3f" height="%.2f"/>' % (x, element, bar_height))
        x += element

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%.1f" height="%.1f" '
        'viewBox="0 0 %.1f %.1f" shape-rendering="crispEdges">\n'
        '  <rect width="100%%" height="100%%" fill="#ffffff"/>\n'
        '  <g fill="#000000">%s</g>\n'
        '  <text x="%.1f" y="%.1f" font-family="monospace" font-size="12" '
        'text-anchor="middle" fill="#000000">%s</text>\n'
        '</svg>'
    ) % (float(width), float(height), float(width), float(height),
         "".join(bars), float(width) / 2.0, float(height) - 3.0, _escape(code_text))


class PurePythonBarcode128:
    """Kept as the module's entry point; the logic lives in the functions
    above so it can be tested without a class in the way."""

    PATTERNS = PATTERNS
    START_CODE = PATTERNS[START_B]
    STOP_CODE = STOP

    @classmethod
    def generate_svg(cls, code_text, width=300, height=80):
        return generate_svg(code_text, width, height)

    @classmethod
    def encode(cls, code_text):
        return encode(code_text)

    @classmethod
    def decode(cls, width_digits):
        return decode(width_digits)
