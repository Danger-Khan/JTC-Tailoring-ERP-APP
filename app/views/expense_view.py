import tkinter as tk
from decimal import Decimal, InvalidOperation
from tkinter import messagebox, ttk
from datetime import date

try:
    from services.expense_service import (
        EXPENSE_CATEGORIES,
        PAYMENT_METHODS,
        ExpenseService,
    )
except ImportError:
    from app.services.expense_service import (
        EXPENSE_CATEGORIES,
        PAYMENT_METHODS,
        ExpenseService,
    )


class ExpenseView:
    def __init__(self, parent, excel_manager, colors):
        self.colors = colors
        self.service = ExpenseService(excel_manager)
        self.frame = tk.Frame(parent, bg=colors["bg_body"])
        self._build()
        self.refresh()

    def _build(self):
        colors = self.colors
        header = tk.Frame(self.frame, bg=colors["bg_body"])
        header.pack(fill=tk.X, padx=2, pady=(2, 14))
        tk.Label(header, text="Shop Expenses", font=("Segoe UI", 19),
                 bg=colors["bg_body"], fg=colors["text_main"]).pack(anchor="w")
        tk.Label(header, text="Record operating costs separately from order payments",
                 font=("Segoe UI", 9), bg=colors["bg_body"],
                 fg=colors["text_muted"]).pack(anchor="w", pady=(2, 0))

        summary = tk.Frame(self.frame, bg=colors["bg_body"])
        summary.pack(fill=tk.X, pady=(0, 12))
        self.month_total = self._summary_value(summary, "THIS MONTH")
        self.all_time_total = self._summary_value(summary, "ALL-TIME EXPENSES")

        form = tk.Frame(self.frame, bg=colors["bg_card"], padx=16, pady=14)
        form.pack(fill=tk.X, pady=(0, 12))
        fields = tk.Frame(form, bg=colors["bg_card"])
        fields.pack(fill=tk.X)

        self.date_entry = self._field(fields, "Date (YYYY-MM-DD)", 0)
        self.date_entry.insert(0, date.today().isoformat())
        self.category_box = self._combo(fields, "Category", 1, EXPENSE_CATEGORIES)
        self.amount_entry = self._field(fields, "Amount (PKR)", 2)
        self.method_box = self._combo(fields, "Payment method", 3, PAYMENT_METHODS)

        detail_row = tk.Frame(form, bg=colors["bg_card"])
        detail_row.pack(fill=tk.X, pady=(10, 0))
        tk.Label(detail_row, text="Description", font=("Segoe UI", 8, "bold"),
                 bg=colors["bg_card"], fg=colors["text_muted"]).pack(anchor="w")
        self.description_entry = tk.Entry(
            detail_row, font=("Segoe UI", 10), bg=colors["well"],
            fg=colors["text_main"], insertbackground=colors["text_main"],
            relief="flat", bd=0,
        )
        self.description_entry.pack(fill=tk.X, ipady=6, pady=(4, 0))

        actions = tk.Frame(form, bg=colors["bg_card"])
        actions.pack(fill=tk.X, pady=(10, 0))
        tk.Button(actions, text="Add expense", command=self.add_expense,
                  bg="#3A3A3A", fg="#F1F1F0", font=("Segoe UI", 9, "bold"),
                  bd=0, padx=16, pady=8, cursor="hand2").pack(side=tk.RIGHT)

        table = tk.Frame(self.frame, bg=colors["bg_card"])
        table.pack(fill=tk.BOTH, expand=True)
        columns = ("date", "category", "description", "amount", "payment_method")
        self.tree = ttk.Treeview(table, columns=columns, show="headings", height=10)
        headings = {
            "date": ("DATE", 110),
            "category": ("CATEGORY", 180),
            "description": ("DESCRIPTION", 300),
            "amount": ("AMOUNT (PKR)", 130),
            "payment_method": ("PAYMENT METHOD", 150),
        }
        for column, (label, width) in headings.items():
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=80, anchor="w")
        scrollbar = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(12, 0), pady=12)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=12)

    def _summary_value(self, parent, caption):
        card = tk.Frame(parent, bg=self.colors["bg_card"], padx=16, pady=12)
        card.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        tk.Label(card, text=caption, font=("Segoe UI", 8, "bold"),
                 bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack(anchor="w")
        value = tk.Label(card, text="PKR 0.00", font=("Segoe UI", 16),
                         bg=self.colors["bg_card"], fg=self.colors["text_main"])
        value.pack(anchor="w", pady=(4, 0))
        return value

    def _field(self, parent, label, column):
        wrapper = tk.Frame(parent, bg=self.colors["bg_card"])
        wrapper.grid(row=0, column=column, sticky="ew", padx=(0, 12))
        parent.grid_columnconfigure(column, weight=1)
        tk.Label(wrapper, text=label, font=("Segoe UI", 8, "bold"),
                 bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack(anchor="w")
        entry = tk.Entry(wrapper, font=("Segoe UI", 10), bg=self.colors["well"],
                         fg=self.colors["text_main"], insertbackground=self.colors["text_main"],
                         relief="flat", bd=0)
        entry.pack(fill=tk.X, ipady=6, pady=(4, 0))
        return entry

    def _combo(self, parent, label, column, values):
        wrapper = tk.Frame(parent, bg=self.colors["bg_card"])
        wrapper.grid(row=0, column=column, sticky="ew", padx=(0, 12))
        parent.grid_columnconfigure(column, weight=1)
        tk.Label(wrapper, text=label, font=("Segoe UI", 8, "bold"),
                 bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack(anchor="w")
        combo = ttk.Combobox(wrapper, values=values, state="readonly", font=("Segoe UI", 9))
        combo.current(0)
        combo.pack(fill=tk.X, pady=(4, 0), ipady=3)
        return combo

    def add_expense(self):
        try:
            self.service.add_expense(
                self.date_entry.get(), self.category_box.get(),
                self.description_entry.get(), self.amount_entry.get(),
                self.method_box.get(),
            )
        except ValueError as exc:
            messagebox.showerror("Invalid expense", str(exc), parent=self.frame)
            return
        except Exception as exc:
            messagebox.showerror("Could not save expense", str(exc), parent=self.frame)
            return

        self.description_entry.delete(0, tk.END)
        self.amount_entry.delete(0, tk.END)
        self.refresh()

    def refresh(self):
        records = self.service.list_expenses()
        for row_id in self.tree.get_children():
            self.tree.delete(row_id)

        today = date.today()
        month_total = Decimal("0.00")
        all_time_total = Decimal("0.00")
        for record in records:
            try:
                amount = Decimal(record.get("amount", "0"))
            except (InvalidOperation, ValueError):
                amount = Decimal("0.00")
            all_time_total += amount
            if record.get("date", "").startswith(today.strftime("%Y-%m")):
                month_total += amount
            self.tree.insert("", tk.END, values=(
                record.get("date", ""), record.get("category", ""),
                record.get("description", ""), f"{amount:,.2f}",
                record.get("payment_method", ""),
            ))

        self.month_total.configure(text=f"PKR {month_total:,.2f}")
        self.all_time_total.configure(text=f"PKR {all_time_total:,.2f}")
