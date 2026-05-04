"""Jinja2 email renderer — produces (html, text) pairs from named templates."""

import os

import html2text
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "templates")

_env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)

_h2t = html2text.HTML2Text()
_h2t.ignore_links = False
_h2t.body_width = 0  # no line wrapping

_BASE_CTX: dict = {
    "product_name": settings.brand_product_name,
    "company_address": settings.brand_company_address,
    "help_url": settings.brand_help_url,
    "privacy_url": settings.brand_privacy_url,
    "terms_url": settings.brand_terms_url,
    "unsubscribe_url": settings.brand_unsubscribe_url,
    "social_links": [],
}


def first_name_from_email(email: str) -> str:
    """Derive a display first name from an email address.

    shiva@gmail.com      → 'Shiva'
    john.doe@example.com → 'John'
    """
    local = email.split("@")[0]
    return local.split(".")[0].capitalize()


def render(template_name: str, context: dict) -> tuple[str, str]:
    """Render a named template with merged base + per-email context.

    Returns (html_body, plain_text_body).
    """
    tmpl = _env.get_template(f"emails/{template_name}.html.j2")
    html = tmpl.render(**_BASE_CTX, **context)
    text = _h2t.handle(html)
    return html, text
