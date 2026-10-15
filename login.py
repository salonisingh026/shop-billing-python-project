"""Launch Singhjee's Python 3 cold-drinks store desktop application."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from datetime import date
from pathlib import Path

from billingdetails import BillingPage, SalesPage
from calendarview import CalendarPage
from database import DEFAULT_LOGIN_PASSWORD, DEFAULT_LOGIN_USERNAME, StoreDatabase
from expirycheck import ExpiryPage
from stockdetails import InventoryPage
from ui import INK, LINE, MUTED, PALE, TEAL, WHITE, format_money, make_tree


class SinghjeeStoreApp:
    def __init__(self, root: tk.Tk, database: StoreDatabase):
        self.root = root
        self.database = database
        self.current_user = ""
        self.page_frame = None
        self._configure_window()
        self._configure_styles()
        self.show_login()

    def _configure_window(self):
        self.root.title("Singhjee Cold Drinks & More")
        self.root.configure(background=PALE)
        self.root.geometry("1220x790")
        self.root.minsize(980, 650)
        icon = Path(__file__).resolve().parent / "favicon.ico"
        if icon.exists():
            try:
                self.root.iconbitmap(str(icon))
            except tk.TclError:
                pass

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Page.TFrame", background=PALE)
        style.configure("Card.TFrame", background=WHITE)
        style.configure("Topbar.TFrame", background=WHITE)
        style.configure("Sidebar.TFrame", background="#152f3b")
        style.configure("Label.TLabel", background=PALE, foreground=INK, font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background=PALE, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("PageTitle.TLabel", background=PALE, foreground=INK, font=("Segoe UI", 23, "bold"))
        style.configure("SectionTitle.TLabel", background=WHITE, foreground=INK, font=("Segoe UI", 12, "bold"))
        style.configure("Total.TLabel", background=WHITE, foreground=TEAL, font=("Segoe UI", 20, "bold"))
        style.configure("SidebarTitle.TLabel", background="#152f3b", foreground=WHITE, font=("Segoe UI", 12, "bold"))
        style.configure("SidebarHint.TLabel", background="#152f3b", foreground="#afc4c9", font=("Segoe UI", 9))
        style.configure("TopbarTitle.TLabel", background=WHITE, foreground=INK, font=("Segoe UI", 13, "bold"))
        style.configure("CardValue.TLabel", background=WHITE, foreground=INK, font=("Segoe UI", 21, "bold"))
        style.configure("CardCaption.TLabel", background=WHITE, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("CardAccent.TLabel", background=WHITE, foreground=TEAL, font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", font=("Segoe UI", 10), background=PALE, foreground=INK)
        style.configure("TButton", font=("Segoe UI", 10), padding=(12, 8), background=WHITE, foreground=INK)
        style.map("TButton", background=[("active", "#e9f0f1")])
        style.configure("Accent.TButton", background=TEAL, foreground=WHITE, borderwidth=0, font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", "#0b625c"), ("disabled", "#9ebdb8")], foreground=[("disabled", "#eff5f4")])
        style.configure("Danger.TButton", background="#fff2f0", foreground="#b42318", borderwidth=0)
        style.map("Danger.TButton", background=[("active", "#fddbd6")])
        style.configure("Nav.TButton", background="#152f3b", foreground="#dbe7e9", anchor="w", borderwidth=0,
                        font=("Segoe UI", 10), padding=(14, 12))
        style.map("Nav.TButton", background=[("active", "#234954")], foreground=[("active", WHITE)])
        style.configure("Treeview", background=WHITE, fieldbackground=WHITE, foreground=INK,
                        rowheight=32, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#eef3f4", foreground="#475569",
                        font=("Segoe UI", 9, "bold"), relief="flat", padding=(8, 9))
        style.map("Treeview", background=[("selected", "#d9eeeb")], foreground=[("selected", INK)])
        style.configure("TEntry", padding=7, fieldbackground=WHITE)
        style.configure("TCombobox", padding=5)
        style.configure("Card.TLabelframe", background=WHITE, bordercolor=LINE, relief="solid")
        style.configure("Card.TLabelframe.Label", background=WHITE, foreground=INK, font=("Segoe UI", 10, "bold"))

    def show_login(self):
        self._clear_root()
        self.root.title("Sign in · Singhjee Cold Drinks & More")
        shell = ttk.Frame(self.root, style="Page.TFrame", padding=34)
        shell.pack(fill="both", expand=True)
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)
        shell.columnconfigure(1, weight=1)

        hero = tk.Canvas(shell, highlightthickness=0, bd=0, background="#123e43")
        hero.grid(row=0, column=0, sticky="nsew")
        hero_image_path = Path(__file__).resolve().parent / "assets" / "singhjee-cold-drinks-bg.png"
        self._login_hero_image = tk.PhotoImage(file=str(hero_image_path))
        self._login_hero_image_id = hero.create_image(0, 0, image=self._login_hero_image, anchor="nw")
        hero.bind(
            "<Configure>",
            lambda event: hero.coords(
                self._login_hero_image_id,
                (event.width - self._login_hero_image.width()) // 2,
                (event.height - self._login_hero_image.height()) // 2,
            ),
        )

        form = ttk.Frame(shell, style="Card.TFrame", padding=(48, 50))
        form.grid(row=0, column=1, sticky="nsew")
        form.columnconfigure(0, weight=1)
        ttk.Label(form, text="Welcome back", background=WHITE, foreground=INK,
                  font=("Segoe UI", 24, "bold")).grid(row=0, column=0, sticky="w", pady=(70, 6))
        ttk.Label(form, text="Sign in to manage your store.", background=WHITE, foreground=MUTED,
                  font=("Segoe UI", 11)).grid(row=1, column=0, sticky="w", pady=(0, 30))

        ttk.Label(form, text="Username", background=WHITE).grid(row=2, column=0, sticky="w", pady=(0, 6))
        self.username = ttk.Entry(form)
        self.username.grid(row=3, column=0, sticky="ew", ipady=5)
        ttk.Label(form, text="Password", background=WHITE).grid(row=4, column=0, sticky="w", pady=(17, 6))
        self.password = ttk.Entry(form, show="•")
        self.password.grid(row=5, column=0, sticky="ew", ipady=5)
        self.login_error = ttk.Label(form, text="", background=WHITE, foreground="#b42318", wraplength=320)
        self.login_error.grid(row=6, column=0, sticky="w", pady=(10, 0))
        ttk.Button(form, text="Sign in", style="Accent.TButton", command=self.sign_in).grid(
            row=7, column=0, sticky="ew", pady=(14, 0), ipady=7
        )
        ttk.Label(form, text=f"", background=WHITE,
                  foreground=MUTED, font=("Segoe UI", 9)).grid(row=8, column=0, sticky="w", pady=(22, 0))
        self.username.focus_set()
        self.root.bind("<Return>", self._login_return)

    def _login_return(self, _event):
        if self.page_frame is None:
            self.sign_in()

    def sign_in(self):
        if self.database.authenticate(self.username.get(), self.password.get()):
            self.current_user = self.username.get().strip()
            self.root.unbind("<Return>")
            self.show_workspace()
        else:
            self.login_error.configure(text="That username and password do not match.")
            self.password.delete(0, "end")
            self.password.focus_set()

    def show_workspace(self):
        self._clear_root()
        self.root.title("Singhjee Cold Drinks & More")
        shell = ttk.Frame(self.root, style="Page.TFrame")
        shell.pack(fill="both", expand=True)
        shell.rowconfigure(1, weight=1)
        shell.columnconfigure(1, weight=1)

        topbar = ttk.Frame(shell, style="Topbar.TFrame", padding=(22, 12))
        topbar.grid(row=0, column=0, columnspan=2, sticky="ew")
        topbar.columnconfigure(0, weight=1)
        ttk.Label(topbar, text="Singhjee Cold Drinks & More", style="TopbarTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(topbar, text=f"{date.today():%A, %d %B %Y}", background=WHITE, foreground=MUTED).grid(
            row=0, column=1, padx=(0, 18)
        )
        ttk.Button(topbar, text="Change password", command=self.change_password).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(topbar, text="Sign out", command=self.sign_out).grid(row=0, column=3)

        sidebar = ttk.Frame(shell, style="Sidebar.TFrame", padding=(12, 22))
        sidebar.grid(row=1, column=0, sticky="nsw")
        sidebar.configure(width=205)
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)
        ttk.Label(sidebar, text="STORE DESK", style="SidebarTitle.TLabel").grid(row=0, column=0, sticky="w", padx=10)
        ttk.Label(sidebar, text="OPERATIONS", style="SidebarHint.TLabel").grid(row=1, column=0, sticky="w", padx=10, pady=(30, 8))
        navigation = (
            ("Overview", self.show_dashboard),
            ("Inventory", self.show_inventory),
            ("Billing", self.show_billing),
            ("Expiry watch", self.show_expiry),
            ("Calendar", self.show_calendar),
            ("Today's sales", self.show_sales),
        )
        for index, (label, callback) in enumerate(navigation, start=2):
            ttk.Button(sidebar, text=label, style="Nav.TButton", command=callback).grid(
                row=index, column=0, sticky="ew", pady=3
            )
        ttk.Label(sidebar, text="Your stock and sales\nstay on this computer.", style="SidebarHint.TLabel",
                  justify="left", wraplength=160).grid(row=8, column=0, sticky="sw", padx=10, pady=(28, 0))

        self.content = ttk.Frame(shell, style="Page.TFrame")
        self.content.grid(row=1, column=1, sticky="nsew")
        self.content.rowconfigure(0, weight=1)
        self.content.columnconfigure(0, weight=1)
        self.show_dashboard()

    def _clear_root(self):
        for child in self.root.winfo_children():
            child.destroy()
        self.page_frame = None

    def _show_page(self, page):
        if self.page_frame is not None:
            self.page_frame.destroy()
        self.page_frame = page(self.content, self.database, self.refresh_dashboard) if page is InventoryPage or page is BillingPage else page(self.content, self.database)
        self.page_frame.grid(row=0, column=0, sticky="nsew")

    def show_dashboard(self):
        if not hasattr(self, "content"):
            return
        if self.page_frame is not None:
            self.page_frame.destroy()
        self.page_frame = DashboardPage(self.content, self.database, self.show_inventory,
                                        self.show_billing, self.show_expiry)
        self.page_frame.grid(row=0, column=0, sticky="nsew")

    def show_inventory(self):
        self._show_page(InventoryPage)

    def show_billing(self):
        self._show_page(BillingPage)

    def show_expiry(self):
        self._show_page(ExpiryPage)

    def show_sales(self):
        self._show_page(SalesPage)

    def show_calendar(self):
        self._show_page(CalendarPage)

    def refresh_dashboard(self):
        if isinstance(self.page_frame, DashboardPage):
            self.page_frame.refresh()

    def sign_out(self):
        self.current_user = ""
        self.show_login()

    def change_password(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Change password")
        dialog.configure(background=PALE)
        dialog.transient(self.root)
        dialog.resizable(False, False)
        dialog.grab_set()
        panel = ttk.Frame(dialog, style="Page.TFrame", padding=24)
        panel.pack(fill="both", expand=True)
        fields = []
        for row, label in enumerate(("Current password", "New password", "Confirm new password")):
            ttk.Label(panel, text=label).grid(row=row * 2, column=0, sticky="w", pady=(0, 5))
            field = ttk.Entry(panel, show="*")
            field.grid(row=row * 2 + 1, column=0, sticky="ew", ipady=4, pady=(0, 12))
            fields.append(field)
        panel.columnconfigure(0, weight=1)

        def save():
            if fields[1].get() != fields[2].get():
                messagebox.showerror("Passwords do not match", "Enter the same new password twice.", parent=dialog)
                return
            try:
                self.database.change_password(self.current_user, fields[0].get(), fields[1].get())
            except ValueError as error:
                messagebox.showerror("Could not change password", str(error), parent=dialog)
                return
            dialog.destroy()
            messagebox.showinfo("Password changed", "Your new password is saved on this computer.", parent=self.root)

        ttk.Button(panel, text="Save password", style="Accent.TButton", command=save).grid(
            row=6, column=0, sticky="ew", ipady=4
        )
        fields[0].focus_set()
        dialog.bind("<Return>", lambda _event: save())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())


class DashboardPage(ttk.Frame):
    def __init__(self, parent, database, open_inventory, open_billing, open_expiry):
        super().__init__(parent, style="Page.TFrame", padding=24)
        self.database = database
        self.open_inventory = open_inventory
        self.open_billing = open_billing
        self.open_expiry = open_expiry
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)
        ttk.Label(self, text="Good day", style="PageTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(self, text="Here is a quick look at your store today.", style="Muted.TLabel").grid(
            row=1, column=0, sticky="w", pady=(5, 20)
        )
        self.cards = ttk.Frame(self, style="Page.TFrame")
        self.cards.grid(row=2, column=0, sticky="ew", pady=(0, 20))
        for column in range(4):
            self.cards.columnconfigure(column, weight=1, uniform="card")
        self.card_values = []
        body = ttk.Frame(self, style="Page.TFrame")
        body.grid(row=3, column=0, sticky="nsew")
        body.rowconfigure(1, weight=1)
        body.columnconfigure(0, weight=3, uniform="dash")
        body.columnconfigure(1, weight=2, uniform="dash")
        ttk.Label(body, text="Stock at a glance", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 9), padx=(0, 12)
        )
        ttk.Label(body, text="Quick actions", style="SectionTitle.TLabel").grid(
            row=0, column=1, sticky="w", pady=(0, 9), padx=(12, 0)
        )
        left, self.tree = make_tree(
            body,
            (("name", "Product", 190), ("category", "Category", 115),
             ("quantity", "In stock", 80), ("cost", "Unit price", 100)),
            height=9,
        )
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 12))
        actions = ttk.Frame(body, style="Card.TFrame", padding=18)
        actions.grid(row=1, column=1, sticky="nsew", padx=(12, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Label(actions, text="Keep the day moving", style="SectionTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(actions, text="Jump straight to the tasks you use most.", style="Muted.TLabel",
                  wraplength=240).grid(row=1, column=0, sticky="w", pady=(4, 16))
        ttk.Button(actions, text="Create a bill", style="Accent.TButton", command=open_billing).grid(
            row=2, column=0, sticky="ew", pady=4, ipady=3
        )
        ttk.Button(actions, text="Review inventory", command=open_inventory).grid(
            row=3, column=0, sticky="ew", pady=4, ipady=3
        )
        ttk.Button(actions, text="Check expiry dates", command=open_expiry).grid(
            row=4, column=0, sticky="ew", pady=4, ipady=3
        )
        self.refresh()

    def refresh(self):
        data = self.database.summary()
        for child in self.cards.winfo_children():
            child.destroy()
        card_data = (
            ("Today's sales", format_money(data["today_total"]), f"{data['today_sales']} bills"),
            ("Products", str(data["item_count"]), f"{data['units']} units in stock"),
            ("Low stock", str(data["low_stock"]), "Products at or below 10 units"),
            ("Expiry watch", str(data["expired"] + data["expiring"]),
             f"{data['expired']} expired · {data['expiring']} due soon"),
        )
        for column, (caption, value, hint) in enumerate(card_data):
            card = ttk.Frame(self.cards, style="Card.TFrame", padding=(16, 14))
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 7, 7 if column < 3 else 0))
            ttk.Label(card, text=caption, style="CardCaption.TLabel").pack(anchor="w")
            ttk.Label(card, text=value, style="CardValue.TLabel").pack(anchor="w", pady=(9, 3))
            ttk.Label(card, text=hint, style="CardAccent.TLabel", wraplength=190).pack(anchor="w")
        if hasattr(self, "tree"):
            self.tree.delete(*self.tree.get_children())
            for item in data["recent_items"]:
                self.tree.insert("", "end", values=(item["name"], item["category"] or "—",
                                item["quantity"], format_money(item["cost"])))


def main():
    root = tk.Tk()
    try:
        database = StoreDatabase()
    except Exception as error:
        messagebox.showerror("Could not open the store database", str(error), parent=root)
        root.destroy()
        return
    SinghjeeStoreApp(root, database)
    root.mainloop()


if __name__ == "__main__":
    main()
