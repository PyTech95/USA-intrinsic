"""Page-source SEO: every standard page's own title and description must be in the server
HTML (what crawlers read), including what the admin enters under SEO & GEO > Per-page overrides.
Runs against an in-memory database (no server needed):

    cd backend && python -m pytest tests/test_page_source_seo.py -n 0
"""
import asyncio
import html as html_lib
import re

import pytest

mongomock_motor = pytest.importorskip("mongomock_motor")

import ssr_render                       # noqa: E402
from ssr import ROUTES                  # noqa: E402

BASE = "https://intrinsicamerica.com"
TEMPLATE = ('<html><head><title>x</title><meta name="description" content="x" /><meta name="keywords" content="x" />'
            '<meta property="og:title" content="x" /><meta property="og:description" content="x" /><meta property="og:url" content="x" />'
            '<meta property="og:type" content="x" /><meta property="og:image" content="x" /><meta name="twitter:title" content="x" />'
            '<meta name="twitter:description" content="x" /><meta name="twitter:image" content="x" /><meta name="robots" content="index, follow" />'
            '</head><body><div id="root"></div></body></html>')


def seo(pages=None, **extra):
    return {"canonical_base": BASE, "title_template": "{title} | Intrinsic Technology",
            "default_title": "Intrinsic Technology | Managed IT, Cybersecurity & Cloud Services",
            "default_description": "Default site description.", "default_keywords": "managed it, cybersecurity",
            "robots_default": "index, follow", "geo": {"faqs": []}, "pages": pages or {}, **extra}


def render(path, settings):
    db = mongomock_motor.AsyncMongoMockClient()["t"]
    return asyncio.run(ssr_render.render(path, "intrinsicamerica.com", db, settings, TEMPLATE))["html"]


def title(html):
    return html_lib.unescape(re.search(r"<title>(.*?)</title>", html, re.S).group(1))


def description(html):
    return html_lib.unescape(re.search(r'<meta name="description" content="([^"]*)"', html).group(1))


class TestPageSourceSeo:
    def test_every_standard_page_has_its_own_title_and_description(self):
        seen_titles, seen_descriptions = {}, {}
        for path in ROUTES:
            html = render(path, seo())
            t, d = title(html), description(html)
            assert t and t != "x" and d and d != "x", path
            assert f'<link rel="canonical" href="{BASE}{path if path != "/" else "/"}"' in html, path
            assert t not in seen_titles, f"{path} repeats the title of {seen_titles.get(t)}"
            seen_titles[t] = path
            seen_descriptions.setdefault(d, []).append(path)
        duplicates = {d: p for d, p in seen_descriptions.items() if len(p) > 1}
        assert not duplicates, f"pages sharing one description: {duplicates}"

    def test_admin_override_appears_in_the_page_source(self):
        pages = {"/services/managed-it": {"title": "Managed IT Services NYC", "description": "Approved description for managed IT.",
                                          "keywords": "managed it services nyc"}}
        html = render("/services/managed-it", seo(pages))
        assert title(html) == "Managed IT Services NYC | Intrinsic Technology"
        assert description(html) == "Approved description for managed IT."
        assert '<meta name="keywords" content="managed it services nyc" />' in html
        assert '<meta property="og:title" content="Managed IT Services NYC | Intrinsic Technology" />' in html
        assert '<meta name="twitter:description" content="Approved description for managed IT." />' in html
        # a page without an override keeps its built-in default
        assert title(render("/services/co-managed-it", seo(pages))) == ROUTES["/services/co-managed-it"]["title"] + " | Intrinsic Technology"

    def test_new_york_and_new_jersey_pages(self):
        pages = {"/service-areas/new-york": {"title": "Business IT Support NYC", "description": "NY description from the approved pack."},
                 "/service-areas/new-jersey": {"description": "NJ description from the approved pack."}}
        ny, nj = render("/service-areas/new-york", seo(pages)), render("/service-areas/new-jersey", seo(pages))
        assert title(ny) == "Business IT Support NYC | Intrinsic Technology" and description(ny) == "NY description from the approved pack."
        assert title(nj) == "Managed IT Services in New Jersey | Intrinsic" and description(nj) == "NJ description from the approved pack."

    def test_homepage_uses_site_defaults_or_its_override(self):
        assert title(render("/", seo())) == "Intrinsic Technology | Managed IT, Cybersecurity & Cloud Services"
        assert description(render("/", seo())) == "Default site description."
        html = render("/", seo({"/": {"title": "Managed IT Services NYC", "description": "Home override."}}))
        assert title(html) == "Managed IT Services NYC | Intrinsic Technology" and description(html) == "Home override."

    def test_per_page_robots_is_respected(self):
        html = render("/privacy-policy", seo({"/privacy-policy": {"robots": "noindex, follow"}}))
        assert '<meta name="robots" content="noindex, follow" data-ssr="1" />' in html
        assert html.count('name="robots"') == 1


class TestNewYorkAndNewJersey:
    """The two service-area pages carry the title and description from On-page Fix Pack 1."""

    def test_new_york(self):
        html = render("/service-areas/new-york", seo())
        assert title(html) == "Managed IT Services NYC | On-site IT Support | Intrinsic"
        assert description(html) == "Managed IT, cybersecurity and cloud support for New York City organizations, from our 14 Wall Street office. On-site and remote. Talk to our team."
        assert len(title(html)) <= 60 and 120 <= len(description(html)) <= 155

    def test_new_jersey(self):
        html = render("/service-areas/new-jersey", seo())
        assert title(html) == "Managed IT Services in New Jersey | Intrinsic"
        assert description(html) == "Managed IT, cybersecurity and cloud support for northern New Jersey organizations, on site and remote, with 24/7 monitoring and a help desk."
        assert len(title(html)) <= 60 and 120 <= len(description(html)) <= 155

    def test_the_heading_on_the_page_is_unchanged(self):
        assert "Managed IT Services in New York City" in render("/service-areas/new-york", seo())
        assert "Managed IT Services in New Jersey" in render("/service-areas/new-jersey", seo())
