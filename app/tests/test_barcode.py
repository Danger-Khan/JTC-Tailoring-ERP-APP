"""Code 128: the table's own invariants, and a round trip through it.

The old encoder produced something barcode-shaped that no scanner would
read, and nothing here would have caught it, because there was nothing
here. A barcode is either exactly right or it is a picture of stripes, so
these tests check the symbology's rules rather than that the output "looks
like" a barcode.

The interesting ones are the table invariants. Transcribing 106 six-digit
patterns is exactly the sort of job that goes wrong quietly.
"""
import unittest

from app.services import barcode_service as bc


class PatternTableTestCase(unittest.TestCase):
    """Checked, not trusted."""

    def test_there_are_one_hundred_and_six_symbols(self):
        self.assertEqual(len(bc.PATTERNS), 106)

    def test_every_symbol_is_eleven_modules(self):
        for value, pattern in enumerate(bc.PATTERNS):
            total = sum(int(c) for c in pattern)
            self.assertEqual(total, bc.MODULES_PER_SYMBOL,
                             "value %d (%s) totals %d" % (value, pattern, total))

    def test_every_symbol_has_six_elements(self):
        for value, pattern in enumerate(bc.PATTERNS):
            self.assertEqual(len(pattern), 6, "value %d is %r" % (value, pattern))

    def test_every_symbols_bars_total_an_even_number_of_modules(self):
        """A real property of Code 128, and the one that catches a
        transposed pair of digits -- which a plain "sums to 11" check
        sails straight past."""
        for value, pattern in enumerate(bc.PATTERNS):
            bars = int(pattern[0]) + int(pattern[2]) + int(pattern[4])
            self.assertEqual(bars % 2, 0, "value %d (%s) has odd bars" % (value, pattern))

    def test_no_two_symbols_share_a_pattern(self):
        self.assertEqual(len(set(bc.PATTERNS)), len(bc.PATTERNS),
                         "two values with the same pattern are ambiguous to a scanner")

    def test_no_element_is_wider_than_four_modules(self):
        for value, pattern in enumerate(bc.PATTERNS):
            for c in pattern:
                self.assertIn(int(c), (1, 2, 3, 4), "value %d has a %s-module element"
                              % (value, c))

    def test_the_stop_pattern_is_thirteen_modules(self):
        self.assertEqual(sum(int(c) for c in bc.STOP), 13)
        self.assertEqual(len(bc.STOP), 7)

    def test_known_bit_patterns_match_the_published_standard(self):
        """Three anchors from the symbology itself. If the table were
        shifted or mistyped these would not line up."""
        self.assertEqual(bc.bits(bc.PATTERNS[0]), "11011001100", "value 0, the space")
        self.assertEqual(bc.bits(bc.PATTERNS[bc.START_B]), "11010010000", "Start B")
        self.assertEqual(bc.bits(bc.STOP), "1100011101011", "Stop")

    def test_the_table_matches_the_rust_implementation(self):
        """This table was generated from explore/barcode-rs, whose own test
        suite checks the same invariants. Two copies that disagree is worse
        than one copy, so keep them in step."""
        import os
        import re
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        rust = os.path.join(root, "explore", "barcode-rs", "src", "lib.rs")
        if not os.path.exists(rust):
            self.skipTest("explore/barcode-rs is not present")
        with open(rust, encoding="utf-8") as handle:
            block = handle.read().split("pub const PATTERNS: [[u8; 6]; 106] = [", 1)[1]
        block = block.split("];", 1)[0]
        rows = ["".join(r) for r in re.findall(r"\[(\d),(\d),(\d),(\d),(\d),(\d)\]", block)]
        self.assertEqual(rows, list(bc.PATTERNS))


class EncodeTestCase(unittest.TestCase):

    def test_set_b_values_are_ascii_minus_32(self):
        values = bc.encode("0A ")
        self.assertEqual(values[0], bc.START_B)
        self.assertEqual(values[1], 16, "'0' is value 16, not 0 -- the old table said 0")
        self.assertEqual(values[2], 33, "'A' is value 33")
        self.assertEqual(values[3], 0, "space is value 0")

    def test_the_check_symbol_is_computed_the_documented_way(self):
        # By hand: start 104, 'A'=33 at position 1, 'B'=34 at position 2.
        # (104 + 1*33 + 2*34) % 103 = 205 % 103 = 102.
        self.assertEqual(bc.encode("AB")[-1], 102)
        self.assertEqual((104 + 33 + 2 * 34) % 103, 102)

    def test_a_barcode_is_start_data_check_and_stop(self):
        values = bc.encode("ORD-101")
        self.assertEqual(len(values), 1 + 7 + 1, "start + data + check")
        self.assertEqual(len(bc.widths(values)), 9 * 6 + 7)

    def test_the_check_symbol_is_present_at_all(self):
        """The old encoder emitted start + data + stop, one symbol short.
        That alone makes every scanner reject it."""
        without_check = bc.PATTERNS[bc.START_B] + "".join(
            bc.PATTERNS[ord(c) - 32] for c in "ORD-101") + bc.STOP
        self.assertEqual(len(bc.widths(bc.encode("ORD-101"))) - len(without_check), 6)

    def test_unsupported_characters_are_refused_not_mangled(self):
        for bad in ("ORD-۱۰۱", "café", "ORD—101"):
            with self.assertRaises(bc.BarcodeError):
                bc.encode(bad)

    def test_empty_input_is_refused(self):
        with self.assertRaises(bc.BarcodeError):
            bc.encode("")


