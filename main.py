import json
import pathlib
import datetime
import shutil
import math
import os
import logging

from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
from threading import Thread
from argparse import ArgumentParser
from typing import Optional

import yaml
import markdown2

from PIL import Image
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from helpers.finances import (
    generate_transparency_table,
    get_transparency_data,
    get_latest_month,
)


class StaticPageHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory="build", **kwargs)


# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

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
    """Render a template to a file.

    Args:
        template_name (str): The name of the template file.
        output_name (str): The name of the output file.
        **kwargs: Additional keyword arguments to pass to the template.
    """
    try:
        template = env.get_template(template_name)
        output_path = output_dir / output_name
        kwargs.setdefault("theme", "plain")
        
        path = "/" + output_name
        if path.endswith("/index.html"):
            path = path[:-10]
        elif path == "/index.html":
            path = "/"
        kwargs.setdefault("request", {"path": path})

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(template.render(**kwargs))
    except TemplateNotFound:
        logging.error(f"Template {template_name} not found.")


def create_thumbnail(input_image_path, output_image_path, size=(150, 150)):
    with Image.open(input_image_path) as img:
        img.thumbnail(size)
        img.save(output_image_path)


def calculate_relative_path(depth):
    return "../" * depth


def copy_assets(src_dir, dest_dir):
    for item in src_dir.iterdir():
        if item.is_dir():
            # Recurse for subdirectories
            item_dest_dir = dest_dir / item.name
            item_dest_dir.mkdir(parents=True, exist_ok=True)
            copy_assets(item, item_dest_dir)
        elif item.is_file():
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


