"""Shared visual helpers for the Tkinter screens."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from tkinter import ttk


INK = "#1f2937"
MUTED = "#687386"
TEAL = "#0f766e"
PALE = "#f4f7f8"
WHITE = "#ffffff"
LINE = "#e3e9ec"


def format_money(value: object) -> str:
    try:
        amount = Decimal(str(value or "0"))
    except (InvalidOperation, ValueError, TypeError):
        amount = Decimal("0")
    return f"₹{amount:,.2f}"


def make_tree(parent, columns: tuple[tuple[str, str, int], ...], *, height: int = 12):
    """Create a consistently styled Treeview with a vertical scrollbar."""
    holder = ttk.Frame(parent, style="Card.TFrame")
    holder.rowconfigure(0, weight=1)
    holder.columnconfigure(0, weight=1)
    names = tuple(column[0] for column in columns)
    tree = ttk.Treeview(holder, columns=names, show="headings", height=height)
    for key, title, width in columns:
        tree.heading(key, text=title)
        tree.column(key, width=width, minwidth=max(60, width // 2), anchor="w", stretch=True)
    scrollbar = ttk.Scrollbar(holder, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    return holder, tree


def add_page_heading(parent, title: str, subtitle: str):
    heading = ttk.Frame(parent, style="Page.TFrame")
    ttk.Label(heading, text=title, style="PageTitle.TLabel").pack(anchor="w")
    ttk.Label(heading, text=subtitle, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))
    return heading