class RoundTripTestCase(unittest.TestCase):

    def test_every_printable_ascii_character_survives(self):
        everything = "".join(chr(c) for c in range(32, 127))
        self.assertEqual(bc.decode(bc.widths(bc.encode(everything))), everything)

    def test_realistic_ids_survive(self):
        for identifier in ("ORD-101", "C-101", "INV-2026-0042", "ORD-101/A",
                           "JTQ ORD 9", "a b c", "#42"):
            self.assertEqual(bc.decode(bc.widths(bc.encode(identifier))), identifier,
                             "failed on %r" % identifier)

    def test_a_long_id_survives(self):
        long_id = "JTQ-9" * 40
        self.assertEqual(bc.decode(bc.widths(bc.encode(long_id))), long_id)


class DecodeStrictnessTestCase(unittest.TestCase):
    """A decoder that accepts a broken barcode proves nothing."""

    def test_a_tampered_check_symbol_is_rejected(self):
        values = bc.encode("ORD-101")
        values[-1] = (values[-1] + 1) % 103
        with self.assertRaises(bc.BarcodeError) as caught:
            bc.decode(bc.widths(values))
        self.assertIn("check symbol", str(caught.exception))

    def test_a_tampered_data_symbol_is_caught_by_the_checksum(self):
        values = bc.encode("ORD-101")
        values[1] = 40  # change a character, keep the old check symbol
        with self.assertRaises(bc.BarcodeError) as caught:
            bc.decode(bc.widths(values))
        self.assertIn("check symbol", str(caught.exception))

    def test_a_missing_stop_pattern_is_rejected(self):
        digits = bc.widths(bc.encode("ORD-101"))
        with self.assertRaises(bc.BarcodeError) as caught:
            bc.decode(digits[:-len(bc.STOP)] + "1111111")
        self.assertIn("stop", str(caught.exception))

    def test_junk_is_rejected(self):
        for junk in ("", "1", "123456", "9" * 40):
            with self.assertRaises(bc.BarcodeError):
                bc.decode(junk)

    def test_the_old_encoders_output_does_not_decode(self):
        """Exactly what the previous implementation produced for ORD-101.
        It does not even reach the checksum: its pattern for '-' was
        211133, which totals 11 and so looks plausible, but is not one of
        the 106 real patterns. A scanner does the same thing."""
        old_output = "2112143122122121231132222111332221222122222221222331112"
        self.assertEqual(len(old_output), 6 + 7 * 6 + 7, "start + 7 characters + stop")
        with self.assertRaises(bc.BarcodeError) as caught:
            bc.decode(old_output)
        self.assertIn("211133", str(caught.exception))

    def test_the_old_space_and_fallback_patterns_are_not_symbols(self):
        self.assertEqual(sum(int(c) for c in "211213"), 10, "the old space pattern")
        self.assertNotIn("211213", bc.PATTERNS)
        self.assertEqual(sum(int(c) for c in "111111"), 6, "the old unknown-char fallback")
        self.assertNotIn("111111", bc.PATTERNS)


class SvgTestCase(unittest.TestCase):

    def test_it_draws_a_bar_for_every_other_element(self):
        svg = bc.generate_svg("ORD-101")
        elements = len(bc.widths(bc.encode("ORD-101")))
        self.assertEqual(svg.count("<rect x="), (elements + 1) // 2)

    def test_it_leaves_a_real_quiet_zone(self):
        """Ten modules, not ten pixels. Without it a scanner cannot find
        the start of the symbol however good the bars are."""
        svg = bc.generate_svg("ORD-101", width=300)
        digits = bc.widths(bc.encode("ORD-101"))
        module = 300.0 / (sum(int(d) for d in digits) + bc.QUIET_ZONE_MODULES * 2)
        self.assertIn('<rect x="%.3f"' % (bc.QUIET_ZONE_MODULES * module), svg)

    def test_the_whole_symbol_fits_the_width_asked_for(self):
        for width in (200, 300, 640):
            svg = bc.generate_svg("INV-2026-0042", width=width)
            self.assertIn('width="%.1f"' % float(width), svg)
            last = svg.rsplit('<rect x="', 1)[1]
            x = float(last.split('"')[0])
            w = float(last.split('width="')[1].split('"')[0])
            self.assertLessEqual(x + w, float(width) + 0.01, "bars run past the edge")

    def test_the_label_is_escaped(self):
        svg = bc.generate_svg("A&B")
        self.assertIn("A&amp;B", svg)
        self.assertNotIn(">A&B<", svg)

    def test_the_class_entry_point_still_works(self):
        """Nothing calls it today, but it is the module's public face."""
        svg = bc.PurePythonBarcode128.generate_svg("ORD-101")
        self.assertTrue(svg.startswith("<svg"))
        self.assertEqual(
            bc.PurePythonBarcode128.decode(
                bc.widths(bc.PurePythonBarcode128.encode("ORD-101"))),
            "ORD-101")


if __name__ == "__main__":
    unittest.main()
