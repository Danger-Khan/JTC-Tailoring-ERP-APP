# barcode-rs — Code 128 that actually scans

An encoder **and a decoder** for Code 128 subset B, with no dependencies.

The decoder is the point. Anyone can draw black rectangles; the only way to
know a barcode is right is to read it back and check the check symbol. So this
crate encodes, decodes, and round-trips every printable ASCII character through
both.

## Why Rust for this

Code 128 is a specification you implement *exactly* or not at all. There is no
partial credit — a barcode that is 95% right is a barcode that does not scan.
That shape of problem is what Rust is for:

- `DecodeError` is an enum with a variant per way a barcode can be wrong, and
  `match` is exhaustive, so a new failure mode cannot be silently ignored.
- `[[u8; 6]; 106]` is a fixed-size array checked at compile time. Adding a row
  with five elements does not compile.
- `#[cfg(test)]` lives beside the code, so the table's invariants are asserted
  in the same file the table is written in.

## The existing Python encoder does not produce a barcode

`app/services/barcode_service.py` has a `PurePythonBarcode128` class that
renders an SVG. It is not a Code 128 symbol. Three independent reasons, each
fatal on its own:

**1. No check symbol.** Code 128 requires a modulo-103 checksum symbol between
the data and the stop pattern. It is not optional. The Python builds
`[START] + patterns + [STOP]` and stops there.

```
$ ./jtq-barcode encode ORD-101
symbols       : [104, 47, 50, 36, 13, 17, 16, 17, 93]
                                                  ^^ the check symbol
```

Its output for the same string is exactly one symbol shorter.

**2. The pattern table is shifted by the ASCII offset.** In set B a character's
value is its ASCII code minus 32, so `'0'` is value 16. The Python gives `'0'`
the pattern `212222`, which is value **0** — the space. Its table simply
assigns the first 39 patterns to `0-9` then `A-Z` in order. Every character
would come out as a different character, if it got that far.

**3. Two of its patterns are not symbols.** Every Code 128 symbol is six
elements totalling exactly 11 modules. Its space is `211213` (10 modules), and
any character outside its 39-entry table falls back to `111111` (6 modules).
Lowercase letters, `/`, `:`, `#` all hit that fallback.

### Shown, not asserted

Run the Python encoder, take the widths it produces, and hand them to a real
decoder:

```
$ ./jtq-barcode decode 2112143122122121231132222111332221222122222221222331112
REJECTED      : symbol 4 has widths [2, 1, 1, 1, 3, 3], which is 11 modules
                but is not one of the 106 Code 128 patterns
```

It does not even survive long enough to fail the checksum — the fifth symbol
is the `-` in `ORD-101`, whose table entry is `211133`. That totals 11, so it
looks plausible, but it is not one of the 106 real patterns. A scanner does
exactly this and rejects the label.

Our own output, by contrast:

```
$ ./jtq-barcode check ORD-101
round trip OK : "ORD-101" -> 9 symbols -> "ORD-101"
```

## The table is checked, not trusted

Transcribing 106 six-digit patterns by hand is exactly the kind of job that
goes wrong quietly, so the tests assert the symbology's own invariants rather
than assuming the typing was perfect:

- every row totals 11 modules;
- **the three bars of every row total an even number of modules** — a real
  property of Code 128, and the one that catches a transposed pair of digits,
  which a plain "sums to 11" check sails straight past;
- no element is wider than 4 modules;
- no two rows are identical (they would be ambiguous to a scanner);
- and three known bit patterns from the published standard are matched exactly:
  value 0 is `11011001100`, Start B is `11010010000`, Stop is `1100011101011`.

## Usage

```sh
jtq-barcode encode ORD-101 [--svg ticket.svg] [--module 2] [--height 60]
jtq-barcode decode 211214133121231131112313122132123221123122123221111341233111
jtq-barcode check  ORD-101
```

The SVG includes the 10-module quiet zone the symbology requires — without it a
scanner cannot find the start of the symbol however good the bars are. The
Python version leaves 10 *pixels*.

## Build

`cargo` is blocked by Smart App Control on this machine (see `../README.md`), so
use `rustc` directly:

```sh
rustc --edition 2021 --test src/lib.rs -o rs_tests && ./rs_tests
rustc --edition 2021 -O --crate-type=lib --crate-name jtq_barcode src/lib.rs -o libjtq_barcode.rlib
rustc --edition 2021 -O --extern jtq_barcode=libjtq_barcode.rlib src/main.rs -o jtq-barcode
```

`Cargo.toml` is committed anyway, so `cargo test` works anywhere that cargo
runs.

## If this were ever wired in

It is not, and that is deliberate. But the shape would be: order tickets get a
Code 128 of the order id, the PDF slip embeds the SVG, and a cheap USB scanner
at the counter becomes a way to pull up an order without typing. That needs a
decision about scanner hardware first, which is why this stops at a library.

**Only subset B is implemented.** Order ids are alphanumeric so that is the
right subset, but a long numeric id would encode to about half the width in
subset C. Worth adding only if ids ever become purely numeric.
