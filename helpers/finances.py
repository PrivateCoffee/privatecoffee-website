from decimal import Decimal


def get_transparency_data(data, year=None, month=None):
    if year is None:
        year = max(data.keys())

    if month is None:
        month = max(data[year].keys())

    assert year in data, f"Year {year} not found in data"
    assert month in data[year], f"Month {month}-{year} not found in data"

    # Initialize balances
    balances = {}
    incomes = {}
    expenses = {}

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
                start_balance = {k: Decimal(v) for k, v in balances.items()}

            for category in data[y][m]:
                for currency, amount in data[y][m][category].items():
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
                end_balance = {k: Decimal(v) for k, v in balances.items()}

    # Calculate accumulated sums of incomes and expenses
    accumulated_incomes = {
        currency: sum(incomes[cat].get(currency, Decimal(0)) for cat in incomes)
        for currency in balances
    }
    accumulated_expenses = {
        currency: sum(expenses[cat].get(currency, Decimal(0)) for cat in expenses)
        for currency in balances
    }

    return {
        "start_balance": start_balance,
        "end_balance": end_balance,
        "incomes": incomes,
        "expenses": expenses,
        "accumulated_incomes": accumulated_incomes,
        "accumulated_expenses": accumulated_expenses,
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
                - {"EUR"}
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
    html += "<tr><td>Account Balance (start of month)</td>"
    for currency in currencies:
        value = result["start_balance"].get(currency, Decimal(0))
        html += f"<td>{format_value(value, currency)}</td>"
    html += "</tr>"

    # Add income rows
    for category, transactions in result["incomes"].items():
        html += f"<tr><td>{category}</td>"
        for currency in currencies:
            value = transactions.get(currency, "")
            if value != "":
                html += f"<td>{format_value(value, currency)}</td>"
            else:
                html += "<td></td>"
        html += "</tr>"

    # Add expense rows
    for category, transactions in result["expenses"].items():
        html += f"<tr><td>{category}</td>"
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

    return html
