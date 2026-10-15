"""Billing and daily sales screens."""

from __future__ import annotations

from datetime import date
import os
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from decimal import Decimal, InvalidOperation

from database import PAYMENT_METHODS, StoreDatabase, decode_sale_items, sales_period_bounds
from excel_export import write_excel_workbook
from ui import MUTED, add_page_heading, format_money, make_tree


class BillingPage(ttk.Frame):
    def __init__(self, parent, database: StoreDatabase, on_change=None):
        super().__init__(parent, style="Page.TFrame", padding=24)
        self.database = database
        self.on_change = on_change or (lambda: None)
        self.cart: dict[int, int] = {}
        self.items: dict[int, dict] = {}
        self.quantity = tk.StringVar(value="1")
        self.search = tk.StringVar()
        self.total = tk.StringVar(value=format_money(0))
        self.payment_method = tk.StringVar(value="Cash")
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        add_page_heading(
            self, "New bill", "Select products and quantities, then save the sale. Stock updates with the bill."
        ).grid(row=0, column=0, sticky="ew", pady=(0, 18))

        customer_box = ttk.LabelFrame(self, text="Customer", style="Card.TLabelframe", padding=14)
        customer_box.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        customer_box.columnconfigure(1, weight=2)
        customer_box.columnconfigure(3, weight=1)
        customer_box.columnconfigure(5, weight=1)
        customer_box.columnconfigure(7, weight=2)
        ttk.Label(customer_box, text="Name").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.customer = ttk.Entry(customer_box)
        self.customer.grid(row=0, column=1, sticky="ew", padx=(0, 18), ipady=4)
        ttk.Label(customer_box, text="Phone (optional)").grid(row=0, column=2, sticky="w", padx=(0, 8))
        self.phone = ttk.Entry(customer_box)
        self.phone.grid(row=0, column=3, sticky="ew", padx=(0, 18), ipady=4)
        ttk.Label(customer_box, text="Paid by").grid(row=0, column=4, sticky="w", padx=(0, 8))
        ttk.Combobox(
            customer_box, textvariable=self.payment_method, values=PAYMENT_METHODS,
            state="readonly", width=14,
        ).grid(row=0, column=5, sticky="ew", padx=(0, 18), ipady=3)
        ttk.Label(customer_box, text="Address").grid(row=0, column=6, sticky="w", padx=(0, 8))
        self.address = ttk.Entry(customer_box)
        self.address.grid(row=0, column=7, sticky="ew", ipady=4)

        content = ttk.Frame(self, style="Page.TFrame")
        content.grid(row=2, column=0, sticky="nsew")
        content.rowconfigure(1, weight=1)
        content.columnconfigure(0, weight=3, uniform="bill")
        content.columnconfigure(1, weight=2, uniform="bill")

        catalog_heading = ttk.Frame(content, style="Page.TFrame")
        catalog_heading.grid(row=0, column=0, sticky="ew", padx=(0, 10), pady=(0, 8))
        catalog_heading.columnconfigure(0, weight=1)
        ttk.Label(catalog_heading, text="Products in stock", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(catalog_heading, textvariable=self.search, width=22).grid(row=0, column=1, sticky="e", ipady=3)
        self.search.trace_add("write", lambda *_: self.refresh_catalog())
        catalog_holder, self.catalog = make_tree(
            content,
            (("name", "Product", 190), ("category", "Category", 110),
             ("quantity", "Available", 80), ("cost", "Price", 90)),
            height=14,
        )
        catalog_holder.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        self.catalog.bind("<Double-1>", lambda _event: self.add_selected())

        cart_panel = ttk.Frame(content, style="Card.TFrame", padding=14)
        cart_panel.grid(row=0, column=1, rowspan=2, sticky="nsew")
        cart_panel.rowconfigure(2, weight=1)
        cart_panel.columnconfigure(0, weight=1)
        ttk.Label(cart_panel, text="Current bill", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )
        add_row = ttk.Frame(cart_panel, style="Card.TFrame")
        add_row.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        add_row.columnconfigure(0, weight=1)
        ttk.Label(add_row, text="Qty", foreground=MUTED).grid(row=0, column=1, padx=(8, 5))
        quantity = ttk.Spinbox(add_row, from_=1, to=99999, textvariable=self.quantity, width=6)
        quantity.grid(row=0, column=2, padx=(0, 8), ipady=3)
        ttk.Button(add_row, text="Add", style="Accent.TButton", command=self.add_selected).grid(row=0, column=3)

        cart_holder, self.cart_tree = make_tree(
            cart_panel,
            (("name", "Product", 155), ("quantity", "Qty", 48), ("amount", "Amount", 85)),
            height=12,
        )
        cart_holder.grid(row=2, column=0, sticky="nsew")

        footer = ttk.Frame(cart_panel, style="Card.TFrame")
        footer.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        footer.columnconfigure(0, weight=1)
        ttk.Button(footer, text="Remove selected", command=self.remove_selected).grid(row=0, column=0, sticky="w")
        ttk.Label(footer, text="Total", foreground=MUTED).grid(row=1, column=0, sticky="w", pady=(14, 0))
        ttk.Label(footer, textvariable=self.total, style="Total.TLabel").grid(row=1, column=1, sticky="e", pady=(10, 0))
        ttk.Button(footer, text="Save bill", style="Accent.TButton", command=self.save_bill).grid(
            row=2, column=0, columnspan=2, sticky="ew", pady=(14, 0), ipady=7
        )

        self.refresh_catalog()

    def refresh_catalog(self):
        self.catalog.delete(*self.catalog.get_children())
        self.items = {item["id"]: item for item in self.database.list_items()}
        query = self.search.get().strip().casefold()
        for item in self.items.values():
            searchable = " ".join((item["name"], item["category"] or "", item["supplier"] or "")).casefold()
            if query and query not in searchable:
                continue
            available = self._int(item["quantity"])
            self.catalog.insert(
                "", "end", iid=str(item["id"]),
                values=(item["name"], item["category"] or "—", available, format_money(item["cost"])),
                tags=("unavailable",) if available == 0 else (),
            )
        self.catalog.tag_configure("unavailable", foreground="#9ca3af")
        self.refresh_cart()

    def add_selected(self):
        selection = self.catalog.selection()
        if not selection:
            messagebox.showinfo("Select a product", "Choose a product from the list first.", parent=self)
            return
        try:
            quantity = int(self.quantity.get())
        except ValueError:
            messagebox.showerror("Invalid quantity", "Enter a whole number greater than zero.", parent=self)
            return
        if quantity < 1:
            messagebox.showerror("Invalid quantity", "Enter a whole number greater than zero.", parent=self)
            return
        item_id = int(selection[0])
        item = self.items[item_id]
        available = self._int(item["quantity"])
        if self.cart.get(item_id, 0) + quantity > available:
            messagebox.showerror("Not enough stock", f"Only {available} unit(s) of {item['name']} are available.", parent=self)
            return
        self.cart[item_id] = self.cart.get(item_id, 0) + quantity
        self.refresh_cart()

    def remove_selected(self):
        selection = self.cart_tree.selection()
        if not selection:
            return
        self.cart.pop(int(selection[0]), None)
        self.refresh_cart()

    def refresh_cart(self):
        self.cart_tree.delete(*self.cart_tree.get_children())
        total = Decimal("0.00")
        for item_id, quantity in self.cart.items():
            item = self.items.get(item_id)
            if not item:
                continue
            try:
                unit_price = Decimal(str(item["cost"]))
            except InvalidOperation:
                unit_price = Decimal("0")
            amount = unit_price * quantity
            total += amount
            self.cart_tree.insert(
                "", "end", iid=str(item_id),
                values=(item["name"], quantity, format_money(amount)),
            )
        self.total.set(format_money(total))

    def save_bill(self):
        try:
            _, _, receipt_path, receipt = self.database.create_sale(
                self.customer.get(), self.address.get(), self.phone.get(),
                self.payment_method.get(), self.cart,
            )
        except (ValueError, OSError) as error:
            messagebox.showerror("Could not save bill", str(error), parent=self)
            self.refresh_catalog()
            return
        self.cart.clear()
        self.customer.delete(0, "end")
        self.phone.delete(0, "end")
        self.address.delete(0, "end")
        self.payment_method.set("Cash")
        self.refresh_catalog()
        self.on_change()
        show_receipt_preview(self, receipt, receipt_path)

    @staticmethod
    def _int(value) -> int:
        try:
            return int(value or 0)
        except (ValueError, TypeError):
            return 0


class SalesPage(ttk.Frame):
    def __init__(self, parent, database: StoreDatabase):
        super().__init__(parent, style="Page.TFrame", padding=24)
        self.database = database
        self.rowconfigure(3, weight=1)
        self.columnconfigure(0, weight=1)
        add_page_heading(self, "Sales analysis", "Review bills and products sold by day, week, month, or year.").grid(
            row=0, column=0, sticky="ew", pady=(0, 22)
        )

        filters = ttk.Frame(self, style="Page.TFrame")
        filters.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(filters, text="Period", style="SectionTitle.TLabel").pack(side="left", padx=(0, 10))
        self.period = tk.StringVar(value="Today")
        period_picker = ttk.Combobox(
            filters, textvariable=self.period,
            values=("Today", "This week", "This month", "This year", "All time"),
            state="readonly", width=16,
        )
        period_picker.pack(side="left")
        period_picker.bind("<<ComboboxSelected>>", lambda _event: self.refresh())
        ttk.Label(filters, text="Search name, phone, or bill no.", style="Muted.TLabel").pack(
            side="left", padx=(20, 8)
        )
        self.search = tk.StringVar()
        ttk.Entry(filters, textvariable=self.search, width=26).pack(side="left", ipady=3)
        ttk.Button(filters, text="Clear", command=lambda: self.search.set("")).pack(
            side="left", padx=(6, 0)
        )
        self.search.trace_add("write", lambda *_: self.refresh())
        ttk.Button(
            filters, text="Export to Excel", style="Accent.TButton", command=self.export_report
        ).pack(side="right")

        summary = ttk.Frame(self, style="Card.TFrame", padding=(14, 10))
        summary.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        self.summary_label = ttk.Label(summary, text="", style="SectionTitle.TLabel")
        self.summary_label.pack(anchor="w")

        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=3, column=0, sticky="nsew")
        products_tab = ttk.Frame(self.tabs, style="Page.TFrame", padding=(0, 10, 0, 0))
        bills_tab = ttk.Frame(self.tabs, style="Page.TFrame", padding=(0, 10, 0, 0))
        self.tabs.add(products_tab, text="Products sold")
        self.tabs.add(bills_tab, text="Bills")

        product_holder, self.products_tree = make_tree(
            products_tab,
            (("product", "Product", 350), ("quantity", "Units sold", 110),
             ("bills", "Bills containing product", 180)),
            height=16,
        )
        product_holder.pack(fill="both", expand=True)
        holder, self.tree = make_tree(
            bills_tab,
            (("bill", "Bill number", 150), ("customer", "Customer", 135),
             ("phone", "Phone", 120), ("payment", "Paid by", 105), ("items", "Items", 65),
             ("total", "Total", 110), ("date", "Date", 120)),
            height=16,
        )
        holder.pack(fill="both", expand=True)
        self.refresh()

    def refresh(self):
        period = self.period.get()
        query = self.search.get().strip()
        sales = self.database.sales_for_period(period, search=query)
        products = self.database.product_sales_for_period(period, search=query)
        self.tree.delete(*self.tree.get_children())
        self.products_tree.delete(*self.products_tree.get_children())
        total = Decimal("0.00")
        unit_count = 0
        for index, sale in enumerate(sales):
            try:
                sale_total = Decimal(sale["total"])
            except (InvalidOperation, ValueError, TypeError, AttributeError):
                sale_total = Decimal("0")
            item_count = sum(
                quantity for _item_id, _name, quantity in decode_sale_items(sale["items"], sale["receipt"])
            )
            total += sale_total
            unit_count += item_count
            self.tree.insert(
                "", "end", iid=str(index),
                values=(
                    sale["bill_number"], sale["customer"], sale["phone"], sale["payment_method"],
                    item_count, format_money(sale_total), sale["date"],
                ),
            )
        summary_text = (
            f"{period}  ·  {len(sales)} bills  ·  {unit_count} units sold  ·  {format_money(total)} total sales"
        )
        if query:
            summary_text += f"  ·  Search: {query}"
        self.summary_label.configure(text=summary_text)
        for index, product in enumerate(products):
            self.products_tree.insert(
                "", "end", iid=str(index),
                values=(product["name"], product["quantity"], product["bills"]),
            )

    def export_report(self):
        period = self.period.get()
        query = self.search.get().strip()
        default_name = f"sales-{period.lower().replace(' ', '-')}-{date.today():%Y-%m-%d}.xlsx"
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save sales report",
            defaultextension=".xlsx",
            initialfile=default_name,
            filetypes=(("Excel workbook", "*.xlsx"),),
        )
        if not path:
            return

        sales = self.database.sales_for_period(period, search=query)
        products = self.database.product_sales_for_period(period, search=query)
        item_names = {str(item["id"]): item["name"] for item in self.database.list_items()}
        bill_rows = []
        total = Decimal("0.00")
        unit_count = 0
        for sale in sales:
            lines = decode_sale_items(sale["items"], sale["receipt"])
            unit_count += sum(quantity for _item_id, _name, quantity in lines)
            items_text = "; ".join(
                f"{name or item_names.get(item_id) or f'Removed product #{item_id}'} x {quantity}"
                for item_id, name, quantity in lines
            )
            try:
                sale_total = Decimal(sale["total"])
            except (InvalidOperation, ValueError, TypeError):
                sale_total = Decimal("0.00")
            total += sale_total
            bill_rows.append([
                sale["date"], sale["bill_number"], sale["customer"], sale["address"],
                sale["phone"], sale["payment_method"], items_text, sale_total,
            ])

        start, end = sales_period_bounds(period)
        date_range = (
            f"{start.isoformat()} to {end.isoformat()}"
            if start is not None and end is not None else "All recorded dates"
        )
        report_rows = [
            [f"Sales report · {period}"],
            ["Period", period, "Date range", date_range, "Generated", date.today().isoformat(),
             "Search", query or "All bills"],
            ["Total sales", total, "Bills", len(sales), "Units sold", unit_count],
            ["PRODUCT SALES", "", "", "", "BILL DETAILS", "", "", "", "", "", "", ""],
            ["Product", "Units sold", "Bills containing product", "", "Date", "Bill number",
             "Customer", "Address", "Phone", "Paid by", "Items", "Total"],
        ]
        for index in range(max(len(products), len(bill_rows))):
            product_columns = (
                [products[index]["name"], products[index]["quantity"], products[index]["bills"]]
                if index < len(products) else ["", "", ""]
            )
            bill_columns = bill_rows[index] if index < len(bill_rows) else ["", "", "", "", "", "", "", ""]
            report_rows.append([*product_columns, "", *bill_columns])
        amount_cells = {"B3"}
        amount_cells.update(f"L{row}" for row in range(6, 6 + len(bill_rows)))
        wrapped_cells = {
            f"{column}{row}"
            for row in range(6, 6 + max(len(products), len(bill_rows)))
            for column in ("A", "G", "H", "I", "K")
        }
        try:
            write_excel_workbook(
                path,
                (("Sales Report", report_rows),),
                section_rows={"Sales Report": (4,)},
                strong_header_rows={"Sales Report": (5,)},
                currency_cells={"Sales Report": amount_cells},
                wrap_cells={"Sales Report": wrapped_cells},
                freeze_rows={"Sales Report": 5},
                body_start_rows={"Sales Report": 6},
                column_widths={
                    "Sales Report": {
                        1: 26, 2: 13, 3: 24, 4: 3, 5: 13, 6: 20,
                        7: 22, 8: 26, 9: 16, 10: 16, 11: 42, 12: 16,
                    }
                },
                print_title_rows={"Sales Report": (4, 5)},
                row_heights={"Sales Report": {1: 30, 4: 24, 5: 38}},
            )
        except OSError as error:
            messagebox.showerror("Could not save report", str(error), parent=self)
            return
        messagebox.showinfo("Report saved", f"Excel report saved to:\n{path}", parent=self)


