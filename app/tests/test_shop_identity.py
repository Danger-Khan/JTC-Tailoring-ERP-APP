"""The shop's name, wherever a customer or the shopkeeper can read it.

It had drifted into three spellings. The receipts, the sidebar and the
confirmation SMS said "Jhagra Creation & Fabrics"; the window title said
"Jhagra Textile & Clothing - Atelier Ledger"; and the API's invoice engine
still carried the starter template's "ATELIER TAILORING & DESIGN STUDIO"
above a "+92 300 1234567" that belongs to nobody -- on a document that goes
out with an order.

These tests read the source files rather than only the constants, because
the failure mode is someone typing the name inline again.
"""
import os
import re
import unittest

from app.services import invoice_service, order_card_service as svc
from app.services import shop_identity as shop

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Files that print or display the shop's name. Excludes the changelog (it
# quotes the old strings on purpose) and the tests (this file names them).
SOURCE_FILES = [
    "app/main_gui.py",
    "app/run.py",
    "app/cli.py",
    "app/services/order_card_service.py",
    "app/services/invoice_service.py",
    "app/services/backup_service.py",
    "app/services/notification_service.py",
    "app/utils/migrator.py",
]


def _read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as handle:
        return handle.read()


class BrandingTestCase(unittest.TestCase):

    def test_no_source_file_still_says_atelier(self):
        """The name of the template this project started from, left on the
        window title, the server banner, the CLI help and an invoice."""
        offenders = [rel for rel in SOURCE_FILES
                     if "atelier" in _read(rel).lower()]
        self.assertEqual(offenders, [], "still branded Atelier: %s" % offenders)

    def test_the_window_title_names_the_shop(self):
        self.assertIn(shop.NAME, shop.APP_TITLE)
        self.assertIn("self.title(card_svc.shop.APP_TITLE)", _read("app/main_gui.py"))

    def test_every_printed_masthead_agrees(self):
        """Four documents print the name: the thermal receipt, the order-card
        PDF, the ledger's PDF and the API invoice."""
        form = {"name": "Farman", "phone": "0300", "total": "1000", "advance": "0"}
        receipt = svc.build_receipt_text(form, "C-101", "ORD-101")
        self.assertIn(shop.NAME_UPPER, receipt)
        self.assertIn(shop.TAGLINE, receipt)

        self.assertEqual(invoice_service.InvoiceEngine.SHOP_NAME, shop.NAME_UPPER)

        for rel in ("app/main_gui.py", "app/services/order_card_service.py"):
            source = _read(rel)
            self.assertNotIn('"%s"' % shop.NAME_UPPER, source,
                             "%s hardcodes the name again" % rel)

    def test_a_blank_contact_line_is_left_off_not_printed_empty(self):
        """A made-up phone number on a receipt is worse than none; an empty
        line where one should be is nearly as bad."""
        self.assertEqual(shop.header_lines()[:2], [shop.NAME_UPPER, shop.TAGLINE])
        self.assertNotIn("", shop.header_lines())

        form = {"name": "Farman", "phone": "0300", "total": "1000", "advance": "0"}
        head = svc.build_receipt_text(form, "C-101", "ORD-101").split("\n")
        self.assertTrue(head[0].strip(), "receipt starts with a blank line")
        self.assertNotIn("+92 300 1234567", "\n".join(head))

    def test_a_supplied_contact_line_does_get_printed(self):
        """The whole point of leaving them blank is that filling them in
        works -- otherwise it is just a deletion."""
        saved = (shop.ADDRESS, shop.PHONE)
        shop.ADDRESS, shop.PHONE = "Kohat Road, Peshawar", "+92 91 000000"
        try:
            lines = shop.header_lines()
            self.assertEqual(lines[2:], ["Kohat Road, Peshawar", "+92 91 000000"])
            form = {"name": "Farman", "phone": "0300", "total": "1", "advance": "0"}
            receipt = svc.build_receipt_text(form, "C-101", "ORD-101")
            self.assertIn("Kohat Road, Peshawar", receipt)
        finally:
            shop.ADDRESS, shop.PHONE = saved

    def test_backups_are_named_after_this_shop(self):
        source = _read("app/services/backup_service.py")
        self.assertIn("shop.SLUG", source)
        self.assertNotIn("backup_atelier_", source)

    def test_the_notification_text_uses_the_same_name(self):
        """It was already right -- keep it that way, case-insensitively: the
        SMS is sentence case, the receipt masthead is upper."""
        self.assertIn(shop.NAME.lower(), _read("app/services/notification_service.py").lower())


