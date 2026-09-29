//! Code 128 (subset B): encode, render, and decode back again.
//!
//! The shop's existing `barcode_service.py` draws something barcode-shaped
//! that no scanner will read. Three separate reasons, each fatal on its own:
//!
//! 1. **The pattern table is shifted.** It gives the character `'0'` the
//!    pattern `212222`, which is the pattern for symbol *value* 0 — the
//!    space character. In Code 128B the value of a character is its ASCII
//!    code minus 32, so `'0'` is value 16, not 0. Every character comes out
//!    as a different character.
//! 2. **No check symbol.** Code 128 requires a modulo-103 checksum symbol
//!    between the data and the stop pattern. It is not optional, and a
//!    conformant scanner rejects the symbol outright without it.
//! 3. **Two invalid patterns.** Every Code 128 symbol is six elements
//!    totalling exactly 11 modules. Its space is `211213` (12 modules), and
//!    any character missing from its 39-entry table falls back to `111111`
//!    (6 modules), which is not a symbol at all.
//!
//! This module is the same thing done properly, and `decode` exists so the
//! claim can be tested rather than asserted: encode, decode, and get the
//! same string back — then point the decoder at the Python encoder's output
//! and watch what comes out.

use std::fmt;

/// Every Code 128 symbol is six elements — bar, space, bar, space, bar,
/// space — and they always total 11 modules.
pub const MODULES_PER_SYMBOL: u32 = 11;

/// Values 0..=102 are data, 103..=105 are the start codes.
pub const START_A: usize = 103;
pub const START_B: usize = 104;
pub const START_C: usize = 105;

/// The stop pattern is the one exception: seven elements, 13 modules,
/// because it carries the terminating bar.
pub const STOP: [u8; 7] = [2, 3, 3, 1, 1, 1, 2];

/// Element widths for symbol values 0..=105.
///
/// Transcribed from the symbology, and checked by the tests rather than
/// trusted: each row totals 11 modules, the three bars of each row total an
/// even number of modules (a property of the encoding that catches digit
/// swaps a simple sum would not), and no two rows are equal.
#[rustfmt::skip]
pub const PATTERNS: [[u8; 6]; 106] = [
    [2,1,2,2,2,2], [2,2,2,1,2,2], [2,2,2,2,2,1], [1,2,1,2,2,3], [1,2,1,3,2,2], // 0-4
    [1,3,1,2,2,2], [1,2,2,2,1,3], [1,2,2,3,1,2], [1,3,2,2,1,2], [2,2,1,2,1,3], // 5-9
    [2,2,1,3,1,2], [2,3,1,2,1,2], [1,1,2,2,3,2], [1,2,2,1,3,2], [1,2,2,2,3,1], // 10-14
    [1,1,3,2,2,2], [1,2,3,1,2,2], [1,2,3,2,2,1], [2,2,3,2,1,1], [2,2,1,1,3,2], // 15-19
    [2,2,1,2,3,1], [2,1,3,2,1,2], [2,2,3,1,1,2], [3,1,2,1,3,1], [3,1,1,2,2,2], // 20-24
    [3,2,1,1,2,2], [3,2,1,2,2,1], [3,1,2,2,1,2], [3,2,2,1,1,2], [3,2,2,2,1,1], // 25-29
    [2,1,2,1,2,3], [2,1,2,3,2,1], [2,3,2,1,2,1], [1,1,1,3,2,3], [1,3,1,1,2,3], // 30-34
    [1,3,1,3,2,1], [1,1,2,3,1,3], [1,3,2,1,1,3], [1,3,2,3,1,1], [2,1,1,3,1,3], // 35-39
    [2,3,1,1,1,3], [2,3,1,3,1,1], [1,1,2,1,3,3], [1,1,2,3,3,1], [1,3,2,1,3,1], // 40-44
    [1,1,3,1,2,3], [1,1,3,3,2,1], [1,3,3,1,2,1], [3,1,3,1,2,1], [2,1,1,3,3,1], // 45-49
    [2,3,1,1,3,1], [2,1,3,1,1,3], [2,1,3,3,1,1], [2,1,3,1,3,1], [3,1,1,1,2,3], // 50-54
    [3,1,1,3,2,1], [3,3,1,1,2,1], [3,1,2,1,1,3], [3,1,2,3,1,1], [3,3,2,1,1,1], // 55-59
    [3,1,4,1,1,1], [2,2,1,4,1,1], [4,3,1,1,1,1], [1,1,1,2,2,4], [1,1,1,4,2,2], // 60-64
    [1,2,1,1,2,4], [1,2,1,4,2,1], [1,4,1,1,2,2], [1,4,1,2,2,1], [1,1,2,2,1,4], // 65-69
    [1,1,2,4,1,2], [1,2,2,1,1,4], [1,2,2,4,1,1], [1,4,2,1,1,2], [1,4,2,2,1,1], // 70-74
    [2,4,1,2,1,1], [2,2,1,1,1,4], [4,1,3,1,1,1], [2,4,1,1,1,2], [1,3,4,1,1,1], // 75-79
    [1,1,1,2,4,2], [1,2,1,1,4,2], [1,2,1,2,4,1], [1,1,4,2,1,2], [1,2,4,1,1,2], // 80-84
    [1,2,4,2,1,1], [4,1,1,2,1,2], [4,2,1,1,1,2], [4,2,1,2,1,1], [2,1,2,1,4,1], // 85-89
    [2,1,4,1,2,1], [4,1,2,1,2,1], [1,1,1,1,4,3], [1,1,1,3,4,1], [1,3,1,1,4,1], // 90-94
    [1,1,4,1,1,3], [1,1,4,3,1,1], [4,1,1,1,1,3], [4,1,1,3,1,1], [1,1,3,1,4,1], // 95-99
    [1,1,4,1,3,1], [3,1,1,1,4,1], [4,1,1,1,3,1], [2,1,1,4,1,2], [2,1,1,2,1,4], // 100-104
    [2,1,1,2,3,2],                                                             // 105
];

