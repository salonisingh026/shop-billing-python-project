"""SQLite storage and business rules for Singhjee Cold Drinks & More."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import textwrap
from typing import Any, Iterator
from uuid import uuid4


ROOT = Path(__file__).resolve().parent
DEFAULT_DATABASE = ROOT / "data" / "grocery.sqlite"
LOW_STOCK_THRESHOLD = 10
PASSWORD_ITERATIONS = 310_000
PAYMENT_METHODS = ("Cash", "Credit card", "Debit card", "UPI")
DEFAULT_LOGIN_USERNAME = "goldsingh026"
DEFAULT_LOGIN_PASSWORD = "singhjee2406"
COLD_DRINK_SAMPLE_ITEMS = (
    ("Coca-Cola 300 ml", "Soft drinks", 48, "40.00", 150, "Hindustan Coca-Cola Beverages"),
    ("Coca-Cola 750 ml", "Soft drinks", 30, "75.00", 150, "Hindustan Coca-Cola Beverages"),
    ("Coca-Cola 2 L", "Soft drinks", 12, "120.00", 150, "Hindustan Coca-Cola Beverages"),
    ("Sprite 300 ml", "Soft drinks", 42, "40.00", 150, "Hindustan Coca-Cola Beverages"),
    ("Sprite 750 ml", "Soft drinks", 24, "75.00", 150, "Hindustan Coca-Cola Beverages"),
    ("Thums Up 300 ml", "Soft drinks", 42, "40.00", 150, "Hindustan Coca-Cola Beverages"),
    ("Thums Up 750 ml", "Soft drinks", 24, "75.00", 150, "Hindustan Coca-Cola Beverages"),
    ("Fanta Orange 300 ml", "Soft drinks", 36, "40.00", 150, "Hindustan Coca-Cola Beverages"),
    ("Limca Lemon 300 ml", "Soft drinks", 30, "40.00", 150, "Hindustan Coca-Cola Beverages"),
    ("Pepsi 300 ml", "Soft drinks", 36, "40.00", 150, "PepsiCo India"),
    ("Pepsi 750 ml", "Soft drinks", 24, "75.00", 150, "PepsiCo India"),
    ("Mountain Dew 300 ml", "Soft drinks", 30, "40.00", 150, "PepsiCo India"),
    ("7UP 300 ml", "Soft drinks", 30, "40.00", 150, "PepsiCo India"),
    ("Appy Fizz Apple 250 ml", "Fruit drinks", 30, "25.00", 180, "Parle Agro"),
    ("Real Mixed Fruit Juice 1 L", "Fruit drinks", 12, "120.00", 210, "Dabur India"),
    ("Tropicana Orange Juice 1 L", "Fruit drinks", 12, "130.00", 210, "PepsiCo India"),
    ("Bisleri Water 500 ml", "Packaged water", 60, "20.00", 240, "Bisleri International"),
    ("Bisleri Water 1 L", "Packaged water", 36, "30.00", 240, "Bisleri International"),
    ("Red Bull Energy Drink 250 ml", "Energy drinks", 18, "125.00", 240, "Red Bull India"),
    ("Sting Energy Drink 250 ml", "Energy drinks", 30, "25.00", 210, "PepsiCo India"),
    ("Amul Kool Kesar 180 ml", "Dairy drinks", 24, "25.00", 90, "Amul"),
    ("Amul Kool Badam 180 ml", "Dairy drinks", 24, "25.00", 90, "Amul"),
    ("Mother Dairy Sweet Lassi 200 ml", "Dairy drinks", 24, "25.00", 45, "Mother Dairy"),
    ("Singhjee Cold Coffee 250 ml", "Cold coffee", 18, "60.00", 30, "Singhjee Store"),
    ("Singhjee Mint Lime Cooler 300 ml", "Mocktails", 18, "50.00", 7, "Singhjee Store"),
)


def parse_date(value: str | None) -> date | None:
    """Read the ISO dates used by this version and common dates in older data."""
    if not value:
        return None
    value = str(value).strip()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, pattern).date()
        except ValueError:
            continue
    return None


def decode_sale_items(value: str | None, receipt: str | None = None) -> list[tuple[str, str, int]]:
    """Read item records saved by this version or the legacy ID-to-quantity format."""
    try:
        records = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if isinstance(records, dict):
        records = [{"id": item_id, "quantity": quantity} for item_id, quantity in records.items()]
    if not isinstance(records, list):
        return []

    if records and any(not isinstance(record, dict) for record in records):
        # The original app saved only a list of product IDs in bill.items. Recover
        # names and quantities from its receipt text when that older format exists.
        receipt_lines: list[tuple[str, int]] = []
        if receipt:
            receipt_rows = receipt.splitlines()
            header_index = next(
                (index for index, line in enumerate(receipt_rows)
                 if "Product" in line and "Qty" in line and "Price" in line),
                None,
            )
            if header_index is not None:
                for line in receipt_rows[header_index + 2:]:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    if set(stripped) == {"-"}:
                        break
                    fields = line.split()
                    if (
                        len(fields) >= 3
                        and re.fullmatch(r"\d+", fields[-2])
                        and re.fullmatch(r"\d+(?:\.\d+)?", fields[-1])
                    ):
                        receipt_lines.append((" ".join(fields[:-2]), int(fields[-2])))
        legacy_items = []
        for index, record in enumerate(records):
            item_id = str(record).strip()
            if index < len(receipt_lines):
                name, quantity = receipt_lines[index]
            elif not re.fullmatch(r"\d+", item_id):
                name, quantity = item_id, 1
                item_id = ""
            else:
                name, quantity = "", 1
            legacy_items.append((item_id, name, quantity))
        return legacy_items

    items: list[tuple[str, str, int]] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        try:
            quantity = int(record.get("quantity", 0))
        except (TypeError, ValueError):
            continue
        if quantity < 1:
            continue
        item_id = str(record.get("id", "")).strip()
        name = str(record.get("name", "")).strip()
        items.append((item_id, name, quantity))
    return items


def sales_period_bounds(period: str, target: date | None = None) -> tuple[date | None, date | None]:
    """Get inclusive date bounds for the sales page's calendar period choices."""
    target = target or date.today()
    if period == "Today":
        return target, target
    if period == "This week":
        start = target - timedelta(days=target.weekday())
        return start, start + timedelta(days=6)
    if period == "This month":
        start = target.replace(day=1)
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        return start, end
    if period == "This year":
        return target.replace(month=1, day=1), target.replace(month=12, day=31)
    if period == "All time":
        return None, None
    raise ValueError("Choose Today, This week, This month, This year, or All time.")


