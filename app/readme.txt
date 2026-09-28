Jhagra Textile & Clothing — Atelier Ledger

A lightweight Tkinter desktop application for managing tailoring orders, customer measurement profiles, staff assignments, order finances, and shop floor analytics.

The app uses Excel-backed persistence for its records, a small local SQLite ledger for finance figures, and a neumorphic (soft UI) interface ported from the JTC web app: raised cards and inset wells on one warm-grey canvas, tracked uppercase captions, rounded status pills, and a pastel accent palette — in both a Light and a Dark theme. There is no top bar; the brand, accent strip and clock all sit in the floating sidebar.

Supports a multilingual UI using centralized translation files in `app/lang`. English and Urdu are fully translated; Pashto, Chinese, and Russian are selectable but currently fall back to English.

Key Features:
- Neumorphic UI: raised cards, inset wells, status pills, sidebar-only chrome.
- Dashboard analytics: three donut gauges in one card, counter tiles (orders/customers/tailors on duty), a finance snapshot with donuts, and an inset-row order ledger with status pills.
- Finance section: Paid, Remaining, and Debt per order and shop-wide, each total carrying its own share-of-total donut, with All/Done/Due filter tabs and an Add Payment form, backed by a local SQLite ledger (finance.db).
- Remembers theme, language, last open section, and window size/position between sessions.
- Production calendar: a month grid of deliveries due by day, with due-this-month, due-in-7-days and overdue counts.
- Inventory: fabric and trim stock in inventory.xlsx, with a summary strip (items tracked, total units, low stock, out of stock) and stock-in/stock-out adjustments.
- Brand imagery from app/Images: the shop sign as the window icon and sidebar logo, the owner photo as the login backdrop, sidebar background and page watermark.
- Opens full screen by default; switch to windowed in Settings (F11 toggles, Esc exits). The choice is remembered.
- Customer hub with contact details, address, and measurement cards.
- Staff and task allocation for tailors and shop workers, linked to real orders.
- Order cards with garment types, measurements, style options, delivery, and payment.
- Built-in local Excel data storage and optional PDF receipt generation.

Project Layout:
- `app/`: Application code and modules.
- `app/data/`: Local Excel storage (customers, orders, employees, inventory), finance.db, and the session cache.
- `app/Images/`: Shop sign and owner photos used across the UI.
- `app/models/`: Data models.
- `app/routes/`: Flask API blueprints.
- `app/security/`: Authentication and validation logic.
- `app/services/`: Shared business logic.
- `app/utils/`: finance_db.py, app_state.py, assets.py, and other local persistence helpers.
- `app/lang/`: Translation dictionaries per language.
- `app/changes/`: Dated changelog entries.
- `app/tests/`: Unit tests and GUI smoke tests.
- `app/views/`: Reusable Tkinter views.
- `config.py`: App configuration for data and backup directories.
- `main_gui.py`: Main desktop GUI entry point.
- `run.py`: Flask backend server (optional; the desktop app does not require it).
- `app/README.md`: Markdown documentation.

Getting Started:
1. Create the virtual environment:
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
2. Install dependencies:
   pip install flask flask-cors openpyxl bcrypt filelock reportlab
3. Run the desktop app:
   python main_gui.py
4. Run the backend server (optional):
   python run.py

Testing:
- Run all tests:
  python -m unittest discover -s app/tests
- Run GUI smoke test only:
  python app/tests/gui_smoke_test.py

Notes:
- Excel files are stored under `app/data/`; the finance ledger is `app/data/finance.db`, and the session cache (theme, language, last section, display mode, window size) is `app/data/cache/app_state_cache.json`.
- Brand images load through Pillow, not Tk's own loader: Tk reads only GIF/PNG/PPM and trusts the extension, while these are hand-renamed camera photos. Missing Pillow or a moved folder falls back to plain text chrome.
- `config.py` defines `DATA_DIR`, `BACKUP_DIR`, and `UPLOAD_DIR`.
- `app/README.md` contains the detailed Markdown documentation.