#[derive(Debug, PartialEq, Eq)]
pub enum EncodeError {
    /// Code 128B covers ASCII 32..=126. Anything else needs a different
    /// subset or an escape, and guessing would silently encode the wrong
    /// ticket.
    Unsupported { ch: char, index: usize },
    Empty,
}

impl fmt::Display for EncodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            EncodeError::Unsupported { ch, index } => write!(
                f,
                "character {ch:?} at position {index} is not in Code 128 set B \
                 (printable ASCII 32..126)"
            ),
            EncodeError::Empty => write!(f, "nothing to encode"),
        }
    }
}

#[derive(Debug, PartialEq, Eq)]
pub enum DecodeError {
    NotAMultiple(usize),
    UnknownSymbol { index: usize, widths: Vec<u8> },
    MissingStart,
    MissingStop,
    BadChecksum { found: usize, expected: usize },
    TooShort,
}

impl fmt::Display for DecodeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            DecodeError::NotAMultiple(n) => write!(
                f,
                "{n} width digits is not a whole number of symbols \
                 (6 each, plus 7 for the stop)"
            ),
            DecodeError::UnknownSymbol { index, widths } => {
                let total: u32 = widths.iter().map(|w| *w as u32).sum();
                // A wrong total and a right total that is still not a real
                // symbol are different mistakes, and saying "total 11, must
                // be 11" helps nobody.
                let why = if total != MODULES_PER_SYMBOL {
                    format!("totals {total} modules, and every symbol is {MODULES_PER_SYMBOL}")
                } else {
                    "is 11 modules but is not one of the 106 Code 128 patterns".to_string()
                };
                write!(f, "symbol {index} has widths {widths:?}, which {why}")
            }
            DecodeError::MissingStart => write!(f, "does not begin with a start symbol"),
            DecodeError::MissingStop => write!(f, "does not end with the stop pattern"),
            DecodeError::BadChecksum { found, expected } => write!(
                f,
                "check symbol is {found}, should be {expected} \
                 (scanners reject the whole barcode on this)"
            ),
            DecodeError::TooShort => write!(f, "too short to be a barcode"),
        }
    }
}

