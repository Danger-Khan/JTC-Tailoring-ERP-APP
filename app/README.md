# 🧵 Jhagra Textile & Clothing — Atelier Ledger

An elegant, lightweight desktop management application for tailoring studios and apparel shops. Manages customer directory profiles, tailor measurement records, staff allocations, work assignments, order finances, and real-time shop floor execution metrics.

This desktop app uses a **neumorphic (soft UI)** design system ported from the JTC web app: one warm-grey canvas with surfaces raised a shade above it, depth carried by a lit top edge and a shadowed bottom edge rather than hard borders, small tracked uppercase captions, and a pastel accent palette — in both a light and a dark theme.

---

## ✨ Key Features

* **Neumorphic Design System**: Raised cards and recessed wells on a single warm canvas, tracked uppercase section captions, rounded status pills, and a pastel accent trio along the top of the sidebar — in both Light and Dark theme.
* **Sidebar-only chrome**: there is no separate top bar; the shop's round sign logo, the accent strip, the signed-in owner block and the live clock all sit in the floating sidebar card, so the full width of the window is content.
* **Brand imagery**: the real shop photos in `app/Images/` are used throughout — the sign as the window icon and sidebar logo, and the owner photo as the login backdrop, the sidebar background, and a faint watermark behind every page.
* **Translucent surfaces**: rounded cards (16px) frosted toward the backdrop photo's own colour, so they read as glass over it rather than as opaque blocks.
* **📅 Production Calendar**: a month grid of deliveries due by day, with counts for due-this-month, due-in-7-days and overdue. Read-only, built from each order's delivery date.
* **📦 Inventory**: fabric and trim stock in its own sheet, with a summary strip (items tracked / total units / low stock / out of stock), stock-in and stock-out adjustments, and low/empty rows tinted in the table.
* **Right-to-left Urdu**: picking Urdu or Pashto mirrors the whole layout, not just the wording — sidebar on the right, headings and tables reading from the right, right-aligned input. English is untouched.
* **Quick theme & language**: chips at the foot of the sidebar flip light/dark and switch language without a trip to Settings (Ctrl+T and Ctrl+G do the same).
* **Full screen by default**: the app opens fullscreen for counter use; switch to windowed in Settings, or press F11 to toggle and Esc to leave fullscreen. The choice is remembered.
* **Visual Analytics Dashboard**:
  * Three donut gauges for **Work Done**, **In Progress**, and **Work Remaining**, sharing one card with the reading printed inside each ring.
  * Counter tiles for **Total Orders**, **Customers**, and **Tailors On Duty**.
  * A finance snapshot row (Paid / Remaining / Debt), each with its own share-of-total donut.
  * An active orders ledger drawn as inset rows: order number, a compound customer / garment / tailor cell, and a rounded status pill.
* **Finance**: a dedicated section tracking **Paid**, **Remaining** (unpaid, not yet delivered), and **Debt** (unpaid, already delivered) per order and shop-wide, backed by a small local SQLite ledger (`finance.db`, mirrored from `orders.xlsx`). Each total card carries its own donut showing that bucket's share of the shop's total order value. Includes **All / Done / Due** filter tabs and an **Add Payment** tab to record a payment against any order with an outstanding balance.
* **Remembers where you left off**: theme, language, the sidebar section you were on, and window size/position are cached to disk and restored the next time the app opens.
* **Multilingual UI**: English and Urdu are fully translated (including RTL layout, section headers, buttons, and table headers); Pashto, Chinese, and Russian are selectable but currently fall back to English pending translation. Centralized translation files live under `app/lang`.
* **Customer Hub**:
  * Manage customer profiles, measurement cards, and address/contact details.
  * 1-click order creation from customer records.
* **Order Card**: a digital mirror of the paper order slip — garment type, style options, delivery, and payment, with customer measurements pulled automatically from the customer's saved record.
* **Staff & Task Allocation**:
  * Track employee roles and duty status.
  * Assign tasks by picking a real order (by customer name), which links the order's tailor and the employee's current task together and shows up on the Dashboard.