def format_receipt(
    customer: str, address: str, payment_method: str,
    line_items: list[tuple[str, int, Decimal]], total: Decimal,
    bill_number: str = "",
) -> str:
    """Format a compact customer receipt without exposing the saved phone number."""
    width = 46
    lines = ["SINGHJEE COLD DRINKS & MORE".center(width), "SALES RECEIPT".center(width), "=" * width]
    for label, value in (
        ("Customer name", customer),
        ("Address", address or "—"),
        ("Mode of payment", payment_method),
        ("Bill number", bill_number),
    ):
        if not value:
            continue
        prefix = f"{label}: "
        wrapped = textwrap.wrap(
            str(value), width=width - len(prefix), break_long_words=True, break_on_hyphens=False
        ) or ["—"]
        lines.append(prefix + wrapped[0])
        lines.extend(" " * len(prefix) + part for part in wrapped[1:])

    lines.extend(("-" * width, "ITEM", "QTY x RATE = AMOUNT", "-" * width))
    for name, quantity, _unit_price in line_items:
        wrapped_name = textwrap.wrap(
            str(name), width=width - 4, break_long_words=True, break_on_hyphens=False
        ) or ["Unnamed product"]
        lines.append(f"  {wrapped_name[0]}")
        lines.extend(f"  {part}" for part in wrapped_name[1:])
        unit_rate = _unit_price.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        line_total = (unit_rate * quantity).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        price_line = f"  {quantity} x ₹{unit_rate:,.2f} = ₹{line_total:,.2f}"
        if len(price_line) <= width:
            lines.append(price_line)
        else:
            lines.append(f"  {quantity} x ₹{unit_rate:,.2f}")
            lines.append(f"  Amount: ₹{line_total:,.2f}")

    amount = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_text = f"₹{amount:,.2f}"
    lines.extend(("-" * width, f"{'TOTAL COST':<32}{total_text:>14}", "=" * width, ""))
    lines.append("THANK YOU FOR SHOPPING WITH US!".center(width))
    lines.append("PLEASE VISIT AGAIN!".center(width))
    return "\n".join(lines) + "\n"