/// The symbol values for `data`, including start, check symbol and stop.
///
/// The check symbol is `(start + Σ position × value) mod 103`, positions
/// counted from 1. It is mandatory.
pub fn encode_b(data: &str) -> Result<Vec<usize>, EncodeError> {
    if data.is_empty() {
        return Err(EncodeError::Empty);
    }

    let mut values = vec![START_B];
    for (index, ch) in data.chars().enumerate() {
        let code = ch as u32;
        if !(32..=126).contains(&code) {
            return Err(EncodeError::Unsupported { ch, index });
        }
        values.push((code - 32) as usize);
    }

    values.push(checksum(&values));
    Ok(values)
}

/// `(start + Σ i × value_i) mod 103` over the start symbol and the data.
pub fn checksum(start_and_data: &[usize]) -> usize {
    let mut sum = start_and_data[0];
    for (i, value) in start_and_data[1..].iter().enumerate() {
        sum += (i + 1) * value;
    }
    sum % 103
}

/// Expand symbol values into element widths, stop pattern included.
pub fn widths(values: &[usize]) -> Vec<u8> {
    let mut out = Vec::with_capacity(values.len() * 6 + 7);
    for value in values {
        out.extend_from_slice(&PATTERNS[*value]);
    }
    out.extend_from_slice(&STOP);
    out
}

/// Widths as a module bit string, bars 1 and spaces 0. Every barcode starts
/// with a bar, so elements simply alternate.
pub fn bits(widths: &[u8]) -> String {
    let mut out = String::new();
    for (i, w) in widths.iter().enumerate() {
        let ch = if i % 2 == 0 { '1' } else { '0' };
        for _ in 0..*w {
            out.push(ch);
        }
    }
    out
}

/// Read a barcode back out of its element widths.
///
/// Verifies the check symbol, which is the whole reason this exists: it is
/// what tells you the encoder was right rather than merely plausible.
pub fn decode(widths: &[u8]) -> Result<String, DecodeError> {
    if widths.len() < 6 + 6 + 7 {
        return Err(DecodeError::TooShort);
    }
    let body_len = widths.len() - STOP.len();
    if body_len % 6 != 0 {
        return Err(DecodeError::NotAMultiple(widths.len()));
    }
    if widths[body_len..] != STOP {
        return Err(DecodeError::MissingStop);
    }

    let mut values = Vec::new();
    for (index, chunk) in widths[..body_len].chunks(6).enumerate() {
        let pattern: [u8; 6] = chunk.try_into().expect("chunks(6) yields 6");
        match PATTERNS.iter().position(|p| *p == pattern) {
            Some(value) => values.push(value),
            None => {
                return Err(DecodeError::UnknownSymbol {
                    index,
                    widths: pattern.to_vec(),
                })
            }
        }
    }

    if !matches!(values[0], START_A | START_B | START_C) {
        return Err(DecodeError::MissingStart);
    }

    let found = *values.last().expect("length checked above");
    let expected = checksum(&values[..values.len() - 1]);
    if found != expected {
        return Err(DecodeError::BadChecksum { found, expected });
    }

    // Set B only: the data symbols map straight back to ASCII.
    Ok(values[1..values.len() - 1]
        .iter()
        .map(|v| char::from(*v as u8 + 32))
        .collect())
}

/// Parse a run of width digits, e.g. "2112142122222331112".
pub fn parse_widths(text: &str) -> Vec<u8> {
    text.chars().filter_map(|c| c.to_digit(10).map(|d| d as u8)).collect()
}

