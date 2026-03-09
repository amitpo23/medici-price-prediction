"""Jinja2 template rendering engine for Medici HTML pages.

Provides a single `render_template(name, **context)` function that loads
Jinja2 templates from src/templates/ and returns rendered HTML strings.
"""
from __future__ import annotations

import os

from jinja2 import Environment, FileSystemLoader

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=False,  # HTML templates, not user-submitted content
)


def render_template(name: str, **context: object) -> str:
    """Render a Jinja2 template by name and return the HTML string."""
    template = _env.get_template(name)
    return template.render(**context)
