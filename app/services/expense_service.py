from datetime import date
from decimal import Decimal, InvalidOperation
import os
from uuid import uuid4


EXPENSE_HEADERS = ["id", "date", "category", "description", "amount", "payment_method"]
EXPENSE_CATEGORIES = (
    "Fabric and materials",
    "Rent",
    "Utilities",
    "Salaries",
    "Transport",
    "Maintenance",
    "Other",
)
PAYMENT_METHODS = ("Cash", "Bank transfer", "Card", "Other")


class ExpenseService:
    def __init__(self, excel_manager):
        self.excel_manager = excel_manager

    def _manager(self):
        return self.excel_manager() if callable(self.excel_manager) else self.excel_manager

    def list_expenses(self):
        manager = self._manager()
        if not os.path.exists(manager.get_filepath("expenses.xlsx")):
            return []
        records = manager.read_records("expenses.xlsx", EXPENSE_HEADERS)
        records = [
            {header: record.get(header, "") for header in EXPENSE_HEADERS}
            for record in records
        ]
        return sorted(records, key=lambda row: (row.get("date", ""), row.get("id", "")), reverse=True)

    def add_expense(self, expense_date, category, description, amount, payment_method):
        try:
            normalized_date = date.fromisoformat(str(expense_date).strip()).isoformat()
        except ValueError as exc:
            raise ValueError("Enter a valid date in YYYY-MM-DD format.") from exc

        category = str(category).strip()
        description = str(description).strip()
        payment_method = str(payment_method).strip()
        if category not in EXPENSE_CATEGORIES:
            raise ValueError("Choose a valid expense category.")
        if not description:
            raise ValueError("Enter a description for the expense.")
        if payment_method not in PAYMENT_METHODS:
            raise ValueError("Choose a valid payment method.")

        try:
            normalized_amount = Decimal(str(amount).strip()).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Enter a valid expense amount.") from exc
        if not normalized_amount.is_finite() or normalized_amount <= 0:
            raise ValueError("Expense amount must be greater than zero.")

        expense = {
            "id": f"EXP-{uuid4().hex[:10].upper()}",
            "date": normalized_date,
            "category": category,
            "description": description,
            "amount": f"{normalized_amount:.2f}",
            "payment_method": payment_method,
        }
        self._manager().append_record(
            "expenses.xlsx", EXPENSE_HEADERS,
            [expense[header] for header in EXPENSE_HEADERS],
        )
        return expense