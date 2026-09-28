from . import en, ur, ps

LANGUAGE_OPTIONS = [
    ("en", "English 🇬🇧"),
    ("ur", "Urdu 🇵🇰"),
    ("ps", "Pashto 🇦🇫"),
]

ORDER_CARD_TRANSLATIONS = {
    "en": en.ORDER_CARD,
    "ur": ur.ORDER_CARD,
    "ps": ps.ORDER_CARD,
}

TRANSLATIONS = {
    "en": en.TRANSLATIONS,
    "ur": ur.TRANSLATIONS,
    "ps": ps.TRANSLATIONS,
}

__all__ = ["LANGUAGE_OPTIONS", "ORDER_CARD_TRANSLATIONS", "TRANSLATIONS"]
