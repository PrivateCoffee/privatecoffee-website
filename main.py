from flask import Flask, render_template, send_from_directory
from jinja2 import TemplateNotFound

import json
import pathlib
import os

from argparse import ArgumentParser

app = Flask(__name__)


@app.route("/assets/<path:path>")
def send_assets(path):
    return send_from_directory("assets", path)


@app.route("/", defaults={"path": "index"})
@app.route("/<path:path>.html")
def catch_all(path):
    try:
        services = json.loads(
            (pathlib.Path(__file__).parent / "services.json").read_text()
        )

        warning = None

        if app.development_mode:
            warning = render_template("prod-warning.html")

        return render_template(
            f"{path}.html", services=services, warning=warning
        )
    except TemplateNotFound:
        return "404 Not Found", 404


app.development_mode = False

if os.environ.get("PRIVATECOFFEE_DEV"):
    app.development_mode = True


if __name__ == "__main__":
    parser = ArgumentParser(description="Run the private.coffee web server.")
    parser.add_argument("--port", type=int, default=9810)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()

    app.development_mode = args.dev or app.development_mode

    app.run(port=args.port, debug=args.debug)
