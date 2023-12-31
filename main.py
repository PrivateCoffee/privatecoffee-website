from flask import Flask, render_template, send_from_directory
from jinja2 import TemplateNotFound

import json
import pathlib

app = Flask(__name__)

@app.route('/assets/<path:path>')
def send_assets(path):
    return send_from_directory('assets', path)

@app.route('/', defaults={'path': 'index'})
@app.route('/<path:path>.html')
def catch_all(path):
    try:
        services = json.loads((pathlib.Path(__file__).parent / "services.json").read_text())
        return render_template(f'{path}.html', services=services)
    except TemplateNotFound:
        return "404 Not Found", 404

if __name__ == '__main__':
    app.run(port=9810)
