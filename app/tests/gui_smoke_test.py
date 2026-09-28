"""Permanent GUI smoke test for the Atelier ERP Tkinter app.

Launches the real AtelierERPApp pointed at a throwaway temp data dir,
then verifies: login -> dashboard, section navigation, theme/language
switches, modal dialogs, Excel persistence, PDF generation and charts.

Run directly:
    python app/tests/gui_smoke_test.py

Exits non-zero if any check fails.
"""
import sys
import os
import shutil
import tempfile
import traceback

from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT.parent
PROJECT_ROOT = APP_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(1, str(APP_DIR))

from app import main_gui as gui

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS  " if cond else "FAIL  ") + name)


def hook(level, *args, **kwargs):
    print(f"[msgbox:{level}]", args)


# Neutralize blocking dialogs
gui.messagebox.showerror = lambda *a, **k: hook("error", *a)
gui.messagebox.showwarning = lambda *a, **k: hook("warning", *a)
gui.messagebox.showinfo = lambda *a, **k: hook("info", *a)

SKIP_PDF = False
try:
    import reportlab  # noqa
except ImportError:
    SKIP_PDF = True

tmpdir = tempfile.mkdtemp(prefix="atelier_gui_smoke_")
pdf_path = None

def run_gui_smoke_test():
    try:
        app = gui.AtelierERPApp()
        app.update()
        check("login dialog shows", hasattr(app, "login_dlg") and app.login_dlg.winfo_exists())

        # Display mode: the app opens fullscreen by default, so drop it back to
        # windowed before the rest of the run (a real fullscreen test window
        # covering the screen for the whole suite is no fun) -- which also
        # exercises the toggle both ways.
        # Asserting a bare "starts fullscreen" here would flap: the app
        # restores whatever display mode the real cache holds, so this check
        # passed or failed depending on how the developer last left the app.
        # Assert the two halves that are actually contracts instead -- the
        # default with nothing saved, and the window agreeing with whatever
        # was restored.
        from app.utils.app_state import AppStateCache, DEFAULTS
        empty_state = AppStateCache(os.path.join(tmpdir, "never_written"))
        check("display mode defaults to fullscreen with nothing saved",
              DEFAULTS["display_mode"] == "fullscreen"
              and empty_state.load()["display_mode"] == "fullscreen")
        check("window agrees with the restored display mode",
              bool(app.attributes("-fullscreen")) == (app.display_mode == "fullscreen"))
        app.apply_display_mode("fullscreen", persist=False)
        app.update()
        check("fullscreen mode turns fullscreen on", app.display_mode == "fullscreen"
              and bool(app.attributes("-fullscreen")))
        app.apply_display_mode("windowed", persist=False)
        app.update()
        check("windowed mode turns fullscreen off", app.display_mode == "windowed"
              and not bool(app.attributes("-fullscreen")))
        app.toggle_display_mode()
        check("F11 toggle returns to fullscreen", app.display_mode == "fullscreen")
        app.apply_display_mode("windowed", persist=False)
        app.update()
        sw, sh = app.winfo_screenwidth(), app.winfo_screenheight()
        check("off-screen saved geometry is pulled back on screen",
              app._sane_geometry("1536x793+-164+54") == "1536x793+0+54")
        check("oversized saved geometry is capped to the screen",
              app._sane_geometry("9999x9999+0+0") == "%dx%d+0+0" % (sw, sh))
        check("edge-relative geometry is left alone",
              app._sane_geometry("1350x850-20-20") == "1350x850-20-20")
        check("unparseable geometry is left to Tk",
              app._sane_geometry("1350x850") == "1350x850"
              and app._sane_geometry("garbage") == "garbage")
        app.apply_display_mode("windowed", persist=False)
        app.update()

        # --- Point the app at a throwaway data dir and seed it ---
        temp_mgr = gui.ExcelManager(data_dir=tmpdir)
        app.excel_mgr = temp_mgr
        temp_mgr.append_record("customers.xlsx", app.cust_headers,
                               ["C-101", "Test Customer", "03001234567", "42", "19", "17", "15", "38", "34", "46", "36", "22"])
        temp_mgr.append_record("orders.xlsx", app.ord_headers,
                               ["ORD-101", "Test Customer", "Shalwar Kameez", "In Progress", "Tailor One",
                                "Half Ban", "Round Cuff", "Side Pocket", "Square Daman", "1. Single Stitch", "Baz Button"])
        # Second order, fully populated (incl. finance columns) and already
        # Delivered with an unpaid balance -- exercises the finance ledger's
        # "debt" bucket (delivered + unpaid) distinctly from "remaining".
        temp_mgr.append_record("orders.xlsx", app.ord_headers,
                               ["ORD-102", "C-101", "Waistcoat", "Delivered", "Tailor One",
                                "Chinese", "Round Cuff", "One", "Square Daman", "1. Single Stitch", "Karh Button",
                                "2026-01-01", "2026-01-05", "17:00", "Tailor One",
                                "Delivered", "", "5000.00", "2000.00", "3000.00"])
        # Third order, fully paid (total == advance, remaining 0, not
        # delivered) -- exercises the finance ledger's "Done" tab distinctly
        # from "Due" (ORD-102) and plain "All" (ORD-101, no total/advance).
        temp_mgr.append_record("orders.xlsx", app.ord_headers,
                               ["ORD-103", "C-101", "Pant", "Ready", "Tailor One",
                                "Normal", "Normal", "One", "Normal", "1. Single Stitch", "Normal",
                                "2026-01-02", "2026-01-08", "", "", "Not Delivered", "", "2000.00", "2000.00", "0.00"])
        temp_mgr.append_record("employees.xlsx", app.emp_headers,
                               ["E-1", "Tailor One", "0300", "Master Cutter", "On Duty", ""])
        # Inventory: one healthy item, one at its reorder level, one empty --
        # so the summary strip has a non-zero number in every bucket.
        temp_mgr.append_record("inventory.xlsx", app.inv_headers,
                               ["INV-101", "Cotton Lawn", "Fabric", "40", "m", "10", "2026-01-01"])
        temp_mgr.append_record("inventory.xlsx", app.inv_headers,
                               ["INV-102", "Baz Buttons", "Trim", "8", "pcs", "20", "2026-01-01"])
        temp_mgr.append_record("inventory.xlsx", app.inv_headers,
                               ["INV-103", "Silk Thread", "Trim", "0", "pcs", "5", "2026-01-01"])

        # --- Login ---
        app.ent_pwd.insert(0, "admin123")
        app.authenticate()
        app.update()
        check("login -> dashboard builds", hasattr(app, "tree_orders") and app.tree_orders.winfo_exists())
        check("seeded orders shown", len(app.tree_orders.get_children()) == 3)
        check("seeded customers shown", len(app.tree_customers.get_children()) == 1)
        check("seeded employees shown", len(app.tree_employees.get_children()) == 1)

        # --- Neumorphic redesign (ported from the web app's design system) ---
        # Compare against the theme the app actually started in -- it restores
        # whichever one was saved, so pinning this to "light" would fail for a
        # user whose last session was dark.
        check("neumorphic canvas palette active",
              app.colors["bg_body"] == gui.THEMES[app.current_theme]["bg_body"]
              and "well" in app.colors and "neu_light" in app.colors)
        # The separate top header bar was folded into the sidebar card, so the
        # brand and the clock now live there and header_frame is gone for good.
        check("top bar folded into the sidebar",
              not hasattr(app, "header_frame") and app.lbl_clock.winfo_exists())
        # The ledger is drawn as inset rows over a hidden tree_orders, which
        # stays the data + selection model for every existing caller.
        check("ledger renders a row per order",
              len(app._ledger_row_widgets) == len(app.tree_orders.get_children()) == 3)
        first_row = list(app._ledger_row_widgets)[0]
        app._select_ledger_row(first_row)
        check("clicking a ledger row drives tree_orders selection",
              app.tree_orders.selection() and app.tree_orders.selection()[0] == first_row)
        check("dashboard counter tiles populated",
              app.lbl_stat_orders.cget("text") == "3"
              and app.lbl_stat_customers.cget("text") == "1")
        # --- Production calendar + inventory ---
        check("inventory loaded from its own sheet", len(app.inventory) == 3)
        check("inventory summary counts low and out of stock",
              app.lbl_inv_stat_items.cget("text") == "3"
              and app.lbl_inv_stat_low.cget("text") == "1"
              and app.lbl_inv_stat_out.cget("text") == "1"
              and app.lbl_inv_stat_units.cget("text") == "48")
        # ORD-101 has no delivery_date, ORD-103/104 do; ORD-102 is delivered
        # already and must not be counted as production work.
        _due = app._orders_by_due_date()
        _bucketed = [o for orders in _due.values() for o in orders]
        _ids = {gui.clean_val(o.get("id")) for o in _bucketed}
        # Must be non-empty, or the "excludes delivered" half below would pass
        # for free -- which is how the "Not Delivered" substring bug hid.
        check("calendar buckets undelivered orders by due date",
              _ids == {"ORD-103"})  # 101 has no due date, 102 is delivered
        check("calendar treats 'Not Delivered' as still due",
              app._is_delivered({"delivery_status": "Not Delivered"}) is False
              and app._is_delivered({"delivery_status": "Delivered"}) is True)
        check("calendar parses the sheet's date format",
              app._parse_date("2026-01-08") is not None
              and app._parse_date("") is None
              and app._parse_date("not a date") is None)
        app.show_section("calendar")
        app.update()
        check("calendar grid renders day cells",
              len(app.cal_grid.winfo_children()) > 7)
        _m, _y = app.cal_month, app.cal_year
        app.shift_calendar_month(1)
        check("calendar month navigation advances",
              (app.cal_year, app.cal_month) != (_y, _m))
        app.calendar_today()
        app.show_section("dashboard")
        app.update()

        check("finance section cards carry donuts",
              app.chart_fin_card_paid.winfo_exists()
              and app.chart_fin_card_remaining.winfo_exists()
              and app.chart_fin_card_debt.winfo_exists())

        # --- Section navigation ---
        for key in ["customer", "employee", "calendar", "inventory",
                    "finance", "admin", "dashboard"]:
            app.show_section(key)
            app.update()
            check(f"section '{key}' visible", bool(app.sections[key].winfo_viewable()))

        # --- Theme switch ---
        app.show_section("admin")
        app.update()
        app.cbo_theme.set("Dark Mode \u263e")
        app.change_theme()
        app.update()
        # Compares against THEMES directly rather than a hardcoded hex value,
        # so retuning the palette (e.g. the soft-glass colors) never stales
        # this test out.
        check("dark theme applied", app.current_theme == "dark" and app.colors["bg_body"] == gui.THEMES["dark"]["bg_body"])
        app.cbo_theme.set("Light Mode \u2600\ufe0f")
        app.change_theme()
        app.update()
        check("light theme restored", app.current_theme == "light" and app.colors["bg_body"] == gui.THEMES["light"]["bg_body"])

        # --- Language switch ---
        app.show_section("admin")
        app.update()
        app.cbo_lang.set("Urdu \U0001F1F5\U0001F1F0")
        app.on_language_change(None)
        app.update()
        check("urdu nav applied", "ڈیش بورڈ" in app.nav_buttons["dashboard"][0].cget("text"))
        app.cbo_lang.set("English \U0001F1EC\U0001F1E7")
        app.on_language_change(None)
        app.update()
        check("english nav restored", "Dashboard" in app.nav_buttons["dashboard"][0].cget("text"))

        # --- Right-to-left layout (Urdu / Pashto) ---
        check("english is left-to-right", not app.is_rtl)
        check("mirror helpers are no-ops in LTR",
              app._side(gui.tk.LEFT) == gui.tk.LEFT and app._anchor("w") == "w"
              and app._justify("left") == "left" and app._pad((0, 16)) == (0, 16)
              and app._columns(("a", "b")) == ("a", "b"))

        def body_x():
            """(sidebar x, content x) -- the sidebar is the first child."""
            kids = app.body_container.winfo_children()
            return kids[0].winfo_x(), kids[1].winfo_x()

        app.update_idletasks()
        ltr_sidebar_x, ltr_content_x = body_x()
        check("LTR puts the sidebar on the left",
              ltr_sidebar_x < ltr_content_x and ltr_sidebar_x == 0)

        app.set_language("ur")
        app.update()
        app.update_idletasks()
        check("urdu is right-to-left", app.is_rtl and "ur" in gui.RTL_LANGS)
        check("mirror helpers flip in RTL",
              app._side(gui.tk.LEFT) == gui.tk.RIGHT
              and app._anchor("w") == "e" and app._anchor("nw") == "ne"
              and app._anchor("center") == "center"   # not "cwntwr"
              and app._justify("left") == "right" and app._pad((0, 16)) == (16, 0)
              and app._columns(("a", "b")) == ("b", "a"))
        rtl_sidebar_x, rtl_content_x = body_x()
        check("RTL moves the sidebar to the right",
              rtl_sidebar_x > rtl_content_x and rtl_content_x == 0)
        check("RTL anchors nav text to the right edge",
              app.nav_buttons["dashboard"][0].cget("anchor") == "e")
        check("RTL right-aligns typed text",
              gui.tk.Entry(app).cget("justify") == "right"
              and app.style.lookup("TCombobox", "justify") == "right")

        # Columns must *display* reversed while every insert(values=...) keeps
        # landing under the right heading -- the reason this uses
        # displaycolumns instead of reordering `columns`.
        check("RTL reverses table column order",
              tuple(app.tree_customers.cget("displaycolumns"))
              == tuple(reversed(tuple(app.cust_headers))))
        probe = app.tree_customers.insert(
            "", "end", values=tuple("v_" + c for c in app.cust_headers))
        check("RTL keeps every cell under its own heading",
              all(app.tree_customers.set(probe, c) == "v_" + c
                  for c in app.cust_headers))
        app.tree_customers.delete(probe)

        # A theme change rebuilds every widget; it used to rebuild them with
        # their English construction-time text while current_lang said "ur".
        app.cbo_theme.set("Dark Mode ☾")
        app.change_theme()
        app.update()
        check("theme change keeps the active language",
              app.current_lang == "ur"
              and "ڈیش بورڈ" in app.nav_buttons["dashboard"][0].cget("text"))
        check("theme change keeps the RTL layout", app.is_rtl and body_x()[0] > body_x()[1])
        app.toggle_theme()
        app.update()
        check("toggle_theme flips back", app.current_theme == "light")

        check("pashto is right-to-left too", "ps" in gui.RTL_LANGS)
        app.set_language("en")
        app.update()
        app.update_idletasks()
        check("returning to english restores LTR",
              not app.is_rtl and body_x() == (ltr_sidebar_x, ltr_content_x)
              and tuple(app.tree_customers.cget("displaycolumns"))
              == tuple(app.cust_headers))

        # --- Calendar mirrors and translates ---
        app.set_language("ur")
        app.show_section("calendar")
        app.update()
        app.update_idletasks()
        check("calendar header is translated",
              app.lbl_cal_title.cget("text") == gui.TRANSLATIONS["ur"]["cal_title"])
        check("calendar month name comes from the pack (not the C locale)",
              any(m in app.lbl_cal_month.cget("text").replace(" ", "")
                  for m in gui.TRANSLATIONS["ur"]["cal_months"]))
        # The week itself has to run the other way, not just its labels.
        heads = {}
        for w in app.cal_grid.winfo_children():
            info = w.grid_info()
            if str(info.get("row")) == "0":
                heads[int(info["column"])] = w.cget("text").replace(" ", "")
        ur_days = gui.TRANSLATIONS["ur"]["cal_days"]
        check("calendar weekday row is translated",
              ur_days[0] in "".join(heads.values()))
        check("RTL puts Monday in the rightmost column",
              heads.get(6) == ur_days[0] and heads.get(0) == ur_days[6])
        check("calendar grid column mirror is a no-op check",
              app._grid_col(0) == 6 and app._grid_col(6) == 0)
        app.set_language("en")
        app.update()
        app.update_idletasks()
        heads_en = {}
        for w in app.cal_grid.winfo_children():
            info = w.grid_info()
            if str(info.get("row")) == "0":
                heads_en[int(info["column"])] = w.cget("text").replace(" ", "")
        # _track() uppercases as well as letter-spacing, so compare case-folded.
        check("LTR puts Monday back in the leftmost column",
              heads_en.get(0, "").lower() == "mon"
              and heads_en.get(6, "").lower() == "sun"
              and app._grid_col(0) == 0)

        # --- Settings page controls are actually on screen ---
        # These three cards were packed fill=BOTH inside a row that does not
        # expand, so _rounded_surface never sized them and all three collapsed
        # to a 1px sliver: the theme and language controls existed but could
        # not be seen or clicked.
        app.show_section("admin")
        app.update()
        app.update_idletasks()
        for name, widget in (("theme", app.cbo_theme), ("display", app.cbo_display),
                             ("language", app.cbo_lang)):
            check("settings %s control is visible" % name,
                  widget.winfo_ismapped() and widget.winfo_height() > 10)
        check("settings cards have real height",
              app.cbo_theme.master.winfo_height() > 40)

        # --- Display mode + theme wording follows the language ---
        app.set_language("ur")
        app.update()
        check("display mode card is translated",
              app.lbl_display_label.cget("text") != "🖥️ Display Mode"
              and "ڈسپلے" in app.lbl_display_label.cget("text"))
        check("display mode values are translated",
              app.cbo_display.get() == app._display_mode_label(app.display_mode)
              and "Windowed" not in app.cbo_display.get())
        check("theme values are translated",
              app.cbo_theme.get() == app._theme_label(app.current_theme)
              and "Mode" not in app.cbo_theme.get())
        # The handlers used to match on the English substrings "Full"/"Dark",
        # which appear in none of the translated values.
        app.cbo_display.set(app._display_mode_label("windowed"))
        app.on_display_mode_change()
        check("translated display selection still applies",
              app.display_mode == "windowed")
        app.cbo_theme.set(app._theme_label("dark"))
        app.change_theme()
        app.update()
        check("translated theme selection still applies", app.current_theme == "dark")
        app.toggle_theme()
        app.update()
        app.set_language("en")
        app.update()

        # --- Admin password (bcrypt, stored as a hash) ---
        from app.utils import admin_password as pw
        state = app._app_state_for_current_data()
        check("factory password opens a fresh install",
              pw.verify("admin123", "") and pw.is_factory_default(""))
        check("wrong factory password refused", not pw.verify("nope", ""))
        h = pw.hash_password("Jhagra#2026")
        check("a set password replaces the factory one",
              pw.verify("Jhagra#2026", h) and not pw.verify("admin123", h))
        check("a corrupt stored hash reads as wrong, not a crash",
              pw.verify("anything", "not-a-bcrypt-hash") is False)
        check("new password is validated",
              pw.validate_new("abc", "abc")[1] == "pw_err_short"
              and pw.validate_new("abcd", "abce")[1] == "pw_err_mismatch"
              and pw.validate_new("abcd", "abcd")[0] is True)
        state.save(admin_password_hash=h)
        check("login honours the stored hash",
              pw.verify("Jhagra#2026",
                        state.load().get("admin_password_hash", "")))
        state.save(admin_password_hash="")
        app.show_section("admin")
        app.update()
        app._refresh_password_hint()
        check("settings warns while on the default password",
              "default" in app.lbl_pw_hint.cget("text").lower()
              or app.lbl_pw_hint.cget("fg") == gui.TERRACOTTA)
        dlg = app.open_change_password_modal()
        check("change-password dialog opens", dlg.winfo_exists() == 1)
        dlg.destroy()

        # --- System monitor (optional, off by default) ---
        check("system monitor is off by default", app.system_monitor_enabled is False)
        check("monitor strip exists but is not packed",
              app.sysmon_frame.winfo_exists() == 1
              and app.sysmon_frame.winfo_ismapped() == 0)
        check("nothing is polling while it is off", app._sysmon_job is None)
        app.var_system_monitor.set(True)
        app.on_system_monitor_toggle()
        app.update()
        check("enabling packs the strip and starts polling",
              app.sysmon_frame.winfo_ismapped() == 1 and app._sysmon_job is not None)
        check("the toggle persists", state.load().get("system_monitor") is True)
        snap = gui.sysmon.snapshot()
        check("snapshot always returns every key",
              set(snap) == {"internet", "cpu", "memory", "disk", "gpu", "psutil"})
        app._paint_system_monitor(snap)
        app.update()
        check("monitor paints a real reading",
              app.sysmon_rows["internet"][1].cget("text") in
              (gui.TRANSLATIONS["en"]["sys_online"], gui.TRANSLATIONS["en"]["sys_offline"]))
        # A probe that cannot answer must render as a dash, not vanish.
        app._paint_system_monitor({"internet": False, "cpu": None, "memory": None,
                                   "disk": None, "gpu": None, "psutil": False})
        app.update()
        check("an unavailable probe renders as a dash",
              app.sysmon_rows["cpu"][1].cget("text") == "\u2014"
              and app.sysmon_rows["gpu"][1].cget("text") == "\u2014")
        app.var_system_monitor.set(False)
        app.on_system_monitor_toggle()
        app.update()
        check("disabling unpacks it and stops polling",
              app.sysmon_frame.winfo_ismapped() == 0 and app._sysmon_job is None)

        # --- Command bar (optional, off by default) ---
        check("command bar is off by default", app.ai_panel_enabled is False)
        app.toggle_command_bar()
        check("disabled command bar does not open", app._cmdbar is None)
        app.var_ai_panel.set(True)
        app.on_ai_panel_toggle()
        app.update()
        check("the toggle persists", state.load().get("ai_panel") is True)
        app.toggle_command_bar()
        app.update()
        check("command bar opens", app._cmdbar is not None and app._cmdbar.winfo_exists() == 1)
        for phrase, want in (("finance", "finance"), ("show me the stock", "inventory"),
                             ("customers please", "customer"), ("calendar", "calendar"),
                             ("settings", "admin")):
            app.open_command_bar()
            app.update()
            app.run_command(phrase)
            app.update()
            check("command '%s' opens %s" % (phrase, want), app.current_section == want)
        app.open_command_bar()
        app.update()
        check("an unknown phrase routes nowhere", app.run_command("zzz qqq") is None)
        check("the bar stays open after a miss", app._cmdbar is not None)
        app.open_command_bar()
        app.update()
        app.run_command("dark mode")
        app.update()
        check("command bar switches theme", app.current_theme == "dark")
        app.toggle_theme()
        app.update()
        # With no endpoint configured the API lookup must be a quiet no-op,
        # never a hang or a stack trace.
        check("no configured API means no lookup", app._ask_command_api("anything") is None)
        app.close_command_bar()
        app.var_ai_panel.set(False)
        app.on_ai_panel_toggle()
        app.update()

        # --- Finance: delete a ledger row ---
        app.show_section("finance")
        app.update()
        fdb = app._finance_db_for_current_data()
        before = len(fdb.get_rows())
        check("finance ledger has rows to delete", before > 0)
        target = fdb.get_rows()[0]["order_id"]
        check("deleting a ledger row removes exactly it",
              fdb.delete_row(target) is True and len(fdb.get_rows()) == before - 1)
        check("deleting an unknown id is a no-op", fdb.delete_row("NOPE-999") is False)
        check("the order itself survives the ledger delete",
              any(str(o.get("id")) == target for o in app.orders))
        app.reload_all_data()
        check("the ledger row returns on the next sync",
              len(fdb.get_rows()) == before)
        check("finance delete button exists", app.btn_fin_delete.winfo_exists() == 1)

        # --- Cards link to the page they summarise ---
        app.show_section("dashboard")
        app.update()
        for widget, want in ((app.lbl_stat_orders, "order_card"),
                             (app.lbl_stat_customers, "customer"),
                             (app.lbl_stat_onduty, "employee")):
            app.show_section("dashboard")
            app.update()
            # Click the number itself, not the card padding -- a card is
            # mostly covered by its own labels.
            widget.event_generate("<Button-1>")
            app.update()
            check("stat tile links to %s" % want, app.current_section == want)
        check("linked cards show a hand cursor",
              app.lbl_stat_customers.cget("cursor") == "hand2")

        # --- Services that existed but were never wired up ---
        url = gui.NotificationService.format_whatsapp_url("0300 1234567", "Hi there")
        check("whatsapp link normalises a local number",
              "phone=923001234567" in url and "text=Hi%20there" in url)
        est = gui.GarmentCalculator.estimate_fabric_meters("Waistcoat", 40.0, 38.0)
        check("fabric estimate returns metres", est["recommended_meters"] == 1.25)
        est2 = gui.GarmentCalculator.estimate_fabric_meters("Shalwar Kameez", 42.0, 46.0)
        check("fabric estimate allows for a larger chest",
              est2["recommended_meters"] > est["recommended_meters"])
        check("customer page offers both services",
              app.btn_cust_whatsapp.winfo_exists() == 1
              and app.btn_cust_fabric.winfo_exists() == 1)

        # Every new control must move with the language pack too -- the cards
        # are built with English text and re-labelled afterwards.
        app.set_language("ur")
        app.show_section("admin")
        app.update()
        ur = gui.TRANSLATIONS["ur"]
        check("new settings cards translate",
              app.lbl_pw_label.cget("text") == ur["pw_label"]
              and app.lbl_mon_label.cget("text") == ur["mon_label"]
              and app.lbl_ai_label.cget("text") == ur["ai_label"]
              and app.chk_system_monitor.cget("text") == ur["mon_toggle"])
        app.show_section("customer")
        app.update()
        check("new toolbar buttons translate",
              app.btn_cust_whatsapp.cget("text") == ur["btn_whatsapp"]
              and app.btn_cust_fabric.cget("text") == ur["fabric_btn"])
        app.show_section("finance")
        app.update()
        check("finance delete button translates",
              app.btn_fin_delete.cget("text") == ur["fin_btn_delete"])
        check("machine readout translates",
              app.sysmon_rows["cpu"][0].cget("text") == ur["sys_cpu"])
        app.set_language("en")
        app.update()

        # --- Sidebar quick controls ---
        check("sidebar has a theme chip",
              hasattr(app, "btn_quick_theme") and app.btn_quick_theme.winfo_exists())
        check("sidebar has a language chip",
              hasattr(app, "btn_quick_lang")
              and "EN" in app.btn_quick_lang.cget("text"))
        app.cycle_language()
        app.update()
        check("cycle_language steps to the next pack", app.current_lang == "ur")
        check("language chip follows the pack", "UR" in app.btn_quick_lang.cget("text"))
        app.set_language("en")
        app.update()

        # --- Modals open without error (grab may fail on unmapped windows; tolerated) ---
        def open_and_destroy(method, name):
            try:
                method()
                app.update()
                toplevels = [w for w in app.winfo_children() if isinstance(w, gui.tk.Toplevel) and w.winfo_exists()]
                check(f"modal '{name}' opens", len(toplevels) == 1)
                for w in toplevels:
                    try:
                        w.grab_release()
                    except Exception:
                        pass
                    w.destroy()
                app.update()
            except Exception as e:
                check(f"modal '{name}' opens", False)
                print("   !!", repr(e))

        open_and_destroy(app.open_add_customer_modal, "add customer")
        open_and_destroy(app.open_add_order_modal, "add order")
        open_and_destroy(app.open_add_employee_modal, "add employee")
        open_and_destroy(app.open_assign_task_modal, "assign task")

        # --- Settings lists seeded ---
        app.show_section("admin")
        app.update()
        check("settings lists populated",
              app.lst_garments.size() == len(app.garment_types) and app.lst_roles.size() == len(app.employee_roles)
              and app.lst_garments.size() > 0 and app.lst_roles.size() > 0)

        # --- Order status change persists to Excel ---
        app.show_section("dashboard")
        app.update()
        children = app.tree_orders.get_children()
        app.tree_orders.selection_set(children[0])
        app.quick_change_order_status("Ready")
        app.update()
        persisted = temp_mgr.read_records("orders.xlsx", app.ord_headers)
        check("status change persisted", any(gui.clean_val(o.get("id")) == "ORD-101" and "ready" in gui.clean_val(o.get("status")).lower() for o in persisted))
        check("button_style preserved", any(gui.clean_val(o.get("button_style")) == "Baz Button" for o in persisted))

        # --- Task assignment persists to Excel ---
        app.update_employee_task("E-1", "Cut ORD-101")
        persisted_emp = temp_mgr.read_records("employees.xlsx", app.emp_headers)
        check("task assignment persisted", any(gui.clean_val(e.get("id")) == "E-1" and gui.clean_val(e.get("current_task")) == "Cut ORD-101" for e in persisted_emp))

        # --- Finance ledger (SQLite): paid/remaining/debt computed from the
        # two seeded orders. ORD-101 has no total/advance -> contributes 0
        # everywhere. ORD-102 is Delivered with total 5000/advance 2000, so
        # its 3000 balance must land in "debt" (delivered+unpaid), not
        # "remaining" (which is reserved for undelivered orders).
        app.show_section("finance")
        app.update()
        check("finance section visible", bool(app.sections["finance"].winfo_viewable()))
        totals = app._finance_db_for_current_data().get_totals()
        check("finance total paid correct", totals["paid"] == 4000.0)
        check("finance total debt correct (delivered+unpaid)", totals["debt"] == 3000.0)
        check("finance total remaining correct (excludes delivered)", totals["remaining"] == 0.0)

        # --- Finance tabs: All / Done / Due filter the ledger table ---
        app.set_finance_tab("all")
        app.update()
        check("finance 'all' tab shows every order", len(app.tree_finance.get_children()) == 3)
        app.set_finance_tab("done")
        app.update()
        check("finance 'done' tab shows only fully-paid orders", len(app.tree_finance.get_children()) == 1)
        app.set_finance_tab("due")
        app.update()
        check("finance 'due' tab shows only orders with a balance", len(app.tree_finance.get_children()) == 1)

        # --- Add Payment tab: pay down ORD-102's remaining debt ---
        app.set_finance_tab("add")
        app.update()
        check("add-payment picker lists the due order", "ORD-102" in app.cbo_fin_pay_order.get())
        app.ent_fin_pay_amount.insert(0, "1000")
        app.record_finance_payment()
        app.update()
        persisted_ord = temp_mgr.read_records("orders.xlsx", app.ord_headers)
        ord102 = next((o for o in persisted_ord if gui.clean_val(o.get("id")) == "ORD-102"), {})
        check("payment updated advance on ORD-102", gui.clean_val(ord102.get("advance")) == "3000.00")
        new_totals = app._finance_db_for_current_data().get_totals()
        check("finance totals reflect the recorded payment", new_totals["paid"] == 5000.0 and new_totals["debt"] == 2000.0)
        app.set_finance_tab("all")
        app.update()

        # --- Settings/session cache: theme, language, and last open section
        # should have been written to <tmpdir>/cache/app_state_cache.json by
        # the show_section()/change_theme()/on_language_change() calls above
        # (all of which happened after excel_mgr was pointed at tmpdir), and
        # a fresh AppStateCache reading the same path should see them --
        # this is the mechanism that lets the real app reopen where the
        # user left off. reload_all_data() also must never have skipped
        # touching the real app/data dir at any point above.
        cache_path = os.path.join(tmpdir, "cache", "app_state_cache.json")
        check("session cache file written to the active data dir", os.path.exists(cache_path))
        # Persist the display mode BEFORE snapshotting, so the round-trip
        # check below compares against a file that is not about to change.
        app.apply_display_mode("windowed")
        saved_state = gui.AppStateCache(tmpdir).load()
        check("session cache remembers last open section", saved_state["last_section"] == "finance")
        check("session cache remembers display mode", saved_state["display_mode"] == "windowed")
        check("session cache remembers theme", saved_state["theme"] == "light")
        check("session cache remembers language", saved_state["lang"] == "en")
        check("session cache round-trips via a fresh instance", gui.AppStateCache(tmpdir).load() == saved_state)

        # --- PDF generation (if reportlab available) ---
        if SKIP_PDF:
            print("SKIP  pdf generation (reportlab not installed)")
        else:
            app.show_section("dashboard")
            app.update()
            app.tree_orders.selection_set(app.tree_orders.get_children()[0])
            pdf_path = os.path.join(tmpdir, "Receipt_ORD-101.pdf")
            gui.filedialog.asksaveasfilename = lambda **k: pdf_path
            app.generate_order_pdf()
            check("pdf generated", pdf_path and os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0)

        # --- Donut chart percentages render ---
        app.update_graphics_and_stats()
        app.update()
        check("charts updated", app.chart_done.percentage >= 0 and app.chart_prog.percentage >= 0 and app.chart_rem.percentage >= 0)

    except Exception:
        traceback.print_exc()
        results.append(("no exceptions during flow", False))

    finally:
        try:
            app.destroy()
        except Exception:
            pass
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    failed = [n for n, ok in results if not ok]
    print("\n===== SUMMARY =====")
    print(f"{len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:", ", ".join(failed))
        sys.exit(1)
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    run_gui_smoke_test()
