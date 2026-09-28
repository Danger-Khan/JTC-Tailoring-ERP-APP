import sys
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from excel_manager import ExcelManager, clean_val
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import gc
import weakref

try:
    from services import order_card_service as card_svc
    from views.order_card_view import OrderCardView
    from lang import LANGUAGE_OPTIONS, ORDER_CARD_TRANSLATIONS, TRANSLATIONS
    from utils.finance_db import FinanceDB
    from utils.app_state import AppStateCache
    from utils.assets import AssetStore
    from views.expense_view import ExpenseView
except ImportError:
    from app.services import order_card_service as card_svc
    from app.views.order_card_view import OrderCardView
    from app.lang import LANGUAGE_OPTIONS, ORDER_CARD_TRANSLATIONS, TRANSLATIONS
    from app.utils.finance_db import FinanceDB
    from app.utils.app_state import AppStateCache
    from app.utils.assets import AssetStore
    from app.views.expense_view import ExpenseView

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A5
    REPORTLAB_INSTALLED = True
except ImportError:
    REPORTLAB_INSTALLED = False

# --- Theme Configuration ---
# Neumorphic ("soft UI") design system, ported from the JTC web app's
# index.css: one warm-grey canvas, surfaces sitting a couple of shades
# lighter on top of it, depth carried by a light top edge plus a dark
# bottom edge rather than by hard borders, and a pastel accent palette.
#
# Tkinter has no box-shadow, so each CSS shadow becomes a 1-2px frame:
#   --shadow-out (raised card) -> "neu_light" strip along the top edge and
#                                 "neu_shadow" along the bottom (_neu_card)
#   --shadow-in  (inset well)  -> "well" fill + "neu_shadow" along the top
#                                 edge, so the block reads recessed (_neu_well)
# The key NAMES are deliberately carried over from the previous soft-glass
# palette so that every existing self.colors[...] lookup in this file (and
# in order_card_view.py) keeps working untouched and simply picks up the
# new look.
THEMES = {
    "light": {
        # --app-canvas / --app-surface / --app-surface-alt
        "bg_body": "#EBE7E2", "bg_header": "#EEEAE6", "bg_sidebar": "#EEEAE6",
        "bg_card": "#EEEAE6", "bg_chart": "#EEEAE6", "surface_alt": "#F2EFEB",
        "border": "#D9D3CC",                                    # --app-line
        # --app-text / --app-text-2 / --app-text-3 / --app-text-4
        "text_main": "#3A3A3A", "text_muted": "#6E6E6E",
        "text_3": "#9A9A9A", "text_4": "#767676",
        # Neumorphic edges + the fill used for inset wells
        "neu_light": "#FBF7F2", "neu_shadow": "#CDC5BB", "well": "#E5E0D9",
        # Legacy alias: the old glass top strip is now a raised card's
        # light edge, so anything still asking for it gets that.
        "glass_highlight": "#FBF7F2",
    },
    "dark": {
        "bg_body": "#2A2927", "bg_header": "#323130", "bg_sidebar": "#323130",
        "bg_card": "#323130", "bg_chart": "#323130", "surface_alt": "#383633",
        "border": "#3A3835",
        "text_main": "#ECE8E2", "text_muted": "#B8B3AC",
        "text_3": "#8A857F", "text_4": "#9A948D",
        "neu_light": "#3C3A38", "neu_shadow": "#1C1B1A", "well": "#282725",
        "glass_highlight": "#3C3A38",
    }
}

# Accent palette, taken verbatim from the web app's brand tokens.
# PRIMARY is its dark neumorphic pill (.btn-dark-neu, #3a3a3a) -- a warm
# near-black used for the active nav item and primary buttons.
PRIMARY = "#3A3A3A"
SUCCESS = "#2ECC8A"     # --sage / --status-success
WARNING = "#FF8077"     # --terracotta / --status-warning
DANGER = "#BD3228"      # the brick red used for destructive actions
SAGE = "#2ECC8A"
TERRACOTTA = "#FF8077"
BLUSH = "#F9AEBE"
DUSTYBLUE = "#B8EFF5"
LAVENDER = "#C9B3F5"
TAN = "#C4996A"
# Dashboard donut gauges, matching how <DonutGauge> is coloured there.
GAUGE_DONE = "#2ECC8A"
GAUGE_PROGRESS = "#FFCB6E"
GAUGE_REMAINING = "#C9B3F5"
# Round avatar chips: customers get the blush circle, tailors the mint one.
AVATAR_BG, AVATAR_FG = "#FFCBDE", "#5A5350"
TAILOR_BG, TAILOR_FG = "#C9E4D5", "#3A6B52"

# 'DM Sans' is the web app's --font-body. It is not installed by default on
# Windows, so FONT_FAMILY only resolves to it when it is actually present
# and otherwise stays on the platform UI face. The swap happens once in
# AtelierERPApp.__init__ -- the first point at which a Tk root exists to
# query the installed font list against.
DESIGN_FONT = "DM Sans"
FONT_FAMILY = "SF Pro Text" if sys.platform == "darwin" else "Segoe UI"

# Thin accent strip along the top edge of the sidebar card (built inline in
# create_layout). Retuned from the old blue/white/red trio to the design
# system's own pastels so it sits on the warm canvas rather than fighting
# it, while keeping the same three-colour brand signature. It used to run
# across the top of the window, but the top bar is gone now.
ACCENT_STRIP = (SAGE, BLUSH, LAVENDER)

# Real window-level translucency. Tk can only apply this to a whole
# top-level, never to individual widgets, and it dims the actual TEXT along
# with everything else -- at 0.97 the desktop behind the window was legible
# straight through the dashboard. Kept deliberately faint; set it to 1.0 to
# turn window translucency off entirely.
#
# The translucency that actually reads as design lives elsewhere: the owner
# photo blended behind each page (PAGE_BACKDROP_OPACITY) and the frosted
# login panel, both baked into images by Pillow (see utils/assets.py),
# because Tk widgets have no opacity of their own.
WINDOW_ALPHA = 0.99

# How much of the owner photo survives behind a page's cards. High enough to
# read as a watermark in the gutters, low enough that card text is unaffected.
PAGE_BACKDROP_OPACITY = 0.11
PAGE_BACKDROP_BLUR = 4

# How far every card / well / sidebar surface is tinted toward the owner
# photo's average colour, to make the cards read as frosted glass sitting on
# that photo rather than as opaque blocks covering it.
#
# This is a tint and not real see-through, deliberately. A Tk frame cannot
# show an image behind its children: every tk.Label inside a card paints its
# own opaque rectangle, so a photo placed behind one is hidden everywhere it
# actually matters. Sharing the backdrop's colour cast is what sells the
# translucency instead. The page canvas (bg_body) is left untinted on
# purpose, so the gutters stay a slightly different shade from the cards and
# the cards keep a visible edge. Set to 0.0 for flat opaque surfaces.
CARD_FROST = 0.09

# --radius-card / --radius-chip from the web app's index.css.
CARD_RADIUS = 16
WELL_RADIUS = 10


class CircularDonutChart(tk.Canvas):
    __slots__ = ('size', 'ring_color', 'bg_color', 'stroke_width', 'percentage')
    
    def __init__(self, parent, size=75, ring_color=PRIMARY, bg_color="#E5E5EA", stroke_width=8, theme_colors=None, **kwargs):
        bg = theme_colors["bg_chart"] if theme_colors else "#FAFAFC"
        super().__init__(parent, width=size, height=size, bg=bg, highlightthickness=0, **kwargs)
        self.size = size
        self.ring_color = ring_color
        self.bg_color = bg_color
        self.stroke_width = stroke_width
        self.percentage = 0
        self.draw_chart()

    def draw_chart(self):
        self.delete("all")
        margin = self.stroke_width / 2 + 2
        x0, y0 = margin, margin
        x1, y1 = self.size - margin, self.size - margin

        self.create_oval(x0, y0, x1, y1, outline=self.bg_color, width=self.stroke_width)

        if self.percentage >= 100:
            self.create_oval(x0, y0, x1, y1, outline=self.ring_color, width=self.stroke_width)
        elif self.percentage > 0:
            extent = -(self.percentage / 100.0) * 360
            self.create_arc(x0, y0, x1, y1, start=90, extent=extent, style=tk.ARC, outline=self.ring_color, width=self.stroke_width)

    def set_percentage(self, pct):
        self.percentage = max(0, min(100, pct))
        self.draw_chart()


class StatusPill(tk.Canvas):
    """Rounded status chip with a leading colour dot -- the web app's
    <StatusBadge> paired with its .pip. Tk labels cannot round their own
    corners, so the capsule is drawn on a canvas (two circles joined by a
    rectangle) and the widget sizes itself to whatever text it is given.

    `capsule` is the chip fill and `bg` the surface behind it, so the pill
    blends into whichever card or well it is packed into.
    """
    __slots__ = ()

    def __init__(self, parent, text, dot_color, bg, capsule, fg,
                 height=21, pad=9, dot=7):
        import tkinter.font as tkfont
        font = (FONT_FAMILY, 8, "bold")
        text_w = tkfont.Font(family=font[0], size=font[1], weight="bold").measure(text)
        width = pad * 2 + dot + 6 + text_w
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0)
        r = height / 2.0
        self.create_oval(0, 0, height, height, fill=capsule, outline="")
        self.create_oval(width - height, 0, width, height, fill=capsule, outline="")
        self.create_rectangle(r, 0, width - r, height, fill=capsule, outline="")
        cy = height / 2.0
        self.create_oval(pad, cy - dot / 2.0, pad + dot, cy + dot / 2.0,
                         fill=dot_color, outline="")
        self.create_text(pad + dot + 6, cy, text=text, anchor="w", fill=fg,
                         font=font)


class AtelierERPApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self._resolve_design_font()
        self.title("Jhagra Textile & Clothing — Atelier Ledger")
        self.minsize(1100, 700)

        # Brand images (logo / icon / owner photo). Safe to construct even
        # when Pillow or the folder is missing -- every accessor then returns
        # None and the app falls back to plain text chrome.
        self.assets = AssetStore(os.path.dirname(os.path.abspath(__file__)))

        if os.path.exists("icon.ico"):
            self.iconbitmap("icon.ico")
        # iconphoto also covers every Toplevel opened later (the login dialog
        # and all the modals), which iconbitmap on its own does not.
        icon_img = self.assets.window_icon()
        if icon_img is not None:
            self._window_icon = icon_img
            try:
                self.iconphoto(True, icon_img)
            except tk.TclError:
                pass
        try:
            self.attributes("-alpha", WINDOW_ALPHA)
        except tk.TclError:
            pass

        self.excel_mgr = ExcelManager()
        # Finance ledger (SQLite): mirrors paid/remaining/debt per order,
        # recomputed from orders.xlsx on every reload_all_data(). Lazily
        # (re)created against whichever data dir self.excel_mgr currently
        # points to — see _finance_db_for_current_data().
        self.finance_db = None
        self._finance_db_dir = None

        # Settings/session cache (theme, language, last open section, window
        # geometry) so closing and reopening the app picks up where the user
        # left off, instead of always resetting to English/Light/Dashboard.
        # Lazily (re)bound to self.excel_mgr's current data dir — same
        # pattern as _finance_db_for_current_data() — so tests that swap
        # excel_mgr to a throwaway temp dir never touch the real app/data
        # cache file.
        self.app_state = None
        self._app_state_dir = None
        saved_state = self._app_state_for_current_data().load()
        self.current_theme = saved_state["theme"] if saved_state["theme"] in THEMES else "light"
        valid_langs = [code for code, _ in LANGUAGE_OPTIONS]
        self.current_lang = saved_state["lang"] if saved_state["lang"] in valid_langs else "en"
        self.current_section = saved_state["last_section"]
        self.display_mode = (saved_state.get("display_mode")
                             if saved_state.get("display_mode") in ("fullscreen", "windowed")
                             else "fullscreen")
        # Keep the windowed geometry around even while fullscreen, so leaving
        # fullscreen restores the size the user last chose rather than a
        # default. self.geometry() would report the whole screen if it were
        # read back while fullscreen, which is why it is stashed separately.
        self.windowed_geometry = self._sane_geometry(saved_state["geometry"])
        try:
            self.geometry(self.windowed_geometry)
        except tk.TclError:
            self.windowed_geometry = "1350x850"
            self.geometry(self.windowed_geometry)
        self.apply_display_mode(self.display_mode, persist=False)
        # F11 toggles, Escape always drops back to windowed -- without an
        # escape hatch a real fullscreen window with no title bar is hard to
        # get out of if the Settings screen is not reachable.
        self.bind("<F11>", lambda e: self.toggle_display_mode())
        self.bind("<Escape>", lambda e: self.apply_display_mode("windowed"))

        # Destructive operations are available only after an administrator login.
        self.current_user_role = "Viewer"
        self.colors = self._tinted_palette(THEMES[self.current_theme])

        # --- HEADERS MATCHING PHYSICAL FORM ---
        # Legacy columns first; order-card columns appended LAST so existing
        # .xlsx rows keep positional compatibility (no data shifting on read).
        self.cust_headers = card_svc.CUST_HEADERS
        self.emp_headers = ["id", "name", "phone", "role", "status", "current_task"]
        self.ord_headers = card_svc.ORD_HEADERS  # expected order columns (includes 'customer_id')
        # Inventory lives in its own sheet rather than inside settings lists,
        # because each item carries several fields and has to be edited row by
        # row like customers and orders are.
        self.inv_headers = ["id", "item", "category", "quantity", "unit",
                            "reorder_level", "updated"]
        self.inventory = []

        self.default_garments = ["Shalwar Kameez", "Waistcoat", "2-Piece Suit"]
        self.default_roles = ["Master Cutter", "Stitching Specialist"]

        self.protocol("WM_DELETE_WINDOW", self.on_app_close)
        self.bind("<Configure>", self._remember_windowed_geometry, add="+")
        self.withdraw()
        self.show_login_screen()

    @staticmethod
    def _resolve_design_font():
        """Switch FONT_FAMILY over to the design's DM Sans when that face is
        actually installed. Reading the installed font list needs a live Tk
        root, which is why this runs at startup rather than at import time;
        every widget in the app is built after this point."""
        global FONT_FAMILY
        try:
            import tkinter.font as tkfont
            if DESIGN_FONT in tkfont.families():
                FONT_FAMILY = DESIGN_FONT
        except Exception:
            pass

    def apply_display_mode(self, mode, persist=True):
        """Switch between real fullscreen and windowed.

        Real fullscreen means the '-fullscreen' attribute -- no title bar and
        covering the taskbar -- not a maximised window, which is what 'zoomed'
        would give and which still leaves the shell chrome on screen.
        """
        mode = "fullscreen" if mode == "fullscreen" else "windowed"
        # Nothing is captured from self.geometry() on the way out of
        # fullscreen: it reports the whole screen while the attribute is still
        # set, so self.windowed_geometry (kept up to date only while actually
        # windowed) is the one usable value.
        self.display_mode = mode
        try:
            if mode == "fullscreen":
                self.attributes("-fullscreen", True)
            else:
                self.attributes("-fullscreen", False)
                if self.windowed_geometry:
                    self.geometry(self.windowed_geometry)
        except tk.TclError:
            # Some window managers refuse the attribute; fall back to zoomed
            # rather than leaving the user with no window at all.
            try:
                self.state("zoomed" if mode == "fullscreen" else "normal")
            except tk.TclError:
                pass
        if hasattr(self, "cbo_display") and self.cbo_display.winfo_exists():
            self.cbo_display.set(self._display_mode_label(mode))
        if persist:
            self._app_state_for_current_data().save(display_mode=mode)

    @staticmethod
    def _display_mode_label(mode):
        return "Full Screen ⛶" if mode == "fullscreen" else "Windowed 🗗"

    def toggle_display_mode(self):
        self.apply_display_mode("windowed" if self.display_mode == "fullscreen"
                                else "fullscreen")

    def on_display_mode_change(self, event=None):
        self.apply_display_mode(
            "fullscreen" if "Full" in self.cbo_display.get() else "windowed")

    def _sane_geometry(self, geo):
        """Clamp a saved "WxH+X+Y" string so the window cannot reopen
        stranded off-screen.

        A saved position is not always still valid: the screen may have
        changed resolution since, and a window manager can hand back a
        negative origin of its own accord while a window is leaving
        fullscreen. Restoring such a value verbatim slices the left edge --
        and the left edge is the sidebar, i.e. every nav control.

        Clamping to the primary screen means a window deliberately parked on
        a second monitor comes back on the main one. That is the deliberate
        trade: this runs on a single shop-counter screen, where a chopped-off
        sidebar is a real failure and a window returning to the main display
        is a shrug.
        """
        # Only the "+X+Y" form is touched. Tk also accepts "-X-Y", which
        # measures from the *right/bottom* edge rather than being a negative
        # coordinate -- reinterpreting that as an origin would move a window
        # that was positioned deliberately. Note Tk spells a negative origin
        # "+-164", hence the sign living inside the group.
        m = re.match(r"^(\d+)x(\d+)\+(-?\d+)\+(-?\d+)$", (geo or "").strip())
        if not m:
            # Size-only ("1350x850"), edge-relative, or unparseable: leave it
            # to Tk.
            return geo
        w, h = int(m.group(1)), int(m.group(2))
        x, y = int(m.group(3)), int(m.group(4))
        try:
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        except tk.TclError:
            return geo
        w = max(800, min(w, sw))
        h = max(600, min(h, sh))
        x = max(0, min(x, max(0, sw - w)))
        y = max(0, min(y, max(0, sh - h)))
        return "%dx%d+%d+%d" % (w, h, x, y)

    def _remember_windowed_geometry(self, _event=None):
        """Track the window's size only while it is actually windowed, so the
        fullscreen size never overwrites the size to come back to."""
        if getattr(self, "display_mode", "windowed") == "windowed":
            try:
                geo = self.geometry()
                if geo and not geo.startswith("1x1"):
                    self.windowed_geometry = self._sane_geometry(geo)
            except tk.TclError:
                pass

    def on_app_close(self):
        """Saves the session cache one last time (in case the 5s
        auto-refresh loop hasn't caught the latest tweak yet) before the
        window actually closes."""
        try:
            self._remember_windowed_geometry()
            self._app_state_for_current_data().save(
                theme=self.current_theme, lang=self.current_lang,
                last_section=getattr(self, "current_section", "dashboard"),
                display_mode=getattr(self, "display_mode", "windowed"),
                # Never the fullscreen size -- see _remember_windowed_geometry.
                geometry=getattr(self, "windowed_geometry", self.geometry()),
            )
        except Exception:
            pass
        self.destroy()

    # ==========================================
    # ID HELPERS
    # ==========================================
    def _next_id(self, prefix, records, start=101):
        """Generate the next sequential ID for a record set (e.g. C-102)."""
        nums = []
        for r in records:
            rid = clean_val(r.get("id"))
            if rid.startswith(prefix + "-"):
                try:
                    nums.append(int(rid.split("-", 1)[1]))
                except (ValueError, IndexError):
                    pass
        return f"{prefix}-{max(nums) + 1 if nums else start}"

    # ==========================================
    # AUTHENTICATION
    # ==========================================
    def show_login_screen(self):
        """Login over the owner photo: the picture fills the dialog and a
        frosted panel sits on top of it.

        The panel is not actually see-through -- Tk has no widget opacity --
        it is an image Pillow blended from the same photo, so the blur lines
        up with the backdrop behind it. The headings are canvas text rather
        than labels for the same reason: canvas text draws with no box behind
        it, whereas a tk.Label would punch an opaque rectangle through the
        photo.
        """
        self.login_dlg = tk.Toplevel(self)
        self.login_dlg.title("System Authentication")
        self.login_dlg.protocol("WM_DELETE_WINDOW", self.destroy)
        self.login_dlg.resizable(False, False)
        self.login_dlg.configure(bg=self.colors["bg_card"])

        W, H = 460, 540
        backdrop = self.assets.backdrop("owner", (W, H), self.colors["bg_body"],
                                        opacity=0.66, blur=1)
        if backdrop is None:
            self._build_plain_login()
            return

        self.login_dlg.geometry("%dx%d" % (W, H))
        cv = tk.Canvas(self.login_dlg, width=W, height=H, highlightthickness=0, bd=0)
        cv.pack(fill=tk.BOTH, expand=True)
        self._login_images = [backdrop]
        cv.create_image(0, 0, image=backdrop, anchor="nw")

        CW, CH = 372, 302
        cx = W // 2
        card_top = H - CH - 34
        # The logo is composited into the panel image rather than stacked on
        # top of it: the panel is a photo blend, not a flat colour, so a
        # separately-matted circle would sit in a square of the wrong shade.
        card = self.assets.panel("owner", (CW, CH), self.colors["bg_card"],
                                 photo_opacity=0.13, blur=14,
                                 emblem="icon", emblem_size=66, emblem_top=20)
        if card is not None:
            self._login_images.append(card)
            cv.create_image(cx, card_top, image=card, anchor="n")

        cv.create_text(cx, card_top + 104, text="JTC Secure Login", anchor="n",
                       fill=self.colors["text_main"], font=(FONT_FAMILY, 15))
        cv.create_text(cx, card_top + 132, text="Enter your administrator password",
                       anchor="n", fill=self.colors["text_muted"], font=(FONT_FAMILY, 9))

        self.ent_pwd = tk.Entry(cv, show="*", font=(FONT_FAMILY, 12), justify="center",
                                bg=self.colors["well"], fg=self.colors["text_main"],
                                insertbackground=self.colors["text_main"], relief="flat",
                                highlightthickness=1,
                                highlightbackground=self.colors["border"])
        self.ent_pwd.bind("<Return>", lambda e: self.authenticate())
        cv.create_window(cx, card_top + 164, window=self.ent_pwd, anchor="n",
                         width=272, height=36)

        btn = tk.Button(cv, text="Login to Dashboard", bg=PRIMARY, fg="#F1F1F0",
                        font=(FONT_FAMILY, 10, "bold"), bd=0, cursor="hand2",
                        activebackground=PRIMARY, activeforeground="#F1F1F0",
                        command=self.authenticate)
        cv.create_window(cx, card_top + 216, window=btn, anchor="n",
                         width=272, height=42)
        self.ent_pwd.focus_set()

    def _build_plain_login(self):
        """Fallback used when the brand images cannot be loaded (Pillow
        missing, or app/Images moved) -- the original flat dialog."""
        self.login_dlg.geometry("400x250")
        tk.Label(self.login_dlg, text="🔒 JTC Secure Login", font=(FONT_FAMILY, 16, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"]).pack(pady=(30, 10))
        tk.Label(self.login_dlg, text="Please enter your administrator password:", font=(FONT_FAMILY, 9), bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack()

        self.ent_pwd = tk.Entry(self.login_dlg, show="*", font=(FONT_FAMILY, 12), justify="center",
                                bg=self.colors["bg_body"], fg=self.colors["text_main"],
                                insertbackground=self.colors["text_main"], relief="flat",
                                highlightthickness=1, highlightbackground=self.colors["border"])
        self.ent_pwd.pack(pady=15, padx=50, fill=tk.X)
        self.ent_pwd.bind("<Return>", lambda e: self.authenticate())

        tk.Button(self.login_dlg, text="🔐 Login to Dashboard", bg=PRIMARY, fg="white", font=(FONT_FAMILY, 10, "bold"), bd=0, pady=8, cursor="hand2", command=self.authenticate).pack(fill=tk.X, padx=50)

    def authenticate(self):
        pwd = self.ent_pwd.get()
        if pwd == "admin123":
            self.current_user_role = "Administrator"
            self.login_dlg.destroy()
            self.initialize_application()
        else:
            messagebox.showerror("Access Denied", "Incorrect password.", parent=self.login_dlg)
            self.ent_pwd.delete(0, tk.END)

    # ==========================================
    # APP LIFECYCLE / REFRESH
    # ==========================================
    def initialize_application(self):
        self.deiconify()
        self.reload_all_data()
        self.build_ui_layout()
        self.update_clock()
        self.auto_refresh_loop()

    def _finance_db_for_current_data(self):
        """Returns a FinanceDB pointed at self.excel_mgr's current data dir,
        recreating it if the data dir changed (e.g. tests swap excel_mgr to
        a throwaway temp dir) so finance.db always lives next to whichever
        orders.xlsx is actually active."""
        data_dir = getattr(self.excel_mgr, "data_dir", None) or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        if self.finance_db is None or self._finance_db_dir != data_dir:
            self.finance_db = FinanceDB(data_dir)
            self._finance_db_dir = data_dir
        return self.finance_db

    def _app_state_for_current_data(self):
        """Same lazy-rebind pattern as _finance_db_for_current_data(), for
        the settings/session cache."""
        data_dir = getattr(self.excel_mgr, "data_dir", None) or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        if self.app_state is None or self._app_state_dir != data_dir:
            self.app_state = AppStateCache(data_dir)
            self._app_state_dir = data_dir
        return self.app_state

    def reload_all_data(self):
        """Load all data in parallel for better performance."""
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all loading tasks in parallel
            cust_future = executor.submit(self.excel_mgr.read_records, "customers.xlsx", self.cust_headers)
            emp_future = executor.submit(self.excel_mgr.read_records, "employees.xlsx", self.emp_headers)
            ord_future = executor.submit(self.excel_mgr.read_records, "orders.xlsx", self.ord_headers)
            
            # Collect results as they complete
            for future in as_completed([cust_future, emp_future, ord_future]):
                try:
                    future.result()
                except Exception as e:
                    pass
        
        # Assign results (they complete quickly)
        self.customers = cust_future.result() if cust_future.done() else []
        self.employees = emp_future.result() if emp_future.done() else []
        self.orders = ord_future.result() if ord_future.done() else []
        try:
            self.inventory = self.excel_mgr.read_records("inventory.xlsx", self.inv_headers)
        except Exception:
            # A missing inventory.xlsx just means nothing has been stocked yet.
            self.inventory = []
        self.garment_types = self.excel_mgr.load_settings_list("garment_type", self.default_garments)
        self.employee_roles = self.excel_mgr.load_settings_list("employee_role", self.default_roles)
        
        # Normalize orders: ensure orders reference customers by id (customer_id) not by name
        cust_name_to_id = {clean_val(c.get('name')): clean_val(c.get('id')) for c in self.customers if c.get('id')}
        changed = False
        for o in self.orders:
            # If older files stored 'customer' as a name in the second column, map it to id
            cid = clean_val(o.get('customer_id') or '')
            if not cid:
                candidate = clean_val(o.get('customer') or '')
                # If candidate looks like an id (C-...) accept it; else try to map name -> id
                if candidate.startswith('C-'):
                    o['customer_id'] = candidate
                    changed = True
                elif candidate and candidate in cust_name_to_id:
                    o['customer_id'] = cust_name_to_id[candidate]
                    changed = True
                else:
                    # leave empty or store raw value — UI will show the raw name if mapping isn't possible
                    o['customer_id'] = candidate

        # Persist migration of orders.xlsx when we successfully mapped names -> ids
        if changed:
            try:
                rows = [[clean_val(o.get(h)) for h in self.ord_headers] for o in self.orders]
                self.excel_mgr.write_all_records('orders.xlsx', self.ord_headers, rows)
            except Exception:
                # Non-fatal — continue running with in-memory normalization
                pass

        # Recompute the finance ledger (paid/remaining/debt) from the orders
        # we just loaded. Non-fatal on failure (e.g. finance.db briefly
        # locked) — the rest of the app must keep working either way.
        try:
            self._finance_db_for_current_data().sync(self.orders, self.customers)
        except Exception as e:
            print(f"[FinanceDB] sync failed: {e}")

        # Clear memory cache periodically
        gc.collect()

    def auto_refresh_loop(self):
        self.reload_all_data()
        if hasattr(self, "tree_orders") and self.tree_orders.winfo_exists():
            self.update_graphics_and_stats()
        self.after(5000, self.auto_refresh_loop)

    # ==========================================
    # THEME / LAYOUT
    # ==========================================
    def change_theme(self, event=None):
        sel = self.cbo_theme.get()
        self.current_theme = "dark" if "Dark" in sel else "light"
        self.colors = self._tinted_palette(THEMES[self.current_theme])
        # Cached images were flattened against the old palette's surface
        # colours, so they have to be rebuilt or they would show the previous
        # theme's background behind every logo and photo.
        self.assets.release_theme_images()
        self._app_state_for_current_data().save(theme=self.current_theme)
        self.body_container.destroy()
        self.build_ui_layout()

    def build_ui_layout(self):
        self.configure(bg=self.colors["bg_body"])
        self.apply_ttk_styles()
        self.create_layout()
        # Reopen on whichever section was active before (theme rebuild,
        # or the section the user was on when they last closed the app) —
        # falls back to "dashboard" the first time the app ever runs.
        self.show_section(self.current_section if self.current_section in
                          ("dashboard", "customer", "order_card", "calendar",
                           "employee", "inventory", "finance", "expenses", "admin")
                          else "dashboard")
        self.update_graphics_and_stats()

    def apply_ttk_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("Treeview", background=self.colors["bg_card"], foreground=self.colors["text_main"], fieldbackground=self.colors["bg_card"], rowheight=34, font=(FONT_FAMILY, 9), borderwidth=0)
        # Headings read as the design's tracked micro-captions: recessed well
        # behind them, muted lettering, no relief.
        self.style.configure("Treeview.Heading", background=self.colors["well"], foreground=self.colors["text_muted"], font=(FONT_FAMILY, 8, "bold"), borderwidth=0, relief="flat")
        self.style.map("Treeview.Heading", background=[('active', self.colors["well"])])
        self.style.map("Treeview", background=[('selected', PRIMARY)], foreground=[('selected', '#F1F1F0')])
        self.style.configure("TCombobox", font=(FONT_FAMILY, 9),
                             fieldbackground=self.colors["bg_card"], background=self.colors["bg_card"],
                             foreground=self.colors["text_main"], arrowcolor=self.colors["text_main"])
        self.style.map("TCombobox",
                       fieldbackground=[('readonly', self.colors["bg_card"])],
                       foreground=[('readonly', self.colors["text_main"])])
        self.option_add('*TCombobox*Listbox.background', self.colors["bg_card"])
        self.option_add('*TCombobox*Listbox.foreground', self.colors["text_main"])
        self.option_add('*TCombobox*Listbox.selectBackground', PRIMARY)
        self.option_add('*TCombobox*Listbox.selectForeground', "white")

    def create_layout(self):
        self.body_container = tk.Frame(self, bg=self.colors["bg_body"])
        self.body_container.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        # The sidebar is a raised card floating on the canvas (.sidebar-float),
        # and now also carries everything the old top header bar held: the
        # brand lockup, the accent trio, and the running clock.
        sidebar_shell = tk.Frame(self.body_container, bg=self.colors["bg_sidebar"], width=232,
                                 highlightbackground=self.colors["border"], highlightthickness=1)
        sidebar_shell.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 16))
        sidebar_shell.pack_propagate(False)

        accent = tk.Frame(sidebar_shell, height=4, bg=self.colors["bg_sidebar"])
        accent.pack(side=tk.TOP, fill=tk.X)
        for color in ACCENT_STRIP:
            tk.Frame(accent, bg=color, height=4).pack(side=tk.LEFT, fill=tk.X, expand=True)

        brand = tk.Frame(sidebar_shell, bg=self.colors["bg_sidebar"])
        brand.pack(side=tk.TOP, fill=tk.X, padx=14, pady=(16, 0))
        # The real shop sign stands in for the old "JTC" text chip whenever the
        # image loads; the chip is still the fallback.
        logo = self.assets.circle("icon", 34, self.colors["bg_sidebar"])
        if logo is not None:
            self._sidebar_logo = logo
            tk.Label(brand, image=logo, bg=self.colors["bg_sidebar"],
                     bd=0).pack(side=tk.LEFT, padx=(0, 9))
        else:
            tk.Label(brand, text="JTC", bg=PRIMARY, fg="#F1F1F0", font=(FONT_FAMILY, 9, "bold"),
                     padx=8, pady=3).pack(side=tk.LEFT, padx=(0, 9))
        tk.Label(brand, text="JHAGRA\nCREATION & FABRICS", bg=self.colors["bg_sidebar"],
                 fg=self.colors["text_main"], font=(FONT_FAMILY, 8, "bold"),
                 justify="left", anchor="w").pack(side=tk.LEFT)
        tk.Frame(sidebar_shell, bg=self.colors["border"], height=1).pack(
            side=tk.TOP, fill=tk.X, padx=14, pady=(14, 10))

        # Packed before the nav list so the expanding list cannot push it off.
        self.lbl_clock = tk.Label(sidebar_shell, text="", bg=self.colors["bg_sidebar"],
                                  fg=self.colors["text_3"], font=(FONT_FAMILY, 8))
        self.lbl_clock.pack(side=tk.BOTTOM, pady=(6, 14))

        # Signed-in owner block at the foot of the sidebar.
        owner = self.assets.circle("owner", 38, self.colors["bg_sidebar"])
        if owner is not None:
            self._sidebar_owner = owner
            owner_row = tk.Frame(sidebar_shell, bg=self.colors["bg_sidebar"])
            owner_row.pack(side=tk.BOTTOM, fill=tk.X, padx=14, pady=(0, 4))
            tk.Label(owner_row, image=owner, bg=self.colors["bg_sidebar"],
                     bd=0).pack(side=tk.LEFT, padx=(0, 9))
            who = tk.Frame(owner_row, bg=self.colors["bg_sidebar"])
            who.pack(side=tk.LEFT, anchor="w")
            tk.Label(who, text="Jhagra", bg=self.colors["bg_sidebar"],
                     fg=self.colors["text_main"], font=(FONT_FAMILY, 9)).pack(anchor="w")
            self.lbl_sidebar_role = tk.Label(who, text=self._track("Owner"),
                                             bg=self.colors["bg_sidebar"],
                                             fg=self.colors["text_4"],
                                             font=(FONT_FAMILY, 7, "bold"))
            self.lbl_sidebar_role.pack(anchor="w")
            tk.Frame(sidebar_shell, bg=self.colors["border"], height=1).pack(
                side=tk.BOTTOM, fill=tk.X, padx=14, pady=(0, 10))

        sidebar = tk.Frame(sidebar_shell, bg=self.colors["bg_sidebar"])
        sidebar.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        # The nav items only fill the top of this frame; everything below them
        # is empty, and it is the one region large enough for the owner photo
        # to actually be legible rather than just a texture, so it gets a
        # stronger blend than the pages do.
        self._attach_page_backdrop(sidebar, opacity=0.22, blur=3,
                                   bg_key="bg_sidebar")

        self.nav_buttons = {}
        nav_keys = [("dashboard", "nav_dash"), ("customer", "nav_cust"),
                    ("order_card", "nav_order_card"),
                    ("calendar", "nav_calendar"),
                    ("employee", "nav_emp"), ("inventory", "nav_inventory"),
                    ("finance", "nav_finance"), ("expenses", "nav_expenses"),
                    ("admin", "nav_admin")]

        for key, lang_key in nav_keys:
            btn = tk.Button(sidebar, text=TRANSLATIONS[self.current_lang][lang_key], anchor="w", font=(FONT_FAMILY, 10, "bold"),
                            bg=self.colors["bg_sidebar"], fg=self.colors["text_muted"], activebackground=PRIMARY, activeforeground="white",
                            bd=0, padx=16, pady=12, cursor="hand2", command=lambda k=key: self.show_section(k))
            btn.pack(fill=tk.X, pady=2, padx=6)
            self.nav_buttons[key] = (btn, lang_key)
            # Hover feedback: lightly tint the button while the mouse is
            # over it, but only when it isn't the active section already
            # (the active one stays solid PRIMARY, handled by show_section).
            def _on_enter(e, b=btn, k=key):
                if self.current_section != k:
                    b.configure(bg=self.colors["bg_chart"])
            def _on_leave(e, b=btn, k=key):
                if self.current_section != k:
                    b.configure(bg=self.colors["bg_sidebar"])
            btn.bind("<Enter>", _on_enter)
            btn.bind("<Leave>", _on_leave)

        self.main_content = tk.Frame(self.body_container, bg=self.colors["bg_body"])
        self.main_content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.sections = {}
        self.build_dashboard_section()
        self.build_customer_section()
        self.build_order_card_section()
        self.build_calendar_section()
        self.build_employee_section()
        self.build_inventory_section()
        self.build_finance_section()
        self.build_expense_section()
        self.build_admin_section()

    def build_expense_section(self):
        sec = tk.Frame(self.main_content, bg=self.colors["bg_body"])
        self.sections["expenses"] = sec
        self._attach_page_backdrop(sec)
        self.expense_view = ExpenseView(sec, lambda: self.excel_mgr, self.colors)
        self.expense_view.frame.pack(fill=tk.BOTH, expand=True)

    def show_section(self, section_key):
        for key, frame in self.sections.items():
            frame.pack_forget()
            btn, _ = self.nav_buttons[key]
            btn.configure(bg=self.colors["bg_sidebar"], fg=self.colors["text_muted"])
        self.sections[section_key].pack(fill=tk.BOTH, expand=True)
        active_btn, _ = self.nav_buttons[section_key]
        # .nav-active in the design is a recessed well rather than a filled
        # block, so the active item reads as pressed into the sidebar.
        active_btn.configure(bg=self.colors["well"], fg=self.colors["text_main"])
        self.current_section = section_key
        self._app_state_for_current_data().save(last_section=section_key)

    # ==========================================
    # NEUMORPHIC UI PRIMITIVES
    # ==========================================
    # Flat-Tkinter stand-ins for the web app's CSS building blocks. Depth
    # there comes from box-shadows, which Tk has no equivalent for, so each
    # one is rebuilt out of thin coloured frames instead: a light edge where
    # the CSS puts a light shadow, a dark edge where it puts a dark one.

    # --- Rounded surfaces ---------------------------------------------------
    # A tk.Frame is always a hard rectangle, so the design's rounded cards
    # (--radius-card: 16px) cannot be built from frames at all. Each one is a
    # tk.Canvas with the rounded shape drawn on it and the real content frame
    # placed inside, inset far enough that its square corners stay within the
    # curve. The canvas paints itself in the PARENT's background colour, which
    # is what makes the cut corners read as empty space rather than as chips
    # of the wrong shade.

    @staticmethod
    def _round_rect(canvas, x0, y0, x1, y1, r, **kwargs):
        """Rounded rectangle as a smoothed polygon.

        Each corner contributes three coincident-ish points -- the two points
        where the curve meets the straight edges plus the corner itself -- so
        Tk's spline bends only at the corners and leaves the edges straight.
        """
        r = max(0, min(r, (x1 - x0) / 2, (y1 - y0) / 2))
        points = [
            x0 + r, y0, x1 - r, y0, x1, y0,
            x1, y0 + r, x1, y1 - r, x1, y1,
            x1 - r, y1, x0 + r, y1, x0, y1,
            x0, y1 - r, x0, y0 + r, x0, y0,
        ]
        return canvas.create_polygon(points, smooth=True, splinesteps=16, **kwargs)

    def _rounded_surface(self, parent, pack_opts, fill_key, radius,
                         padx, pady, raised=True, inset_pad=6):
        """Shared builder behind _neu_card and _neu_well.

        Returns the INNER frame, so every existing caller keeps treating the
        result as a plain tk.Frame it can pack widgets into.
        """
        # Match whatever is actually behind this card so the corners blend.
        try:
            parent_bg = parent.cget("bg")
        except tk.TclError:
            parent_bg = self.colors["bg_body"]

        cv = tk.Canvas(parent, bg=parent_bg, highlightthickness=0, bd=0,
                       height=1, width=1)
        cv.pack(**pack_opts)

        inner = tk.Frame(cv, bg=self.colors[fill_key], padx=padx, pady=pady)
        item = cv.create_window(inset_pad, inset_pad, window=inner, anchor="nw")

        fills = str(pack_opts.get("fill", "none"))
        stretch_x = fills in ("x", "both")
        stretch_y = fills in ("y", "both") and pack_opts.get("expand", False)

        def draw(_event=None):
            if not cv.winfo_exists():
                return
            w, h = cv.winfo_width(), cv.winfo_height()
            if w <= 1 or h <= 1:
                return
            cv.delete("surface")
            if raised:
                # Offset copy underneath stands in for --shadow-out; Tk has no
                # blur, so it is a hard edge peeking out along the bottom.
                self._round_rect(cv, 1, 3, w - 1, h - 1, radius,
                                 fill=self.colors["neu_shadow"], outline="",
                                 tags="surface")
            self._round_rect(cv, 1, 1, w - 1, h - 3 if raised else h - 1, radius,
                             fill=self.colors[fill_key],
                             outline=self.colors["border"], width=1,
                             tags="surface")
            cv.tag_lower("surface")
            if stretch_x:
                cv.itemconfigure(item, width=max(1, w - inset_pad * 2))
            if stretch_y:
                cv.itemconfigure(item, height=max(1, h - inset_pad * 2 - 2))

        def fit(_event=None):
            """Grow the canvas to whatever the content needs, unless pack is
            already stretching it."""
            if not cv.winfo_exists():
                return
            if not stretch_y:
                need = inner.winfo_reqheight() + inset_pad * 2 + 3
                if cv.winfo_height() != need:
                    cv.configure(height=need)
            if not stretch_x:
                need_w = inner.winfo_reqwidth() + inset_pad * 2 + 2
                if cv.winfo_width() != need_w:
                    cv.configure(width=need_w)
            draw()

        cv.bind("<Configure>", draw)
        inner.bind("<Configure>", fit)
        self.after_idle(fit)
        return inner

    def _neu_card(self, parent, pack_opts, bg_key="bg_card", padx=18, pady=16):
        """Raised rounded surface (.neu-raised / --radius-card)."""
        return self._rounded_surface(parent, pack_opts, bg_key, CARD_RADIUS,
                                     padx, pady, raised=True)

    def _glass_card(self, parent, pack_opts, bg_key="bg_chart", padx=14, pady=14):
        """Pre-existing call sites (here and in order_card_view) still ask for
        a 'glass card'; the design system replaced that with the raised
        neumorphic surface, so this forwards while keeping the old padding
        defaults so no existing card changes size."""
        return self._neu_card(parent, pack_opts, bg_key=bg_key, padx=padx, pady=pady)

    def _neu_well(self, parent, pack_opts, padx=13, pady=10):
        """Inset rounded well (.neu-inset-sm / --radius-chip): filled a shade
        DARKER than the surface it sits on and drawn without the raised
        shadow, so it reads as pressed in rather than standing out."""
        return self._rounded_surface(parent, pack_opts, "well", WELL_RADIUS,
                                     padx, pady, raised=False, inset_pad=4)

    @staticmethod
    def _track(text):
        """Stand-in for the design's wide letter-spacing on its small
        uppercase labels (0.06em-0.1em), which Tk fonts cannot express:
        weave thin spaces between the characters instead.

        Skipped for anything non-ASCII so Urdu -- and any other shaped
        script -- is never pulled apart into disconnected letters.
        """
        if not text.isascii():
            return text
        return "\u2009".join(text.upper())

    def _section_label(self, parent, text, bg_key="bg_card"):
        """The recurring 11px / 600 / uppercase / tracked section caption."""
        return tk.Label(parent, text=self._track(text), font=(FONT_FAMILY, 8, "bold"),
                        bg=self.colors[bg_key], fg=self.colors["text_muted"])

    def _avatar(self, parent, letter, fill, fg, size=40, bg_key="bg_card"):
        """Round initial chip, as used on the customer and tailor cards."""
        c = tk.Canvas(parent, width=size, height=size, bg=self.colors[bg_key],
                      highlightthickness=0)
        c.create_oval(0, 0, size - 1, size - 1, fill=fill, outline="")
        c.create_text(size / 2.0, size / 2.0, text=letter, fill=fg,
                      font=(FONT_FAMILY, max(8, int(size * 0.34)), "bold"))
        return c

    def _stat_tile(self, parent, pack_opts, icon, value, label):
        """Icon + big number + tracked caption tile. Returns the value label
        so the caller can keep it and update the number later."""
        card = self._neu_card(parent, pack_opts, padx=16, pady=14)
        tile = self._neu_well(card, dict(side=tk.LEFT, padx=(0, 13)), padx=8, pady=5)
        tk.Label(tile, text=icon, font=(FONT_FAMILY, 15), bg=self.colors["well"],
                 fg=self.colors["text_muted"]).pack()
        box = tk.Frame(card, bg=self.colors["bg_card"])
        box.pack(side=tk.LEFT, anchor="w")
        val = tk.Label(box, text=str(value), font=(FONT_FAMILY, 17),
                       bg=self.colors["bg_card"], fg=self.colors["text_main"])
        val.pack(anchor="w")
        cap = tk.Label(box, text=self._track(label), font=(FONT_FAMILY, 7, "bold"),
                       bg=self.colors["bg_card"], fg=self.colors["text_4"])
        cap.pack(anchor="w")
        return val, cap

    def _tinted_palette(self, base):
        """A copy of `base` with the card surfaces frosted toward the owner
        photo's average colour (see CARD_FROST).

        Returns a NEW dict -- THEMES must never be mutated, or the tint would
        compound every time the theme is switched.
        """
        colors = dict(base)
        if not CARD_FROST or not self.assets.available:
            return colors
        tint = self.assets.average_color("owner")
        if not tint:
            return colors
        tr, tg, tb = (int(tint[i:i + 2], 16) for i in (1, 3, 5))
        # bg_body is intentionally absent: leaving the page canvas untinted is
        # what keeps a visible edge between a card and the gutter beside it.
        # neu_light / neu_shadow / border are deliberately excluded: they are
        # what give a card its edge, and tinting them toward the same colour
        # as the surface they outline flattens every card into the page.
        for key in ("bg_card", "bg_chart", "bg_sidebar", "bg_header",
                    "well", "surface_alt"):
            if key not in colors:
                continue
            r, g, b = (int(colors[key][i:i + 2], 16) for i in (1, 3, 5))
            colors[key] = "#%02X%02X%02X" % (
                round(r + (tr - r) * CARD_FROST),
                round(g + (tg - g) * CARD_FROST),
                round(b + (tb - b) * CARD_FROST))
        return colors

    def _attach_page_backdrop(self, sec, opacity=None, blur=None, bg_key="bg_body"):
        """Blend the owner photo faintly behind a page, so it shows through
        the gutters between cards.

        Tk frames cannot be transparent, so this is not a layer the cards sit
        *over* -- it is a full-bleed image placed behind them and then lowered.
        Cards are opaque and cover most of it; what remains visible is the
        page margins and the gaps between cards, which is exactly the part
        that should read as background.

        Rebuilt on resize, debounced and snapped to a 24px grid so dragging
        the window edge does not re-blur a full-size photo on every pixel.
        """
        if not self.assets.available:
            return
        holder = tk.Label(sec, bd=0, bg=self.colors[bg_key])
        holder.place(x=0, y=0, relwidth=1, relheight=1)
        holder.lower()

        def redraw():
            sec._backdrop_job = None
            if not sec.winfo_exists():
                return
            w = ((max(1, sec.winfo_width()) // 24) + 1) * 24
            h = ((max(1, sec.winfo_height()) // 24) + 1) * 24
            img = self.assets.backdrop(
                "owner", (w, h), self.colors[bg_key],
                opacity=PAGE_BACKDROP_OPACITY if opacity is None else opacity,
                blur=PAGE_BACKDROP_BLUR if blur is None else blur)
            if img is not None:
                holder.configure(image=img)
                # Tk drops an image the moment its last Python reference goes,
                # which would blank the label; the store caches it too, but
                # pinning it here keeps that independent of cache eviction.
                holder.image = img

        def schedule(_event=None):
            job = getattr(sec, "_backdrop_job", None)
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
            sec._backdrop_job = self.after(120, redraw)

        sec._backdrop_job = None
        sec.bind("<Configure>", schedule)
        schedule()

    def _page_header(self, parent, title, subtitle):
        """Stacked title + subtitle on the left, room for a primary action on
        the right -- the design's <PageHeader>. Returns (title_label,
        subtitle_label, right_slot); pack the primary button into the slot."""
        hdr = tk.Frame(parent, bg=self.colors["bg_body"])
        hdr.pack(fill=tk.X, padx=2, pady=(2, 12))
        titles = tk.Frame(hdr, bg=self.colors["bg_body"])
        titles.pack(side=tk.LEFT)
        lbl_title = tk.Label(titles, text=title, font=(FONT_FAMILY, 19),
                             bg=self.colors["bg_body"], fg=self.colors["text_main"])
        lbl_title.pack(anchor="w")
        lbl_sub = tk.Label(titles, text=subtitle, font=(FONT_FAMILY, 9),
                           bg=self.colors["bg_body"], fg=self.colors["text_muted"])
        lbl_sub.pack(anchor="w", pady=(2, 0))
        right = tk.Frame(hdr, bg=self.colors["bg_body"])
        right.pack(side=tk.RIGHT)
        return lbl_title, lbl_sub, right

    def _primary_button(self, parent, text, command):
        """The dark neumorphic pill (.btn-dark-neu) used for a page's one
        primary action."""
        return tk.Button(parent, text=text, bg=PRIMARY, fg="#F1F1F0",
                         font=(FONT_FAMILY, 9, "bold"), bd=0, padx=16, pady=8,
                         cursor="hand2", activebackground=PRIMARY,
                         activeforeground="#F1F1F0", command=command)

    def _toolbar_button(self, parent, text, command, danger=False):
        """A raised surface chip (.btn-neu) for secondary row actions -- quiet
        by default, brick-red lettering when the action is destructive."""
        return tk.Button(parent, text=text, bg=self.colors["bg_card"],
                         fg=DANGER if danger else self.colors["text_muted"],
                         font=(FONT_FAMILY, 9, "bold"), bd=0, padx=12, pady=7,
                         cursor="hand2", activebackground=self.colors["well"],
                         activeforeground=DANGER if danger else self.colors["text_main"],
                         highlightbackground=self.colors["border"], highlightthickness=1,
                         command=command)

    def _search_row(self, parent, label_text, entry_attr, on_key, on_clear):
        """Search field rendered as an inset well, as the design's inputs are."""
        row = tk.Frame(parent, bg=self.colors["bg_body"])
        row.pack(fill=tk.X, pady=(0, 12))
        well = self._neu_well(row, dict(fill=tk.X), padx=12, pady=7)
        tk.Label(well, text=label_text, font=(FONT_FAMILY, 8, "bold"),
                 bg=self.colors["well"], fg=self.colors["text_muted"]).pack(side=tk.LEFT, padx=(0, 8))
        ent = tk.Entry(well, font=(FONT_FAMILY, 10), bg=self.colors["well"],
                       fg=self.colors["text_main"], insertbackground=self.colors["text_main"],
                       relief="flat", highlightthickness=0, bd=0)
        ent.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        ent.bind("<KeyRelease>", on_key)
        setattr(self, entry_attr, ent)
        tk.Button(well, text="✖", bg=self.colors["well"], fg=self.colors["text_3"],
                  font=(FONT_FAMILY, 9), bd=0, padx=6, pady=0, cursor="hand2",
                  activebackground=self.colors["well"], command=on_clear).pack(side=tk.LEFT)
        return row

    # ==========================================
    # DASHBOARD SECTION
    # ==========================================
    def build_dashboard_section(self):
        # The page itself is the bare canvas; every block on it is a raised
        # card floating on top, which is how the web Dashboard is laid out.
        sec = tk.Frame(self.main_content, bg=self.colors["bg_body"])
        self.sections["dashboard"] = sec
        self._attach_page_backdrop(sec)

        # --- Page header: title + live date line on the left, primary action
        # on the right (the web app's <PageHeader> and the button beside it).
        hdr = tk.Frame(sec, bg=self.colors["bg_body"])
        hdr.pack(fill=tk.X, padx=2, pady=(2, 14))
        titles = tk.Frame(hdr, bg=self.colors["bg_body"])
        titles.pack(side=tk.LEFT)
        # Deliberately NOT bold: the design sets its page titles in a light
        # weight (400) and leans on size alone for hierarchy.
        self.lbl_dash_title = tk.Label(titles, text="Dashboard", font=(FONT_FAMILY, 19),
                                       bg=self.colors["bg_body"], fg=self.colors["text_main"])
        self.lbl_dash_title.pack(anchor="w")
        subrow = tk.Frame(titles, bg=self.colors["bg_body"])
        subrow.pack(anchor="w", pady=(2, 0))
        self.lbl_dash_sub = tk.Label(subrow, text="Live overview of tailoring work",
                                     font=(FONT_FAMILY, 9), bg=self.colors["bg_body"],
                                     fg=self.colors["text_muted"])
        self.lbl_dash_sub.pack(side=tk.LEFT)
        # Long-form date + running clock, as the web dashboard carries.
        self.lbl_dash_datetime = tk.Label(subrow, text="", font=(FONT_FAMILY, 9),
                                          bg=self.colors["bg_body"], fg=self.colors["text_3"])
        self.lbl_dash_datetime.pack(side=tk.LEFT)
        self.btn_dash_new_order = tk.Button(
            hdr, text="+ New Order", bg=PRIMARY, fg="#F1F1F0",
            font=(FONT_FAMILY, 9, "bold"), bd=0, padx=16, pady=8, cursor="hand2",
            activebackground=PRIMARY, activeforeground="#F1F1F0",
            command=self.open_add_order_modal)
        self.btn_dash_new_order.pack(side=tk.RIGHT)

        # --- All three order gauges share ONE raised card, spread evenly
        # across it, rather than sitting in three separate cards.
        gauge_card = self._neu_card(sec, dict(fill=tk.X, pady=(0, 14)), padx=20, pady=18)
        gauges = tk.Frame(gauge_card, bg=self.colors["bg_card"])
        gauges.pack(fill=tk.X)

        def gauge(caption, color):
            col = tk.Frame(gauges, bg=self.colors["bg_card"])
            col.pack(side=tk.LEFT, expand=True, fill=tk.X)
            chart = CircularDonutChart(col, size=94, ring_color=color,
                                       bg_color=self.colors["well"], stroke_width=9,
                                       theme_colors=self.colors)
            chart.pack()
            # The reading sits INSIDE the ring; a placed label is the simplest
            # way to centre text over a canvas without touching the widget.
            pct = tk.Label(chart, text="0%", font=(FONT_FAMILY, 15),
                           bg=self.colors["bg_chart"], fg=self.colors["text_main"])
            pct.place(relx=0.5, rely=0.5, anchor="center")
            cap = self._section_label(col, caption)
            cap.pack(pady=(10, 0))
            return chart, pct, cap

        self.chart_done, self.lbl_done_pct, self.lbl_done_title = gauge("WORK DONE", GAUGE_DONE)
        self.chart_prog, self.lbl_prog_pct, self.lbl_prog_title = gauge("IN PROGRESS", GAUGE_PROGRESS)
        self.chart_rem, self.lbl_rem_pct, self.lbl_rem_title = gauge("REMAINING", GAUGE_REMAINING)

        # --- Counter tiles: icon well + big light number + tracked caption.
        tiles = tk.Frame(sec, bg=self.colors["bg_body"])
        tiles.pack(fill=tk.X, pady=(0, 14))
        self.lbl_stat_orders, self.lbl_stat_orders_cap = self._stat_tile(
            tiles, dict(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 7)), "\U0001F9FE", 0, "Total Orders")
        self.lbl_stat_customers, self.lbl_stat_customers_cap = self._stat_tile(
            tiles, dict(side=tk.LEFT, expand=True, fill=tk.X, padx=7), "\U0001F465", 0, "Customers")
        self.lbl_stat_onduty, self.lbl_stat_onduty_cap = self._stat_tile(
            tiles, dict(side=tk.LEFT, expand=True, fill=tk.X, padx=(7, 0)), "✂️", 0, "Tailors On Duty")

        # --- Finance snapshot row: mirrors the Finance section's totals so
        # the money picture is visible without leaving the Dashboard. Values
        # (and the donut percentages, each share-of-grand-total) are
        # populated by refresh_finance_ui() from FinanceDB (SQL), not here.
        finance_frame = tk.Frame(sec, bg=self.colors["bg_body"])
        finance_frame.pack(fill=tk.X, pady=(0, 14))

        def money_card(pack_opts, caption, color):
            card = self._neu_card(finance_frame, pack_opts, padx=16, pady=13)
            box = tk.Frame(card, bg=self.colors["bg_card"])
            box.pack(side=tk.LEFT, anchor="w")
            cap = self._section_label(box, caption)
            cap.pack(anchor="w")
            val = tk.Label(box, text="PKR 0.00", font=(FONT_FAMILY, 14),
                           bg=self.colors["bg_card"], fg=self.colors["text_main"])
            val.pack(anchor="w", pady=(3, 0))
            chart = CircularDonutChart(card, size=62, ring_color=color,
                                       bg_color=self.colors["well"], stroke_width=7,
                                       theme_colors=self.colors)
            chart.pack(side=tk.RIGHT)
            return cap, val, chart

        self.lbl_fin_paid_title, self.lbl_fin_paid_val, self.chart_fin_paid = money_card(
            dict(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 7)), "TOTAL PAID", SAGE)
        self.lbl_fin_remaining_title, self.lbl_fin_remaining_val, self.chart_fin_remaining = money_card(
            dict(side=tk.LEFT, expand=True, fill=tk.X, padx=7), "TOTAL REMAINING", GAUGE_PROGRESS)
        self.lbl_fin_debt_title, self.lbl_fin_debt_val, self.chart_fin_debt = money_card(
            dict(side=tk.LEFT, expand=True, fill=tk.X, padx=(7, 0)), "TOTAL DEBT", TERRACOTTA)

        # --- Active ledger -------------------------------------------------
        ledger_card = self._neu_card(sec, dict(fill=tk.BOTH, expand=True, pady=(0, 2)),
                                     padx=18, pady=16)
        tbl_bar = tk.Frame(ledger_card, bg=self.colors["bg_card"])
        tbl_bar.pack(fill=tk.X, pady=(0, 12))
        self.lbl_ledger_head = self._section_label(tbl_bar, "Active Orders Ledger")
        self.lbl_ledger_head.pack(side=tk.LEFT)
        tk.Button(tbl_bar, text="✔ Mark Ready", bg=self.colors["bg_card"], fg=SAGE,
                  font=(FONT_FAMILY, 8, "bold"), bd=0, padx=10, pady=4, cursor="hand2",
                  activebackground=self.colors["well"], activeforeground=SAGE,
                  command=lambda: self.quick_change_order_status("Ready")).pack(side=tk.RIGHT)

        # The ledger is rendered as a list of inset rows (order no. + a
        # compound customer/garment cell + a status pill) instead of a grid,
        # which is the shape the web app uses.
        self.ledger_rows = tk.Frame(ledger_card, bg=self.colors["bg_card"])
        self.ledger_rows.pack(fill=tk.BOTH, expand=True)
        self._ledger_row_widgets = {}
        self._ledger_selected = None

        # tree_orders stays as the ledger's data + selection model. It is
        # deliberately never packed: every existing caller (the context menu,
        # quick_change_order_status, generate_order_pdf, the smoke test) keeps
        # reading selection() / get_children() off it exactly as before, while
        # _render_ledger_rows draws the visible list from those same rows. That
        # keeps a single source of truth and left every call site unchanged.
        self.tree_orders = ttk.Treeview(ledger_card, columns=self.ord_headers, show="headings")
        for c in self.ord_headers:
            if c == 'customer_id':
                header_text = TRANSLATIONS[self.current_lang].get('tbl_cust', 'Customer').upper()
            else:
                header_text = c.upper().replace("_", " ")
            self.tree_orders.heading(c, text=header_text)
            self.tree_orders.column(c, width=90)

    def _ledger_status_style(self, status):
        """Pill colour and display text for an order status, reusing the same
        three accents the gauges above the ledger are drawn in."""
        st = clean_val(status).lower()
        if "ready" in st or "done" in st or "deliver" in st:
            return GAUGE_DONE, clean_val(status) or "Ready"
        if "progress" in st:
            return GAUGE_PROGRESS, clean_val(status) or "In Progress"
        return GAUGE_REMAINING, clean_val(status) or "Pending"

    def _render_ledger_rows(self):
        """Draw the visible ledger from whatever tree_orders currently holds,
        so the list and the selection model can never drift apart."""
        for w in self.ledger_rows.winfo_children():
            w.destroy()
        self._ledger_row_widgets = {}

        idx = {h: i for i, h in enumerate(self.ord_headers)}
        children = self.tree_orders.get_children()
        if not children:
            tk.Label(self.ledger_rows, text="No active orders yet.",
                     font=(FONT_FAMILY, 9), bg=self.colors["bg_card"],
                     fg=self.colors["text_3"]).pack(anchor="w", pady=6)
            return

        unassigned = TRANSLATIONS[self.current_lang].get("dash_unassigned", "Unassigned")
        for iid in children[:8]:
            vals = list(self.tree_orders.item(iid)["values"])

            def cell(name, _vals=vals):
                i = idx.get(name)
                return clean_val(_vals[i]) if i is not None and i < len(_vals) else ""

            row = self._neu_well(self.ledger_rows, dict(fill=tk.X, pady=3), padx=13, pady=9)
            tk.Label(row, text=cell("id"), font=(FONT_FAMILY, 8, "bold"), width=9,
                     anchor="w", bg=self.colors["well"],
                     fg=self.colors["text_3"]).pack(side=tk.LEFT)

            # Compound cell: customer on top, garment + tailor underneath.
            mid = tk.Frame(row, bg=self.colors["well"])
            mid.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(mid, text=cell("customer_id"), font=(FONT_FAMILY, 10),
                     anchor="w", bg=self.colors["well"],
                     fg=self.colors["text_main"]).pack(anchor="w", fill=tk.X)
            tk.Label(mid, text=cell("garment") + "  ·  " + (cell("tailor") or unassigned),
                     font=(FONT_FAMILY, 8), anchor="w", bg=self.colors["well"],
                     fg=self.colors["text_4"]).pack(anchor="w", fill=tk.X)

            color, text = self._ledger_status_style(cell("status"))
            StatusPill(row, text, color, self.colors["well"],
                       self.colors["bg_card"], self.colors["text_main"]).pack(side=tk.RIGHT)

            shell = row.master
            self._ledger_row_widgets[iid] = shell
            # Clicking a row mirrors the selection into the hidden tree, so the
            # toolbar button, the context menu and PDF export all act on
            # whichever row the user actually clicked.
            targets = [shell, row, mid] + list(mid.winfo_children()) + list(row.winfo_children())
            for w in targets:
                w.bind("<Button-1>", lambda e, i=iid: self._select_ledger_row(i))
                w.bind("<Button-3>", lambda e, i=iid: self._ledger_row_menu(e, i))

        if self._ledger_selected in self._ledger_row_widgets:
            self._select_ledger_row(self._ledger_selected)

    def _select_ledger_row(self, iid):
        self._ledger_selected = iid
        self.tree_orders.selection_set(iid)
        for other, shell in self._ledger_row_widgets.items():
            shell.configure(highlightbackground=PRIMARY if other == iid
                            else self.colors["border"])

    def _ledger_row_menu(self, event, iid):
        self._select_ledger_row(iid)
        self.show_order_context_menu(event)

    def show_order_context_menu(self, event):
        # Ledger rows are inset blocks now rather than tree rows, so there is
        # nothing to hit-test here: _ledger_row_menu has already mirrored the
        # click into tree_orders' selection before handing the event over.
        if self.tree_orders.selection():
            menu = tk.Menu(self, tearoff=0)
            menu.add_command(label="✔ Mark Ready", command=lambda: self.quick_change_order_status("Ready"))
            menu.add_command(label="⏳ Mark In Progress", command=lambda: self.quick_change_order_status("In Progress"))
            menu.add_separator()
            menu.add_command(label="📄 Print Order PDF", command=self.generate_order_pdf)
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

    def quick_change_order_status(self, new_status):
        sel = self.tree_orders.selection()
        if not sel:
            return
        ord_id = str(self.tree_orders.item(sel[0])["values"][0])
        rows_to_write = []
        for o in self.orders:
            curr_id = clean_val(o.get("id"))
            status = new_status if curr_id == ord_id else clean_val(o.get("status"))
            # Schema-aware rewrite: preserves every column (legacy + order-card).
            r = [clean_val(o.get(h)) for h in self.ord_headers]
            r[self.ord_headers.index("id")] = curr_id
            r[self.ord_headers.index("status")] = status
            rows_to_write.append(r)
        try:
            self.excel_mgr.write_all_records("orders.xlsx", self.ord_headers, rows_to_write)
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            return
        self.reload_all_data()
        self.update_graphics_and_stats()

    # ==========================================
    # CUSTOMER SECTION
    # ==========================================
    def build_customer_section(self):
        sec = tk.Frame(self.main_content, bg=self.colors["bg_body"])
        self.sections["customer"] = sec
        self._attach_page_backdrop(sec)

        self.lbl_cust_title, self.lbl_cust_sub, hdr_right = self._page_header(
            sec, "Customer Hub", "Manage customer profiles & measurements")
        t = TRANSLATIONS[self.current_lang]
        self.btn_cust_modal = self._primary_button(hdr_right, "+ Add Customer",
                                                   self.open_add_customer_modal)
        self.btn_cust_modal.pack(side=tk.RIGHT)

        # Secondary actions live on their own row so they can never crowd the
        # title the way five buttons in the header used to.
        tools = tk.Frame(sec, bg=self.colors["bg_body"])
        tools.pack(fill=tk.X, pady=(0, 12))
        self.btn_new_card = self._toolbar_button(
            tools, "🖨️ New Order Card", lambda: self.show_section("order_card"))
        self.btn_new_card.pack(side=tk.LEFT, padx=(0, 7))
        self.btn_cust_receipt = self._toolbar_button(
            tools, t.get("cust_btn_receipt", "🧾 Print Latest Receipt"),
            self.print_selected_customer_receipt)
        self.btn_cust_receipt.pack(side=tk.LEFT, padx=(0, 7))
        self.btn_cust_edit = self._toolbar_button(
            tools, t.get("cust_btn_edit", "✏️ Edit"), self.edit_selected_customer)
        self.btn_cust_edit.pack(side=tk.LEFT, padx=(0, 7))
        self.btn_cust_delete = self._toolbar_button(
            tools, t.get("cust_btn_delete", "🗑️ Delete"),
            self.delete_selected_customer, danger=True)
        self.btn_cust_delete.pack(side=tk.LEFT)

        self._search_row(sec, "🔍 SEARCH", "ent_cust_search",
                         self.filter_customers, self.clear_customer_search)

        table_card = self._neu_card(sec, dict(fill=tk.BOTH, expand=True), padx=14, pady=12)
        self.tree_customers = ttk.Treeview(table_card, columns=self.cust_headers, show="headings")
        for c in self.cust_headers:
            self.tree_customers.heading(c, text=c.upper())
            self.tree_customers.column(c, width=75)
        self.tree_customers.pack(fill=tk.BOTH, expand=True)

        # Store original customer data for filtering
        self._customer_filter_data = []

    # ==========================================
    # ORDER CARD SECTION  (digital JTQ paper slip)
    # ==========================================
    def build_order_card_section(self):
        """Mounts the reusable OrderCardView into the main content area."""
        sec = tk.Frame(self.main_content, bg=self.colors["bg_body"])
        self.sections["order_card"] = sec
        self.order_card = OrderCardView(sec, self, self.colors, FONT_FAMILY,
                                        PRIMARY, SUCCESS, WARNING, DANGER)
        self.order_card.pack(fill=tk.BOTH, expand=True)

    # ==========================================
    # EMPLOYEE SECTION
    # ==========================================
    def build_employee_section(self):
        sec = tk.Frame(self.main_content, bg=self.colors["bg_body"])
        self.sections["employee"] = sec
        self._attach_page_backdrop(sec)

        self.lbl_emp_title, self.lbl_emp_sub, hdr_right = self._page_header(
            sec, "Staff & Tailors", "Manage staff, roles and daily tasks")
        self.btn_emp_modal = self._primary_button(hdr_right, "+ Add Staff",
                                                  self.open_add_employee_modal)
        self.btn_emp_modal.pack(side=tk.RIGHT)

        # Secondary actions on their own row, same as the Customer Hub.
        tools = tk.Frame(sec, bg=self.colors["bg_body"])
        tools.pack(fill=tk.X, pady=(0, 12))
        self.btn_task_modal = self._toolbar_button(tools, "🛠️ Assign Task",
                                                   self.open_assign_task_modal)
        self.btn_task_modal.pack(side=tk.LEFT, padx=(0, 7))
        self.btn_emp_print = self._toolbar_button(tools, "🧾 Print Task Slip",
                                                  self.print_selected_employee_task)
        self.btn_emp_print.pack(side=tk.LEFT, padx=(0, 7))
        self.btn_emp_edit = self._toolbar_button(tools, "✏️ Edit",
                                                 self.edit_selected_employee)
        self.btn_emp_edit.pack(side=tk.LEFT, padx=(0, 7))
        self.btn_emp_delete = self._toolbar_button(tools, "🗑️ Delete",
                                                   self.delete_selected_employee, danger=True)
        self.btn_emp_delete.pack(side=tk.LEFT)

        table_card = self._neu_card(sec, dict(fill=tk.BOTH, expand=True), padx=14, pady=12)
        self.tree_employees = ttk.Treeview(table_card, columns=self.emp_headers, show="headings")
        for c in self.emp_headers:
            self.tree_employees.heading(c, text=c.upper())
            self.tree_employees.column(c, width=120)
        self.tree_employees.pack(fill=tk.BOTH, expand=True)

    # ==========================================
    # PRODUCTION CALENDAR SECTION
    # ==========================================
    def build_calendar_section(self):
        """Month grid of what is due when, built from each order's
        delivery_date. Read-only: it is a planning view over orders that
        already exist, not another place to create them."""
        sec = tk.Frame(self.main_content, bg=self.colors["bg_body"])
        self.sections["calendar"] = sec
        self._attach_page_backdrop(sec)

        self.lbl_cal_title, self.lbl_cal_sub, hdr_right = self._page_header(
            sec, "Production Calendar", "Deliveries due, by day")

        nav = tk.Frame(hdr_right, bg=self.colors["bg_body"])
        nav.pack(side=tk.RIGHT)
        self.btn_cal_today = self._toolbar_button(nav, "Today", self.calendar_today)
        self.btn_cal_today.pack(side=tk.LEFT, padx=(0, 7))
        self._toolbar_button(nav, "‹", lambda: self.shift_calendar_month(-1)).pack(side=tk.LEFT, padx=(0, 4))
        self._toolbar_button(nav, "›", lambda: self.shift_calendar_month(1)).pack(side=tk.LEFT)

        # Workload strip: the three numbers a shop actually plans against.
        strip = tk.Frame(sec, bg=self.colors["bg_body"])
        strip.pack(fill=tk.X, pady=(0, 12))
        self.lbl_cal_stat_month, self.lbl_cal_stat_month_cap = self._stat_tile(
            strip, dict(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 7)),
            "📅", 0, "Due This Month")
        self.lbl_cal_stat_week, self.lbl_cal_stat_week_cap = self._stat_tile(
            strip, dict(side=tk.LEFT, expand=True, fill=tk.X, padx=7),
            "⏳", 0, "Due In 7 Days")
        self.lbl_cal_stat_late, self.lbl_cal_stat_late_cap = self._stat_tile(
            strip, dict(side=tk.LEFT, expand=True, fill=tk.X, padx=(7, 0)),
            "⚠️", 0, "Overdue")

        card = self._neu_card(sec, dict(fill=tk.BOTH, expand=True), padx=16, pady=14)
        bar = tk.Frame(card, bg=self.colors["bg_card"])
        bar.pack(fill=tk.X, pady=(0, 10))
        self.lbl_cal_month = self._section_label(bar, "MONTH")
        self.lbl_cal_month.pack(side=tk.LEFT)

        self.cal_grid = tk.Frame(card, bg=self.colors["bg_card"])
        self.cal_grid.pack(fill=tk.BOTH, expand=True)
        for col in range(7):
            self.cal_grid.columnconfigure(col, weight=1, uniform="cal")

        today = datetime.now()
        self.cal_year, self.cal_month = today.year, today.month

    def shift_calendar_month(self, delta):
        month = self.cal_month + delta
        self.cal_year += (month - 1) // 12
        self.cal_month = (month - 1) % 12 + 1
        self.refresh_calendar_ui()

    def calendar_today(self):
        now = datetime.now()
        self.cal_year, self.cal_month = now.year, now.month
        self.refresh_calendar_ui()

    @staticmethod
    def _parse_date(value):
        """Delivery dates are typed by hand, so accept the handful of shapes
        that actually turn up in the sheet rather than one strict format."""
        text = clean_val(value).strip()
        if not text:
            return None
        text = text.split(" ")[0]
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _is_delivered(order):
        """True only for an affirmative "Delivered".

        The sheet also stores "Not Delivered", which *contains* the word
        "deliver" -- so a substring test hides every undelivered order, which
        is exactly the set the calendar exists to show. Anchoring at the start
        of the string is what separates the two.
        """
        for field in ("delivery_status", "status"):
            if clean_val(order.get(field)).strip().lower().startswith("deliver"):
                return True
        return False

    def _orders_by_due_date(self):
        """Map of date -> orders due that day, skipping anything already
        delivered (it is no longer production work)."""
        buckets = {}
        for o in getattr(self, "orders", []):
            if not o.get("id"):
                continue
            if self._is_delivered(o):
                continue
            due = self._parse_date(o.get("delivery_date"))
            if due is None:
                continue
            buckets.setdefault(due, []).append(o)
        return buckets

    def refresh_calendar_ui(self):
        if not hasattr(self, "cal_grid") or not self.cal_grid.winfo_exists():
            return
        import calendar as _calendar

        for w in self.cal_grid.winfo_children():
            w.destroy()

        buckets = self._orders_by_due_date()
        today = datetime.now().date()
        t = {**TRANSLATIONS["en"], **TRANSLATIONS.get(self.current_lang, {})}

        self.lbl_cal_month.configure(text=self._track(
            "%s %d" % (_calendar.month_name[self.cal_month], self.cal_year)))

        # Weekday header row.
        for col, day in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            tk.Label(self.cal_grid, text=self._track(day), font=(FONT_FAMILY, 7, "bold"),
                     bg=self.colors["bg_card"], fg=self.colors["text_4"]).grid(
                row=0, column=col, sticky="w", padx=3, pady=(0, 4))

        weeks = _calendar.Calendar(firstweekday=0).monthdatescalendar(
            self.cal_year, self.cal_month)
        for r, week in enumerate(weeks, start=1):
            self.cal_grid.rowconfigure(r, weight=1, uniform="calrow")
            for c, day in enumerate(week):
                in_month = day.month == self.cal_month
                due = buckets.get(day, [])
                cell = self._neu_well(
                    tk.Frame(self.cal_grid, bg=self.colors["bg_card"]),
                    dict(fill=tk.BOTH, expand=True), padx=7, pady=5)
                holder = cell.master.master
                holder.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)

                head = tk.Frame(cell, bg=self.colors["well"])
                head.pack(fill=tk.X)
                # Days outside the current month stay visible but recede, so
                # the grid keeps its shape without pulling focus.
                day_fg = (self.colors["text_main"] if in_month
                          else self.colors["text_3"])
                tk.Label(head, text=str(day.day), font=(FONT_FAMILY, 9,
                         "bold" if day == today else "normal"),
                         bg=self.colors["well"],
                         fg=PRIMARY if day == today else day_fg).pack(side=tk.LEFT)
                if due:
                    StatusPill(head, str(len(due)),
                               TERRACOTTA if day < today else GAUGE_PROGRESS,
                               self.colors["well"], self.colors["bg_card"],
                               self.colors["text_main"], height=17, pad=6,
                               dot=5).pack(side=tk.RIGHT)

                for o in due[:3]:
                    name = clean_val(o.get("customer_id"))
                    match = next((clean_val(x.get("name")) for x in self.customers
                                  if clean_val(x.get("id")) == name), name)
                    tk.Label(cell, text="· " + (match or "—"),
                             font=(FONT_FAMILY, 7), anchor="w",
                             bg=self.colors["well"], fg=self.colors["text_muted"]
                             ).pack(anchor="w", fill=tk.X)
                if len(due) > 3:
                    tk.Label(cell, text="+%d more" % (len(due) - 3),
                             font=(FONT_FAMILY, 7), anchor="w",
                             bg=self.colors["well"], fg=self.colors["text_3"]
                             ).pack(anchor="w", fill=tk.X)

        month_due = sum(len(v) for k, v in buckets.items()
                        if k.year == self.cal_year and k.month == self.cal_month)
        week_due = sum(len(v) for k, v in buckets.items()
                       if 0 <= (k - today).days <= 7)
        overdue = sum(len(v) for k, v in buckets.items() if k < today)
        self.lbl_cal_stat_month.configure(text=str(month_due))
        self.lbl_cal_stat_week.configure(text=str(week_due))
        self.lbl_cal_stat_late.configure(text=str(overdue))

    # ==========================================
    # INVENTORY SECTION
    # ==========================================
    def build_inventory_section(self):
        """Stock on hand, with a summary strip over the table. Backed by its
        own inventory.xlsx, using the same read/append/write-all pattern as
        every other sheet in the app."""
        sec = tk.Frame(self.main_content, bg=self.colors["bg_body"])
        self.sections["inventory"] = sec
        self._attach_page_backdrop(sec)

        self.lbl_inv_title, self.lbl_inv_sub, hdr_right = self._page_header(
            sec, "Inventory", "Fabric and trim stock on hand")
        self.btn_inv_add = self._primary_button(hdr_right, "+ Add Item",
                                                self.open_add_inventory_modal)
        self.btn_inv_add.pack(side=tk.RIGHT)

        tools = tk.Frame(sec, bg=self.colors["bg_body"])
        tools.pack(fill=tk.X, pady=(0, 12))
        self.btn_inv_in = self._toolbar_button(tools, "➕ Stock In",
                                               lambda: self.adjust_inventory(1))
        self.btn_inv_in.pack(side=tk.LEFT, padx=(0, 7))
        self.btn_inv_out = self._toolbar_button(tools, "➖ Stock Out",
                                                lambda: self.adjust_inventory(-1))
        self.btn_inv_out.pack(side=tk.LEFT, padx=(0, 7))
        self.btn_inv_delete = self._toolbar_button(tools, "🗑️ Delete",
                                                   self.delete_selected_inventory,
                                                   danger=True)
        self.btn_inv_delete.pack(side=tk.LEFT)

        # --- Summary strip ---
        strip = tk.Frame(sec, bg=self.colors["bg_body"])
        strip.pack(fill=tk.X, pady=(0, 12))
        self.lbl_inv_stat_items, self.lbl_inv_stat_items_cap = self._stat_tile(
            strip, dict(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 7)),
            "📦", 0, "Items Tracked")
        self.lbl_inv_stat_units, self.lbl_inv_stat_units_cap = self._stat_tile(
            strip, dict(side=tk.LEFT, expand=True, fill=tk.X, padx=7),
            "🧶", 0, "Total Units")
        self.lbl_inv_stat_low, self.lbl_inv_stat_low_cap = self._stat_tile(
            strip, dict(side=tk.LEFT, expand=True, fill=tk.X, padx=7),
            "⚠️", 0, "Low Stock")
        self.lbl_inv_stat_out, self.lbl_inv_stat_out_cap = self._stat_tile(
            strip, dict(side=tk.LEFT, expand=True, fill=tk.X, padx=(7, 0)),
            "🚫", 0, "Out Of Stock")

        table_card = self._neu_card(sec, dict(fill=tk.BOTH, expand=True), padx=14, pady=12)
        self.tree_inventory = ttk.Treeview(table_card, columns=self.inv_headers,
                                           show="headings")
        for c in self.inv_headers:
            self.tree_inventory.heading(c, text=c.replace("_", " ").upper())
            self.tree_inventory.column(c, width=110)
        self.tree_inventory.pack(fill=tk.BOTH, expand=True)
        self.tree_inventory.tag_configure(
            "low", foreground=TAN if self.current_theme == "light" else GAUGE_PROGRESS)
        self.tree_inventory.tag_configure(
            "out", foreground=DANGER if self.current_theme == "light" else TERRACOTTA)

    def _inventory_level(self, record):
        """(quantity, reorder_level) as numbers, tolerating blank or junk
        cells the way the rest of the sheet handling does."""
        try:
            qty = float(clean_val(record.get("quantity")) or 0)
        except ValueError:
            qty = 0.0
        try:
            reorder = float(clean_val(record.get("reorder_level")) or 0)
        except ValueError:
            reorder = 0.0
        return qty, reorder

    def refresh_inventory_ui(self):
        if not hasattr(self, "tree_inventory") or not self.tree_inventory.winfo_exists():
            return
        self.tree_inventory.delete(*self.tree_inventory.get_children())
        items = [i for i in getattr(self, "inventory", []) if i.get("id")]
        total_units = 0.0
        low = out = 0
        for rec in items:
            qty, reorder = self._inventory_level(rec)
            total_units += qty
            if qty <= 0:
                tag, out = "out", out + 1
            elif reorder and qty <= reorder:
                tag, low = "low", low + 1
            else:
                tag = ""
            self.tree_inventory.insert(
                "", tk.END, values=[clean_val(rec.get(h, "")) for h in self.inv_headers],
                tags=(tag,) if tag else ())
        self.lbl_inv_stat_items.configure(text=str(len(items)))
        self.lbl_inv_stat_units.configure(text=("%g" % total_units))
        self.lbl_inv_stat_low.configure(text=str(low))
        self.lbl_inv_stat_out.configure(text=str(out))

    def _write_inventory(self):
        rows = [[clean_val(r.get(h, "")) for h in self.inv_headers]
                for r in self.inventory if r.get("id")]
        self.excel_mgr.write_all_records("inventory.xlsx", self.inv_headers, rows)

    def adjust_inventory(self, direction):
        """Move the selected item's quantity by a typed amount. `direction`
        is +1 for stock in and -1 for stock out."""
        rec = self._selected_record(self.tree_inventory, self.inventory)
        if not rec:
            messagebox.showwarning("No Selection", "Select an inventory item first.")
            return
        from tkinter import simpledialog
        amount = simpledialog.askfloat(
            "Stock In" if direction > 0 else "Stock Out",
            "Quantity to %s for '%s':" % ("add" if direction > 0 else "remove",
                                          clean_val(rec.get("item"))),
            parent=self, minvalue=0.0)
        if not amount:
            return
        qty, _ = self._inventory_level(rec)
        # Stock never goes negative -- a shop cannot hold -3 metres of cloth.
        rec["quantity"] = "%g" % max(0.0, qty + amount * direction)
        rec["updated"] = datetime.now().strftime("%Y-%m-%d")
        try:
            self._write_inventory()
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            return
        self.reload_all_data()
        self.refresh_inventory_ui()

    def delete_selected_inventory(self):
        if not self._require_admin():
            return
        rec = self._selected_record(self.tree_inventory, self.inventory)
        if not rec:
            messagebox.showwarning("No Selection", "Select an inventory item first.")
            return
        if not messagebox.askyesno("Delete Item",
                                   "Delete '%s' from inventory?" % clean_val(rec.get("item"))):
            return
        self.inventory = [r for r in self.inventory
                          if clean_val(r.get("id")) != clean_val(rec.get("id"))]
        try:
            self._write_inventory()
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            return
        self.reload_all_data()
        self.refresh_inventory_ui()

    def open_add_inventory_modal(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Inventory Item")
        dlg.configure(bg=self.colors["bg_card"])
        dlg.resizable(False, False)
        dlg.transient(self)

        fields = [("item", "Item name"), ("category", "Category"),
                  ("quantity", "Quantity"), ("unit", "Unit (m / pcs)"),
                  ("reorder_level", "Reorder level")]
        entries = {}
        tk.Label(dlg, text="📦 New Inventory Item", font=(FONT_FAMILY, 13, "bold"),
                 bg=self.colors["bg_card"], fg=self.colors["text_main"]).pack(
            anchor="w", padx=22, pady=(20, 14))
        for key, label in fields:
            row = tk.Frame(dlg, bg=self.colors["bg_card"])
            row.pack(fill=tk.X, padx=22, pady=4)
            tk.Label(row, text=label, width=16, anchor="w", font=(FONT_FAMILY, 9),
                     bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack(side=tk.LEFT)
            ent = tk.Entry(row, font=(FONT_FAMILY, 10), bg=self.colors["well"],
                           fg=self.colors["text_main"], relief="flat",
                           insertbackground=self.colors["text_main"],
                           highlightthickness=1,
                           highlightbackground=self.colors["border"])
            ent.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
            entries[key] = ent

        def save():
            item = entries["item"].get().strip()
            if not item:
                messagebox.showwarning("Missing Item", "Item name is required.",
                                       parent=dlg)
                return
            row = {h: "" for h in self.inv_headers}
            row["id"] = self._next_id("INV", self.inventory)
            for key, _ in fields:
                row[key] = entries[key].get().strip()
            row["updated"] = datetime.now().strftime("%Y-%m-%d")
            try:
                self.excel_mgr.append_record(
                    "inventory.xlsx", self.inv_headers,
                    [row.get(h, "") for h in self.inv_headers])
            except Exception as e:
                messagebox.showerror("Save Error", str(e), parent=dlg)
                return
            dlg.destroy()
            self.reload_all_data()
            self.refresh_inventory_ui()

        btns = tk.Frame(dlg, bg=self.colors["bg_card"])
        btns.pack(fill=tk.X, padx=22, pady=(16, 20))
        self._primary_button(btns, "Save Item", save).pack(side=tk.RIGHT)
        self.inv_modal_entries = entries
        self.inv_modal = dlg

    # ==========================================
    # FINANCE SECTION
    # ==========================================
    def build_finance_section(self):
        """Paid / remaining / debt, sourced entirely from FinanceDB (SQL) —
        see refresh_finance_ui() for how the numbers get in here. Includes
        a small tab bar (All / Done / Due / Add Payment) above the ledger."""
        sec = tk.Frame(self.main_content, bg=self.colors["bg_body"])
        self.sections["finance"] = sec
        self._attach_page_backdrop(sec)
        self.finance_tab = getattr(self, "finance_tab", "all")

        hdr = tk.Frame(sec, bg=self.colors["bg_body"])
        hdr.pack(fill=tk.X, padx=2, pady=(2, 14))
        self.lbl_fin_title = tk.Label(hdr, text="Finance", font=(FONT_FAMILY, 19), bg=self.colors["bg_body"], fg=self.colors["text_main"])
        self.lbl_fin_title.pack(anchor="w")
        self.lbl_fin_sub = tk.Label(hdr, text="Paid, remaining and debt across all orders", font=(FONT_FAMILY, 9), bg=self.colors["bg_body"], fg=self.colors["text_muted"])
        self.lbl_fin_sub.pack(anchor="w", pady=(2, 0))

        cards_row = tk.Frame(sec, bg=self.colors["bg_body"])
        cards_row.pack(fill=tk.X, pady=(0, 12))

        # Each total carries its own donut, the same share-of-grand-total ring
        # the Dashboard's finance row shows; percentages are set in
        # refresh_finance_ui() alongside the PKR figures.
        def fin_card(pack_opts, caption, color):
            card = self._neu_card(cards_row, pack_opts, padx=18, pady=15)
            box = tk.Frame(card, bg=self.colors["bg_card"])
            box.pack(side=tk.LEFT, anchor="w")
            cap = self._section_label(box, caption)
            cap.pack(anchor="w")
            val = tk.Label(box, text="PKR 0.00", font=(FONT_FAMILY, 17),
                           bg=self.colors["bg_card"], fg=self.colors["text_main"])
            val.pack(anchor="w", pady=(4, 0))
            chart = CircularDonutChart(card, size=72, ring_color=color,
                                       bg_color=self.colors["well"], stroke_width=8,
                                       theme_colors=self.colors)
            chart.pack(side=tk.RIGHT)
            pct = tk.Label(chart, text="0%", font=(FONT_FAMILY, 9),
                           bg=self.colors["bg_chart"], fg=self.colors["text_muted"])
            pct.place(relx=0.5, rely=0.5, anchor="center")
            return cap, val, chart, pct

        (self.lbl_fin_card_paid_title, self.lbl_fin_card_paid_val,
         self.chart_fin_card_paid, self.lbl_fin_card_paid_pct) = fin_card(
            dict(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 7)), "TOTAL PAID", SAGE)
        (self.lbl_fin_card_remaining_title, self.lbl_fin_card_remaining_val,
         self.chart_fin_card_remaining, self.lbl_fin_card_remaining_pct) = fin_card(
            dict(side=tk.LEFT, expand=True, fill=tk.X, padx=7), "TOTAL REMAINING", GAUGE_PROGRESS)
        (self.lbl_fin_card_debt_title, self.lbl_fin_card_debt_val,
         self.chart_fin_card_debt, self.lbl_fin_card_debt_pct) = fin_card(
            dict(side=tk.LEFT, expand=True, fill=tk.X, padx=(7, 0)), "TOTAL DEBT", TERRACOTTA)

        # --- Tab bar: All / Done / Due / Add Payment ---
        tab_bar = tk.Frame(sec, bg=self.colors["bg_card"])
        tab_bar.pack(fill=tk.X, padx=24, pady=(6, 8))
        self.fin_tab_buttons = {}
        tab_specs = [("all", "fin_tab_all", "📋"), ("done", "fin_tab_done", "✅"),
                     ("due", "fin_tab_due", "⚠️"), ("add", "fin_tab_add", "➕")]
        for key, lang_key, icon in tab_specs:
            b = tk.Button(tab_bar, text=f"{icon} {TRANSLATIONS[self.current_lang][lang_key]}",
                         font=(FONT_FAMILY, 9, "bold"), bd=0, padx=14, pady=6, cursor="hand2",
                         command=lambda k=key: self.set_finance_tab(k))
            b.pack(side=tk.LEFT, padx=(0, 6))
            self.fin_tab_buttons[key] = (b, lang_key, icon)

        # --- Ledger table (All / Done / Due) ---
        self.fin_ledger_container = tk.Frame(sec, bg=self.colors["bg_card"])

        tbl_bar = tk.Frame(self.fin_ledger_container, bg=self.colors["bg_card"])
        tbl_bar.pack(fill=tk.X, pady=(8, 8))
        self.lbl_fin_tbl_head = tk.Label(tbl_bar, text="Order Finance Ledger", font=(FONT_FAMILY, 12, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"])
        self.lbl_fin_tbl_head.pack(side=tk.LEFT)

        table_frame = tk.Frame(self.fin_ledger_container, bg=self.colors["bg_card"])
        table_frame.pack(fill=tk.BOTH, expand=True)

        self.fin_columns = ("order_id", "customer_name", "garment", "total", "paid", "remaining", "debt", "status", "delivery_status")
        self.tree_finance = ttk.Treeview(table_frame, columns=self.fin_columns, show="headings")
        for c in self.fin_columns:
            self.tree_finance.heading(c, text=c.replace("_", " ").upper())
            self.tree_finance.column(c, width=100)
        self.tree_finance.pack(fill=tk.BOTH, expand=True)

        self.tree_finance.tag_configure("has_debt", foreground=DANGER if self.current_theme == "light" else TERRACOTTA)
        self.tree_finance.tag_configure("has_remaining", foreground=TAN if self.current_theme == "light" else GAUGE_PROGRESS)

        # --- Add Payment form ---
        self.fin_add_container = tk.Frame(sec, bg=self.colors["bg_card"])
        add_card = self._glass_card(self.fin_add_container, dict(fill=tk.X), padx=20, pady=18, bg_key="bg_card")
        self.lbl_fin_add_heading = tk.Label(add_card, text="➕ Record a Payment", font=(FONT_FAMILY, 12, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"])
        self.lbl_fin_add_heading.pack(anchor="w", pady=(0, 12))

        self.lbl_fin_add_order = tk.Label(add_card, text="Order with a due balance:", font=(FONT_FAMILY, 9, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"])
        self.lbl_fin_add_order.pack(anchor="w")
        self.cbo_fin_pay_order = ttk.Combobox(add_card, state="readonly", font=(FONT_FAMILY, 10))
        self.cbo_fin_pay_order.pack(fill=tk.X, pady=(4, 12))

        self.lbl_fin_add_amount = tk.Label(add_card, text="Payment Amount (PKR):", font=(FONT_FAMILY, 9, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"])
        self.lbl_fin_add_amount.pack(anchor="w")
        self.ent_fin_pay_amount = tk.Entry(add_card, font=(FONT_FAMILY, 11),
                                           bg=self.colors["bg_body"], fg=self.colors["text_main"],
                                           insertbackground=self.colors["text_main"], relief="flat",
                                           highlightthickness=1, highlightbackground=self.colors["border"])
        self.ent_fin_pay_amount.pack(fill=tk.X, pady=(4, 14))

        self.btn_fin_pay_submit = tk.Button(add_card, text="💾 Record Payment", bg=SUCCESS, fg="white",
                                            font=(FONT_FAMILY, 10, "bold"), bd=0, pady=8, cursor="hand2",
                                            command=self.record_finance_payment)
        self.btn_fin_pay_submit.pack(fill=tk.X)

        self.set_finance_tab(self.finance_tab)

    def set_finance_tab(self, tab_key):
        """Switches the Finance view between the All/Done/Due ledger and the
        Add Payment form, restyling the tab buttons to show which is active."""
        self.finance_tab = tab_key
        for key, (b, lang_key, icon) in self.fin_tab_buttons.items():
            active = key == tab_key
            b.configure(bg=PRIMARY if active else self.colors["bg_chart"],
                       fg="white" if active else self.colors["text_main"])
        if tab_key == "add":
            self.fin_ledger_container.pack_forget()
            self._refresh_finance_payment_picker()
            self.fin_add_container.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 20))
        else:
            self.fin_add_container.pack_forget()
            self.fin_ledger_container.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 20))
            self.refresh_finance_ui()

    def _refresh_finance_payment_picker(self):
        """Fills the Add Payment order picker with only orders that still
        carry a due balance (remaining or debt > 0)."""
        if not (hasattr(self, "cbo_fin_pay_order") and self.cbo_fin_pay_order.winfo_exists()):
            return
        try:
            due_rows = [r for r in self._finance_db_for_current_data().get_rows()
                       if (r.get("remaining") or 0) > 0 or (r.get("debt") or 0) > 0]
        except Exception:
            due_rows = []
        options = [f"{r['order_id']} - {r['customer_name']} (Due PKR {(r.get('remaining') or 0) + (r.get('debt') or 0):,.2f})"
                  for r in due_rows]
        self.cbo_fin_pay_order.configure(values=options)
        if options:
            self.cbo_fin_pay_order.current(0)
        else:
            self.cbo_fin_pay_order.set("")

    def record_finance_payment(self):
        """Applies a manual payment to the selected order's `advance` field
        (capped at the order's total), writes it back to orders.xlsx with
        the same schema-aware rewrite pattern used elsewhere, then reloads
        so the Finance/Dashboard figures and the order card reflect it."""
        selection = self.cbo_fin_pay_order.get().strip()
        if not selection:
            messagebox.showwarning("No Order Selected", "Pick an order with a due balance first.")
            return
        order_id = selection.split(" - ", 1)[0].strip()
        try:
            amount = float(self.ent_fin_pay_amount.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Amount", "Enter a valid numeric payment amount.")
            return
        if amount <= 0:
            messagebox.showerror("Invalid Amount", "Payment amount must be greater than zero.")
            return

        order = next((o for o in self.orders if clean_val(o.get("id")) == order_id), None)
        if not order:
            messagebox.showerror("Not Found", f"Order {order_id} could not be found.")
            return

        total = card_svc.clean_num(order.get("total"))
        old_advance = card_svc.clean_num(order.get("advance"))
        new_advance = min(total, round(old_advance + amount, 2))
        new_remaining = card_svc.compute_remaining(total, new_advance)

        rows_to_write = []
        for o in self.orders:
            curr_id = clean_val(o.get("id"))
            r = [clean_val(o.get(h)) for h in self.ord_headers]
            if curr_id == order_id:
                r[self.ord_headers.index("advance")] = f"{new_advance:.2f}"
                r[self.ord_headers.index("remaining")] = f"{new_remaining:.2f}"
            rows_to_write.append(r)
        try:
            self.excel_mgr.write_all_records("orders.xlsx", self.ord_headers, rows_to_write)
        except Exception as e:
            messagebox.showerror("Save Error", str(e))
            return

        self.reload_all_data()
        self.update_graphics_and_stats()
        self.ent_fin_pay_amount.delete(0, tk.END)
        self._refresh_finance_payment_picker()
        messagebox.showinfo("Payment Recorded", f"Recorded PKR {amount:,.2f} against {order_id}.")

    def refresh_finance_ui(self):
        """Pulls paid/remaining/debt back out via SQL (FinanceDB) and paints
        both the Dashboard's finance snapshot row and the Finance section's
        summary cards + per-order table (filtered by the active Done/Due/All
        tab). Safe to call before the Finance section exists (auto_refresh_
        loop can fire before build_ui_layout)."""
        try:
            fdb = self._finance_db_for_current_data()
            totals = fdb.get_totals()
        except Exception as e:
            print(f"[FinanceDB] refresh failed: {e}")
            return

        def fmt(v):
            return f"PKR {v:,.2f}"

        # Each donut shows that bucket's share of the shop's total order
        # value (paid + remaining + debt) — same "percent of the whole"
        # reading as the WORK DONE / IN PROGRESS / REMAINING donuts above.
        grand_total = totals["paid"] + totals["remaining"] + totals["debt"]
        paid_pct = int(round((totals["paid"] / grand_total) * 100)) if grand_total > 0 else 0
        remaining_pct = int(round((totals["remaining"] / grand_total) * 100)) if grand_total > 0 else 0
        debt_pct = int(round((totals["debt"] / grand_total) * 100)) if grand_total > 0 else 0

        if hasattr(self, "lbl_fin_paid_val") and self.lbl_fin_paid_val.winfo_exists():
            self.lbl_fin_paid_val.configure(text=fmt(totals["paid"]))
            self.lbl_fin_remaining_val.configure(text=fmt(totals["remaining"]))
            self.lbl_fin_debt_val.configure(text=fmt(totals["debt"]))
            self.chart_fin_paid.set_percentage(paid_pct)
            self.chart_fin_remaining.set_percentage(remaining_pct)
            self.chart_fin_debt.set_percentage(debt_pct)

        if not (hasattr(self, "tree_finance") and self.tree_finance.winfo_exists()):
            return

        self.lbl_fin_card_paid_val.configure(text=fmt(totals["paid"]))
        self.lbl_fin_card_remaining_val.configure(text=fmt(totals["remaining"]))
        self.lbl_fin_card_debt_val.configure(text=fmt(totals["debt"]))
        # Same share-of-grand-total rings as the Dashboard row, with the
        # percentage printed inside each one.
        for chart, label, pct in (
            (self.chart_fin_card_paid, self.lbl_fin_card_paid_pct, paid_pct),
            (self.chart_fin_card_remaining, self.lbl_fin_card_remaining_pct, remaining_pct),
            (self.chart_fin_card_debt, self.lbl_fin_card_debt_pct, debt_pct),
        ):
            chart.set_percentage(pct)
            label.configure(text=str(pct) + "%")

        rows = fdb.get_rows()
        tab = getattr(self, "finance_tab", "all")
        if tab == "done":
            rows = [r for r in rows if (r.get("remaining") or 0) <= 0 and (r.get("debt") or 0) <= 0 and (r.get("total") or 0) > 0]
        elif tab == "due":
            rows = [r for r in rows if (r.get("remaining") or 0) > 0 or (r.get("debt") or 0) > 0]

        self.tree_finance.delete(*self.tree_finance.get_children())
        for row in rows:
            debt = row.get("debt") or 0
            remaining = row.get("remaining") or 0
            tag = "has_debt" if debt > 0 else "has_remaining" if remaining > 0 else ""
            values = [
                row.get("order_id", ""), row.get("customer_name", ""), row.get("garment", ""),
                f"{row.get('total', 0):.2f}", f"{row.get('paid', 0):.2f}",
                f"{remaining:.2f}", f"{debt:.2f}",
                row.get("status", ""), row.get("delivery_status", ""),
            ]
            self.tree_finance.insert("", tk.END, values=values, tags=(tag,) if tag else ())

    # ==========================================
    # ADMIN / SETTINGS SECTION
    # ==========================================
    def build_admin_section(self):
        sec = tk.Frame(self.main_content, bg=self.colors["bg_card"], highlightbackground=self.colors["border"], highlightthickness=1)
        self.sections["admin"] = sec
        hdr = tk.Frame(sec, bg=self.colors["bg_card"])
        hdr.pack(fill=tk.X, padx=24, pady=(20, 4))
        self.lbl_admin_title = tk.Label(hdr, text="Settings", font=(FONT_FAMILY, 16, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"])
        self.lbl_admin_title.pack(anchor="w")
        self.lbl_admin_sub = tk.Label(hdr, text="Theme, language, garments & employee roles", font=(FONT_FAMILY, 9), bg=self.colors["bg_card"], fg=self.colors["text_muted"])
        self.lbl_admin_sub.pack(anchor="w")

        cards_frame = tk.Frame(sec, bg=self.colors["bg_card"])
        cards_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=10)

        # Row 1: Theme + Language
        row1 = tk.Frame(cards_frame, bg=self.colors["bg_card"])
        row1.pack(fill=tk.X, pady=(0, 10))

        c_theme = self._glass_card(row1, dict(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6)))
        self.lbl_theme_label = tk.Label(c_theme, text="🛠️ System Theme", font=(FONT_FAMILY, 10, "bold"), bg=self.colors["bg_chart"], fg=self.colors["text_main"])
        self.lbl_theme_label.pack(anchor="w", pady=(0, 8))
        self.cbo_theme = ttk.Combobox(c_theme, values=["Light Mode ☀️", "Dark Mode 🌙"], state="readonly")
        self.cbo_theme.current(0 if self.current_theme == "light" else 1)
        self.cbo_theme.pack(fill=tk.X, pady=(2, 4))
        self.cbo_theme.bind("<<ComboboxSelected>>", self.change_theme)

        c_display = self._glass_card(row1, dict(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6))
        self.lbl_display_label = tk.Label(c_display, text="🖥️ Display Mode", font=(FONT_FAMILY, 10, "bold"), bg=self.colors["bg_chart"], fg=self.colors["text_main"])
        self.lbl_display_label.pack(anchor="w", pady=(0, 8))
        self.cbo_display = ttk.Combobox(c_display, state="readonly",
                                        values=[self._display_mode_label("fullscreen"),
                                                self._display_mode_label("windowed")])
        self.cbo_display.set(self._display_mode_label(getattr(self, "display_mode", "fullscreen")))
        self.cbo_display.pack(fill=tk.X, pady=(2, 4))
        self.cbo_display.bind("<<ComboboxSelected>>", self.on_display_mode_change)
        self.lbl_display_hint = tk.Label(c_display, text="F11 toggles · Esc exits full screen",
                                         font=(FONT_FAMILY, 8), bg=self.colors["bg_chart"],
                                         fg=self.colors["text_3"])
        self.lbl_display_hint.pack(anchor="w")

        c_lang = self._glass_card(row1, dict(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0)))
        self.lbl_language_label = tk.Label(c_lang, text="🌐 Language / زبان", font=(FONT_FAMILY, 10, "bold"), bg=self.colors["bg_chart"], fg=self.colors["text_main"])
        self.lbl_language_label.pack(anchor="w", pady=(0, 8))
        self.cbo_lang = ttk.Combobox(c_lang, values=[label for _, label in LANGUAGE_OPTIONS], state="readonly")
        if self.current_lang in [code for code, _ in LANGUAGE_OPTIONS]:
            self.cbo_lang.current([code for code, _ in LANGUAGE_OPTIONS].index(self.current_lang))
        else:
            self.cbo_lang.current(0)
        self.cbo_lang.pack(fill=tk.X, pady=(2, 4))
        self.cbo_lang.bind("<<ComboboxSelected>>", self.on_language_change)

        # Row 2: Garment types + Employee roles
        row2 = tk.Frame(cards_frame, bg=self.colors["bg_card"])
        row2.pack(fill=tk.BOTH, expand=True)

        c_garments = self._glass_card(row2, dict(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6)))
        self.lbl_admin_card_garments = tk.Label(c_garments, text=TRANSLATIONS[self.current_lang].get("admin_card_garments", "🧵 Garment Types"), font=(FONT_FAMILY, 10, "bold"), bg=self.colors["bg_chart"], fg=self.colors["text_main"])
        self.lbl_admin_card_garments.pack(anchor="w", pady=(0, 8))

        list_wrap_g = tk.Frame(c_garments, bg=self.colors["bg_chart"])
        list_wrap_g.pack(fill=tk.BOTH, expand=True)
        self.lst_garments = tk.Listbox(list_wrap_g, bg=self.colors["bg_card"], fg=self.colors["text_main"], selectbackground=PRIMARY, selectforeground="white", highlightthickness=1, highlightbackground=self.colors["border"], font=(FONT_FAMILY, 9))
        sb_g = ttk.Scrollbar(list_wrap_g, orient=tk.VERTICAL, command=self.lst_garments.yview)
        self.lst_garments.configure(yscrollcommand=sb_g.set)
        self.lst_garments.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_g.pack(side=tk.RIGHT, fill=tk.Y)

        ent_row_g = tk.Frame(c_garments, bg=self.colors["bg_chart"])
        ent_row_g.pack(fill=tk.X, pady=(8, 0))
        self.ent_new_garment = tk.Entry(ent_row_g, font=(FONT_FAMILY, 9),
                                        bg=self.colors["bg_body"], fg=self.colors["text_main"],
                                        insertbackground=self.colors["text_main"], relief="flat",
                                        highlightthickness=1, highlightbackground=self.colors["border"])
        self.ent_new_garment.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.btn_add_garment = tk.Button(ent_row_g, text=TRANSLATIONS[self.current_lang].get("btn_item_add", "➕ Add"), bg=PRIMARY, fg="white", font=(FONT_FAMILY, 8, "bold"), bd=0, padx=10, pady=4, cursor="hand2", command=self.add_garment_type)
        self.btn_add_garment.pack(side=tk.LEFT, padx=(0, 4))
        self.btn_remove_garment = tk.Button(ent_row_g, text=TRANSLATIONS[self.current_lang].get("btn_item_remove", "✖ Remove"), bg=DANGER, fg="white", font=(FONT_FAMILY, 8, "bold"), bd=0, padx=10, pady=4, cursor="hand2", command=self.remove_garment_type)
        self.btn_remove_garment.pack(side=tk.LEFT)

        c_roles = self._glass_card(row2, dict(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(6, 0)))
        self.lbl_admin_card_roles = tk.Label(c_roles, text=TRANSLATIONS[self.current_lang].get("admin_card_roles", "👔 Employee Roles"), font=(FONT_FAMILY, 10, "bold"), bg=self.colors["bg_chart"], fg=self.colors["text_main"])
        self.lbl_admin_card_roles.pack(anchor="w", pady=(0, 8))

        list_wrap_r = tk.Frame(c_roles, bg=self.colors["bg_chart"])
        list_wrap_r.pack(fill=tk.BOTH, expand=True)
        self.lst_roles = tk.Listbox(list_wrap_r, bg=self.colors["bg_card"], fg=self.colors["text_main"], selectbackground=PRIMARY, selectforeground="white", highlightthickness=1, highlightbackground=self.colors["border"], font=(FONT_FAMILY, 9))
        sb_r = ttk.Scrollbar(list_wrap_r, orient=tk.VERTICAL, command=self.lst_roles.yview)
        self.lst_roles.configure(yscrollcommand=sb_r.set)
        self.lst_roles.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb_r.pack(side=tk.RIGHT, fill=tk.Y)

        ent_row_r = tk.Frame(c_roles, bg=self.colors["bg_chart"])
        ent_row_r.pack(fill=tk.X, pady=(8, 0))
        self.ent_new_role = tk.Entry(ent_row_r, font=(FONT_FAMILY, 9),
                                     bg=self.colors["bg_body"], fg=self.colors["text_main"],
                                     insertbackground=self.colors["text_main"], relief="flat",
                                     highlightthickness=1, highlightbackground=self.colors["border"])
        self.ent_new_role.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        self.btn_add_role = tk.Button(ent_row_r, text=TRANSLATIONS[self.current_lang].get("btn_item_add", "➕ Add"), bg=PRIMARY, fg="white", font=(FONT_FAMILY, 8, "bold"), bd=0, padx=10, pady=4, cursor="hand2", command=self.add_employee_role)
        self.btn_add_role.pack(side=tk.LEFT, padx=(0, 4))
        self.btn_remove_role = tk.Button(ent_row_r, text=TRANSLATIONS[self.current_lang].get("btn_item_remove", "✖ Remove"), bg=DANGER, fg="white", font=(FONT_FAMILY, 8, "bold"), bd=0, padx=10, pady=4, cursor="hand2", command=self.remove_employee_role)
        self.btn_remove_role.pack(side=tk.LEFT)

        self.refresh_settings_ui()

    def refresh_settings_ui(self):
        self.lst_garments.delete(0, tk.END)
        for g in self.garment_types:
            self.lst_garments.insert(tk.END, g)
        self.lst_roles.delete(0, tk.END)
        for r in self.employee_roles:
            self.lst_roles.insert(tk.END, r)

    # --- Garment type management ---
    def add_garment_type(self):
        val = self.ent_new_garment.get().strip()
        if not val:
            return
        if val in self.garment_types:
            messagebox.showinfo("Already Exists", "This garment type is already in the list.")
            return
        self.garment_types.append(val)
        try:
            self.excel_mgr.save_settings_list("garment_type", self.garment_types)
            self.ent_new_garment.delete(0, tk.END)
            self.reload_all_data()
            self.refresh_settings_ui()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def remove_garment_type(self):
        sel = self.lst_garments.curselection()
        if not sel:
            return
        val = self.lst_garments.get(sel[0])
        self.garment_types.remove(val)
        try:
            self.excel_mgr.save_settings_list("garment_type", self.garment_types)
            self.reload_all_data()
            self.refresh_settings_ui()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # --- Employee role management ---
    def add_employee_role(self):
        val = self.ent_new_role.get().strip()
        if not val:
            return
        if val in self.employee_roles:
            messagebox.showinfo("Already Exists", "This role is already in the list.")
            return
        self.employee_roles.append(val)
        try:
            self.excel_mgr.save_settings_list("employee_role", self.employee_roles)
            self.ent_new_role.delete(0, tk.END)
            self.reload_all_data()
            self.refresh_settings_ui()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def remove_employee_role(self):
        sel = self.lst_roles.curselection()
        if not sel:
            return
        val = self.lst_roles.get(sel[0])
        self.employee_roles.remove(val)
        try:
            self.excel_mgr.save_settings_list("employee_role", self.employee_roles)
            self.reload_all_data()
            self.refresh_settings_ui()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ==========================================
    # MODALS MATCHING PHYSICAL RECEIPT FORM
    # ==========================================
    def open_add_customer_modal(self):
        # Merge with English so a partial language pack never KeyErrors —
        # same pattern as apply_language_pack(). Built once per open, since
        # this dialog (unlike the persistent Order Card screen) is created
        # fresh every time and doesn't need to react to a later language
        # switch while it's open.
        t = {**TRANSLATIONS["en"], **TRANSLATIONS.get(self.current_lang, {})}

        dlg = tk.Toplevel(self)
        dlg.title(t["nc_title"])
        dlg.geometry("500x590")
        dlg.configure(bg=self.colors["bg_card"])
        dlg.grab_set()

        tk.Label(dlg, text=t["nc_heading"], font=(FONT_FAMILY, 12, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"]).pack(pady=12)

        info_frame = tk.Frame(dlg, bg=self.colors["bg_card"])
        info_frame.pack(fill=tk.X, padx=20)
        tk.Label(info_frame, text=t["nc_name"], font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_muted"]).grid(row=0, column=0, sticky="w")
        e_name = tk.Entry(info_frame, bg=self.colors["bg_body"], fg=self.colors["text_main"],
                          insertbackground=self.colors["text_main"], relief="flat",
                          highlightthickness=1, highlightbackground=self.colors["border"])
        e_name.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        tk.Label(info_frame, text=t["nc_phone"], font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_muted"]).grid(row=1, column=0, sticky="w")
        e_phone = tk.Entry(info_frame, bg=self.colors["bg_body"], fg=self.colors["text_main"],
                           insertbackground=self.colors["text_main"], relief="flat",
                           highlightthickness=1, highlightbackground=self.colors["border"])
        e_phone.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        tk.Label(info_frame, text=t["nc_address"], font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_muted"]).grid(row=2, column=0, sticky="w")
        e_address = tk.Entry(info_frame, bg=self.colors["bg_body"], fg=self.colors["text_main"],
                             insertbackground=self.colors["text_main"], relief="flat",
                             highlightthickness=1, highlightbackground=self.colors["border"])
        e_address.grid(row=2, column=1, padx=5, pady=5, sticky="ew")
        info_frame.columnconfigure(1, weight=1)

        measure_frame = tk.LabelFrame(dlg, text=t["nc_measurements_frame"], bg=self.colors["bg_card"], fg=PRIMARY, font=(FONT_FAMILY, 9, "bold"))
        measure_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # (translation key, customers.xlsx column) — order matches the
        # physical paper slip's layout, unchanged from before.
        fields = [
            ("meas_lambai", "length"), ("meas_sleeve", "sleeve"), ("meas_shoulder", "shoulder"),
            ("meas_collar", "collar"), ("meas_chest", "chest"), ("meas_waist", "waist"),
            ("meas_daman", "daman"), ("meas_shalwar_length", "shalwar_len"), ("meas_paancha", "paancha"),
        ]
        entries = {}
        for idx, (lbl_key, key) in enumerate(fields):
            r = idx // 2
            c = (idx % 2) * 2
            tk.Label(measure_frame, text=t[lbl_key], bg=self.colors["bg_card"], fg=self.colors["text_main"], font=(FONT_FAMILY, 8)).grid(row=r, column=c, padx=5, pady=5, sticky="e")
            ent = tk.Entry(measure_frame, width=10, bg=self.colors["bg_body"], fg=self.colors["text_main"],
                           insertbackground=self.colors["text_main"], relief="flat",
                           highlightthickness=1, highlightbackground=self.colors["border"])
            ent.grid(row=r, column=c + 1, padx=5, pady=5, sticky="w")
            entries[key] = ent

        def save():
            if not e_name.get():
                messagebox.showerror("Error", "Name required!")
                return
            c_id = self._next_id("C", self.customers, 101)
            created_date = datetime.now().strftime("%Y-%m-%d")
            row = ([c_id, e_name.get(), e_phone.get()]
                   + [entries[k].get() or "0" for k in [f[1] for f in fields]]
                   + [e_address.get().strip(), created_date])
            try:
                self.excel_mgr.append_record("customers.xlsx", self.cust_headers, row)
            except Exception as e:
                messagebox.showerror("Save Error", str(e))
                return
            self.reload_all_data()
            self.update_graphics_and_stats()
            dlg.destroy()

        tk.Button(dlg, text=t["nc_save"], bg=PRIMARY, fg="white", font=(FONT_FAMILY, 10, "bold"), bd=0, pady=8, command=save).pack(fill=tk.X, padx=20, pady=10)

    def open_add_order_modal(self):
        dlg = tk.Toplevel(self)
        dlg.title("Create Style Order")
        dlg.geometry("520x660")
        dlg.configure(bg=self.colors["bg_card"])
        dlg.grab_set()

        tk.Label(dlg, text="Garment Style Configuration", font=(FONT_FAMILY, 12, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"]).pack(pady=10)

        f1 = tk.Frame(dlg, bg=self.colors["bg_card"])
        f1.pack(fill=tk.X, padx=20)
        cbo_cust = ttk.Combobox(f1, values=[f"{c['id']} - {c['name']}" for c in self.customers if c.get("name")], state="readonly")
        if cbo_cust["values"]:
            cbo_cust.current(0)
        tk.Label(f1, text="Customer:", bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack(anchor="w"); cbo_cust.pack(fill=tk.X, pady=(0, 5))

        cbo_garment = ttk.Combobox(f1, values=self.garment_types, state="readonly")
        if cbo_garment["values"]:
            cbo_garment.current(0)
        tk.Label(f1, text="Garment:", bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack(anchor="w"); cbo_garment.pack(fill=tk.X, pady=(0, 5))

        cbo_tailor = ttk.Combobox(f1, values=[e["name"] for e in self.employees if e.get("name")], state="readonly")
        if cbo_tailor["values"]:
            cbo_tailor.current(0)
        tk.Label(f1, text="Assign Tailor:", bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack(anchor="w"); cbo_tailor.pack(fill=tk.X, pady=(0, 5))

        style_frame = tk.LabelFrame(dlg, text=" Visual Form Styles (as per JTQ slip) ", bg=self.colors["bg_card"], fg=PRIMARY, font=(FONT_FAMILY, 9, "bold"))
        style_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Exact groups from the physical JTQ slip
        style_options = {
            "Button Style": ["Baz Button (باز بٹن)", "Karh Button (کڑ بٹن)"],
            "Collar Type": ["Half Ban", "Cut Ban", "Normal Ban", "Collar (کالر)"],
            "Cuff Type": ["Round Cuff (گول کف)", "Square Cuff (چورس کف)", "Round Sleeve Cut (گول بازو)", "Round Sleeve"],
            "Pocket Type": ["Side Pocket (سائن با کٹ)", "Round Pocket (گول جیب)", "Shalwar Pocket (شلوار جیب)", "Simple Patti (سادہ پٹی)", "Patti (پٹی)"],
            "Daman Type": ["Square Daman (چورس واشن)", "Round Daman (گول واشن)"],
            "Stitching": ["1. Single Stitch", "2. Double Stitch", "3. Choka Stitch", "4. Triple Stitch"]
        }

        combos = {}
        rows = list(style_options.items())

        # Left column: button/placket styles (باز بٹن / کڑ بٹن)
        label, opts = rows[0]
        tk.Label(style_frame, text=label + ":", bg=self.colors["bg_card"], fg=self.colors["text_main"], font=(FONT_FAMILY, 8, "bold")).grid(row=0, column=0, padx=8, pady=8, sticky="e")
        cb = ttk.Combobox(style_frame, values=opts, state="readonly", width=26)
        cb.current(0)
        cb.grid(row=0, column=1, padx=8, pady=8, sticky="w")
        combos[label] = cb

        # Center column: Collar, Cuff, Pocket, Daman
        for r, (label, opts) in enumerate(rows[1:5], start=0):
            tk.Label(style_frame, text=label + ":", bg=self.colors["bg_card"], fg=self.colors["text_main"], font=(FONT_FAMILY, 8, "bold")).grid(row=r, column=2, padx=8, pady=8, sticky="e")
            cb = ttk.Combobox(style_frame, values=opts, state="readonly", width=26)
            cb.current(0)
            cb.grid(row=r, column=3, padx=8, pady=8, sticky="w")
            combos[label] = cb

        # Bottom of the center column: Stitching (the 4 numbered options on the slip)
        label, opts = rows[5]
        tk.Label(style_frame, text=label + ":", bg=self.colors["bg_card"], fg=self.colors["text_main"], font=(FONT_FAMILY, 8, "bold")).grid(row=5, column=2, padx=8, pady=8, sticky="e")
        cb = ttk.Combobox(style_frame, values=opts, state="readonly", width=26)
        cb.current(0)
        cb.grid(row=5, column=3, padx=8, pady=8, sticky="w")
        combos[label] = cb

        style_frame.columnconfigure(1, weight=1)
        style_frame.columnconfigure(3, weight=1)

        def save():
            if not cbo_cust.get() or not cbo_tailor.get():
                messagebox.showerror("Error", "Customer & Tailor needed!")
                return
            c_id = cbo_cust.get().split(" - ")[0]
            c_name = cbo_cust.get().split(" - ")[-1]
            o_id = self._next_id("ORD", self.orders, 101)

            row = [
                o_id, c_id, cbo_garment.get() or "Shalwar Kameez", "In Progress", cbo_tailor.get(),
                combos["Collar Type"].get(), combos["Cuff Type"].get(),
                combos["Pocket Type"].get(), combos["Daman Type"].get(), combos["Stitching"].get(),
                combos["Button Style"].get()
            ]
            try:
                self.excel_mgr.append_record("orders.xlsx", self.ord_headers, row)
            except Exception as e:
                messagebox.showerror("Save Error", str(e))
                return
            self.reload_all_data()
            self.update_graphics_and_stats()
            dlg.destroy()

        tk.Button(dlg, text="✅ Place Order", bg=SUCCESS, fg="white", font=(FONT_FAMILY, 10, "bold"), bd=0, pady=8, command=save).pack(fill=tk.X, padx=20, pady=10)

    def open_add_employee_modal(self):
        t = {**TRANSLATIONS["en"], **TRANSLATIONS.get(self.current_lang, {})}

        dlg = tk.Toplevel(self)
        dlg.title(t["emp_modal_title"])
        dlg.geometry("400x260")
        dlg.configure(bg=self.colors["bg_card"])
        dlg.grab_set()

        tk.Label(dlg, text=t["emp_modal_heading"], font=(FONT_FAMILY, 12, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"]).pack(pady=(14, 10))

        f = tk.Frame(dlg, bg=self.colors["bg_card"])
        f.pack(fill=tk.X, padx=24)
        tk.Label(f, text=t["emp_lbl_full_name"], font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_muted"]).grid(row=0, column=0, sticky="w", pady=4)
        e_name = tk.Entry(f, bg=self.colors["bg_body"], fg=self.colors["text_main"],
                          insertbackground=self.colors["text_main"], relief="flat",
                          highlightthickness=1, highlightbackground=self.colors["border"])
        e_name.grid(row=0, column=1, padx=8, pady=4, sticky="ew")
        tk.Label(f, text=t["emp_lbl_phone"], font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_muted"]).grid(row=1, column=0, sticky="w", pady=4)
        e_phone = tk.Entry(f, bg=self.colors["bg_body"], fg=self.colors["text_main"],
                           insertbackground=self.colors["text_main"], relief="flat",
                           highlightthickness=1, highlightbackground=self.colors["border"])
        e_phone.grid(row=1, column=1, padx=8, pady=4, sticky="ew")
        tk.Label(f, text=t["emp_lbl_role"], font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_muted"]).grid(row=2, column=0, sticky="w", pady=4)
        cbo_role = ttk.Combobox(f, values=self.employee_roles, state="readonly")
        if cbo_role["values"]:
            cbo_role.current(0)
        cbo_role.grid(row=2, column=1, padx=8, pady=4, sticky="ew")
        f.columnconfigure(1, weight=1)

        def save():
            if not e_name.get():
                messagebox.showerror("Error", "Name required!")
                return
            e_id = self._next_id("E", self.employees, 1)
            row = [e_id, e_name.get(), e_phone.get(), cbo_role.get() or "Tailor", "On Duty", "None"]
            try:
                self.excel_mgr.append_record("employees.xlsx", self.emp_headers, row)
            except Exception as e:
                messagebox.showerror("Save Error", str(e))
                return
            self.reload_all_data()
            self.update_graphics_and_stats()
            dlg.destroy()

        tk.Button(dlg, text=t["emp_btn_save_staff"], bg=PRIMARY, fg="white", font=(FONT_FAMILY, 10, "bold"), bd=0, pady=8, command=save).pack(fill=tk.X, padx=24, pady=(14, 10))

    def open_assign_task_modal(self):
        """Assign an existing order (picked by customer name) to a staff
        member. Selecting an order shows its details read-only, mirroring
        the order card's customer auto-fill. Confirming links both ways —
        the order's Tailor field AND the employee's Current Task — so the
        Dashboard's Active Orders Ledger (which reads Tailor live) and the
        Employee table both reflect the assignment immediately."""
        t = {**TRANSLATIONS["en"], **TRANSLATIONS.get(self.current_lang, {})}

        dlg = tk.Toplevel(self)
        dlg.title(t["task_modal_title"])
        dlg.geometry("440x480")
        dlg.configure(bg=self.colors["bg_card"])
        dlg.grab_set()

        tk.Label(dlg, text=t["task_modal_heading"], font=(FONT_FAMILY, 12, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"]).pack(pady=(14, 10))

        f = tk.Frame(dlg, bg=self.colors["bg_card"])
        f.pack(fill=tk.BOTH, expand=True, padx=24)

        tk.Label(f, text=t["task_lbl_staff_member"], font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack(anchor="w", pady=(0, 2))
        cbo_emp = ttk.Combobox(f, values=[f"{e['id']} - {e['name']}" for e in self.employees if e.get("name")], state="readonly")
        if cbo_emp["values"]:
            cbo_emp.current(0)
        cbo_emp.pack(fill=tk.X, pady=(0, 8))
        if not cbo_emp["values"]:
            tk.Label(f, text=t["task_lbl_no_staff"], bg=self.colors["bg_card"], fg=DANGER, font=(FONT_FAMILY, 8)).pack(anchor="w")

        # --- Order picker: open orders (not yet Delivered), labeled by
        # customer name — not a raw order id, so a tailor can find "who".
        cust_by_id = {clean_val(c.get("id")): clean_val(c.get("name")) for c in self.customers}
        open_orders = {clean_val(o.get("id")): o for o in self.orders
                       if clean_val(o.get("id")) and clean_val(o.get("status")) != "Delivered"}
        order_labels = {}
        for oid, o in open_orders.items():
            cust_name = cust_by_id.get(clean_val(o.get("customer_id"))) or "Walk-in"
            order_labels[f"{oid} — {cust_name} ({clean_val(o.get('garment'))})"] = oid

        tk.Label(f, text=t["task_lbl_order"], font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack(anchor="w", pady=(6, 2))
        cbo_order = ttk.Combobox(f, values=list(order_labels.keys()), state="readonly")
        cbo_order.pack(fill=tk.X, pady=(0, 8))
        if not order_labels:
            tk.Label(f, text=t["task_lbl_no_orders"], bg=self.colors["bg_card"], fg=DANGER, font=(FONT_FAMILY, 8)).pack(anchor="w")

        # Read-only order-details block, filled in once an order is picked.
        details = self._glass_card(f, dict(fill=tk.X, pady=(0, 8)), padx=10, pady=8)
        detail_specs = [
            ("garment", "task_details_garment"), ("status", "task_details_status"),
            ("order_date", "task_details_order_date"), ("delivery_date", "task_details_delivery_date"),
            ("tailor", "task_details_tailor"),
            ("total", "task_details_total"), ("advance", "task_details_advance"), ("remaining", "task_details_remaining"),
        ]
        detail_vals = {}
        for field, label_key in detail_specs:
            row = tk.Frame(details, bg=self.colors["bg_chart"])
            row.pack(fill=tk.X)
            tk.Label(row, text=t[label_key] + ":", width=16, anchor="w", font=(FONT_FAMILY, 8),
                    bg=self.colors["bg_chart"], fg=self.colors["text_muted"]).pack(side=tk.LEFT)
            val_lbl = tk.Label(row, text="—", anchor="w", font=(FONT_FAMILY, 8, "bold"),
                               bg=self.colors["bg_chart"], fg=self.colors["text_main"])
            val_lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
            detail_vals[field] = val_lbl

        tk.Label(f, text=t["task_lbl_task_note"], font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_muted"]).pack(anchor="w", pady=(4, 2))
        e_task = tk.Entry(f, bg=self.colors["bg_body"], fg=self.colors["text_main"],
                          insertbackground=self.colors["text_main"], relief="flat",
                          highlightthickness=1, highlightbackground=self.colors["border"])
        e_task.pack(fill=tk.X, pady=(0, 10))

        def on_order_selected(event=None):
            oid = order_labels.get(cbo_order.get())
            order = open_orders.get(oid)
            if not order:
                return
            for field, lbl in detail_vals.items():
                lbl.configure(text=clean_val(order.get(field)) or "—")
            cust_name = cust_by_id.get(clean_val(order.get("customer_id"))) or "Walk-in"
            e_task.delete(0, tk.END)
            e_task.insert(0, f"{clean_val(order.get('garment'))} for {cust_name} ({oid})")

        cbo_order.bind("<<ComboboxSelected>>", on_order_selected)

        def save():
            if not cbo_emp.get() or not cbo_order.get():
                messagebox.showerror("Error", "Select a staff member and an order!")
                return
            emp_id = cbo_emp.get().split(" - ")[0]
            emp_name = next((e.get("name") for e in self.employees if clean_val(e.get("id")) == emp_id), "")
            oid = order_labels[cbo_order.get()]
            task_text = e_task.get().strip() or cbo_order.get()

            self._assign_order_tailor(oid, emp_name)
            self.update_employee_task(emp_id, task_text)
            self.reload_all_data()
            self.update_graphics_and_stats()
            dlg.destroy()

        tk.Button(dlg, text=t["task_btn_assign"], bg=WARNING, fg="white", font=(FONT_FAMILY, 10, "bold"), bd=0, pady=8, command=save).pack(fill=tk.X, padx=24, pady=(0, 14))

    def update_employee_task(self, emp_id, task_text):
        rows_to_write = []
        for e in self.employees:
            curr_id = clean_val(e.get("id"))
            is_target = curr_id == emp_id
            status = "On Task" if is_target else clean_val(e.get("status"))
            current_task = task_text if is_target else clean_val(e.get("current_task"))
            rows_to_write.append([curr_id, clean_val(e.get("name")), clean_val(e.get("phone")),
                                  clean_val(e.get("role")), status, current_task])
        try:
            self.excel_mgr.write_all_records("employees.xlsx", self.emp_headers, rows_to_write)
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def _assign_order_tailor(self, order_id, tailor_name):
        """Sets one order's Tailor field. Schema-aware rewrite (same pattern
        as quick_change_order_status) preserves every column, legacy +
        order-card. The Dashboard's Active Orders Ledger reads self.orders
        live, so it reflects this the moment reload_all_data() runs."""
        rows_to_write = []
        for o in self.orders:
            curr_id = clean_val(o.get("id"))
            tailor = tailor_name if curr_id == order_id else clean_val(o.get("tailor"))
            r = [clean_val(o.get(h)) for h in self.ord_headers]
            r[self.ord_headers.index("id")] = curr_id
            r[self.ord_headers.index("tailor")] = tailor
            rows_to_write.append(r)
        try:
            self.excel_mgr.write_all_records("orders.xlsx", self.ord_headers, rows_to_write)
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ==========================================
    # RESTRICTED CUSTOMER / EMPLOYEE ACTIONS
    # ==========================================
    def _require_admin(self):
        if self.current_user_role == "Administrator":
            return True
        messagebox.showerror("Restricted", "Only an Administrator may edit or delete records.")
        return False

    def _selected_record(self, tree, records):
        selection = tree.selection()
        if not selection:
            messagebox.showwarning("Select a record", "Select a row first.")
            return None
        record_id = str(tree.item(selection[0])["values"][0])
        return next((r for r in records if clean_val(r.get("id")) == record_id), None)

    def _replace_records(self, filename, headers, records):
        self.excel_mgr.write_all_records(filename, headers,
                                         [[clean_val(record.get(h)) for h in headers] for record in records])
        self.reload_all_data()
        self.update_graphics_and_stats()

    def edit_selected_customer(self):
        if not self._require_admin():
            return
        customer = self._selected_record(self.tree_customers, self.customers)
        if not customer:
            return
        dlg = tk.Toplevel(self); dlg.title("Edit Customer"); dlg.geometry("400x260"); dlg.configure(bg=self.colors["bg_card"]); dlg.grab_set()
        fields = {}
        specs = (("name", "Name"), ("phone", "Phone"), ("address", "Address"))
        for row, (key, label) in enumerate(specs):
            tk.Label(dlg, text=label + ":", font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"]).grid(row=row, column=0, padx=18, pady=10, sticky="w")
            entry = tk.Entry(dlg, width=35, bg=self.colors["bg_body"], fg=self.colors["text_main"],
                             insertbackground=self.colors["text_main"], relief="flat",
                             highlightthickness=1, highlightbackground=self.colors["border"])
            entry.insert(0, clean_val(customer.get(key))); entry.grid(row=row, column=1, padx=8, pady=10); fields[key] = entry
        def save():
            if not fields["name"].get().strip():
                messagebox.showerror("Validation", "Customer name is required.", parent=dlg); return
            customer.update({key: entry.get().strip() for key, entry in fields.items()})
            self._replace_records("customers.xlsx", self.cust_headers, self.customers); dlg.destroy()
        tk.Button(dlg, text="💾 Save Changes", command=save, bg=PRIMARY, fg="white", font=(FONT_FAMILY, 10, "bold"),
                 bd=0, cursor="hand2").grid(row=len(specs), column=0, columnspan=2, sticky="ew", padx=20, pady=14)

    def delete_selected_customer(self):
        if not self._require_admin():
            return
        customer = self._selected_record(self.tree_customers, self.customers)
        if not customer:
            return
        customer_id = clean_val(customer.get("id"))
        if not messagebox.askyesno("Delete Customer", f"Delete {clean_val(customer.get('name'))}? Existing orders are kept for audit history."):
            return
        self._replace_records("customers.xlsx", self.cust_headers, [c for c in self.customers if clean_val(c.get("id")) != customer_id])

    def print_selected_customer_receipt(self):
        customer = self._selected_record(self.tree_customers, self.customers)
        if not customer:
            return
        customer_id = clean_val(customer.get("id"))
        # Find the most recent order for this customer by customer_id
        order = next((o for o in reversed(self.orders) if clean_val(o.get("customer_id")) == customer_id), None)
        if not order:
            messagebox.showinfo("No Receipt", "This customer has no order to print yet.")
            return
        self.generate_order_pdf(clean_val(order.get("id")))

    def filter_customers(self, event=None):
        """Filter customer tree by search query (name, phone, id)."""
        search_query = self.ent_cust_search.get().strip().lower()
        
        # Clear tree
        self.tree_customers.delete(*self.tree_customers.get_children())
        
        # Filter and display matching customers
        if not search_query:
            # Show all customers if search is empty
            for c in self.customers:
                if c.get("id"):
                    row_values = [clean_val(c.get(h, "")) for h in self.cust_headers]
                    self.tree_customers.insert("", tk.END, values=row_values)
        else:
            # Show only matching customers
            for c in self.customers:
                if c.get("id"):
                    name = clean_val(c.get("name", "")).lower()
                    phone = clean_val(c.get("phone", "")).lower()
                    cust_id = clean_val(c.get("id", "")).lower()
                    
                    if search_query in name or search_query in phone or search_query in cust_id:
                        row_values = [clean_val(c.get(h, "")) for h in self.cust_headers]
                        self.tree_customers.insert("", tk.END, values=row_values)

    def clear_customer_search(self):
        """Clear search field and show all customers."""
        self.ent_cust_search.delete(0, tk.END)
        self.filter_customers()

    def edit_selected_employee(self):
        if not self._require_admin():
            return
        employee = self._selected_record(self.tree_employees, self.employees)
        if not employee:
            return
        t = {**TRANSLATIONS["en"], **TRANSLATIONS.get(self.current_lang, {})}
        dlg = tk.Toplevel(self); dlg.title(t["emp_edit_title"]); dlg.geometry("410x330"); dlg.configure(bg=self.colors["bg_card"]); dlg.grab_set()
        fields = {}
        specs = (("name", "emp_edit_lbl_name"), ("phone", "emp_edit_lbl_phone"), ("role", "emp_edit_lbl_role"),
                 ("status", "emp_edit_lbl_status"), ("current_task", "emp_edit_lbl_task"))
        for row, (key, label_key) in enumerate(specs):
            tk.Label(dlg, text=t[label_key] + ":", font=(FONT_FAMILY, 8, "bold"), bg=self.colors["bg_card"], fg=self.colors["text_main"]).grid(row=row, column=0, padx=18, pady=8, sticky="w")
            entry = tk.Entry(dlg, width=34, bg=self.colors["bg_body"], fg=self.colors["text_main"],
                             insertbackground=self.colors["text_main"], relief="flat",
                             highlightthickness=1, highlightbackground=self.colors["border"])
            entry.insert(0, clean_val(employee.get(key))); entry.grid(row=row, column=1, padx=8, pady=8); fields[key] = entry
        def save():
            if not fields["name"].get().strip():
                messagebox.showerror("Validation", "Employee name is required.", parent=dlg); return
            employee.update({key: entry.get().strip() for key, entry in fields.items()})
            self._replace_records("employees.xlsx", self.emp_headers, self.employees); dlg.destroy()
        tk.Button(dlg, text=t["btn_save_changes"], command=save, bg=PRIMARY, fg="white", font=(FONT_FAMILY, 10, "bold"),
                 bd=0, cursor="hand2").grid(row=len(specs), column=0, columnspan=2, sticky="ew", padx=20, pady=14)

    def delete_selected_employee(self):
        if not self._require_admin():
            return
        employee = self._selected_record(self.tree_employees, self.employees)
        if not employee:
            return
        employee_id = clean_val(employee.get("id"))
        if not messagebox.askyesno("Delete Employee", f"Delete {clean_val(employee.get('name'))}? This cannot be undone."):
            return
        self._replace_records("employees.xlsx", self.emp_headers, [e for e in self.employees if clean_val(e.get("id")) != employee_id])

    def print_selected_employee_task(self):
        employee = self._selected_record(self.tree_employees, self.employees)
        if not employee:
            return
        if not REPORTLAB_INSTALLED:
            messagebox.showerror("Missing Library", "Install reportlab to print task slips."); return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"Task_{clean_val(employee.get('id'))}.pdf", filetypes=[("PDF Files", "*.pdf")])
        if not path:
            return
        pdf = canvas.Canvas(path, pagesize=A5); width, height = A5
        pdf.setFont("Helvetica-Bold", 18); pdf.drawString(40, height - 55, "JTQ EMPLOYEE TASK SLIP")
        pdf.setFont("Helvetica", 12)
        for index, (label, key) in enumerate((("Employee", "name"), ("Role", "role"), ("Status", "status"), ("Task", "current_task"))):
            pdf.drawString(40, height - 105 - index * 30, f"{label}: {clean_val(employee.get(key))}")
        pdf.drawString(40, height - 250, f"Printed: {datetime.now().strftime('%Y-%m-%d %H:%M')}"); pdf.save()
        messagebox.showinfo("Task Slip Saved", f"Saved to:\n{path}")

    # ==========================================
    # PDF GENERATOR LOGIC
    # ==========================================
    def generate_order_pdf(self, order_id=None):
        if not REPORTLAB_INSTALLED:
            messagebox.showerror("Missing Library", "To print PDF files, open your terminal/command prompt and run:\n\npip install reportlab")
            return

        if order_id:
            ord_id = order_id
        else:
            sel = self.tree_orders.selection()
            if not sel:
                messagebox.showwarning("Select Order", "Select an order from the active ledger first!")
                return
            ord_id = str(self.tree_orders.item(sel[0])["values"][0])

        # Get Full Order Data
        order_data = next((o for o in self.orders if clean_val(o.get("id")) == ord_id), None)
        if not order_data:
            return

        # Get Full Customer Data (orders reference customers by id)
        cid = clean_val(order_data.get("customer_id") or "")
        cust_data = next((c for c in self.customers if clean_val(c.get("id")) == cid), {})
        cust_name = clean_val(cust_data.get('name', cid))

        file_path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"Receipt_{ord_id}.pdf", title="Save Order PDF as...", filetypes=[("PDF Files", "*.pdf")])
        if not file_path:
            return

        try:
            c = canvas.Canvas(file_path, pagesize=A5)
            width, height = A5

            # Header
            c.setFont("Helvetica-Bold", 18)
            c.drawString(40, height - 50, "JHAGRA CREATION & FABRICS")
            c.setFont("Helvetica", 10)
            c.drawString(40, height - 65, "The Name Of Quality - JTQ")

            c.line(40, height - 75, width - 40, height - 75)

            # Info
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, height - 100, f"No: {ord_id}")
            c.drawString(150, height - 100, f"Name: {cust_name}")
            c.drawString(40, height - 120, f"Contact: {clean_val(cust_data.get('phone', 'N/A'))}")
            c.drawString(40, height - 140, f"Date: {datetime.now().strftime('%Y-%m-%d')}")

            # 9 Measurements (right column of the physical slip)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, height - 170, "Measurements (Inches)")
            c.setFont("Helvetica", 11)

            meas_y = height - 190
            m_list = [
                ("Length (لبادی)", cust_data.get("length")), ("Sleeve (چستین)", cust_data.get("sleeve")),
                ("Shoulder (تیرہ)", cust_data.get("shoulder")), ("Collar (کالر)", cust_data.get("collar")),
                ("Chest (چھاتاں)", cust_data.get("chest")), ("Waist (کمر)", cust_data.get("waist")),
                ("Daman (واشن)", cust_data.get("daman")), ("Shalwar Length (شلوار لیبا)", cust_data.get("shalwar_len")),
                ("Paancha (بائی پا)", cust_data.get("paancha"))
            ]

            for name, val in m_list:
                c.drawString(50, meas_y, f"{name}:")
                c.drawString(150, meas_y, str(clean_val(val)))
                c.line(145, meas_y - 2, 250, meas_y - 2)
                meas_y -= 20

            # Style selections (center/left visual elements of the physical slip)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(280, height - 170, "Selected Styles")
            c.setFont("Helvetica", 11)

            style_y = height - 190
            s_list = [
                ("Button", order_data.get("button_style")),
                ("Collar", order_data.get("collar_style")),
                ("Cuffs", order_data.get("cuff_style")),
                ("Pocket", order_data.get("pocket_style")),
                ("Daman", order_data.get("daman_style")),
                ("Stitch", order_data.get("stitching"))
            ]

            for name, val in s_list:
                c.drawString(280, style_y, f"{name}:")
                c.drawString(330, style_y, str(clean_val(val)))
                style_y -= 25

            c.save()
            messagebox.showinfo("Success", f"PDF Form generated successfully at:\n{file_path}")

        except Exception as e:
            messagebox.showerror("PDF Error", str(e))

    # ==========================================
    # LIVE STATS / TABLES
    # ==========================================
    def update_graphics_and_stats(self):
        valid_orders = [o for o in self.orders if o.get("id")]
        total = len(valid_orders)

        ready = sum(1 for o in valid_orders if "ready" in clean_val(o.get("status")).lower())
        prog = sum(1 for o in valid_orders if "progress" in clean_val(o.get("status")).lower())
        rem = total - ready - prog

        done_pct = int((ready / total) * 100) if total > 0 else 0
        prog_pct = int((prog / total) * 100) if total > 0 else 0
        rem_pct = int((rem / total) * 100) if total > 0 else 0

        self.chart_done.set_percentage(done_pct)
        self.chart_prog.set_percentage(prog_pct)
        self.chart_rem.set_percentage(rem_pct)

        self.lbl_done_pct.configure(text=f"{done_pct}%")
        self.lbl_prog_pct.configure(text=f"{prog_pct}%")
        self.lbl_rem_pct.configure(text=f"{rem_pct}%")

        self.tree_orders.delete(*self.tree_orders.get_children())
        for o in valid_orders:
            st = clean_val(o.get("status")).lower()
            tag = "status_ready" if "ready" in st else "status_prog" if "progress" in st else "status_pending"
            # Insert values in the explicit column order to keep id at index 0 and preserve ordering
            row_values = []
            for h in self.ord_headers:
                if h == 'customer_id':
                    cid = clean_val(o.get('customer_id', ''))
                    # Display customer name when possible; fall back to id/raw value
                    name = next((clean_val(c.get('name')) for c in self.customers if clean_val(c.get('id')) == cid), cid)
                    row_values.append(name)
                else:
                    row_values.append(clean_val(o.get(h, "")))
            self.tree_orders.insert("", tk.END, values=row_values, tags=(tag,))

        self.tree_customers.delete(*self.tree_customers.get_children())
        for c in self.customers:
            if c.get("id"):
                # Ensure values are in the correct column order (FIX FOR ORDER PICKING ISSUE)
                row_values = [clean_val(c.get(h, "")) for h in self.cust_headers]
                self.tree_customers.insert("", tk.END, values=row_values)
        

        self.tree_employees.delete(*self.tree_employees.get_children())
        for e in self.employees:
            if e.get("id"):
                # Ensure values are in the correct column order
                row_values = [clean_val(e.get(h, "")) for h in self.emp_headers]
                self.tree_employees.insert("", tk.END, values=row_values)

        # Counter tiles + the visible ledger list, both derived from the data
        # already loaded above.
        on_duty = sum(1 for e in self.employees
                      if e.get("id") and "duty" in clean_val(e.get("status")).lower()
                      and "off" not in clean_val(e.get("status")).lower())
        self.lbl_stat_orders.configure(text=str(total))
        self.lbl_stat_customers.configure(text=str(sum(1 for c in self.customers if c.get("id"))))
        self.lbl_stat_onduty.configure(text=str(on_duty))
        self._render_ledger_rows()

        self.refresh_finance_ui()
        self.refresh_inventory_ui()
        self.refresh_calendar_ui()

    def update_clock(self):
        now = datetime.now()
        self.lbl_clock.configure(text=now.strftime("%Y-%m-%d %H:%M:%S"))
        # The dashboard header carries the same clock in the design's
        # long-form "Monday, 28 September - 18:30:12" shape.
        if hasattr(self, "lbl_dash_datetime") and self.lbl_dash_datetime.winfo_exists():
            self.lbl_dash_datetime.configure(
                text="  ·  " + now.strftime("%A, %d %B") + "  ·  " + now.strftime("%H:%M:%S"))
        self.after(1000, self.update_clock)

    # ==========================================
    # LANGUAGE ENGINE
    # ==========================================
    def on_language_change(self, event):
        selected_label = self.cbo_lang.get()
        label_to_code = {label: code for code, label in LANGUAGE_OPTIONS}
        self.current_lang = label_to_code.get(selected_label, self.current_lang)
        self._app_state_for_current_data().save(lang=self.current_lang)
        self.apply_language_pack()

    def apply_language_pack(self):
        # Some language packs are intentionally partial; preserve English labels
        # for any key that has not been translated yet.
        t = {**TRANSLATIONS["en"], **TRANSLATIONS.get(self.current_lang, {})}
        label_to_code = {label: code for code, label in LANGUAGE_OPTIONS}
        code_to_label = {code: label for code, label in LANGUAGE_OPTIONS}
        self.cbo_lang.set(code_to_label.get(self.current_lang, code_to_label[LANGUAGE_OPTIONS[0][0]]))

        for _, (btn, lang_key) in self.nav_buttons.items():
            btn.configure(text=t[lang_key])

        self.lbl_dash_title.configure(text=t["dash_title"])
        self.lbl_dash_sub.configure(text=t["dash_sub"])
        # These are the design's tracked uppercase captions, so the text has to
        # go back through _track() here or a language switch would flatten them
        # (it is a no-op for non-ASCII scripts such as Urdu).
        self.lbl_done_title.configure(text=self._track(t["work_done"]))
        self.lbl_prog_title.configure(text=self._track(t["in_prog"]))
        self.lbl_rem_title.configure(text=self._track(t["work_rem"]))
        self.lbl_ledger_head.configure(text=self._track(t["active_ledger"]))
        self.btn_dash_new_order.configure(text=t["dash_new_order"])
        self.lbl_stat_orders_cap.configure(text=self._track(t["dash_total_orders"]))
        self.lbl_stat_customers_cap.configure(text=self._track(t["dash_customers"]))
        self.lbl_stat_onduty_cap.configure(text=self._track(t["dash_on_duty"]))
        self._render_ledger_rows()

        self.lbl_cust_title.configure(text=t["cust_title"])
        self.lbl_cust_sub.configure(text=t["cust_sub"])
        self.btn_cust_modal.configure(text=t["btn_add_cust"])
        self.btn_new_card.configure(text=t["btn_new_card"])
        self.btn_cust_receipt.configure(text=t.get("cust_btn_receipt", self.btn_cust_receipt.cget("text")))
        self.btn_cust_edit.configure(text=t.get("cust_btn_edit", self.btn_cust_edit.cget("text")))
        self.btn_cust_delete.configure(text=t.get("cust_btn_delete", self.btn_cust_delete.cget("text")))
        if hasattr(self, "order_card"):
            self.order_card.set_language(self.current_lang)

        self.lbl_emp_title.configure(text=t["emp_title"])
        self.lbl_emp_sub.configure(text=t["emp_sub"])
        self.btn_task_modal.configure(text=t["btn_assign_task"])
        self.btn_emp_modal.configure(text=t["btn_add_emp"])
        self.btn_emp_print.configure(text=t["emp_btn_print"])
        self.btn_emp_edit.configure(text=t["emp_btn_edit"])
        self.btn_emp_delete.configure(text=t["emp_btn_delete"])
        for col, key in (("id", "tbl_emp_id"), ("name", "tbl_emp_name"), ("phone", "tbl_emp_phone"),
                        ("role", "tbl_emp_role"), ("status", "tbl_emp_status"), ("current_task", "tbl_emp_task")):
            self.tree_employees.heading(col, text=t[key])

        self.lbl_fin_paid_title.configure(text=self._track(t["dash_fin_paid"]))
        self.lbl_fin_remaining_title.configure(text=self._track(t["dash_fin_remaining"]))
        self.lbl_fin_debt_title.configure(text=self._track(t["dash_fin_debt"]))

        self.lbl_fin_title.configure(text=t["fin_title"])
        self.lbl_fin_sub.configure(text=t["fin_sub"])
        self.lbl_fin_card_paid_title.configure(text=t["fin_card_paid"])
        self.lbl_fin_card_remaining_title.configure(text=t["fin_card_remaining"])
        self.lbl_fin_card_debt_title.configure(text=t["fin_card_debt"])
        self.lbl_fin_tbl_head.configure(text=t["fin_tbl_head"])
        for col, key in (("order_id", "fin_tbl_order"), ("customer_name", "fin_tbl_customer"),
                        ("garment", "fin_tbl_garment"), ("total", "fin_tbl_total"),
                        ("paid", "fin_tbl_paid"), ("remaining", "fin_tbl_remaining"),
                        ("debt", "fin_tbl_debt"), ("status", "fin_tbl_status"),
                        ("delivery_status", "fin_tbl_delivery")):
            self.tree_finance.heading(col, text=t[key])
        for key, (b, lang_key, icon) in self.fin_tab_buttons.items():
            b.configure(text=f"{icon} {t[lang_key]}")
        self.lbl_fin_add_heading.configure(text=f"➕ {t['fin_add_heading']}")
        self.lbl_fin_add_order.configure(text=t["fin_add_order"])
        self.lbl_fin_add_amount.configure(text=t["fin_add_amount"])
        self.btn_fin_pay_submit.configure(text=f"💾 {t['fin_add_submit']}")

        self.lbl_admin_title.configure(text=t["admin_title"])
        self.lbl_admin_sub.configure(text=t["admin_sub"])
        self.lbl_theme_label.configure(text=t.get("theme_label", self.lbl_theme_label.cget("text")))
        self.lbl_language_label.configure(text=t.get("language_label", self.lbl_language_label.cget("text")))
        self.lbl_admin_card_garments.configure(text=t.get("admin_card_garments", self.lbl_admin_card_garments.cget("text")))
        self.lbl_admin_card_roles.configure(text=t.get("admin_card_roles", self.lbl_admin_card_roles.cget("text")))
        self.btn_add_garment.configure(text=t.get("btn_item_add", self.btn_add_garment.cget("text")))
        self.btn_remove_garment.configure(text=t.get("btn_item_remove", self.btn_remove_garment.cget("text")))
        self.btn_add_role.configure(text=t.get("btn_item_add", self.btn_add_role.cget("text")))
        self.btn_remove_role.configure(text=t.get("btn_item_remove", self.btn_remove_role.cget("text")))

        self.tree_orders.heading("id", text=t["tbl_ord_id"])
        # customer_id column displays a friendly 'Customer' label
        self.tree_orders.heading("customer_id", text=t["tbl_cust"])
        self.tree_orders.heading("garment", text=t["tbl_garment"])
        self.tree_orders.heading("status", text=t["tbl_status"])
        self.tree_orders.heading("tailor", text=t["tbl_tailor"])


if __name__ == "__main__":
    app = AtelierERPApp()
    app.mainloop()
