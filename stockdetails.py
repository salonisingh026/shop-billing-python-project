"""Inventory screens: searchable stock, add, edit, and remove products."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from database import StoreDatabase, parse_item_form
from ui import INK, MUTED, TEAL, WHITE, add_page_heading, format_money, make_tree


class InventoryPage(ttk.Frame):
    def __init__(self, parent, database: StoreDatabase, on_change=None):
        super().__init__(parent, style="Page.TFrame", padding=24)
        self.database = database
        self.on_change = on_change or (lambda: None)
        self.search = tk.StringVar()
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        add_page_heading(
            self, "Inventory", "Manage products, quantities, prices, and expiry dates."
        ).grid(row=0, column=0, sticky="ew", pady=(0, 22))

        toolbar = ttk.Frame(self, style="Page.TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        toolbar.columnconfigure(0, weight=1)
        search = ttk.Entry(toolbar, textvariable=self.search, width=34)
        search.grid(row=0, column=0, sticky="w", ipady=5)
        search.insert(0, "")
        self.search.trace_add("write", lambda *_: self.refresh())
        ttk.Button(toolbar, text="Add product", style="Accent.TButton", command=self.add_item).grid(
            row=0, column=1, padx=(12, 0), ipady=4
        )
        ttk.Button(toolbar, text="Edit selected", command=self.edit_item).grid(
            row=0, column=2, padx=(8, 0), ipady=4
        )
        ttk.Button(toolbar, text="Delete", style="Danger.TButton", command=self.delete_item).grid(
            row=0, column=3, padx=(8, 0), ipady=4
        )

        holder, self.tree = make_tree(
            self,
            (("id", "ID", 58), ("name", "Product", 210), ("category", "Category", 130),
             ("quantity", "In stock", 85), ("cost", "Unit price", 100),
             ("expiry", "Expiry date", 118), ("supplier", "Supplier", 160)),
            height=18,
        )
        holder.grid(row=2, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _event: self.edit_item())
        self.tree.bind("<Return>", lambda _event: self.edit_item())
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for item in self.database.list_items(self.search.get()):
            self.tree.insert(
                "", "end", iid=str(item["id"]),
                values=(item["id"], item["name"], item["category"] or "—",
                        item["quantity"], format_money(item["cost"]), item["expiry"] or "—",
                        item["supplier"] or "—"),
            )

    def selected_item(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Select a product", "Choose a product from the inventory first.", parent=self)
            return None
        item_id = int(selection[0])
        return next((item for item in self.database.list_items() if item["id"] == item_id), None)

    def add_item(self):
        self._open_editor()

    def edit_item(self):
        item = self.selected_item()
        if item:
            self._open_editor(item)

    def delete_item(self):
        item = self.selected_item()
        if not item:
            return
        if not messagebox.askyesno(
            "Delete product", f"Remove {item['name']} from the inventory?", parent=self
        ):
            return
        try:
            self.database.delete_item(item["id"])
        except (ValueError, OSError) as error:
            messagebox.showerror("Could not delete product", str(error), parent=self)
            return
        self.refresh()
        self.on_change()

    def _open_editor(self, item=None):
        dialog = tk.Toplevel(self)
        dialog.title("Edit product" if item else "Add product")
        dialog.configure(background="#f4f7f8")
        dialog.resizable(False, False)
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.columnconfigure(1, weight=1)

        ttk.Label(dialog, text="Product details", font=("Segoe UI", 17, "bold"), foreground=INK).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=24, pady=(22, 4)
        )
        ttk.Label(
            dialog, text="Expiry dates use YYYY-MM-DD. Leave the date blank if it is not tracked.",
            foreground=MUTED, wraplength=380,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=24, pady=(0, 16))

        defaults = [
            item["name"] if item else "", item["category"] if item else "",
            str(item["quantity"]) if item else "0", str(item["cost"]) if item else "0.00",
            item["expiry"] if item else "", item["supplier"] if item else "",
        ]
        labels = ("Product name", "Category", "Quantity", "Unit price (₹)", "Expiry date", "Supplier")
        fields = []
        for row, (label, default) in enumerate(zip(labels, defaults), start=2):
            ttk.Label(dialog, text=label, foreground=INK).grid(
                row=row, column=0, sticky="w", padx=(24, 14), pady=6
            )
            field = ttk.Entry(dialog, width=34)
            field.insert(0, str(default or ""))
            field.grid(row=row, column=1, sticky="ew", padx=(0, 24), pady=6, ipady=4)
            fields.append(field)

        def save():
            try:
                values = parse_item_form(*(field.get() for field in fields))
                if item:
                    self.database.update_item(item["id"], *values)
                else:
                    self.database.add_item(*values)
            except (ValueError, OSError) as error:
                messagebox.showerror("Check product details", str(error), parent=dialog)
                return
            dialog.destroy()
            self.refresh()
            self.on_change()

        actions = ttk.Frame(dialog, style="Page.TFrame", padding=(24, 16, 24, 22))
        actions.grid(row=8, column=0, columnspan=2, sticky="ew")
        ttk.Button(actions, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(actions, text="Save product", style="Accent.TButton", command=save).pack(
            side="right", padx=(0, 8)
        )
        fields[0].focus_set()
        dialog.bind("<Return>", lambda _event: save())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_rootx() + (self.winfo_toplevel().winfo_width() - dialog.winfo_width()) // 2
        y = self.winfo_toplevel().winfo_rooty() + (self.winfo_toplevel().winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
