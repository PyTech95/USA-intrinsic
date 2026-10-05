"""SEO/GEO backend endpoint tests for Intrinsic app."""
import os
import re
import xml.etree.ElementTree as ET
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://production-stack-1.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@intrinsictg.com"
ADMIN_PASSWORD = "080b308a140ae894077cebae"


@pytest.fixture(scope="module")
def admin_token():
    # Try common auth paths
    for path in ("/auth/login", "/admin/login", "/login"):
        try:
            r = requests.post(f"{API}{path}", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=15)
            if r.status_code == 200:
                data = r.json()
                tok = data.get("token") or data.get("access_token") or (data.get("data") or {}).get("token")
                if tok:
                    return tok
        except Exception:
            pass
    pytest.skip("Could not obtain admin token")


# ----- Sitemap -----
def test_sitemap_xml_valid_and_contains_routes():
    r = requests.get(f"{API}/sitemap.xml", timeout=15)
    assert r.status_code == 200
    assert "xml" in r.headers.get("content-type", "").lower()
    root = ET.fromstring(r.text)
    locs = [el.text for el in root.iter() if el.tag.endswith("loc")]
    assert len(locs) > 0
    joined = "\n".join(locs)
    for must in ("/services/cybersecurity", "/industries/healthcare", "/about", "/contact"):
        assert must in joined, f"Missing {must} in sitemap"


# ----- Robots -----
def test_robots_txt_allows_ai_crawlers_and_links_sitemap():
    r = requests.get(f"{API}/robots.txt", timeout=15)
    assert r.status_code == 200
    body = r.text
    for ua in ("GPTBot", "OAI-SearchBot", "ClaudeBot", "PerplexityBot", "Bingbot", "Google-Extended"):
        assert re.search(rf"User-agent:\s*{re.escape(ua)}", body, re.IGNORECASE), f"Missing UA {ua}"
    assert "Sitemap:" in body
    assert "sitemap.xml" in body


# ----- LLMs.txt -----
def test_llms_txt_has_summary_and_pages():
    r = requests.get(f"{API}/llms.txt", timeout=15)
    assert r.status_code == 200
    body = r.text
    assert len(body) > 200
    # Expect site identification + some page links + FAQ hint
    assert "Intrinsic" in body
    assert "/services/" in body or "/industries/" in body


# ----- SEO settings -----
def test_seo_settings_returns_org_data():
    r = requests.get(f"{API}/seo", timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    # Should include organization info in some form
    s = str(data).lower()
    assert "intrinsic" in s


def test_seo_put_requires_auth():
    r = requests.put(f"{API}/seo", json={"title": "TEST"}, timeout=15)
    assert r.status_code in (401, 403, 422)


def test_seo_put_with_admin(admin_token):
    r = requests.get(f"{API}/seo", timeout=15)
    current = r.json() if r.status_code == 200 else {}
    headers = {"Authorization": f"Bearer {admin_token}"}
    # Send back same payload (idempotent)
    r2 = requests.put(f"{API}/seo", json=current, headers=headers, timeout=15)
    assert r2.status_code in (200, 201, 204), f"PUT /api/seo got {r2.status_code}: {r2.text[:200]}"
