from decimal import Decimal
from datetime import datetime


def get_latest_month(data, allow_current=False):
    years = sorted(data.keys())
    latest_year = years[-1]
    months = sorted(data[latest_year].keys())
    latest_month = months[-1]

    if (
        not allow_current
        and latest_year == str(datetime.now().year)
        and latest_month == str(datetime.now().month)
    ):
        try:
            latest_month = months[-2]
        except IndexError:
            latest_year = years[-2]
            latest_month = sorted(data[latest_year].keys())[-1]

    return int(latest_month), int(latest_year)


def get_transparency_data(data, year=None, month=None, allow_current=False):
    if year is None:
        year = max(data.keys())

    if month is None:
        month = max(data[year].keys())

    year = str(year)
    month = str(month).zfill(2)

    if (
        not allow_current
        and year == str(datetime.now().year)
        and month == str(datetime.now().month).zfill(2)
    ):
        try:
            month = max([m for m in data[year].keys() if m != str(datetime.now().month)])
        except ValueError:
            year = str(int(year) - 1)
            month = max(data[year].keys())

    assert year in data, f"Year {year} not found in data"
    assert month in data[year], f"Month {month}-{year} not found in data"

    # Initialize balances
    balances = {}
    incomes = {}
    expenses = {}
    notes = {}

    start_balance = {}
    end_balance = {}

    for y in sorted(data.keys()):
        if int(y) > int(year):
            break

        for m in sorted(data[y].keys()):
            if int(y) == int(year) and int(m) > int(month):
                break

            # If the month is the one we are interested in, capture the start balance
            if int(y) == int(year) and int(m) == int(month):
                start_balance = {
                    k: Decimal(v) for k, v in balances.items() if k != "Notes"
                }

            for category in data[y][m]:
                for currency, amount in data[y][m][category].items():
                    if currency == "Notes":
                        if int(y) == int(year) and int(m) == int(month):
                            notes[category] = amount
                    else:
                        if currency not in balances:
                            balances[currency] = Decimal(0)
                        balances[currency] += Decimal(str(amount))

                        # Track incomes and expenses
                        if int(y) == int(year) and int(m) == int(month):
                            if Decimal(str(amount)) > 0:
                                if category not in incomes:
                                    incomes[category] = {}
                                if currency not in incomes[category]:
                                    incomes[category][currency] = Decimal(0)
                                incomes[category][currency] += Decimal(str(amount))
                            else:
                                if category not in expenses:
                                    expenses[category] = {}
                                if currency not in expenses[category]:
                                    expenses[category][currency] = Decimal(0)
                                expenses[category][currency] += Decimal(str(amount))

            # If the month is the one we are interested in, capture the end balance
            if int(y) == int(year) and int(m) == int(month):
                end_balance = {
                    k: Decimal(v) for k, v in balances.items() if k != "Notes"
                }

    # Calculate accumulated sums of incomes and expenses
    accumulated_incomes = {
        currency: sum(incomes[cat].get(currency, Decimal(0)) for cat in incomes)
        for currency in balances
        if currency != "Notes"
    }
    accumulated_expenses = {
        currency: sum(expenses[cat].get(currency, Decimal(0)) for cat in expenses)
        for currency in balances
        if currency != "Notes"
    }

    return {
        "start_balance": start_balance,
        "end_balance": end_balance,
        "incomes": incomes,
        "expenses": expenses,
        "accumulated_incomes": accumulated_incomes,
        "accumulated_expenses": accumulated_expenses,
        "notes": notes,
    }


def generate_transparency_table(result, currencies=None):
    def extract_currencies(data):
        return ["EUR"] + (
            list(
                set(
                    list(data["start_balance"].keys())
                    + list(data["end_balance"].keys())
                    + list(data["accumulated_incomes"].keys())
                    + list(data["accumulated_expenses"].keys())
                )
                - {"EUR", "Notes"}
            )
        )

    def format_currency(value, currency):
        if currency == "EUR":
            return f"€{value:,.2f}"
        elif currency in ["BTC", "ETH", "XMR"]:
            return f"{value:,.9f} {currency}"
        else:
            return f"{value} {currency}"

    def format_value(value, currency):
        if value == 0:
            return f"{format_currency(value, currency)}"
        elif value > 0:
            return f"+ {format_currency(value, currency)}"
        else:
            return f"- {format_currency(abs(value), currency)}"

    html = """
    <table class="table table-bordered table-transparency">
        <thead class="table-light">
            <tr>
                <th scope="col">Category</th>
    """

    if currencies is None:
        currencies = extract_currencies(result)

    # Add currency headers
    for currency in currencies:
        if currency == "EUR":
            html += '<th class="currency-col" scope="col">Euros (€)</th>'
        elif currency == "BTC":
            html += '<th class="currency-col" scope="col">Bitcoin (BTC)</th>'
        elif currency == "ETH":
            html += '<th class="currency-col" scope="col">Ethereum (ETH)</th>'
        elif currency == "XMR":
            html += '<th class="currency-col" scope="col">Monero (XMR)</th>'
        else:
            html += f'<th class="currency-col" scope="col">{currency}</th>'

    html += """
            </tr>
        </thead>
        <tbody>
    """

    # Add start balance row
    html += "<tr class=\"transparency-start-balance-row\"><td>Account Balance (start of month)</td>"
    for currency in currencies:
        value = result["start_balance"].get(currency, Decimal(0))
        html += f"<td>{format_value(value, currency)}</td>"
    html += "</tr>"

    # Add income rows
    for category, transactions in result["incomes"].items():
        has_notes = result["notes"].get(category)
        html += f"<tr><td>{category}{'*' if has_notes else ''}</td>"
        for currency in currencies:
            value = transactions.get(currency, "")
            if value != "":
                html += f"<td>{format_value(value, currency)}</td>"
            else:
                html += "<td></td>"
        html += "</tr>"

    # Add expense rows
    for category, transactions in result["expenses"].items():
        has_notes = result["notes"].get(category)
        html += f"<tr><td>{category}{'*' if has_notes else ''}</td>"
        for currency in currencies:
            value = transactions.get(currency, "")
            if value != "":
                html += f"<td>{format_value(value, currency)}</td>"
            else:
                html += "<td></td>"
        html += "</tr>"

    # Add total income row
    html += '<tr class="table-secondary"><td><b>Total Income</b></td>'
    for currency in currencies:
        value = result["accumulated_incomes"].get(currency, Decimal(0))
        html += f"<td><b>{format_value(value, currency)}</b></td>"
    html += "</tr>"

    # Add total expenses row
    html += '<tr class="table-secondary"><td><b>Total Expenses</b></td>'
    for currency in currencies:
        value = result["accumulated_expenses"].get(currency, Decimal(0))
        html += f"<td><b>{format_value(value, currency)}</b></td>"
    html += "</tr>"

    # Add end balance row
    html += '<tr class="table-secondary"><td><b>Account Balance (end of month)</b></td>'
    for currency in currencies:
        value = result["end_balance"].get(currency, Decimal(0))
        html += f"<td><b>{format_value(value, currency)}</b></td>"
    html += "</tr>"

    html += """
        </tbody>
    </table>
    """

    if result["notes"]:
        html += "<p><b>Notes:</b></p>"
        html += "<ul>"
        for category, footnote in result["notes"].items():
            html += f"<li>{category}: {footnote}</li>"
        html += "</ul>"

    return html
