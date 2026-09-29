import os
import shutil
import openpyxl
from datetime import datetime
from filelock import FileLock
from config import Config

# Row 1 of every workbook this module manages. Everything here keys off the
# header row by name -- get_all() zips it to each value row, save_record()
# maps a record's fields onto it, delete_record() finds the id column in it --
# so a table without one is not an empty table, it is an unreadable one.
#
# The column lists mirror the to_dict() order of the matching model in
# app/models/schemas.py; `users` has no model and follows the record built by
# auth_routes.create_user().
TABLE_SCHEMAS = {
    "users": ["id", "username", "password_hash", "role", "created_at"],
    "customers": ["id", "name", "phone", "chest", "waist", "length",
                  "sleeves", "created_at"],
    "orders": ["id", "invoice_number", "customer_id", "customer_name",
               "garment_type", "price", "advance_payment", "discount",
               "remaining_balance", "order_date", "delivery_date", "status",
               "assigned_tailor", "priority", "measurements_snapshot",
               "notes"],
    "employees": ["id", "name", "role", "status", "phone", "salary", "cnic",
                  "current_task", "specialization"],
    "inventory": ["id", "item_code", "item_name", "stock_quantity",
                  "min_stock_alert", "unit", "category", "unit_cost",
                  "selling_price", "supplier"],
}


def _write_header_row(sheet, headers):
    """Put `headers` in row 1.

    Not sheet.append(): on a workbook loaded from disk that was saved with an
    empty sheet, max_row reads 1 while the sheet holds nothing, and append
    lands on row 2 -- leaving row 1 blank and every subsequent read of
    sheet[1] returning a row of Nones.
    """
    for col, name in enumerate(headers, 1):
        sheet.cell(row=1, column=col).value = name


def _has_header_row(sheet):
    return sheet.max_row >= 1 and any(cell.value is not None for cell in sheet[1])

class ExcelDB:
    """Abstract database handler. Replace this class to migrate to SQL later."""
    
    def __init__(self, table_name: str):
        self.filepath = os.path.join(Config.DATA_DIR, f"{table_name}.xlsx")
        self.lockpath = f"{self.filepath}.lock"

    def _backup(self):
        """Creates a timestamped backup before any write operation."""
        if os.path.exists(self.filepath):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_filename = f"{timestamp}_{os.path.basename(self.filepath)}"
            shutil.copy2(self.filepath, os.path.join(Config.BACKUP_DIR, backup_filename))

    def get_all(self) -> list[dict]:
        """Reads Excel safely and returns a list of dictionaries."""
        if not os.path.exists(self.filepath):
            return []
            
        with FileLock(self.lockpath):
            try:
                wb = openpyxl.load_workbook(self.filepath, data_only=True)
                sheet = wb.active
                rows = list(sheet.iter_rows(values_only=True))
                
                if not rows or len(rows) < 2:
                    return []
                    
                headers = [str(h) for h in rows[0]]
                return [dict(zip(headers, row)) for row in rows[1:]]
            except Exception as e:
                # Log corruption detection here
                raise RuntimeError(f"Database read error: {str(e)}")

    def save_record(self, record: dict, id_field: str = 'id'):
        """Inserts or updates a record transactionally."""
        with FileLock(self.lockpath):
            self._backup()
            wb = openpyxl.load_workbook(self.filepath) if os.path.exists(self.filepath) else openpyxl.Workbook()
            sheet = wb.active

            # Handle a sheet with no header row: seed one from this record's
            # own fields, in row 1 (see _write_header_row on why not append).
            if not _has_header_row(sheet):
                _write_header_row(sheet, list(record.keys()))

            headers = [str(cell.value) for cell in sheet[1]]
            existing_id_col = headers.index(id_field) + 1 if id_field in headers else None

            # Check for update
            updated = False
            if existing_id_col:
                for row_idx in range(2, sheet.max_row + 1):
                    if str(sheet.cell(row_idx, existing_id_col).value) == str(record.get(id_field)):
                        for col_idx, key in enumerate(headers, 1):
                            sheet.cell(row_idx, col_idx).value = record.get(key, "")
                        updated = True
                        break

            # Insert if not updated
            if not updated:
                row_data = [record.get(h, "") for h in headers]
                sheet.append(row_data)

            wb.save(self.filepath)

    def delete_record(self, record_id, id_field: str = 'id') -> bool:
        """Delete one record by id, retaining the workbook schema and backup."""
        if not os.path.exists(self.filepath):
            return False
        with FileLock(self.lockpath):
            self._backup()
            wb = openpyxl.load_workbook(self.filepath)
            sheet = wb.active
            headers = [str(cell.value) for cell in sheet[1]]
            if id_field not in headers:
                return False
            id_col = headers.index(id_field) + 1
            for row_idx in range(2, sheet.max_row + 1):
                if str(sheet.cell(row_idx, id_col).value) == str(record_id):
                    sheet.delete_rows(row_idx, 1)
                    wb.save(self.filepath)
                    return True
            return False

def initialize_database():
    """Create any missing API tables, each with its header row.

    This used to save a bare `openpyxl.Workbook()`, i.e. a workbook whose one
    sheet is completely empty. That is not a usable empty table: get_all()
    bails on `len(rows) < 2` and so returns [] no matter what is written
    afterwards, delete_record() raises ValueError looking for the id column,
    and save_record()'s repair path wrote its headers into row 2 -- after
    which every field mapped through row 1 resolved to None and each record
    was stored as a row of blanks. app/data/users.xlsx is still headerless
    from the single time this ran with app/ on sys.path.

    Existing workbooks are left alone apart from that one repair: a file that
    already has a header row keeps it, even if its columns differ from
    TABLE_SCHEMAS. Reshaping somebody's data is not initialisation's job.
    """
    if os.path.abspath(Config.DATA_DIR) == os.path.abspath(Config.DESKTOP_DATA_DIR):
        raise RuntimeError(
            "Refusing to initialise API tables in the desktop app's data "
            "directory (%s). Both sides define customers/orders/inventory/"
            "employees with different columns, so creating them here would "
            "write the API's schema over live shop records. Point "
            "JTC_DATA_DIR somewhere else." % Config.DESKTOP_DATA_DIR)

    for table, headers in TABLE_SCHEMAS.items():
        db = ExcelDB(table)
        if os.path.exists(db.filepath):
            wb = openpyxl.load_workbook(db.filepath)
            sheet = wb.active
            if not _has_header_row(sheet):
                _write_header_row(sheet, headers)
                wb.save(db.filepath)
            continue
        wb = openpyxl.Workbook()
        _write_header_row(wb.active, headers)
        wb.save(db.filepath)
