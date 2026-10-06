#!/usr/bin/env python3
"""Reproducible SEO/GEO audit of the SSR layer.

Hits the FastAPI SSR renderer (which is what nginx serves for every HTML page in
production) for every sitemap URL plus domain/legacy/error variants, and records
status, title, description, canonical, OG/Twitter, body content, schema types and
simple validation. Usage:

    python3 audit_seo.py            # uses REACT_APP_BACKEND_URL from frontend/.env
    AUDIT_BASE=https://intrinsicamerica.com python3 audit_seo.py   # live prod
"""
import json, os, re, sys, urllib.request, urllib.parse
from pathlib import Path

def api_base():
    if os.environ.get("AUDIT_API"):
        return os.environ["AUDIT_API"].rstrip("/")
    env = (Path(__file__).resolve().parents[1] / "frontend" / ".env").read_text()
    m = re.search(r"^REACT_APP_BACKEND_URL\s*=\s*(.+)$", env, re.M)
    return m.group(1).strip().rstrip("/") + "/api"

API = api_base()

_noredir = urllib.request.build_opener(type("NoRedir", (urllib.request.HTTPRedirectHandler,), {"redirect_request": lambda self, *a, **k: None})())

def fetch(path, header_host=None, follow=True):
    url = f"{API}/ssr?path=" + urllib.parse.quote(path)
    req = urllib.request.Request(url, headers={"User-Agent": "SEO-Audit"})
    if header_host:
        req.add_header("X-Forwarded-Host", header_host)
    opener = urllib.request.urlopen if follow else _noredir.open
    try:
        r = opener(req, timeout=20)
        return r.getcode(), r.read().decode("utf-8", "replace"), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e.headers

def analyze(html):
    title = (re.search(r"<title>(.*?)</title>", html) or [None, ""])[1]
    desc = (re.search(r'<meta name="description" content="(.*?)"', html) or [None, ""])[1]
    canon = (re.search(r'<link rel="canonical" href="(.*?)"', html) or [None, ""])[1]
    h1 = (re.search(r"<h1>(.*?)</h1>", html, re.S) or [None, ""])[1]
    types = re.findall(r'"@type":\s*"([A-Za-z]+)"', html)
    og = bool(re.search(r'property="og:title"', html)) and bool(re.search(r'property="og:image"', html))
    tw = bool(re.search(r'name="twitter:title"', html))
    faq = "FAQPage" in types
    # validate each ld+json block parses
    lds = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    bad = 0
    for b in lds:
        try: json.loads(b)
        except Exception: bad += 1
    h1count = len(re.findall(r"<h1>", html))
    return {"title": title[:70], "title_len": len(title), "desc_len": len(desc),
            "canonical": canon, "h1": re.sub("<.*?>", "", h1)[:60], "h1_count": h1count,
            "schema": sorted(set(types)), "og": og, "twitter": tw, "faq": faq,
            "ld_blocks": len(lds), "ld_parse_errors": bad, "body_len": len(re.sub("<.*?>", " ", html))}

def sitemap_paths():
    code, body, _ = fetch("/")  # warm
    url = API + "/sitemap.xml"
    xml = urllib.request.urlopen(url, timeout=20).read().decode()
    locs = re.findall(r"<loc>(.*?)</loc>", xml)
    out = []
    for l in locs:
        p = re.sub(r"^https?://[^/]+", "", l) or "/"
        out.append(p)
    return out

def main():
    paths = sitemap_paths()
    print(f"# SEO/GEO Audit via {API}\n# sitemap URLs: {len(paths)}\n")
    rows = []
    problems = []
    for p in paths:
        code, html, hdr = fetch(p)
        a = analyze(html)
        ok = code == 200 and a["h1_count"] == 1 and a["og"] and a["canonical"].endswith(p if p != "/" else "/") and a["ld_parse_errors"] == 0
        rows.append((p, code, a))
        if not ok:
            problems.append((p, code, a))
        print(f"[{code}] {p}")
        print(f"      title({a['title_len']}): {a['title']}")
        print(f"      desc_len={a['desc_len']} h1={a['h1_count']} og={a['og']} tw={a['twitter']} faq={a['faq']} schema={a['schema']} ld_err={a['ld_parse_errors']} canonical={a['canonical']}")

    print("\n# Variants")
    variants = [
        ("www host -> 301", lambda: fetch("/about", header_host="www.intrinsicamerica.com", follow=False)),
        ("/about-us (legacy)", lambda: fetch("/about-us", follow=False)),
        ("/help-desk-support (legacy)", lambda: fetch("/help-desk-support", follow=False)),
        ("/services/managed-support (alias)", lambda: fetch("/services/managed-support", follow=False)),
        ("/jobs/accounting-specialist (gone)", lambda: fetch("/jobs/accounting-specialist", follow=False)),
        ("/this-does-not-exist (404)", lambda: fetch("/this-does-not-exist-xyz", follow=False)),
    ]
    for name, fn in variants:
        code, html, hdr = fn()
        loc = hdr.get("Location", "")
        print(f"[{code}] {name}  {('-> ' + loc) if loc else ''}")

    print(f"\n# SUMMARY: {len(rows)} pages audited, {len(problems)} with issues")
    for p, code, a in problems:
        print(f"  ISSUE {p} code={code} h1={a['h1_count']} og={a['og']} canon={a['canonical']} ld_err={a['ld_parse_errors']}")
    return 0 if not problems else 1

if __name__ == "__main__":
    sys.exit(main())