class ReceiptContentTestCase(unittest.TestCase):
    """The masthead change must not have eaten anything below it."""

    def setUp(self):
        self.form = {
            "name": "Farman Saim", "phone": "03001234567", "date": "2026-01-10",
            "garments": ["Kameez"], "status": "Pending",
            "total": "3000", "advance": "1000",
            "collar_style": "Normal", "cuff_style": "Round Cuff",
            "pocket_style": "One", "button_style": "Baz Button",
            "daman_style": "Round Daman", "stitching": "1. Single Stitch",
        }
        self.receipt = svc.build_receipt_text(self.form, "C-101", "ORD-101")

    def test_the_order_details_still_print(self):
        for expected in ("ORD-101", "Farman Saim", "03001234567", "Kameez"):
            self.assertIn(expected, self.receipt)

    def test_the_money_still_adds_up(self):
        self.assertIn("Total     : PKR 3000.00", self.receipt)
        self.assertIn("Advance   : PKR 1000.00", self.receipt)
        self.assertIn("Remaining : PKR 2000.00", self.receipt)

    def test_every_line_fits_a_40_column_printer(self):
        for line in self.receipt.split("\n"):
            self.assertLessEqual(len(line), 40, repr(line))

    def test_the_masthead_is_centred(self):
        first = self.receipt.split("\n")[0]
        self.assertEqual(first.strip(), shop.NAME_UPPER)
        self.assertEqual(len(first), 40)
        # Centred, not left-padded by accident.
        lead = len(first) - len(first.lstrip())
        self.assertLessEqual(abs(lead - (40 - len(shop.NAME_UPPER) - lead)), 1)


class InvoiceEngineTestCase(unittest.TestCase):
    """Unwired today, but it is what the API would hand a customer."""

    ORDER = {"invoice_number": "INV-9", "customer_name": "Farman Saim",
             "garment_type": "Shalwar Kameez", "price": 3000,
             "advance_payment": 1000, "discount": 200}

    def test_the_thermal_receipt_names_this_shop(self):
        text = invoice_service.InvoiceEngine.generate_thermal_text_receipt(self.ORDER)
        self.assertIn(shop.NAME_UPPER, text)
        self.assertNotIn("ATELIER", text)
        self.assertNotIn("1234567", text)

    def test_the_thermal_receipt_has_no_blank_masthead_lines(self):
        body = invoice_service.InvoiceEngine.generate_thermal_text_receipt(self.ORDER)
        head = [line for line in body.split("\n") if line.strip()][:1]
        self.assertEqual(head[0].strip(), shop.NAME_UPPER)
        self.assertNotRegex(body, r"\n[ \t]*\n[ \t]*=")

    def test_the_balance_is_price_minus_discount_minus_advance(self):
        text = invoice_service.InvoiceEngine.generate_thermal_text_receipt(self.ORDER)
        self.assertIn("1800.00", text)

    def test_the_html_invoice_names_this_shop_and_escapes_its_input(self):
        html_out = invoice_service.InvoiceEngine.generate_printable_html_invoice(
            {**self.ORDER, "customer_name": "<script>alert(1)</script>"})
        self.assertIn(shop.NAME_UPPER, html_out)
        self.assertNotIn("ATELIER", html_out)
        self.assertNotIn("<script>", html_out)

    def test_the_html_contact_line_is_not_a_bare_separator(self):
        html_out = invoice_service.InvoiceEngine.generate_printable_html_invoice(self.ORDER)
        self.assertNotRegex(html_out, r"<p>\s*\|\s*</p>")
        self.assertIn(shop.TAGLINE, re.sub(r"\s+", " ", html_out))


if __name__ == "__main__":
    unittest.main()
