from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import json
import pathlib
import os
import datetime
import shutil

from argparse import ArgumentParser

from helpers.finances import (
    generate_transparency_table,
    get_transparency_data,
    get_latest_month,
)

# Configure Jinja2 environment
env = Environment(loader=FileSystemLoader('templates'))

# Set up the output directory for static files
output_dir = pathlib.Path('build')
output_dir.mkdir(exist_ok=True, parents=True)

# Define the icon filter
def icon(icon_name):
    icon_path = pathlib.Path('assets') / f"dist/icons/{icon_name}.svg"
    try:
        with open(icon_path, 'r', encoding='utf-8') as file:
            file_content = file.read()
    except FileNotFoundError:
        file_content = ''
    return file_content

env.filters['icon'] = icon

def render_template_to_file(template_name, output_name, **kwargs):
    try:
        template = env.get_template(template_name)
        output_path = output_dir / output_name
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(template.render(**kwargs))
    except TemplateNotFound:
        print(f"Template {template_name} not found.")

def generate_static_site(development_mode=False):
    # Common context
    kwargs = {}
    if development_mode:
        kwargs.update(
            {
                "warning": env.get_template("prod-warning.html").render(),
            }
        )

    # Load services data
    services = json.loads(
        (pathlib.Path(__file__).parent / "data" / "services.json").read_text()
    )

    # Load finances data
    finances = json.loads(
        (pathlib.Path(__file__).parent / "data" / "finances.json").read_text()
    )

    # Iterate over all templates in the templates directory
    templates_path = pathlib.Path('templates')
    for template_file in templates_path.glob('*.html'):
        template_name = template_file.stem
        context = kwargs.copy()

        if template_name in ["index", "simple"]:
            context.update({"services": services})

        if template_name == "membership":
            allow_current = development_mode
            finances_month, finances_year = get_latest_month(finances, allow_current)
            finances_period = datetime.date(finances_year, finances_month, 1)
            finances_period_str = finances_period.strftime("%B %Y")
            finances_table = generate_transparency_table(
                get_transparency_data(finances, finances_year, finances_month, allow_current)
            )
            context.update({
                "finances": finances_table,
                "finances_period": finances_period_str,
            })

        if template_name == "transparency":
            finance_data = {}
            for year in sorted(finances.keys(), reverse=True):
                for month in sorted(finances[year].keys(), reverse=True):
                    if year not in finance_data:
                        finance_data[year] = {}
                    finance_data[year][month] = generate_transparency_table(
                        get_transparency_data(finances, year, month)
                    )
            context.update({"finances": finance_data})

        render_template_to_file(f"{template_name}.html", f"{template_name}.html", **context)

    # Generate metrics
    balances = get_transparency_data(finances, allow_current=True)["end_balance"]

    response = (
        "# HELP privatecoffee_balance The balance of the private.coffee account\n"
    )
    response += "# TYPE privatecoffee_balance gauge\n"

    for currency, balance in balances.items():
        response += f'privatecoffee_balance{{currency="{currency}"}} {balance}\n'

    metrics_path = output_dir / "metrics.txt"
    with open(metrics_path, 'w', encoding='utf-8') as f:
        f.write(response)

    # Copy static assets
    assets_src = pathlib.Path('assets')
    assets_dst = output_dir / 'assets'
    if assets_dst.exists():
        shutil.rmtree(assets_dst)
    shutil.copytree(assets_src, assets_dst)

    print("Static site generated successfully.")

if __name__ == "__main__":
    parser = ArgumentParser(description="Generate the private.coffee static site.")
    parser.add_argument("--dev", action="store_true", help="Enable development mode")
    args = parser.parse_args()

    generate_static_site(development_mode=args.dev)