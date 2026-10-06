"""SSR / SEO iteration 30 tests — verifies /api/ssr renders unique per-page HTML,
redirects, errors, crawler files, OG images, and sitemap/robots/llms.
"""
import json
import os
import re
import xml.etree.ElementTree as ET

import pytest
import requests

API = "http://localhost:8001/api"
TIMEOUT = 20

SSR_PATHS = [
    "/",
    "/about",
    "/services/managed-it",
    "/services/cybersecurity",
    "/industries/healthcare",
    "/service-areas/new-york",
    "/service-areas/new-jersey",
    "/careers",
    "/case-studies/strengthening-endpoint-security-and-patch-compliance",
    "/careers/cloud-solutions-engineer",
]

CORE_SERVICE_PATHS = {
    "/services/managed-it",
    "/services/cybersecurity",
    "/services/cloud",
    "/services/ai",
    "/services/vcio-vciso",
}

LOCATION_PATHS = {"/service-areas/new-york", "/service-areas/new-jersey"}


def ssr(path, follow=True, extra_headers=None):
    h = {"X-Original-URI": path}
    if extra_headers:
        h.update(extra_headers)
    return requests.get(
        f"{API}/ssr", params={"path": path}, headers=h,
        allow_redirects=follow, timeout=TIMEOUT,
    )


def _all_jsonld(html):
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE,
    )
    parsed = []
    errs = 0
    for b in blocks:
        try:
            parsed.append(json.loads(b))
        except Exception:
            errs += 1
    return parsed, errs


def _flatten_schema_types(parsed):
    types = []
    def walk(x):
        if isinstance(x, dict):
            t = x.get("@type")
            if isinstance(t, list):
                types.extend(t)
            elif isinstance(t, str):
                types.append(t)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(parsed)
    return types


# --- SSR per-path tests ---
@pytest.mark.parametrize("path", SSR_PATHS)
def test_ssr_page_html(path):
    r = ssr(path)
    assert r.status_code == 200, f"SSR {path} -> {r.status_code}"
    html = r.text
    # title unique and non-empty
    titles = re.findall(r"<title>(.*?)</title>", html, re.DOTALL)
    assert titles and titles[0].strip(), f"missing <title> on {path}"
    # description
    assert re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'][^"\']+["\']', html, re.I), \
        f"missing description on {path}"
    # exactly ONE canonical pointing to intrinsicamerica.com<path>
    canonicals = re.findall(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.I)
    assert len(canonicals) == 1, f"canonical count={len(canonicals)} on {path}: {canonicals}"
    expected = f"https://intrinsicamerica.com{path if path != '/' else ''}"
    # home may be https://intrinsicamerica.com or /
    assert canonicals[0].rstrip("/") == expected.rstrip("/"), f"canonical {canonicals[0]} != {expected} on {path}"
    # og/twitter
    for prop in ("og:title", "og:description", "og:image"):
        assert re.search(rf'property=["\']{prop}["\']', html, re.I), f"missing {prop} on {path}"
    assert re.search(r'name=["\']twitter:', html, re.I), f"missing twitter tag on {path}"
    # exactly ONE h1
    h1s = re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.DOTALL | re.I)
    assert len(h1s) == 1, f"h1 count={len(h1s)} on {path}"
    assert re.sub(r"<[^>]+>", "", h1s[0]).strip(), f"empty h1 on {path}"
    # body not empty
    body = re.search(r"<body[^>]*>(.*)</body>", html, re.DOTALL | re.I)
    assert body, f"no body on {path}"
    text = re.sub(r"<[^>]+>", " ", body.group(1))
    assert len(text.strip()) > 300, f"body too small on {path} (len={len(text.strip())})"
    # JSON-LD valid
    parsed, errs = _all_jsonld(html)
    assert errs == 0, f"invalid JSON-LD on {path}"
    assert parsed, f"no JSON-LD on {path}"
    types = _flatten_schema_types(parsed)
    # schema requirements
    if path.startswith("/services/"):
        assert "Service" in types, f"missing Service on {path}: {types}"
        assert "BreadcrumbList" in types, f"missing BreadcrumbList on {path}"
    if path in CORE_SERVICE_PATHS or path in LOCATION_PATHS or path == "/":
        assert "FAQPage" in types, f"missing FAQPage on {path}: {types}"
    if path.startswith("/case-studies/"):
        assert "Article" in types, f"missing Article on {path}"
    if path.startswith("/careers/") and path != "/careers":
        assert "JobPosting" in types, f"missing JobPosting on {path}"
        # Required fields
        jp = next((d for d in _all_dicts(parsed) if d.get("@type") == "JobPosting"), None)
        assert jp, "JobPosting dict not found"
        for k in ("employmentType", "datePosted", "hiringOrganization"):
            assert k in jp, f"JobPosting missing {k} on {path}"


