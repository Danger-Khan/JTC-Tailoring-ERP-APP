"""One spelling of the shop's name, for everything that prints or shows it.

The name reached the customer in three different forms. The sidebar, the
order receipts and the confirmation SMS said "Jhagra Creation & Fabrics";
the window title said "Jhagra Textile & Clothing - Atelier Ledger"; and the
API's invoice engine said "ATELIER TAILORING & DESIGN STUDIO" with a
"+92 300 1234567" under it -- placeholders from the template this project
started out as, sitting on a document that goes out with an order.

Address and phone are deliberately empty. A made-up phone number on a
receipt is worse than no phone number on a receipt, so the masthead skips
whatever is blank; fill these in and every printed document picks them up.
"""

NAME = "Jhagra Creation & Fabrics"
NAME_UPPER = "JHAGRA CREATION & FABRICS"
TAGLINE = "The Name Of Quality - JTQ"
SHORT = "JTQ"

ADDRESS = ""
PHONE = ""

# Window title, log banners, backup filenames -- anywhere the app names
# itself rather than the shop.
APP_TITLE = "%s - Order Ledger" % NAME
SLUG = "jtq"


def header_lines():
    """The receipt masthead: name, tagline, and whatever contact details the
    shop has actually supplied."""
    return [line for line in (NAME_UPPER, TAGLINE, ADDRESS, PHONE) if line]
