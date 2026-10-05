"""GEO/SEO iteration 29 checks: raw HTML, robots/llms/sitemap, per-page tags, schema."""
import os
import re
import json
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
       "https://intrinsic-deploy-1.preview.emergentagent.com"


def _get(path):
    return requests.get(BASE + path, timeout=20)


# --- RAW HTML (non-JS) ---
def test_raw_home_contains_geo_essentials():
    r = _get("/")
    assert r.status_code == 200
    html = r.text
    scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert scripts, "no JSON-LD in raw HTML"
    data = json.loads(scripts[0])
    types = [n.get("@type") for n in data.get("@graph", [])]
    assert "Organization" in types
    assert "ProfessionalService" in types
    assert "WebSite" in types
    assert "<noscript>" in html
    assert "14 Wall Street" in html
    assert "consulting@intrinsicamerica.com" in html
    assert "/services/cybersecurity" in html
    assert "/industries/healthcare" in html
    assert re.search(r'<meta[^>]+name="description"', html)
    assert re.search(r'<meta[^>]+property="og:title"', html)
    assert re.search(r'<meta[^>]+property="og:image"', html)


# --- ROBOTS / LLMS / SITEMAP ---
def test_robots_root():
    r = _get("/robots.txt")
    assert r.status_code == 200
    txt = r.text
    for ua in ["GPTBot", "ClaudeBot", "PerplexityBot", "Bingbot"]:
        assert ua in txt, f"{ua} missing"
    assert "Sitemap:" in txt


def test_llms_root():
    r = _get("/llms.txt")
    assert r.status_code == 200
    assert "Intrinsic" in r.text
    assert len(r.text) > 300


def test_api_robots():
    r = _get("/api/robots.txt")
    assert r.status_code == 200
    for ua in ["GPTBot", "ClaudeBot", "PerplexityBot", "Bingbot"]:
        assert ua in r.text


def test_api_llms():
    r = _get("/api/llms.txt")
    assert r.status_code == 200
    assert "Intrinsic" in r.text


def test_api_sitemap():
    r = _get("/api/sitemap.xml")
    assert r.status_code == 200
    assert "<urlset" in r.text
    assert "https://intrinsicamerica.com/" in r.text
    assert r.text.count("<loc>") >= 5
