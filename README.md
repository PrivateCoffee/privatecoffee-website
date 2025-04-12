# Private.coffee Website

[![Support Private.coffee!](https://shields.private.coffee/badge/private.coffee-Support%20us!-pink?logo=coffeescript)](https://private.coffee)
[![MIT License](https://shields.private.coffee/badge/license-MIT-blue.svg)](LICENSE)

This is the source code for the [Private.coffee](https://private.coffee)
website.

It is a simple Jinja2 static website generator that compiles the templates in
the `templates` directory in conjunction with the JSON files in the `data`
directory and Markdown blog entries in the `blog` directory to generate static
HTML files in the `build` directory.

## Development

To run the website locally, you will need to have Python 3 installed. Then, you
can install the dependencies and run the website with the following commands:

```bash
pip install -r requirements.txt
python main.py
```

The website will be built into the `build` directory, and you can view it by
opening the `index.html` file in your browser or using the included HTTP server
(`python main.py --serve`).

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE)
file for details.

The assets in `assets/dist` are not part of this project and are subject to
their own licenses.

Blog posts in the `blog` directory are licensed under the [Creative Commons
Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/),
unless otherwise indicated. They may contain additional material under
different licenses - see the individual blog posts for details.

## Attribution

This website is built using the [Bootstrap](https://getbootstrap.com) framework
and [Phosphor Icons](https://phosphoricons.com).
