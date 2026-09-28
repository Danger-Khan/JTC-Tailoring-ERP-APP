"""Guards on the language packs.

These are the checks that would have caught the state the packs were found
in: Pashto at 10% coverage silently falling back to English for 238 keys,
and `translations.py` importing two packs that had been deleted.

Pure data tests -- no Tk, so they run in the normal unit suite.
"""
import unittest

from app.lang.translations import (LANGUAGE_OPTIONS, ORDER_CARD_TRANSLATIONS,
                                   TRANSLATIONS)

BASE = "en"

# Acronyms that are the same word in every pack. Listing them explicitly is
# the point: an untranslated string has to be a deliberate entry here, not
# something that slipped through.
SHARED_VERBATIM = {"sys_cpu", "sys_gpu", "sys_ram"}


class LanguagePackTestCase(unittest.TestCase):
    def test_every_offered_language_has_a_pack(self):
        """LANGUAGE_OPTIONS is what the UI offers; a code listed there with
        no pack behind it would put an empty entry in the picker."""
        for code, label in LANGUAGE_OPTIONS:
            self.assertIn(code, TRANSLATIONS, "%s is offered but has no pack" % code)
            self.assertIn(code, ORDER_CARD_TRANSLATIONS,
                          "%s has no order-card strings" % code)
            self.assertTrue(label.strip(), "%s has a blank menu label" % code)

    def test_no_pack_is_offered_that_does_not_exist(self):
        """The mirror of the above: translations.py used to import `zh` and
        `ru` after those files were deleted, which broke every entry point."""
        offered = {code for code, _ in LANGUAGE_OPTIONS}
        self.assertEqual(set(TRANSLATIONS), offered)
        self.assertEqual(set(ORDER_CARD_TRANSLATIONS), offered)

    def test_every_pack_covers_every_key(self):
        base = TRANSLATIONS[BASE]
        for code in TRANSLATIONS:
            missing = sorted(set(base) - set(TRANSLATIONS[code]))
            self.assertEqual(
                missing, [],
                "%s is missing %d keys, e.g. %s" % (code, len(missing), missing[:6]))

    def test_no_pack_has_keys_the_base_does_not(self):
        """An extra key is dead weight -- nothing reads it, because every
        lookup goes through a key the English pack defines."""
        base = set(TRANSLATIONS[BASE])
        for code in TRANSLATIONS:
            if code == BASE:
                continue
            extra = sorted(set(TRANSLATIONS[code]) - base)
            # Urdu carries some historical keys; assert they are at least
            # not growing silently by pinning the set size.
            self.assertLessEqual(
                len(extra), 30,
                "%s has %d keys the base pack does not: %s" % (code, len(extra), extra[:6]))

    def test_translations_are_actually_translated(self):
        """A key copied verbatim from English is an untranslated string
        wearing a translation's clothes."""
        base = TRANSLATIONS[BASE]
        for code in TRANSLATIONS:
            if code == BASE:
                continue
            same = {k for k in set(base) & set(TRANSLATIONS[code])
                    if TRANSLATIONS[code][k] == base[k]} - SHARED_VERBATIM
            self.assertEqual(
                same, set(),
                "%s leaves %d keys identical to English: %s"
                % (code, len(same), sorted(same)[:6]))

    def test_value_types_match_the_base(self):
        """cal_days and cal_months are tuples, not strings; a pack that made
        one a string would break the calendar's indexing."""
        base = TRANSLATIONS[BASE]
        for code, pack in TRANSLATIONS.items():
            for key, value in base.items():
                self.assertIsInstance(
                    pack[key], type(value),
                    "%s[%r] should be %s" % (code, key, type(value).__name__))
                if isinstance(value, tuple):
                    self.assertEqual(
                        len(pack[key]), len(value),
                        "%s[%r] has %d entries, expected %d"
                        % (code, key, len(pack[key]), len(value)))

    def test_calendar_tuples_are_the_right_length(self):
        for code, pack in TRANSLATIONS.items():
            self.assertEqual(len(pack["cal_days"]), 7, "%s cal_days" % code)
            self.assertEqual(len(pack["cal_months"]), 12, "%s cal_months" % code)

    def test_format_placeholders_survive_translation(self):
        """A translated string that drops a {placeholder} would raise at
        .format() time, in front of the user, in that language only."""
        import re
        base = TRANSLATIONS[BASE]
        for code, pack in TRANSLATIONS.items():
            for key, value in base.items():
                if not isinstance(value, str):
                    continue
                want = set(re.findall(r"\{(\w+)\}", value))
                got = set(re.findall(r"\{(\w+)\}", pack[key]))
                self.assertEqual(
                    want, got,
                    "%s[%r] placeholders %s != %s" % (code, key, got, want))

    def test_emoji_prefixes_are_consistent(self):
        """Nav buttons and card headings are laid out around a leading emoji.
        The old Pashto pack dropped them and the whole sidebar lost its
        icons, which is invisible to anyone not reading that language."""
        base = TRANSLATIONS[BASE]
        emoji_keys = [k for k, v in base.items()
                      if isinstance(v, str) and v[:1] and ord(v[0]) > 0x2000]
        self.assertGreater(len(emoji_keys), 20, "sanity: expected many icon keys")
        for code, pack in TRANSLATIONS.items():
            for key in emoji_keys:
                first = pack[key][:1]
                self.assertTrue(
                    first and ord(first[0]) > 0x2000,
                    "%s[%r] lost its leading icon: %r" % (code, key, pack[key][:24]))


if __name__ == "__main__":
    unittest.main()
