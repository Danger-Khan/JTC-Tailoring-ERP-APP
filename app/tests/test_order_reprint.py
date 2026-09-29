"""Reprinting a saved order must print the measurements it was taken with.

Every order save snapshots its measurements and styles into
measurements.xlsx / styles.xlsx, keyed by order_id -- and nothing read those
sheets back. The ledger's "Print Order PDF" pulled measurements out of
customers.xlsx instead, which keeps only whatever was entered last.

So: measure a customer, take an order, re-measure them for a second order,
then reprint the first one. It came out with the new numbers on it. A tailor
cuts cloth from that slip.

Two of the style choices had a quieter version of the same problem --
sleeve_type and shalwar_type (Full/Half, Churidar/Patiala) have no column in
orders.xlsx, so they were written to styles.xlsx and never read anywhere.
"""
import os
import shutil
import tempfile
import unittest

from app.excel_manager import ExcelManager
from app.services import order_card_service as svc


def _form(**overrides):
    form = {
        "name": "Farman Saim", "phone": "03001234567", "date": "2026-01-10",
        "address": "Kohat Road", "garments": ["Kameez", "Shalwar"],
        "status": "Pending", "tailor": "Ali", "delivery_status": "Not Delivered",
        "total": "3000", "advance": "1000",
        "lambai": "40", "chest": "38", "waist": "34", "shoulder": "15",
        "sleeve": "22", "collar": "16", "daman": "20",
        "shalwar_length": "38", "paancha": "10",
        "button_style": "Baz Button", "collar_style": "Normal",
        "cuff_style": "Round Cuff", "pocket_style": "One",
        "daman_style": "Round Daman", "stitching": "1. Single Stitch",
        "sleeve_type": "Full", "shalwar_type": "Churidar",
    }
    form.update(overrides)
    return form


