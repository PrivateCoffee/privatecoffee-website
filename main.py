from jinja2 import Environment, FileSystemLoader, TemplateNotFound
import json
import pathlib
import datetime
import shutil
import math

from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
from threading import Thread

import yaml
import markdown2

from argparse import ArgumentParser

from helpers.finances import (
    generate_transparency_table,
    get_transparency_data,
    get_latest_month,
)


class StaticPageHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="build", **kwargs)


# Configure Jinja2 environment
env = Environment(loader=FileSystemLoader("templates"))

# Set up the output directory for static files
output_dir = pathlib.Path("build")
output_dir.mkdir(exist_ok=True, parents=True)


# Define the icon filter
def icon(icon_name):
    icon_path = pathlib.Path("assets") / f"dist/icons/{icon_name}.svg"
    try:
        with open(icon_path, "r", encoding="utf-8") as file:
            file_content = file.read()
    except FileNotFoundError:
        file_content = ""
    return file_content


env.filters["icon"] = icon


# Filter for rendering a month name from a number
def month_name(month_number):
    return datetime.date(1900, int(month_number), 1).strftime("%B")


env.filters["month_name"] = month_name


def render_template_to_file(template_name, output_name, **kwargs):
    try:
        template = env.get_template(template_name)
        output_path = output_dir / output_name
        kwargs.setdefault("theme", "plain")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(template.render(**kwargs))
    except TemplateNotFound:
        print(f"Template {template_name} not found.")


def calculate_relative_path(depth):
    return "../" * depth


def copy_assets(src_dir, dest_dir):
    for item in src_dir.iterdir():
        if item.is_dir():
            # Recur for subdirectories
            item_dest_dir = dest_dir / item.name
            item_dest_dir.mkdir(parents=True, exist_ok=True)
            copy_assets(item, item_dest_dir)
        elif item.is_file() and item.suffix not in [".md"]:
            shutil.copy(item, dest_dir)


def parse_markdown_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        # Split the front matter and markdown content
        parts = content.split("---", 2)
        if len(parts) == 3:
            _, fm_text, md_content = parts
            front_matter = yaml.safe_load(fm_text)
        else:
            front_matter, md_content = {}, content
        return front_matter, md_content


def generate_blog_html(posts_per_page=5):
    blog_dir = pathlib.Path("blog")
    blog_posts = []

    for post_dir in blog_dir.iterdir():
        if post_dir.is_dir():
            md_path = post_dir / "index.md"
            if md_path.exists():
                front_matter, md_content = parse_markdown_file(md_path)
                html_content = markdown2.markdown(md_content)
                front_matter["content"] = html_content
                front_matter["slug"] = post_dir.name
                blog_posts.append(front_matter)

                # Ensure the build directory structure exists
                output_post_dir = output_dir / "blog" / post_dir.name
                output_post_dir.mkdir(parents=True, exist_ok=True)

                # Copy non-markdown assets
                copy_assets(post_dir, output_post_dir)

    # Sort posts by date, descending
    blog_posts.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Calculate total pages
    total_posts = len(blog_posts)
    total_pages = math.ceil(total_posts / posts_per_page)

    # Generate each index page
    for page in range(total_pages):
        start = page * posts_per_page
        end = start + posts_per_page
        paginated_posts = blog_posts[start:end]
        context = {
            "posts": paginated_posts,
            "current_page": page + 1,
            "total_pages": total_pages,
            "relative_path": calculate_relative_path(1 if page == 0 else 2),
        }
        output_path = (
            f"blog/index.html" if page == 0 else f"blog/page/{page + 1}/index.html"
        )
        render_template_to_file("blog/index.html", output_path, **context)

    # Render each individual post
    for post in blog_posts:
        post_slug = post["slug"]
        render_template_to_file(
            "blog/post.html",
            f"blog/{post_slug}/index.html",
            **{**post, "relative_path": calculate_relative_path(2)},
        )

    print("Blog section generated successfully.")


def generate_static_site(development_mode=False, theme="plain"):
    # Common context
    kwargs = {
        "timestamp": int(datetime.datetime.now().timestamp()),
        "theme": theme,
    }

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

    # Load bridges data
    bridges = json.loads(
        (pathlib.Path(__file__).parent / "data" / "bridges.json").read_text()
    )

    # Iterate over all templates in the templates directory
    templates_path = pathlib.Path("templates")
    for template_file in templates_path.glob("*.html"):
        template_name = template_file.stem
        context = kwargs.copy()

        context["path"] = f"{template_name}.html" if template_name != "index" else ""

        if template_name in ["index", "simple"]:
            context.update({"services": services})

        if template_name == "bridges":
            context.update({"bridges": bridges})

        if template_name.startswith("membership"):
            allow_current = development_mode
            finances_month, finances_year = get_latest_month(finances, allow_current)
            finances_period = datetime.date(finances_year, finances_month, 1)
            finances_period_str = finances_period.strftime("%B %Y")
            finances_table = generate_transparency_table(
                get_transparency_data(
                    finances, finances_year, finances_month, allow_current
                )
            )
            context.update(
                {
                    "finances": finances_table,
                    "finances_period": finances_period_str,
                }
            )

        if template_name == "transparency":
            finance_data = {}
            for year in sorted(finances.keys(), reverse=True):
                for month in sorted(finances[year].keys(), reverse=True):
                    if year not in finance_data:
                        finance_data[year] = {}
                    finance_data[year][month] = generate_transparency_table(
                        get_transparency_data(finances, year, month, True)
                    )
            context.update({"finances": finance_data})

        render_template_to_file(
            f"{template_name}.html", f"{template_name}.html", **context
        )

    # Generate blog section
    generate_blog_html()

    # Generate metrics
    balances = get_transparency_data(finances, allow_current=True)["end_balance"]

    response = (
        "# HELP privatecoffee_balance The balance of the private.coffee account\n"
    )
    response += "# TYPE privatecoffee_balance gauge\n"

    for currency, balance in balances.items():
        response += f'privatecoffee_balance{{currency="{currency}"}} {balance}\n'

    metrics_path = output_dir / "metrics.txt"
    with open(metrics_path, "w", encoding="utf-8") as f:
        f.write(response)

    # Copy static assets
    for folder in ["assets", "data"]:
        src = pathlib.Path(folder)
        dst = output_dir / folder
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    print("Static site generated successfully.")


if __name__ == "__main__":
    parser = ArgumentParser(description="Generate the private.coffee static site.")
    parser.add_argument("--dev", action="store_true", help="Enable development mode")
    parser.add_argument(
        "--serve", action="store_true", help="Serve the site after building"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to serve the site on"
    )
    parser.add_argument(
        "--theme", type=str, default="plain", help="Theme to use for the site"
    )

    args = parser.parse_args()

    generate_static_site(development_mode=args.dev, theme=args.theme)

    if args.serve:
        server = TCPServer(("", args.port), StaticPageHandler)
        print(f"Serving on http://localhost:{args.port}")
        thread = Thread(target=server.serve_forever)
        thread.start()
        thread.join()
