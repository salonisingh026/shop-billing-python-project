"""Expiry date monitoring screen."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from database import StoreDatabase
from ui import add_page_heading, make_tree


class ExpiryPage(ttk.Frame):
    def __init__(self, parent, database: StoreDatabase):
        super().__init__(parent, style="Page.TFrame", padding=24)
        self.database = database
        self.status = tk.StringVar(value="All items")
        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        add_page_heading(
            self, "Expiry watch", "Find expired products and stock due to expire in the next 30 days."
        ).grid(row=0, column=0, sticky="ew", pady=(0, 20))
        toolbar = ttk.Frame(self, style="Page.TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(toolbar, text="Show").pack(side="left", padx=(0, 8))
        picker = ttk.Combobox(
            toolbar, textvariable=self.status, state="readonly", width=24,
            values=("All items", "Expired", "Expiring in 30 days"),
        )
        picker.pack(side="left")
        picker.bind("<<ComboboxSelected>>", lambda _event: self.refresh())

        holder, self.tree = make_tree(
            self,
            (("name", "Product", 220), ("category", "Category", 145),
             ("quantity", "In stock", 92), ("expiry", "Expiry date", 125),
             ("days", "Days left", 92), ("status", "Status", 140)),
            height=18,
        )
        holder.grid(row=2, column=0, sticky="nsew")
        self.tree.tag_configure("expired", foreground="#b42318")
        self.tree.tag_configure("soon", foreground="#a15c07")
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for item in self.database.expiring_items(self.status.get()):
            days_left = item["days_left"]
            if days_left is None:
                days = "—"
                tag = ""
            elif days_left < 0:
                days = f"{abs(days_left)} days ago"
                tag = "expired"
            else:
                days = str(days_left)
                tag = "soon" if days_left <= 30 else ""
            self.tree.insert(
                "", "end", values=(item["name"], item["category"] or "—", item["quantity"],
                                    item["expiry"] or "—", days, item["status"]), tags=(tag,),
            )