def generate_blog_html(template_kwargs={}, posts_per_page=5):
    blog_dir = pathlib.Path("blog")
    blog_posts = []

    blog_tags = {}

    for post_dir in blog_dir.iterdir():
        if post_dir.is_dir():
            md_path = post_dir / "index.md"
            if md_path.exists():
                front_matter, md_content = parse_markdown_file(md_path)
                html_content = markdown2.markdown(md_content)

                # Only process future posts in development mode
                if front_matter.get("date"):
                    if isinstance(front_matter["date"], str):
                        post_date = datetime.datetime.strptime(
                            front_matter["date"], "%Y-%m-%d %H:%M:%S"
                        )
                    else:
                        post_date = front_matter["date"]
                        front_matter["date"] = post_date.strftime("%Y-%m-%d %H:%M:%S")

                    if post_date > datetime.datetime.now():
                        if not args.dev:
                            logging.info(f"Skipping future post: {post_dir.name}")
                            continue

                        front_matter["date"] = front_matter["date"] + " (future)"

                front_matter["content"] = html_content
                front_matter["slug"] = post_dir.name

                # Add post to relevant tag lists
                if "tags" in front_matter:
                    for tag in front_matter["tags"].split(","):
                        tag = tag.strip()

                        if tag not in blog_tags:
                            blog_tags[tag] = []

                        blog_tags[tag].append(front_matter)

                # Create excerpt if not present
                if "excerpt" not in front_matter:
                    excerpt = html_content.split("</p>")[0]
                    front_matter["excerpt"] = excerpt

                blog_posts.append(front_matter)

                # Ensure the build directory structure exists
                output_post_dir = output_dir / "blog" / post_dir.name
                output_post_dir.mkdir(parents=True, exist_ok=True)

                # Generate thumbnail if image is present
                if "image" in front_matter:
                    original_image = post_dir / front_matter["image"]
                    thumbnail_image_name = f"thumb_{original_image.name}"
                    thumbnail_image = (
                        output_dir / "blog" / post_dir.name / thumbnail_image_name
                    )
                    create_thumbnail(original_image, thumbnail_image)

                    front_matter["thumbnail"] = thumbnail_image_name

                # Copy non-markdown assets
                copy_assets(post_dir, output_post_dir)

    # Sort posts by date, descending
    blog_posts.sort(key=lambda x: x.get("date", ""), reverse=True)

    # Render each individual post
    for post in blog_posts:
        post.setdefault("license", "CC BY-SA 4.0")
        post.setdefault(
            "license-url", "https://creativecommons.org/licenses/by-sa/4.0/"
        )
        post.setdefault("author", "Private.coffee Team")
        post.setdefault("author-url", "https://private.coffee")

        post["tags"] = [tag.strip() for tag in post.get("tags", "").split(",") if tag]

        post_slug = post["slug"]
        render_template_to_file(
            "blog/post.html",
            f"blog/{post_slug}/index.html",
            **{**post, "relative_path": calculate_relative_path(2)},
            **template_kwargs,
        )

    # Add tags to template kwargs
    template_kwargs["tags"] = blog_tags.keys()

    # Generate each index page
    total_posts = len(blog_posts)
    total_pages = math.ceil(total_posts / posts_per_page)

    for page in range(total_pages):
        start = page * posts_per_page
        end = start + posts_per_page
        paginated_posts = blog_posts[start:end]
        context = {
            "posts": paginated_posts,
            "current_page": page + 1,
            "total_pages": total_pages,
            "relative_path": calculate_relative_path(1 if page == 0 else 3),
            **template_kwargs,
        }
        output_path = (
            "blog/index.html" if page == 0 else f"blog/page/{page + 1}/index.html"
        )
        render_template_to_file("blog/index.html", output_path, **context)

        if page == 0:
            pathlib.Path("build/blog/page/1").mkdir(parents=True, exist_ok=True)
            context["relative_path"] = calculate_relative_path(3)
            render_template_to_file(
                "blog/index.html", "blog/page/1/index.html", **context
            )

    # Generate tag pages
    for tag, posts in blog_tags.items():
        tag_posts = sorted(posts, key=lambda x: x.get("date", ""), reverse=True)
        total_tag_posts = len(tag_posts)
        total_tag_pages = math.ceil(total_tag_posts / posts_per_page)

        for page in range(total_tag_pages):
            start = page * posts_per_page
            end = start + posts_per_page
            paginated_posts = tag_posts[start:end]
            context = {
                "posts": paginated_posts,
                "current_page": page + 1,
                "total_pages": total_tag_pages,
                "tag": tag,
                "relative_path": calculate_relative_path(3),
                **template_kwargs,
            }
            output_path = (
                f"blog/tag/{tag}/index.html"
                if page == 0
                else f"blog/tag/{tag}/page/{page + 1}/index.html"
            )
            render_template_to_file("blog/index.html", output_path, **context)

            if page == 0:
                pathlib.Path(f"build/blog/tag/{tag}/page/1").mkdir(
                    parents=True, exist_ok=True
                )
                context["relative_path"] = calculate_relative_path(5)
                render_template_to_file(
                    "blog/index.html", f"blog/tag/{tag}/page/1/index.html", **context
                )

    logging.info("Blog section generated successfully.")


def generate_blog_rss(development_mode=False):
    blog_dir = pathlib.Path("blog")
    blog_posts = []

    for post_dir in blog_dir.iterdir():
        if post_dir.is_dir():
            md_path = post_dir / "index.md"
            if md_path.exists():
                front_matter, _ = parse_markdown_file(md_path)

                # Ensure date is RFC 822 compliant
                if "date" in front_matter:
                    if isinstance(front_matter["date"], str):
                        post_date = datetime.datetime.strptime(
                            front_matter["date"], "%Y-%m-%d %H:%M:%S"
                        )

                    else:
                        post_date = front_matter["date"]

                    if post_date.tzinfo is None:
                        post_date = post_date.astimezone()

                    front_matter["date"] = post_date.strftime(
                        "%a, %d %b %Y %H:%M:%S %z"
                    )

                front_matter["link"] = (
                    f"https://{"dev." if development_mode else ""}private.coffee/blog/{post_dir.name}/"
                )

                blog_posts.append(front_matter)

    blog_posts.sort(key=lambda x: x.get("date", ""), reverse=True)

    context = {
        "development_mode": development_mode,
        "posts": blog_posts,
        "current_time": datetime.datetime.now()
        .astimezone()
        .strftime("%a, %d %b %Y %H:%M:%S %z"),
    }
    render_template_to_file("blog/rss.xml", "blog/rss.xml", **context)

    logging.info("RSS feed generated successfully.")


