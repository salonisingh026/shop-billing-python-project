# Singhjee Cold Drinks & More

A desktop application for managing Singhjee Cold Drinks & More inventory, billing, sales, and expiry dates. The interface is built with Python's `tkinter` and `ttk`; store data is kept in SQLite.

## Features

- Search, add, edit, and remove cold drinks, juices, packaged water, dairy drinks, energy drinks, and mocktails.
- Create bills and update inventory in one database transaction.
- Record an optional customer phone number and choose Cash, Credit card, Debit card, or UPI for every bill.
- Preview and print a formatted receipt with customer name, address, payment method, bill number, item quantities × unit rates, line amounts, total cost, and a thank-you message; customer phone stays off the receipt.
- Save a text receipt for each bill; sales analysis keeps customer phone and payment method for private review.
- Review sales for today, this week, this month, this year, or all time, with a breakdown of units sold by product.
- Search sales by customer name, phone number, or bill number; the bill list, product summary, and Excel export follow the selected search.
- Mark festivals, Sundays, special dates, and consecutive date ranges in the store calendar, with a five-item numbered stock work list.
- Export the selected sales period to one Excel sheet, with product sales and bill details side by side.
- Review today's sales and monitor expired or soon-to-expire products.
- Open and use the app on Windows, macOS, or Linux with a Python installation that includes Tk.

## Requirements

- Python 3.10 or later.
- Tk/Tcl, included with the standard Windows installer and available as a system package on some Linux distributions.
- No third-party Python packages are required.

Check Python and Tk availability:

```sh
python --version
python -m tkinter
```

On Debian or Ubuntu, install Tk if needed with `sudo apt install python3-tk`.

## Run

From this directory, start the app with:

```sh
python login.py
```

Set `DEFAULT_LOGIN_USERNAME` and `DEFAULT_LOGIN_PASSWORD` near the top of `database.py` to choose the login. On startup, the app applies changed values to the saved account once and stores the password as a salted hash. If you forget the login, edit these two settings and relaunch the app. A password changed with **Change password** stays active until you edit the source password setting again.

## Data and upgrades

The app stores its database in `data/grocery.sqlite` and saves receipt text files in `data/receipts/`. Both paths are ignored by Git, so customer and sales data stay out of commits.

The first run creates 25 sample cold-drink products and a demo login. To carry an older database forward, copy the old `grocery.sqlite` file to `data/grocery.sqlite` before the first launch. The app keeps customer and bill history and moves old plain-text login entries into a salted password-hash table. Old expiry and bill dates are read in day-first or month-first format; new dates use ISO `YYYY-MM-DD`.

You can store the database somewhere else by setting `GROCERY_DB_PATH` to its full path before launching:

```powershell
$env:GROCERY_DB_PATH = "$env:LOCALAPPDATA\SinghjeeColdDrinks\grocery.sqlite"
python login.py
```

```sh
GROCERY_DB_PATH="$HOME/.local/share/singhjee-cold-drinks/grocery.sqlite" python login.py
```

## Project files

| File | Purpose |
| --- | --- |
| `login.py` | App window, sign-in screen, navigation, and overview dashboard |
| `database.py` | SQLite access, legacy database migration, inventory and sales rules |
| `stockdetails.py` | Inventory management screen |
| `billingdetails.py` | Billing and daily sales screens |
| `calendarview.py` | Calendar for marking one day or an event date range |
| `excel_export.py` | Dependency-free Excel workbook export |
| `expirycheck.py` | Expiry monitoring screen |
| `ui.py` | Shared visual styles and widgets |

## License

MIT. See [LICENSE](LICENSE). Copyright (c) 2016–2017 Rohit Shankarrao Ukirde.