class OrderSnapshotTestCase(unittest.TestCase):
    """Against a real ExcelManager on a temp directory, never app/data."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="jtc-reprint-")
        self.mgr = ExcelManager(data_dir=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _customers(self):
        return self.mgr.read_records("customers.xlsx", svc.CUST_HEADERS)

    def _orders(self):
        return self.mgr.read_records("orders.xlsx", svc.ORD_HEADERS)

    def test_the_manager_writes_only_into_its_own_directory(self):
        svc.save_order(self.mgr, [], [], _form())
        self.assertTrue(os.path.exists(os.path.join(self.tmp, "measurements.xlsx")))

    def test_an_order_reprints_with_the_measurements_it_was_taken_with(self):
        """The regression. Re-measuring a customer must not rewrite history."""
        cid, first = svc.save_order(self.mgr, [], [], _form(lambai="40", chest="38"))
        # Months later the same customer is re-measured in the Customer Hub.
        svc.save_customer(self.mgr, self._customers(),
                          _form(lambai="44", chest="46"), cid)

        customer = self._customers()[0]
        self.assertEqual(customer["id"], cid, "still one customer, re-measured")
        self.assertEqual(customer["length"], "44.0", "customers.xlsx keeps the latest")

        meas, from_snapshot = svc.measurements_for_order(self.mgr, first, customer)
        self.assertTrue(from_snapshot)
        self.assertEqual(meas["lambai"], "40.0")
        self.assertEqual(meas["chest"], "38.0")

    def test_two_orders_by_one_customer_keep_separate_measurements(self):
        cid, first = svc.save_order(self.mgr, [], [], _form(lambai="40"))
        _, second = svc.save_order(self.mgr, self._customers(), self._orders(),
                                   _form(lambai="44"), customer_id=cid)
        customer = self._customers()[0]
        self.assertEqual(len(self._customers()), 1, "same customer, not a new one")

        self.assertEqual(svc.measurements_for_order(self.mgr, first, customer)[0]["lambai"],
                         "40.0")
        self.assertEqual(svc.measurements_for_order(self.mgr, second, customer)[0]["lambai"],
                         "44.0")

    def test_an_order_with_no_snapshot_falls_back_and_says_so(self):
        """Orders entered before the order card existed have nothing to read;
        the caller is told, so the slip can label where the numbers came from
        instead of implying they are the order's own."""
        customer = {"id": "C-101", "name": "Older Record", "length": "41",
                    "chest": "39", "shalwar_len": "37"}
        meas, from_snapshot = svc.measurements_for_order(self.mgr, "ORD-999", customer)
        self.assertFalse(from_snapshot)
        self.assertEqual(meas["lambai"], "41")
        self.assertEqual(meas["shalwar_length"], "37")

    def test_an_all_zero_snapshot_is_treated_as_no_snapshot(self):
        """save_order writes a row for every order, zeros included. A row of
        zeros is an order nobody measured, not a customer measured at zero --
        the profile is the better guess, and it gets labelled as the profile."""
        blank = {key: "0" for key, _ in svc.MEASUREMENT_FIELDS}
        self.mgr.write_all_records(
            "measurements.xlsx", svc.MEAS_HEADERS,
            [[{"order_id": "ORD-101", **blank}.get(h, "") for h in svc.MEAS_HEADERS]])
        meas, from_snapshot = svc.measurements_for_order(
            self.mgr, "ORD-101", {"length": "41"})
        self.assertFalse(from_snapshot)
        self.assertEqual(meas["lambai"], "41")

    def test_a_missing_order_id_does_not_match_an_orphaned_row(self):
        """A row whose order_id went missing would otherwise answer to every
        lookup made with a blank id, handing one order another's numbers."""
        orphan = {key: "0" for key, _ in svc.MEASUREMENT_FIELDS}
        orphan.update(order_id="", lambai="99")
        self.mgr.write_all_records(
            "measurements.xlsx", svc.MEAS_HEADERS,
            [[orphan.get(h, "") for h in svc.MEAS_HEADERS]])

        self.assertIsNone(svc.load_measurements(self.mgr, ""))
        self.assertIsNone(svc.load_measurements(self.mgr, None))
        self.assertIsNone(svc.load_measurements(self.mgr, "   "))
        meas, from_snapshot = svc.measurements_for_order(
            self.mgr, "", {"length": "41"})
        self.assertFalse(from_snapshot)
        self.assertEqual(meas["lambai"], "41")

    def test_sleeve_and_shalwar_styles_survive_the_round_trip(self):
        """Neither has a column in orders.xlsx, so styles.xlsx is the only
        place they exist -- and it was never read."""
        _, order_id = svc.save_order(self.mgr, [], [], _form(
            sleeve_type="Half", shalwar_type="Patiala"))
        self.assertNotIn("sleeve_type", svc.ORD_HEADERS)
        self.assertNotIn("shalwar_type", svc.ORD_HEADERS)

        styles = svc.styles_for_order(self.mgr, order_id, self._orders()[0])
        self.assertEqual(styles["sleeve_type"], "Half")
        self.assertEqual(styles["shalwar_type"], "Patiala")
        self.assertEqual(styles["collar_style"], "Normal")

    def test_styles_fall_back_to_the_order_row(self):
        order = {"id": "ORD-900", "collar_style": "Sherwani", "stitching": "3. Choka Stitch"}
        styles = svc.styles_for_order(self.mgr, "ORD-900", order)
        self.assertEqual(styles["collar_style"], "Sherwani")
        self.assertEqual(styles["sleeve_type"], "", "nothing to fall back to")

    def test_every_style_group_is_present_either_way(self):
        _, order_id = svc.save_order(self.mgr, [], [], _form())
        self.assertEqual(set(svc.styles_for_order(self.mgr, order_id)), set(svc.STYLE_GROUPS))
        self.assertEqual(set(svc.styles_for_order(self.mgr, "ORD-nope")), set(svc.STYLE_GROUPS))


class LegacyMeasurementMapTestCase(unittest.TestCase):
    """customer_row and customer_measurements are inverses of each other; the
    map lived in three places before, spelled slightly differently in each."""

    def test_the_customer_row_round_trips_through_the_legacy_columns(self):
        form = _form()
        row = svc.customer_row(form, "C-101")
        recovered = svc.customer_measurements(row)
        for ord_key in svc.LEGACY_CUSTOMER_MEASUREMENTS:
            self.assertEqual(float(recovered[ord_key]), float(form[ord_key]), ord_key)

    def test_the_columns_it_maps_onto_all_exist_in_the_sheet(self):
        for cust_col in svc.LEGACY_CUSTOMER_MEASUREMENTS.values():
            self.assertIn(cust_col, svc.CUST_HEADERS)

    def test_the_keys_it_maps_from_are_all_real_measurements(self):
        keys = {key for key, _ in svc.MEASUREMENT_FIELDS}
        for ord_key in svc.LEGACY_CUSTOMER_MEASUREMENTS:
            self.assertIn(ord_key, keys)

    def test_a_customer_with_nothing_recorded_yields_blanks_not_crashes(self):
        self.assertEqual(set(svc.customer_measurements(None)),
                         set(svc.LEGACY_CUSTOMER_MEASUREMENTS))
        self.assertEqual(set(svc.customer_measurements({}).values()), {""})


if __name__ == "__main__":
    unittest.main()