* **Diagnostics & Settings**:
  * Theme, language, garment types, and employee roles, all editable from one screen.
  * Stores application data in the `data/` folder (Excel) plus small SQLite/JSON caches (`finance.db`, `cache/app_state_cache.json`).
* **Real-time Header Clock**: Displays a live timestamp in the top header bar.

---

## 📁 Directory Structure

```text
app/
├── data/                   <-- Local Excel data storage (incl. inventory.xlsx), finance.db, session cache
├── Images/                 <-- Brand photos: shop sign (logo/icon) and owner
├── models/                 <-- Data model definitions
├── routes/                 <-- Flask API route blueprints
├── security/                <-- Authentication and validation logic
├── services/                <-- Shared business logic and persistence helpers
├── tests/                   <-- Unit tests and smoke tests
├── utils/                   <-- finance_db.py, app_state.py, assets.py, logger, excel_db, migrator
├── lang/                    <-- Per-language translation dictionaries (en, ur, ps, zh, ru)
├── changes/                 <-- Dated changelog entries (one or more per work session)
└── views/                   <-- Reusable Tkinter screen views

config.py                   <-- Application configuration
main_gui.py                 <-- Main Tkinter GUI entry point
run.py                      <-- Flask backend server entry point
README.md                   <-- This documentation file
readme.txt                  <-- Alternate plain-text summary
readme.me                   <-- Short-form summary
```

---

## 🚀 Getting Started

1. Create and activate your virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install flask flask-cors openpyxl bcrypt filelock reportlab
```

3. Run the desktop GUI:

```powershell
python main_gui.py
```

4. Run the Flask API backend (optional — the desktop GUI is fully self-contained on Excel/SQLite and does not require this):

```powershell
python run.py
```

---

## 🧪 Running Tests

To run all tests:

```powershell
python -m unittest discover -s app/tests
```

To run the GUI smoke test only (launches the real app against a throwaway temp data directory and drives it end-to-end):

```powershell
python app/tests/gui_smoke_test.py
```

---

## 🎨 Theme Reference

| Token | Light | Dark | Usage |
| --- | --- | --- | --- |
| `bg_body` (canvas) | `#EBE7E2` | `#2A2927` | Page backdrop; also the fill of inset wells |
| `bg_card` (surface) | `#EEEAE6` | `#323130` | Raised cards, sidebar |
| `border` (line) | `#D9D3CC` | `#3A3835` | Hairline dividers |
| `neu_light` / `neu_shadow` | `#FBF7F2` / `#CDC5BB` | `#3C3A38` / `#1C1B1A` | The lit top edge and shadowed bottom edge that give a card its depth |
| Primary | `#3A3A3A` | same | Dark pill buttons, active nav |
| Sage | `#2ECC8A` | same | Paid, done, ready |
| Amber | `#FFCB6E` | same | In progress, remaining |
| Lavender | `#C9B3F5` | same | Pending / not yet started |
| Terracotta | `#FF8077` | same | Debt |
| Danger | `#BD3228` | same | Destructive actions |

A thin sage / blush / lavender accent strip runs along the top of the sidebar card as a small brand signature.

---

## 🔧 Notes

* Excel files are stored in `app/data/` by default (customers, orders, employees, inventory); the finance ledger lives alongside them in `app/data/finance.db`, and the session cache — theme, language, last section, display mode, window size — in `app/data/cache/app_state_cache.json`.
* Brand images live in `app/Images/`. They are loaded through Pillow rather than Tk's own image loader, because Tk only reads GIF/PNG/PPM and trusts the file extension, while these are hand-renamed camera photos. If Pillow is missing or the folder is moved, every image simply falls back to the plain text chrome.
* `config.py` defines paths for `DATA_DIR`, `BACKUP_DIR`, and `UPLOAD_DIR`.
* The app is intentionally built to use Excel-backed persistence for its records (customers/orders/employees) so it can run without a full SQL server; the Finance ledger and session cache are the two places it uses SQLite/JSON locally for numbers and preferences that benefit from being queried or reloaded directly.