def _all_dicts(parsed):
    out = []
    def walk(x):
        if isinstance(x, dict):
            out.append(x)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(parsed)
    return out


# --- Unique titles ---
def test_ssr_titles_are_unique():
    titles = {}
    for p in SSR_PATHS:
        r = ssr(p)
        t = re.findall(r"<title>(.*?)</title>", r.text, re.DOTALL)[0].strip()
        titles[p] = t
    assert len(set(titles.values())) == len(titles), f"non-unique titles: {titles}"


# --- Redirects / errors ---
REDIRECTS = [
    ("/about-us", 301, "/about"),
    ("/help-desk-support", 301, "/services/managed-it"),
    ("/healthcare", 301, "/industries/healthcare"),
    ("/terms-conditions", 301, "/terms-of-service"),
    ("/contact-us", 301, "/contact"),
    ("/jobs", 301, "/careers"),
    ("/services/managed-support", 301, "/services/managed-it"),
    ("/services/ai-automation", 301, "/services/ai"),
    ("/jobs/it-support-level-2", 301, "/careers/it-support-level-2"),
]


@pytest.mark.parametrize("src,code,dst", REDIRECTS)
def test_redirect(src, code, dst):
    r = ssr(src, follow=False)
    assert r.status_code == code, f"{src}: expected {code}, got {r.status_code}"
    loc = r.headers.get("location") or r.headers.get("Location")
    assert loc, f"{src}: no Location header"
    expected = f"https://intrinsicamerica.com{dst}"
    assert loc.rstrip("/") == expected.rstrip("/"), f"{src} -> {loc} (expected {expected})"


def test_jobs_accounting_gone_410():
    r = ssr("/jobs/accounting-specialist", follow=False)
    assert r.status_code == 410, f"expected 410, got {r.status_code}"


def test_nonexistent_404():
    r = ssr("/nope-xyz-404", follow=False)
    assert r.status_code == 404, f"got {r.status_code}"


def test_www_redirects_to_non_www():
    r = ssr("/about", follow=False, extra_headers={"X-Forwarded-Host": "www.intrinsicamerica.com"})
    assert r.status_code == 301, f"www -> {r.status_code}"
    loc = r.headers.get("location", "")
    assert "www." not in loc, f"redirect still has www: {loc}"
    assert loc.startswith("https://intrinsicamerica.com"), loc


# --- Crawler files ---
def test_robots_txt():
    r = requests.get(f"{API}/robots.txt", timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.text
    for ua in ("GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "PerplexityBot", "Bingbot", "Google-Extended"):
        assert re.search(rf"User-agent:\s*{re.escape(ua)}", body, re.I), f"missing UA {ua}"
    assert "Sitemap:" in body


def test_llms_txt():
    r = requests.get(f"{API}/llms.txt", timeout=TIMEOUT)
    assert r.status_code == 200
    assert len(r.text) > 200
    assert "Intrinsic" in r.text


def test_sitemap_xml():
    r = requests.get(f"{API}/sitemap.xml", timeout=TIMEOUT)
    assert r.status_code == 200
    root = ET.fromstring(r.text)
    locs = [el.text for el in root.iter() if el.tag.endswith("loc")]
    joined = "\n".join(locs)
    for must in (
        "/services/cybersecurity", "/industries/healthcare", "/about", "/contact",
        "/service-areas/new-york", "/service-areas/new-jersey",
    ):
        assert must in joined, f"missing {must} in sitemap"
    # Exclude redirect/admin paths
    for forbidden in ("/about-us", "/jobs", "/admin", "/help-desk-support", "/contact-us"):
        # /jobs is tricky because /careers/jobs could not exist; check line-anchored
        assert not re.search(rf"<loc>https?://[^<]*{re.escape(forbidden)}(/|<)", r.text), \
            f"sitemap contains forbidden {forbidden}"


# --- OG images ---
def test_og_default_png():
    r = requests.get(f"{API}/og/default.png", timeout=TIMEOUT)
    assert r.status_code == 200
    assert "image/png" in r.headers.get("content-type", "").lower()
    assert len(r.content) > 1000


def test_og_page_png():
    r = requests.get(f"{API}/og/page.png", params={"title": "Test", "label": "Service"}, timeout=TIMEOUT)
    assert r.status_code == 200
    assert "image/png" in r.headers.get("content-type", "").lower()
    assert len(r.content) > 1000