/// An SVG of the barcode, sized so the narrow module is `module_px` wide.
pub fn to_svg(data: &str, values: &[usize], module_px: f64, height_px: f64) -> String {
    let w = widths(values);
    let quiet = 10.0 * module_px; // Code 128 needs >=10 modules of quiet zone
    let bar_modules: u32 = w.iter().map(|x| *x as u32).sum();
    let total_w = bar_modules as f64 * module_px + quiet * 2.0;
    let text_h = 14.0;
    let total_h = height_px + text_h + 6.0;

    let mut rects = String::new();
    let mut x = quiet;
    for (i, width) in w.iter().enumerate() {
        let px = *width as f64 * module_px;
        if i % 2 == 0 {
            rects.push_str(&format!(
                "<rect x=\"{x:.3}\" y=\"0\" width=\"{px:.3}\" height=\"{height_px:.1}\" />"
            ));
        }
        x += px;
    }

    format!(
        "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{total_w:.1}\" \
height=\"{total_h:.1}\" viewBox=\"0 0 {total_w:.1} {total_h:.1}\" \
shape-rendering=\"crispEdges\">\n\
\x20 <rect width=\"100%\" height=\"100%\" fill=\"#ffffff\"/>\n\
\x20 <g fill=\"#000000\">{rects}</g>\n\
\x20 <text x=\"{mid:.1}\" y=\"{ty:.1}\" font-family=\"monospace\" font-size=\"12\" \
text-anchor=\"middle\" fill=\"#000000\">{label}</text>\n\
</svg>\n",
        mid = total_w / 2.0,
        ty = total_h - 3.0,
        label = escape_xml(data),
    )
}

fn escape_xml(s: &str) -> String {
    s.chars()
        .map(|c| match c {
            '&' => "&amp;".to_string(),
            '<' => "&lt;".to_string(),
            '>' => "&gt;".to_string(),
            '"' => "&quot;".to_string(),
            _ => c.to_string(),
        })
        .collect()
}

// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests {
    use super::*;

    // ---- the table itself, checked rather than trusted -------------------

    #[test]
    fn every_symbol_is_eleven_modules() {
        for (value, pattern) in PATTERNS.iter().enumerate() {
            let total: u32 = pattern.iter().map(|w| *w as u32).sum();
            assert_eq!(total, MODULES_PER_SYMBOL, "value {value} totals {total}");
        }
    }

    #[test]
    fn the_stop_pattern_is_thirteen_modules() {
        assert_eq!(STOP.iter().map(|w| *w as u32).sum::<u32>(), 13);
    }

    #[test]
    fn every_symbols_bars_total_an_even_number_of_modules() {
        // A property of Code 128 that a plain "sums to 11" check misses:
        // it catches a transposed pair of digits, which is the likeliest way
        // to get a table entry wrong when typing it in.
        for (value, pattern) in PATTERNS.iter().enumerate() {
            let bars = pattern[0] + pattern[2] + pattern[4];
            assert_eq!(bars % 2, 0, "value {value} has odd bars: {pattern:?}");
        }
    }

    #[test]
    fn no_two_symbols_share_a_pattern() {
        for i in 0..PATTERNS.len() {
            for j in (i + 1)..PATTERNS.len() {
                assert_ne!(PATTERNS[i], PATTERNS[j], "values {i} and {j} collide");
            }
        }
    }

    #[test]
    fn no_element_is_wider_than_four_modules() {
        for (value, pattern) in PATTERNS.iter().enumerate() {
            for w in pattern {
                assert!((1..=4).contains(w), "value {value} has a {w}-module element");
            }
        }
    }

    // ---- anchored against the published bit patterns ---------------------

    #[test]
    fn known_bit_patterns_match_the_standard() {
        assert_eq!(bits(&PATTERNS[0]), "11011001100", "value 0 (space)");
        assert_eq!(bits(&PATTERNS[START_B]), "11010010000", "Start B");
        assert_eq!(bits(&STOP), "1100011101011", "Stop");
    }

    // ---- encoding --------------------------------------------------------

    #[test]
    fn set_b_values_are_ascii_minus_32() {
        let values = encode_b("0A ").unwrap();
        assert_eq!(values[0], START_B);
        assert_eq!(values[1], 16, "'0' is value 16, not 0");
        assert_eq!(values[2], 33, "'A' is value 33");
        assert_eq!(values[3], 0, "space is value 0");
    }

    #[test]
    fn the_check_symbol_is_computed_the_documented_way() {
        // Worked by hand: start 104, then 'A'=33 at position 1, 'B'=34 at 2.
        // (104 + 1*33 + 2*34) % 103 = 205 % 103 = 102.
        let values = encode_b("AB").unwrap();
        assert_eq!(*values.last().unwrap(), 102);
        assert_eq!((104 + 33 + 2 * 34) % 103, 102);
    }

    #[test]
    fn a_barcode_carries_start_data_check_and_stop() {
        let values = encode_b("ORD-101").unwrap();
        assert_eq!(values.len(), 1 + 7 + 1);
        let w = widths(&values);
        assert_eq!(w.len(), 9 * 6 + 7);
    }

    #[test]
    fn non_ascii_is_refused_rather_than_mangled() {
        assert_eq!(
            encode_b("ORD-۱۰۱"),
            Err(EncodeError::Unsupported { ch: '۱', index: 4 })
        );
        assert_eq!(encode_b(""), Err(EncodeError::Empty));
    }

    // ---- round trip ------------------------------------------------------

    #[test]
    fn every_printable_ascii_character_round_trips() {
        let all: String = (32u8..=126).map(char::from).collect();
        let values = encode_b(&all).unwrap();
        assert_eq!(decode(&widths(&values)).unwrap(), all);
    }

    #[test]
    fn realistic_order_ids_round_trip() {
        for id in ["ORD-101", "C-101", "INV-2026-0042", "ORD-101/A", "a b c"] {
            let values = encode_b(id).unwrap();
            assert_eq!(decode(&widths(&values)).unwrap(), id, "failed on {id}");
        }
    }

    #[test]
    fn a_long_id_round_trips() {
        let long: String = std::iter::repeat("JTQ-9").take(40).collect();
        let values = encode_b(&long).unwrap();
        assert_eq!(decode(&widths(&values)).unwrap(), long);
    }

    // ---- the decoder is strict ------------------------------------------

    #[test]
    fn a_tampered_check_symbol_is_rejected() {
        let mut values = encode_b("ORD-101").unwrap();
        let last = values.len() - 1;
        values[last] = (values[last] + 1) % 103;
        assert!(matches!(
            decode(&widths(&values)),
            Err(DecodeError::BadChecksum { .. })
        ));
    }

    #[test]
    fn a_tampered_data_symbol_is_caught_by_the_checksum() {
        let mut values = encode_b("ORD-101").unwrap();
        values[1] = 40; // change the first character, keep the old check symbol
        assert!(matches!(
            decode(&widths(&values)),
            Err(DecodeError::BadChecksum { .. })
        ));
    }

    #[test]
    fn a_missing_stop_pattern_is_rejected() {
        let values = encode_b("ORD-101").unwrap();
        let mut w = widths(&values);
        w.truncate(w.len() - STOP.len());
        w.extend_from_slice(&[1, 1, 1, 1, 1, 1, 1]);
        assert_eq!(decode(&w), Err(DecodeError::MissingStop));
    }

    #[test]
    fn a_width_that_is_not_a_symbol_is_rejected() {
        let values = encode_b("ORD-101").unwrap();
        let mut w = widths(&values);
        w[6] = 4;
        w[7] = 4; // now that symbol totals more than 11
        assert!(matches!(
            decode(&w),
            Err(DecodeError::UnknownSymbol { .. })
        ));
    }

    #[test]
    fn junk_is_rejected_rather_than_decoded() {
        assert_eq!(decode(&[]), Err(DecodeError::TooShort));
        assert_eq!(decode(&[1; 5]), Err(DecodeError::TooShort));
        assert!(decode(&[1; 40]).is_err());
    }

    // ---- what the Python encoder actually produces -----------------------

    /// Exactly what `barcode_service.py` emits for "ORD-101", taken from a
    /// run of it rather than typed out from reading the source:
    ///
    /// ```text
    /// mods = [START] + [PATTERNS.get(c, "111111") for c in code] + [STOP]
    /// ```
    const PYTHON_ORD_101: &str =
        "2112143122122121231132222111332221222122222221222331112";

    #[test]
    fn the_python_encoders_output_does_not_decode() {
        let w = parse_widths(PYTHON_ORD_101);
        assert_eq!(w.len(), 6 + 7 * 6 + 7, "start + 7 characters + stop");

        let result = decode(&w);
        assert!(result.is_err(), "it should not read back as ORD-101: {result:?}");

        // It does not even reach the checksum. The fifth symbol is '-',
        // which its table stores as 211133 -- 11 modules, so it looks
        // plausible, but it is not one of the 106 Code 128 patterns.
        match result {
            Err(DecodeError::UnknownSymbol { index, ref widths }) => {
                assert_eq!(index, 4);
                assert_eq!(widths, &[2, 1, 1, 1, 3, 3]);
            }
            other => panic!("expected an unknown symbol, got {other:?}"),
        }
    }

    #[test]
    fn the_python_encoder_omits_the_check_symbol_entirely() {
        // Length is the giveaway: 9 symbols' worth of elements for 7
        // characters means start + 7 + stop, with no check symbol between
        // the data and the stop. Ours is one symbol longer for the same
        // input, and that symbol is the only thing that makes it scannable.
        let theirs = parse_widths(PYTHON_ORD_101).len();
        let ours = widths(&encode_b("ORD-101").unwrap()).len();
        assert_eq!(theirs, 6 * 9 + 1, "start + 7 data + stop");
        assert_eq!(ours, 6 * 9 + 6 + 1, "start + 7 data + check + stop");
        assert_eq!(ours - theirs, 6, "exactly one missing symbol");
    }

    #[test]
    fn the_python_space_pattern_is_not_a_code_128_symbol() {
        // "211213" totals 10 modules. Every Code 128 symbol is 11.
        let space = [2u8, 1, 1, 2, 1, 3];
        assert_eq!(space.iter().map(|w| *w as u32).sum::<u32>(), 10);
        assert_ne!(space.iter().map(|w| *w as u32).sum::<u32>(), MODULES_PER_SYMBOL);
        assert!(!PATTERNS.contains(&space));

        // And any character outside its 39-entry table becomes "111111":
        // six modules, which is not a symbol in any symbology.
        let fallback = [1u8, 1, 1, 1, 1, 1];
        assert_eq!(fallback.iter().map(|w| *w as u32).sum::<u32>(), 6);
        assert!(!PATTERNS.contains(&fallback));
    }

    #[test]
    fn the_python_table_is_shifted_by_the_ascii_offset() {
        // Its entry for '0' is 212222, which is this table's value 0 --
        // the space. In set B a character's value is its ASCII code minus
        // 32, so '0' is 16. Every character it encodes is a different one.
        assert_eq!(PATTERNS[0], [2, 1, 2, 2, 2, 2], "value 0 is the space");
        assert_eq!(('0' as usize) - 32, 16);
        assert_ne!(PATTERNS[16], PATTERNS[0]);
    }

    // ---- svg -------------------------------------------------------------

    #[test]
    fn the_svg_has_a_bar_for_every_odd_element() {
        let values = encode_b("ORD-101").unwrap();
        let svg = to_svg("ORD-101", &values, 2.0, 60.0);
        let bars = widths(&values).len().div_ceil(2);
        assert_eq!(svg.matches("<rect x=").count(), bars);
        assert!(svg.contains("ORD-101"));
    }

    #[test]
    fn the_svg_escapes_its_label() {
        let values = encode_b("A&B").unwrap();
        let svg = to_svg("A&B", &values, 2.0, 60.0);
        assert!(svg.contains("A&amp;B"));
        assert!(!svg.contains(">A&B<"));
    }

    #[test]
    fn the_svg_leaves_a_quiet_zone() {
        // Without >=10 modules of clear space either side, a scanner cannot
        // find the start of the symbol however good the bars are.
        let values = encode_b("ORD-101").unwrap();
        let svg = to_svg("ORD-101", &values, 2.0, 60.0);
        assert!(svg.contains("<rect x=\"20.000\""), "first bar should start at 10 modules");
    }
}