def generate_static_pages(development_mode=False, data={}, template_kwargs={}):
    # Iterate over all templates in the templates directory
    templates_path = pathlib.Path("templates")
    for template_file in templates_path.glob("*.html"):
        template_name = template_file.stem
        context = template_kwargs.copy()

        context["path"] = f"{template_name}.html" if template_name != "index" else ""

        if template_name == "index":
            # Get featured services for the homepage
            featured_services = [
                service
                for service in data["services"]["services"]
                if service.get("featured", False)
                and not service.get("exclude_from_index", False)
            ]
            # Limit to 3 featured services if there are more
            # TODO: Do something smarter here
            if len(featured_services) > 6:
                featured_services = featured_services[:3]
            context.update(
                {"services": data["services"], "featured_services": featured_services}
            )

        if template_name == "services":
            # Extract all categories from services
            categories = sorted(
                list(
                    set(
                        [
                            service.get("category", "Uncategorized")
                            for service in data["services"]["services"]
                            if not service.get("exclude_from_index", False)
                        ]
                    )
                )
            )
            context.update({"services": data["services"], "categories": categories})

        if template_name == "simple":
            context.update({"services": data["services"]})

        if template_name == "bridges":
            context.update({"bridges": data["bridges"]})

        if template_name.startswith("membership"):
            allow_current = development_mode
            finances_month, finances_year = get_latest_month(
                data["finances"], allow_current
            )
            finances_period = datetime.date(finances_year, finances_month, 1)
            finances_period_str = finances_period.strftime("%B %Y")
            finances_table = generate_transparency_table(
                get_transparency_data(
                    data["finances"], finances_year, finances_month, allow_current
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
            for year in sorted(data["finances"].keys(), reverse=True):
                for month in sorted(data["finances"][year].keys(), reverse=True):
                    if year not in finance_data:
                        finance_data[year] = {}
                    finance_data[year][month] = generate_transparency_table(
                        get_transparency_data(data["finances"], year, month, True)
                    )

            context.update({"finances": finance_data})

        render_template_to_file(
            f"{template_name}.html", f"{template_name}.html", **context
        )

    logging.info("Static pages generated successfully.")


def generate_metrics(data):
    balances = get_transparency_data(data["finances"], allow_current=True)[
        "end_balance"
    ]

    response = (
        "# HELP privatecoffee_balance The balance of the private.coffee account\n"
    )
    response += "# TYPE privatecoffee_balance gauge\n"

    for currency, balance in balances.items():
        response += f'privatecoffee_balance{{currency="{currency}"}} {balance}\n'

    metrics_path = output_dir / "metrics.txt"
    with open(metrics_path, "w", encoding="utf-8") as f:
        f.write(response)

    logging.info("Metrics generated successfully.")


def autoselect_theme():
    # Load schedule from file
    json_content = (
        pathlib.Path(__file__).parent / "data" / "theme_schedule.jsonc"
    ).read_text()

    # Remove comments
    json_content = "\n".join(
        line.split("//", 1)[0] for line in json_content.split("\n")
    )

    schedule = json.loads(json_content)

    # Find the current theme
    current_time = datetime.datetime.now().timestamp()

    for theme in schedule:
        start_time = datetime.datetime.strptime(theme["start"], "%Y-%m-%d").replace(
            hour=0, minute=0, second=0
        )

        # Special case for recurring themes - if the start time is *far* in the past, assume it's recurring
        if start_time.year < 2000:
            start_time = start_time.replace(year=datetime.datetime.now().year)

        end_time = datetime.datetime.strptime(theme["end"], "%Y-%m-%d").replace(
            hour=23, minute=59, second=59
        )

        if end_time.year < 2000:
            end_time = end_time.replace(year=datetime.datetime.now().year)

        # Special case for themes that span the new year
        if start_time > end_time:
            end_time = end_time.replace(year=end_time.year + 1)

        if start_time.timestamp() <= current_time <= end_time.timestamp():
            logging.info(f"Selected theme: {theme['name']}")
            return theme["name"]

    logging.info("No theme selected or scheduled, defaulting to plain.")
    return "plain"


def generate_static_site(
    development_mode: bool = False,
    theme: Optional[str] = None,
    domains: Optional[str] = None,
):
    if not theme:
        theme = autoselect_theme()

    # Common context
    template_kwargs = {
        "timestamp": int(datetime.datetime.now().timestamp()),
        "theme": theme,
    }

    if development_mode:
        template_kwargs.update(
            {
                "warning": env.get_template("prod-warning.html").render(),
            }
        )

    data = {}

    # Load services data
    data["services"] = json.loads(
        (pathlib.Path(__file__).parent / "data" / "services.json").read_text()
    )

    # Load finances data
    data["finances"] = json.loads(
        (pathlib.Path(__file__).parent / "data" / "finances.json").read_text()
    )

    # Load bridges data
    data["bridges"] = json.loads(
        (pathlib.Path(__file__).parent / "data" / "bridges.json").read_text()
    )

    # Generate static pages
    generate_static_pages(development_mode, data, template_kwargs)

    # Generate blog section
    generate_blog_html(template_kwargs)
    generate_blog_rss(development_mode)

    # Generate metrics
    generate_metrics(data)

    # Copy static assets
    for folder in ["assets", "data"]:
        src = pathlib.Path(folder)
        dst = output_dir / folder
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)

    # Create .domains for Forgejo Pages
    domains_dest_path = output_dir / ".domains"

    if domains_dest_path.exists():
        os.remove(domains_dest_path)

    if domains:
        for domain in domains.split(","):
            domain = domain.strip()
            if domain:
                with open(domains_dest_path, "a", encoding="utf-8") as f:
                    f.write(f"{domain}\n")
    else:
        # Default to domains from data/domains.txt
        domains_path = pathlib.Path("data/domains.txt")
        if domains_path.exists():
            with open(domains_dest_path, "w", encoding="utf-8") as f:
                f.write(domains_path.read_text())

    # Copy the .well-known directory
    well_known_src = pathlib.Path("assets") / ".well-known"
    well_known_dst = output_dir / ".well-known"

    if well_known_src.exists():
        if well_known_dst.exists():
            shutil.rmtree(well_known_dst)

        shutil.copytree(well_known_src, well_known_dst)

    # Create _redirects file for Forgejo Pages
    redirects_dst = output_dir / "_redirects"
    redirects_src = pathlib.Path("data") / "redirects.txt"

    if redirects_src.exists():
        if redirects_dst.exists():
            os.remove(redirects_dst)

        with open(redirects_dst, "w", encoding="utf-8") as f:
            f.write(redirects_src.read_text())

    logging.info("Static site generated successfully.")


if __name__ == "__main__":
    parser = ArgumentParser(description="Generate the private.coffee static site.")
    parser.add_argument("--dev", action="store_true", help="Enable development mode")
    parser.add_argument(
        "--serve", action="store_true", help="Serve the site after building"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to serve the site on"
    )
    parser.add_argument("--theme", type=str, help="Theme to use for the site")
    parser.add_argument(
        "--domains",
        type=str,
        help="Domains to use for Forgejo Pages (default: domains from data/domains.txt)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug output")

    args = parser.parse_args()

    if os.environ.get("PRIVATECOFFEE_DEV"):
        args.dev = True

    if os.environ.get("PRIVATECOFFEE_THEME"):
        args.theme = os.environ["PRIVATECOFFEE_THEME"]

    if os.environ.get("PRIVATECOFFEE_PORT"):
        args.serve = True
        args.port = int(os.environ["PRIVATECOFFEE_PORT"])

    if os.environ.get("PRIVATECOFFEE_DOMAINS"):
        args.domains = os.environ["PRIVATECOFFEE_DOMAINS"]

    if os.environ.get("PRIVATECOFFEE_DEBUG"):
        logging.getLogger().setLevel(logging.DEBUG)

    generate_static_site(
        development_mode=args.dev, theme=args.theme, domains=args.domains
    )

    if args.serve:
        server = TCPServer(("", args.port), StaticPageHandler)
        logging.info(f"Serving on http://localhost:{args.port}")
        thread = Thread(target=server.serve_forever)
        thread.start()
        thread.join()
