import os
import shutil
import tempfile
import unittest

from app.excel_manager import ExcelManager
from app.services.expense_service import ExpenseService


class ExpenseServiceTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="expense_service_test_")
        self.excel_manager = ExcelManager(data_dir=self.temp_dir)
        self.service = ExpenseService(self.excel_manager)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_expense_round_trips_without_changing_customer_records(self):
        self.excel_manager.append_record(
            "customers.xlsx", ["id", "name"], ["C-1", "Existing Customer"]
        )

        expense = self.service.add_expense(
            "2026-09-28", "Utilities", "Workshop electricity", "1250", "Cash"
        )

        self.assertEqual(expense["amount"], "1250.00")
        self.assertEqual(self.service.list_expenses(), [expense])
        self.assertEqual(
            self.excel_manager.read_records("customers.xlsx", ["id", "name"])[0]["name"],
            "Existing Customer",
        )
        self.assertTrue(os.path.exists(os.path.join(self.temp_dir, "expenses.xlsx")))

    def test_rejects_invalid_or_nonpositive_amounts(self):
        for amount in ("0", "-3", "not money"):
            with self.subTest(amount=amount):
                with self.assertRaises(ValueError):
                    self.service.add_expense(
                        "2026-09-28", "Utilities", "Electricity", amount, "Cash"
                    )

    def test_rejects_invalid_dates_and_empty_descriptions(self):
        with self.assertRaises(ValueError):
            self.service.add_expense("yesterday", "Utilities", "Electricity", "10", "Cash")
        with self.assertRaises(ValueError):
            self.service.add_expense("2026-09-28", "Utilities", "", "10", "Cash")


if __name__ == "__main__":
    unittest.main()