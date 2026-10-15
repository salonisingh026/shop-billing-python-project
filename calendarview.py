"""Calendar for marking store festivals, holidays, and other busy dates."""

from __future__ import annotations

import calendar
from datetime import date
import tkinter as tk
from tkinter import messagebox, ttk

from database import StoreDatabase
from ui import add_page_heading, make_tree


class CalendarPage(ttk.Frame):
    def __init__(self, parent, database: StoreDatabase):
        super().__init__(parent, style="Page.TFrame", padding=24)
        self.database = database
        today = date.today()
        self.display_year = today.year
        self.display_month = today.month
        self.selection_start: date | None = None
        self.selection_end: date | None = None
        self.event_name = tk.StringVar()
        self.stock_tasks = [tk.StringVar() for _ in range(5)]
        self.events: list[dict] = []
        self.month_events: list[tuple[date, date, str]] = []

        style = ttk.Style(self)
        style.configure("Calendar.TButton", padding=(3, 9))
        style.configure("CalendarMarked.TButton", padding=(3, 9), foreground="#0f766e")
        style.configure("CalendarMarked.TButton", background="#d8eeea")
        style.map("CalendarMarked.TButton", background=[("active", "#c5e4df")])
        style.configure("CalendarToday.TButton", padding=(3, 9), foreground="#0f766e")
        style.configure("CalendarToday.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("CalendarEmpty.TLabel", background="#ffffff")
        style.configure("Calendar.Treeview", rowheight=26)
        style.configure("Calendar.Treeview.Heading", rowheight=32)

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        add_page_heading(
            self,
            "Calendar & special dates",
            "Mark festivals, Sundays, and busy periods so you can plan stock ahead.",
        ).grid(row=0, column=0, sticky="ew", pady=(0, 18))

        content = ttk.Frame(self, style="Page.TFrame")
        content.grid(row=1, column=0, sticky="nsew")
        content.rowconfigure(0, weight=1)
        content.columnconfigure(0, weight=3, uniform="calendar")
        content.columnconfigure(1, weight=2, uniform="calendar")

        calendar_card = ttk.Frame(content, style="Card.TFrame", padding=16)
        calendar_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        calendar_card.columnconfigure(0, weight=1)
        calendar_card.rowconfigure(2, weight=1)

        month_bar = ttk.Frame(calendar_card, style="Card.TFrame")
        month_bar.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        month_bar.columnconfigure(1, weight=1)
        ttk.Button(month_bar, text="‹", width=4, command=self.previous_month).grid(row=0, column=0)
        self.month_label = ttk.Label(month_bar, text="", style="SectionTitle.TLabel", anchor="center")
        self.month_label.grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(month_bar, text="›", width=4, command=self.next_month).grid(row=0, column=2)

        weekdays = ttk.Frame(calendar_card, style="Card.TFrame")
        weekdays.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        for column, label in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            weekdays.columnconfigure(column, weight=1, uniform="weekday")
            ttk.Label(weekdays, text=label, anchor="center", style="Muted.TLabel").grid(
                row=0, column=column, sticky="ew", padx=2
            )

        self.calendar_grid = ttk.Frame(calendar_card, style="Card.TFrame")
        self.calendar_grid.grid(row=2, column=0, sticky="nsew")
        for column in range(7):
            self.calendar_grid.columnconfigure(column, weight=1, uniform="day")

        ttk.Label(
            calendar_card,
            text="Click a start date, then an end date. Save after one click to mark a single day.",
            style="Muted.TLabel", wraplength=550,
        ).grid(row=3, column=0, sticky="w", pady=(10, 0))

        side = ttk.Frame(content, style="Card.TFrame", padding=16)
        side.grid(row=0, column=1, sticky="nsew")
        side.rowconfigure(0, weight=1)
        side.columnconfigure(0, weight=1)
        tabs = ttk.Notebook(side)
        tabs.grid(row=0, column=0, sticky="nsew")
        plan_tab = ttk.Frame(tabs, style="Page.TFrame", padding=12)
        events_tab = ttk.Frame(tabs, style="Page.TFrame", padding=12)
        tabs.add(plan_tab, text="Plan date")
        tabs.add(events_tab, text="Saved events")

        plan_tab.columnconfigure(0, weight=1)
        ttk.Label(plan_tab, text="Mark a date or range", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )
        self.range_label = ttk.Label(plan_tab, text="Select a date on the calendar.", style="Muted.TLabel")
        self.range_label.grid(row=1, column=0, sticky="w", pady=(0, 10))
        ttk.Label(plan_tab, text="Event name").grid(row=2, column=0, sticky="w", pady=(0, 4))
        event_entry = ttk.Entry(plan_tab, textvariable=self.event_name)
        event_entry.grid(row=3, column=0, sticky="ew", ipady=4)
        event_entry.bind("<Return>", lambda _event: self.save_event())
        ttk.Label(plan_tab, text="Stock planning work list").grid(
            row=4, column=0, sticky="w", pady=(10, 4)
        )
        tasks = ttk.Frame(plan_tab, style="Page.TFrame")
        tasks.grid(row=5, column=0, sticky="ew")
        tasks.columnconfigure(1, weight=1)
        for index, variable in enumerate(self.stock_tasks, start=1):
            ttk.Label(tasks, text=f"{index}.").grid(row=index - 1, column=0, sticky="w", padx=(0, 8), pady=2)
            ttk.Entry(tasks, textvariable=variable).grid(row=index - 1, column=1, sticky="ew", ipady=3, pady=2)
        ttk.Button(plan_tab, text="Save date", style="Accent.TButton", command=self.save_event).grid(
            row=6, column=0, sticky="ew", pady=(10, 0), ipady=3
        )

        events_tab.columnconfigure(0, weight=1)
        events_tab.rowconfigure(1, weight=1)
        ttk.Label(events_tab, text="Saved events", style="SectionTitle.TLabel").grid(
            row=0, column=0, sticky="nw", pady=(0, 8)
        )
        holder, self.events_tree = make_tree(
            events_tab,
            (("name", "Event", 190), ("dates", "Date or range", 180)),
            height=16,
        )
        holder.grid(row=1, column=0, sticky="nsew")
        self.events_tree.configure(style="Calendar.Treeview")
        self.event_details = ttk.Label(
            events_tab, text="Select a saved event to view its five work-list rows.", style="Muted.TLabel",
            wraplength=370, justify="left",
        )
        self.event_details.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        actions = ttk.Frame(events_tab, style="Page.TFrame")
        actions.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Delete selected", command=self.delete_selected).pack(side="right")
        self.events_tree.bind("<<TreeviewSelect>>", self.show_selected_event)

        self.refresh_events()

    def previous_month(self):
        if self.display_month == 1:
            self.display_year -= 1
            self.display_month = 12
        else:
            self.display_month -= 1
        self.render_month()

    def next_month(self):
        if self.display_month == 12:
            self.display_year += 1
            self.display_month = 1
        else:
            self.display_month += 1
        self.render_month()

    def choose_date(self, selected: date):
        if self.selection_start is None or self.selection_end is not None:
            self.selection_start = selected
            self.selection_end = None
        elif selected < self.selection_start:
            self.selection_end = self.selection_start
            self.selection_start = selected
        else:
            self.selection_end = selected
        self.update_range_label()
        self.render_month()

    def update_range_label(self):
        if self.selection_start is None:
            text = "Select a date on the calendar."
        elif self.selection_end is None:
            text = f"Start: {self.selection_start:%d %b %Y} · choose an end date or save for one day."
        else:
            text = f"{self.selection_start:%d %b %Y} – {self.selection_end:%d %b %Y}"
        self.range_label.configure(text=text)

    def render_month(self):
        self.month_label.configure(text=f"{calendar.month_name[self.display_month]} {self.display_year}")
        for child in self.calendar_grid.winfo_children():
            child.destroy()
        marked_dates: set[date] = set()
        for start, end, _name in self.month_events:
            month_start = date(self.display_year, self.display_month, 1)
            month_end = date(
                self.display_year, self.display_month,
                calendar.monthrange(self.display_year, self.display_month)[1],
            )
            if end < month_start or start > month_end:
                continue
            first = max(start, month_start)
            last = min(end, month_end)
            for day_offset in range((last - first).days + 1):
                marked_dates.add(first.fromordinal(first.toordinal() + day_offset))

        today = date.today()
        for row, week in enumerate(calendar.monthcalendar(self.display_year, self.display_month)):
            for column, day in enumerate(week):
                if day == 0:
                    ttk.Label(self.calendar_grid, text="", style="CalendarEmpty.TLabel").grid(
                        row=row, column=column, sticky="nsew", padx=2, pady=2
                    )
                    continue
                current = date(self.display_year, self.display_month, day)
                selected = (
                    self.selection_start is not None
                    and self.selection_start <= current <= (self.selection_end or self.selection_start)
                )
                label = f"{day} *" if current in marked_dates else str(day)
                button_style = "Accent.TButton" if selected else (
                    "CalendarMarked.TButton" if current in marked_dates else (
                        "CalendarToday.TButton" if current == today else "Calendar.TButton"
                    )
                )
                ttk.Button(
                    self.calendar_grid, text=label, style=button_style,
                    command=lambda selected_date=current: self.choose_date(selected_date),
                ).grid(row=row, column=column, sticky="nsew", padx=2, pady=2)
        for row in range(6):
            self.calendar_grid.rowconfigure(row, weight=1)

    def refresh_events(self):
        self.events = self.database.calendar_events()
        self.month_events = []
        self.events_tree.delete(*self.events_tree.get_children())
        for event in self.events:
            try:
                start = date.fromisoformat(event["start_date"])
                end = date.fromisoformat(event["end_date"])
            except (TypeError, ValueError):
                continue
            self.month_events.append((start, end, event["event_name"]))
            dates = start.strftime("%d %b %Y") if start == end else f"{start:%d %b %Y} – {end:%d %b %Y}"
            self.events_tree.insert(
                "", "end", iid=str(event["id"]), values=(event["event_name"], dates)
            )
        self.render_month()

    def save_event(self):
        if self.selection_start is None:
            messagebox.showinfo("Choose a date", "Select a date on the calendar first.", parent=self)
            return
        try:
            stock_note = "\n".join(
                f"{index}. {task.get().strip()}"
                for index, task in enumerate(self.stock_tasks, start=1)
                if task.get().strip()
            )
            event_id = self.database.add_calendar_event(
                self.event_name.get(), self.selection_start, self.selection_end or self.selection_start,
                stock_note,
            )
        except ValueError as error:
            messagebox.showerror("Could not save event", str(error), parent=self)
            return
        self.event_name.set("")
        for task in self.stock_tasks:
            task.set("")
        self.selection_start = self.selection_end = None
        self.update_range_label()
        self.refresh_events()
        self.events_tree.see(str(event_id))

    def show_selected_event(self, _event=None):
        selection = self.events_tree.selection()
        if not selection:
            return
        event = next((row for row in self.events if str(row["id"]) == selection[0]), None)
        if event is None:
            return
        work_list = event.get("stock_note", "").strip() or "No work-list items were added."
        self.event_details.configure(text=f"{event['event_name']}\n{work_list}")

    def delete_selected(self):
        selection = self.events_tree.selection()
        if not selection:
            messagebox.showinfo("Choose an event", "Select an event to delete.", parent=self)
            return
        if not messagebox.askyesno("Delete event", "Delete the selected calendar event?", parent=self):
            return
        try:
            self.database.delete_calendar_event(int(selection[0]))
        except ValueError as error:
            messagebox.showerror("Could not delete event", str(error), parent=self)
            return
        self.refresh_events()
        self.event_details.configure(text="Select a saved event to view its five work-list rows.")
