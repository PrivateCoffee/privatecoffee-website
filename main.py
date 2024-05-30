from flask import Flask, render_template, send_from_directory
from jinja2 import TemplateNotFound

import json
import pathlib
import os
import datetime

from argparse import ArgumentParser

from helpers.finances import (
    generate_transparency_table,
    get_transparency_data,
    get_latest_month,
)

app = Flask(__name__)


@app.route("/assets/<path:path>")
def send_assets(path):
    return send_from_directory("assets", path)


@app.route("/", defaults={"path": "index"})
@app.route("/<path:path>.html")
def catch_all(path):
    try:
        kwargs = {}

        if app.development_mode:
            kwargs.update(
                {
                    "warning": render_template("prod-warning.html"),
                }
            )

        if path in (
            "index",
            "simple",
        ):
            services = json.loads(
                (pathlib.Path(__file__).parent / "data" / "services.json").read_text()
            )

            kwargs.update(
                {
                    "services": services,
                }
            )

        if path == "membership":
            finances = json.loads(
                (pathlib.Path(__file__).parent / "data" / "finances.json").read_text()
            )

            finances_month, finances_year = get_latest_month(finances)
            finances_period = datetime.date(finances_year, finances_month, 1)
            finances_period_str = finances_period.strftime("%B %Y")

            finances_table = generate_transparency_table(
                get_transparency_data(finances)
            )

            kwargs.update(
                {
                    "finances": finances_table,
                    "finances_period": finances_period_str,
                }
            )

        return render_template(f"{path}.html", **kwargs)

    except TemplateNotFound:
        return "404 Not Found", 404


app.development_mode = False

if os.environ.get("PRIVATECOFFEE_DEV"):
    app.development_mode = True


def icon(icon_name):
    file = send_from_directory("assets", f"dist/icons/{icon_name}.svg")
    try:
        file_content = file.response.file.read().decode("utf-8")
    except AttributeError:
        file_content = file.response.read().decode("utf-8")
    return file_content


app.add_template_filter(icon)

if __name__ == "__main__":
    parser = ArgumentParser(description="Run the private.coffee web server.")
    parser.add_argument("--port", type=int, default=9810)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()

    app.development_mode = args.dev or app.development_mode

    app.run(port=args.port, debug=args.debug)