def _password_hash(password: str, salt: bytes | None = None) -> tuple[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return salt.hex(), digest.hex()


class StoreDatabase:
    """Small connection-per-operation repository that supports the legacy schema."""

    def __init__(self, path: str | Path | None = None) -> None:
        configured_path = path or os.environ.get("GROCERY_DB_PATH") or DEFAULT_DATABASE
        self.path = Path(configured_path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS grocerylist (
                    Item_No INTEGER PRIMARY KEY AUTOINCREMENT,
                    Item_Name TEXT NOT NULL,
                    Item_Type TEXT NOT NULL DEFAULT '',
                    Quantity_Remain INTEGER NOT NULL DEFAULT 0,
                    Item_Cost TEXT NOT NULL DEFAULT '0.00',
                    Expiry_Date TEXT NOT NULL DEFAULT '',
                    Manufactured_By TEXT NOT NULL DEFAULT ''
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS bill (
                    cusname TEXT, cusaddress TEXT, items TEXT, totalcost TEXT,
                    billingdate TEXT, billno TEXT, bill TEXT,
                    cusphone TEXT NOT NULL DEFAULT '',
                    payment_method TEXT NOT NULL DEFAULT 'Cash'
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS customer (
                    name TEXT NOT NULL, address TEXT NOT NULL, phone TEXT NOT NULL DEFAULT ''
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS stock_calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    stock_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    CHECK (start_date <= end_date)
                )"""
            )
            self._ensure_column(connection, "bill", "cusphone", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "bill", "payment_method", "TEXT NOT NULL DEFAULT 'Cash'")
            self._ensure_column(connection, "customer", "phone", "TEXT NOT NULL DEFAULT ''")
            self._repair_legacy_item_ids(connection)
            connection.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    salt TEXT NOT NULL,
                    password_hash TEXT NOT NULL
                )"""
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS app_settings (
                    setting_key TEXT PRIMARY KEY,
                    setting_value TEXT NOT NULL
                )"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_grocery_name ON grocerylist(Item_Name)")
            connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_grocery_item_no ON grocerylist(Item_No)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_bill_date ON bill(billingdate)")
            connection.execute("CREATE INDEX IF NOT EXISTS idx_customer_phone ON customer(phone)")
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_stock_calendar_dates ON stock_calendar_events(start_date, end_date)"
            )

            self._migrate_legacy_users(connection)
            self._sync_configured_login(connection)

            item_count = connection.execute("SELECT COUNT(*) FROM grocerylist").fetchone()[0]
            if not item_count:
                today = date.today()
                connection.executemany(
                    """INSERT INTO grocerylist
                       (Item_Name, Item_Type, Quantity_Remain, Item_Cost, Expiry_Date, Manufactured_By)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    [
                        (name, category, quantity, price,
                         (today + timedelta(days=expiry_days)).isoformat(), manufacturer)
                        for name, category, quantity, price, expiry_days, manufacturer
                        in COLD_DRINK_SAMPLE_ITEMS
                    ],
                )

    @staticmethod
    def _sync_configured_login(connection: sqlite3.Connection) -> None:
        """Apply changed source credentials once, without undoing UI password changes."""
        username = DEFAULT_LOGIN_USERNAME.strip()
        password = DEFAULT_LOGIN_PASSWORD
        if not username:
            raise ValueError("DEFAULT_LOGIN_USERNAME cannot be empty.")
        if len(password) < 8:
            raise ValueError("DEFAULT_LOGIN_PASSWORD must contain at least 8 characters.")

        settings = dict(connection.execute("SELECT setting_key, setting_value FROM app_settings"))
        saved_username = settings.get("login_config_username")
        saved_salt = settings.get("login_config_salt")
        saved_hash = settings.get("login_config_hash")
        configured_salt, configured_hash = _password_hash(password)

        if saved_username and saved_salt and saved_hash:
            previous_hash = _password_hash(password, bytes.fromhex(saved_salt))[1]
            username_changed = saved_username.casefold() != username.casefold()
            password_changed = not secrets.compare_digest(previous_hash, saved_hash)
            account = connection.execute(
                "SELECT username FROM users WHERE username = ? COLLATE NOCASE", (saved_username,)
            ).fetchone()

            if username_changed:
                collision = connection.execute(
                    "SELECT username FROM users WHERE username = ? COLLATE NOCASE", (username,)
                ).fetchone()
                if account and collision and collision[0].casefold() != account[0].casefold():
                    raise ValueError(f"The configured username {username!r} already belongs to another account.")

            if account:
                assignments = []
                values: list[str] = []
                if username_changed:
                    assignments.append("username = ?")
                    values.append(username)
                if password_changed:
                    assignments.extend(("salt = ?", "password_hash = ?"))
                    values.extend((configured_salt, configured_hash))
                if assignments:
                    values.append(account[0])
                    connection.execute(
                        f"UPDATE users SET {', '.join(assignments)} WHERE username = ?", values
                    )
            elif not connection.execute(
                "SELECT 1 FROM users WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone():
                connection.execute(
                    "INSERT INTO users (username, salt, password_hash) VALUES (?, ?, ?)",
                    (username, configured_salt, configured_hash),
                )
        else:
            # On first upgrade, make the configured login usable in an older database.
            connection.execute(
                """INSERT INTO users (username, salt, password_hash) VALUES (?, ?, ?)
                   ON CONFLICT(username) DO UPDATE SET salt = excluded.salt,
                                                       password_hash = excluded.password_hash""",
                (username, configured_salt, configured_hash),
            )

        connection.executemany(
            """INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?)
               ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value""",
            (
                ("login_config_username", username),
                ("login_config_salt", configured_salt),
                ("login_config_hash", configured_hash),
            ),
        )

    @staticmethod
    def _ensure_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    @staticmethod
    def _repair_legacy_item_ids(connection: sqlite3.Connection) -> None:
        """Give legacy inventory rows a unique positive ID before adding stock."""
        rows = connection.execute(
            "SELECT rowid AS row_id, Item_No FROM grocerylist ORDER BY rowid"
        ).fetchall()
        reserved: set[int] = set()
        for row in rows:
            try:
                item_id = int(row["Item_No"])
            except (TypeError, ValueError):
                continue
            if item_id > 0:
                reserved.add(item_id)

        used: set[int] = set()
        next_id = max(reserved, default=0) + 1
        for row in rows:
            try:
                item_id = int(row["Item_No"])
            except (TypeError, ValueError):
                item_id = 0
            if item_id > 0 and item_id not in used:
                used.add(item_id)
                continue
            while next_id in reserved or next_id in used:
                next_id += 1
            connection.execute(
                "UPDATE grocerylist SET Item_No = ? WHERE rowid = ?",
                (next_id, row["row_id"]),
            )
            used.add(next_id)
            next_id += 1

    @staticmethod
    def _migrate_legacy_users(connection: sqlite3.Connection) -> None:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if "logs" not in tables:
            return
        columns = {row[1] for row in connection.execute("PRAGMA table_info(logs)")}
        if not {"username", "password"}.issubset(columns):
            return
        existing = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if not existing:
            for row in connection.execute("SELECT username, password FROM logs"):
                username, password = row[0], row[1]
                if not username or password is None:
                    continue
                salt, digest = _password_hash(str(password))
                connection.execute(
                    "INSERT OR IGNORE INTO users (username, salt, password_hash) VALUES (?, ?, ?)",
                    (str(username), salt, digest),
                )
        # The old table stored passwords as readable text. Migrate it into users and remove it.
        connection.execute("DROP TABLE logs")

    def authenticate(self, username: str, password: str) -> bool:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT salt, password_hash FROM users WHERE username = ?", (username.strip(),)
            ).fetchone()
        if row is None:
            return False
        _, candidate = _password_hash(password, bytes.fromhex(row["salt"]))
        return secrets.compare_digest(candidate, row["password_hash"])

    def change_password(self, username: str, current_password: str, new_password: str) -> None:
        if not self.authenticate(username, current_password):
            raise ValueError("The current password is incorrect.")
        if len(new_password) < 8:
            raise ValueError("Choose a password with at least 8 characters.")
        salt, digest = _password_hash(new_password)
        with self.connection() as connection:
            connection.execute(
                "UPDATE users SET salt = ?, password_hash = ? WHERE username = ?",
                (salt, digest, username),
            )

    def list_items(self, search: str = "") -> list[dict[str, Any]]:
        query = """SELECT Item_No AS id, Item_Name AS name, Item_Type AS category,
                          Quantity_Remain AS quantity, Item_Cost AS cost,
                          Expiry_Date AS expiry, Manufactured_By AS supplier
                   FROM grocerylist"""
        parameters: tuple[Any, ...] = ()
        if search.strip():
            query += " WHERE Item_Name LIKE ? OR Item_Type LIKE ? OR Manufactured_By LIKE ?"
            pattern = f"%{search.strip()}%"
            parameters = (pattern, pattern, pattern)
        query += " ORDER BY Item_Name COLLATE NOCASE"
        with self.connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def add_item(
        self, name: str, category: str, quantity: int, cost: Decimal,
        expiry: date | None, supplier: str,
    ) -> int:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            item_id = connection.execute(
                "SELECT COALESCE(MAX(Item_No), 0) + 1 FROM grocerylist"
            ).fetchone()[0]
            cursor = connection.execute(
                """INSERT INTO grocerylist
                   (Item_No, Item_Name, Item_Type, Quantity_Remain, Item_Cost, Expiry_Date, Manufactured_By)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (item_id, name.strip(), category.strip(), quantity, self._money(cost),
                 expiry.isoformat() if expiry else "", supplier.strip()),
            )
            return int(item_id)

    def update_item(
        self, item_id: int, name: str, category: str, quantity: int, cost: Decimal,
        expiry: date | None, supplier: str,
    ) -> None:
        with self.connection() as connection:
            cursor = connection.execute(
                """UPDATE grocerylist
                   SET Item_Name = ?, Item_Type = ?, Quantity_Remain = ?, Item_Cost = ?,
                       Expiry_Date = ?, Manufactured_By = ?
                   WHERE Item_No = ?""",
                (name.strip(), category.strip(), quantity, self._money(cost),
                 expiry.isoformat() if expiry else "", supplier.strip(), item_id),
            )
            if not cursor.rowcount:
                raise ValueError("That stock item no longer exists.")

    def delete_item(self, item_id: int) -> None:
        with self.connection() as connection:
            cursor = connection.execute("DELETE FROM grocerylist WHERE Item_No = ?", (item_id,))
            if not cursor.rowcount:
                raise ValueError("That stock item no longer exists.")

    def calendar_events(self) -> list[dict[str, Any]]:
        """Return saved stock-planning calendar events with their optional notes."""
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT id, event_name, start_date, end_date, stock_note
                   FROM stock_calendar_events ORDER BY start_date, end_date, event_name COLLATE NOCASE"""
            ).fetchall()
        return [dict(row) for row in rows]

    def add_calendar_event(
        self, event_name: str, start_date: date, end_date: date, stock_note: str = "",
    ) -> int:
        event_name = event_name.strip()
        if not event_name:
            raise ValueError("Enter an event name.")
        if end_date < start_date:
            raise ValueError("The end date must be the same as or later than the start date.")
        with self.connection() as connection:
            cursor = connection.execute(
                """INSERT INTO stock_calendar_events
                   (event_name, start_date, end_date, stock_note)
                   VALUES (?, ?, ?, ?)""",
                (event_name, start_date.isoformat(), end_date.isoformat(), stock_note.strip()),
            )
            return int(cursor.lastrowid)

    def calendar_events_between(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        """List events overlapping the inclusive date range."""
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT id, event_name, start_date, end_date, stock_note
                   FROM stock_calendar_events
                   WHERE start_date <= ? AND end_date >= ?
                   ORDER BY start_date, end_date, event_name COLLATE NOCASE""",
                (end_date.isoformat(), start_date.isoformat()),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_calendar_event(self, event_id: int) -> None:
        with self.connection() as connection:
            cursor = connection.execute(
                "DELETE FROM stock_calendar_events WHERE id = ?", (event_id,)
            )
            if not cursor.rowcount:
                raise ValueError("That calendar event no longer exists.")

    def summary(self) -> dict[str, Any]:
        items = self.list_items()
        today = date.today()
        expired = 0
        expiring = 0
        for item in items:
            expiry = parse_date(item["expiry"])
            if expiry and expiry < today:
                expired += 1
            elif expiry and expiry <= today + timedelta(days=30):
                expiring += 1
        sales = self.sales_for_date(today)
        return {
            "item_count": len(items),
            "units": sum(self._integer(item["quantity"]) for item in items),
            "low_stock": sum(self._integer(item["quantity"]) <= LOW_STOCK_THRESHOLD for item in items),
            "expired": expired,
            "expiring": expiring,
            "today_total": sum((Decimal(sale["total"]) for sale in sales), Decimal("0")),
            "today_sales": len(sales),
            "recent_items": items[:6],
        }

    def expiring_items(self, status: str = "All items") -> list[dict[str, Any]]:
        today = date.today()
        matches: list[dict[str, Any]] = []
        for item in self.list_items():
            expiry = parse_date(item["expiry"])
            if expiry is None:
                item["days_left"] = None
                label = "No date"
            else:
                days_left = (expiry - today).days
                item["days_left"] = days_left
                label = "Expired" if days_left < 0 else "Expiring soon" if days_left <= 30 else "Fresh"
            item["status"] = label
            if status == "Expired" and label != "Expired":
                continue
            if status == "Expiring in 30 days" and label not in ("Expired", "Expiring soon"):
                continue
            matches.append(item)
        matches.sort(key=lambda item: (item["days_left"] is None, item["days_left"] or 0))
        return matches

    def sales_for_date(self, target: date | None = None) -> list[dict[str, Any]]:
        return self.sales_for_period("Today", target)

    def sales_for_period(
        self, period: str, target: date | None = None, search: str = "",
    ) -> list[dict[str, Any]]:
        """Return period bills, optionally searching customer, phone, or bill number."""
        start, end = sales_period_bounds(period, target)
        query = search.strip().casefold()
        phone_query = re.sub(r"\D", "", query)

        with self.connection() as connection:
            rows = connection.execute(
                """SELECT cusname, cusaddress, cusphone, payment_method, items,
                          totalcost, billingdate, billno, bill FROM bill"""
            ).fetchall()
        sales = []
        for row in rows:
            sale_date = parse_date(row["billingdate"])
            if sale_date is None or (start is not None and sale_date < start) or (end is not None and sale_date > end):
                continue
            customer = row["cusname"] or "Walk-in customer"
            phone = row["cusphone"] or ""
            bill_number = row["billno"] or ""
            if query and not (
                query in customer.casefold()
                or query in bill_number.casefold()
                or (phone_query and phone_query in re.sub(r"\D", "", phone))
            ):
                continue
            try:
                total = str(Decimal(str(row["totalcost"] or "0")))
            except InvalidOperation:
                total = "0"
            sales.append({
                "customer": customer,
                "address": row["cusaddress"] or "",
                "phone": phone,
                "payment_method": row["payment_method"] or "Cash",
                "items": row["items"] or "[]",
                "total": total,
                "date": row["billingdate"] or "",
                "bill_number": bill_number,
                "receipt": row["bill"] or "",
            })
        sales.sort(key=lambda sale: (parse_date(sale["date"]) or date.min, sale["bill_number"]), reverse=True)
        return sales

    def product_sales_for_period(
        self, period: str, target: date | None = None, search: str = "",
    ) -> list[dict[str, Any]]:
        """Summarize units sold by product, preserving names in new and future sales."""
        sales = self.sales_for_period(period, target, search)
        current_names = {str(item["id"]): item["name"] for item in self.list_items()}
        products: dict[str, dict[str, Any]] = {}
        for sale in sales:
            seen_in_bill: set[str] = set()
            for item_id, saved_name, quantity in decode_sale_items(sale["items"], sale["receipt"]):
                name = saved_name or current_names.get(item_id) or f"Removed product #{item_id}"
                key = item_id or name.casefold()
                product = products.setdefault(
                    key, {"name": name, "quantity": 0, "bills": 0}
                )
                product["quantity"] += quantity
                seen_in_bill.add(key)
            for key in seen_in_bill:
                products[key]["bills"] += 1
        return sorted(products.values(), key=lambda item: (-item["quantity"], item["name"].casefold()))

    def create_sale(
        self, customer: str, address: str, phone: str, payment_method: str,
        cart: dict[int, int],
    ) -> tuple[str, Decimal, str, str]:
        if not cart:
            raise ValueError("Add at least one product to the bill.")
        customer = customer.strip() or "Walk-in customer"
        address = address.strip()
        phone = normalize_phone(phone)
        if payment_method not in PAYMENT_METHODS:
            raise ValueError("Choose Cash, Credit card, Debit card, or UPI as the payment method.")
        line_items: list[tuple[int, str, int, Decimal]] = []
        total = Decimal("0.00")
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            for item_id, quantity in cart.items():
                if quantity < 1:
                    raise ValueError("Quantities must be at least one.")
                row = connection.execute(
                    """SELECT Item_Name, Quantity_Remain, Item_Cost
                       FROM grocerylist WHERE Item_No = ?""", (item_id,),
                ).fetchone()
                if row is None:
                    raise ValueError("A product in this bill has been removed. Refresh and try again.")
                available = self._integer(row["Quantity_Remain"])
                if quantity > available:
                    raise ValueError(f"Only {available} unit(s) of {row['Item_Name']} remain in stock.")
                try:
                    unit_price = Decimal(str(row["Item_Cost"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                except InvalidOperation as error:
                    raise ValueError(f"{row['Item_Name']} has an invalid price. Update its stock record first.") from error
                line_items.append((item_id, row["Item_Name"], quantity, unit_price))
                total += unit_price * quantity
                connection.execute(
                    "UPDATE grocerylist SET Quantity_Remain = ? WHERE Item_No = ?",
                    (available - quantity, item_id),
                )

            bill_number = f"{date.today():%Y%m%d}-{uuid4().hex[:6].upper()}"
            receipt = format_receipt(
                customer,
                address,
                payment_method,
                [(name, quantity, unit_price) for _item_id, name, quantity, unit_price in line_items],
                total,
                bill_number=bill_number,
            )
            connection.execute(
                """INSERT INTO bill
                   (cusname, cusaddress, cusphone, payment_method, items, totalcost, billingdate, billno, bill)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (customer, address, phone, payment_method,
                 json.dumps([
                     {"id": item_id, "name": name, "quantity": quantity}
                     for item_id, name, quantity, _unit_price in line_items
                 ]),
                 self._money(total), date.today().isoformat(), bill_number, receipt),
            )
            if customer != "Walk-in customer":
                connection.execute(
                    "INSERT INTO customer (name, address, phone) VALUES (?, ?, ?)",
                    (customer, address, phone),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        receipt_directory = self.path.parent / "receipts"
        try:
            receipt_directory.mkdir(parents=True, exist_ok=True)
            receipt_path = receipt_directory / f"receipt-{bill_number}.txt"
            receipt_path.write_text(receipt, encoding="utf-8")
            saved_path = str(receipt_path)
        except OSError:
            # The committed receipt remains in the bill table if the text export is unavailable.
            saved_path = ""
        return bill_number, total, saved_path, receipt

    @staticmethod
    def _integer(value: Any) -> int:
        try:
            return int(Decimal(str(value or "0")))
        except (InvalidOperation, ValueError, TypeError):
            return 0

    @staticmethod
    def _money(value: Decimal) -> str:
        return str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def parse_item_form(
    name: str, category: str, quantity: str, cost: str, expiry_text: str, supplier: str,
) -> tuple[str, str, int, Decimal, date | None, str]:
    name = name.strip()
    if not name:
        raise ValueError("Enter a product name.")
    try:
        parsed_quantity = int(quantity)
    except ValueError as error:
        raise ValueError("Quantity must be a whole number.") from error
    if parsed_quantity < 0:
        raise ValueError("Quantity cannot be negative.")
    try:
        parsed_cost = Decimal(cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError) as error:
        raise ValueError("Enter a valid unit price.") from error
    if not parsed_cost.is_finite() or parsed_cost < 0:
        raise ValueError("Unit price cannot be negative.")
    expiry_text = expiry_text.strip()
    if expiry_text:
        parsed_expiry = parse_date(expiry_text)
        if parsed_expiry is None:
            raise ValueError("Use an expiry date in YYYY-MM-DD format.")
    else:
        parsed_expiry = None
    return name, category.strip(), parsed_quantity, parsed_cost, parsed_expiry, supplier.strip()


def normalize_phone(value: str | None) -> str:
    """Normalize an optional phone number while retaining a leading country-code plus."""
    value = (value or "").strip()
    if not value:
        return ""
    if not re.fullmatch(r"\+?[\d\s().-]+", value):
        raise ValueError("Enter a phone number using digits, spaces, +, parentheses, or hyphens.")
    has_plus = value.startswith("+")
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 15:
        raise ValueError("Phone numbers must contain 7 to 15 digits.")
    return f"+{digits}" if has_plus else digits