def show_receipt_preview(parent, receipt: str, receipt_path: str):
    """Preview a compact, print-ready customer receipt."""
    dialog = tk.Toplevel(parent)
    dialog.title("Receipt preview")
    dialog.configure(background="#f4f7f8")
    dialog.transient(parent.winfo_toplevel())
    dialog.resizable(False, False)
    dialog.grab_set()
    panel = ttk.Frame(dialog, style="Page.TFrame", padding=20)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="Receipt preview", style="Muted.TLabel").pack(anchor="center", pady=(0, 10))
    receipt_height = min(max(len(receipt.splitlines()), 12), 28)
    receipt_frame = ttk.Frame(panel, style="Page.TFrame")
    receipt_frame.pack(anchor="center")
    preview = tk.Text(
        receipt_frame, width=52, height=receipt_height, wrap="none", font=("Consolas", 10),
        background="#ffffff", foreground="#1f2937", relief="solid", borderwidth=1,
        padx=18, pady=14,
    )
    preview.pack(side="left")
    if len(receipt.splitlines()) > receipt_height:
        scrollbar = ttk.Scrollbar(receipt_frame, orient="vertical", command=preview.yview)
        scrollbar.pack(side="right", fill="y")
        preview.configure(yscrollcommand=scrollbar.set)
    preview.insert("1.0", receipt)
    preview.configure(state="disabled")

    def print_bill():
        if not receipt_path:
            messagebox.showerror(
                "Receipt file unavailable",
                "The bill is saved in the database, but its receipt file could not be created.",
                parent=dialog,
            )
            return
        try:
            start_file = getattr(os, "startfile", None)
            if start_file is not None:
                start_file(receipt_path, "print")
            else:
                printer = shutil.which("lp") or shutil.which("lpr")
                if not printer:
                    raise OSError("No system print command is available on this computer.")
                subprocess.run([printer, receipt_path], check=True, timeout=30, capture_output=True, text=True)
        except (OSError, subprocess.SubprocessError) as error:
            messagebox.showerror("Could not print bill", str(error), parent=dialog)

    actions = ttk.Frame(panel, style="Page.TFrame")
    actions.pack(fill="x", pady=(12, 0))
    ttk.Button(actions, text="Close", command=dialog.destroy).pack(side="right")
    ttk.Button(actions, text="Print bill", style="Accent.TButton", command=print_bill).pack(
        side="right", padx=(0, 8)
    )
