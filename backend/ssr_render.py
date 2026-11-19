"""Request-time render orchestrator for public pages (used by /api/ssr)."""
from __future__ import annotations
import re
from ssr import (ROUTES, INTRO, FAQS, REDIRECTS, REDIRECT_PREFIXES, OLD_JOB_PATHS, ORG, PREFERRED_BASE,
                 esc, titlecase, normalize, breadcrumb_ld, faq_ld, _ld,
                 _nav_and_contact, _faq_html, _crumbs_html)


def _slug(s: str) -> str:
    s = (s or "").lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _paras(text) -> list:
    return [p for p in re.split(r"\n+", str(text or "")) if p.strip()]


def _meta_head(template: str, *, title: str, description: str, canonical: str,
               robots: str, og_image: str, og_type: str, extra_ld: list, keywords: str = "") -> str:
    html = template
    html = re.sub(r"<title>[\s\S]*?</title>", f"<title>{esc(title)}</title>", html, count=1)
    html = re.sub(r'<meta name="description"[^>]*>', f'<meta name="description" content="{esc(description)}" />', html, count=1)
    if keywords:
        html = re.sub(r'<meta name="keywords"[^>]*>', f'<meta name="keywords" content="{esc(keywords)}" />', html, count=1)
    html = re.sub(r'<meta property="og:title"[^>]*>', f'<meta property="og:title" content="{esc(title)}" />', html, count=1)
    html = re.sub(r'<meta property="og:description"[^>]*>', f'<meta property="og:description" content="{esc(description)}" />', html, count=1)
    html = re.sub(r'<meta property="og:url"[^>]*>', f'<meta property="og:url" content="{esc(canonical)}" />', html, count=1)
    html = re.sub(r'<meta property="og:type"[^>]*>', f'<meta property="og:type" content="{esc(og_type)}" />', html, count=1)
    html = re.sub(r'<meta property="og:image"[^>]*>', f'<meta property="og:image" content="{esc(og_image)}" />', html, count=1)
    html = re.sub(r'<meta name="twitter:title"[^>]*>', f'<meta name="twitter:title" content="{esc(title)}" />', html, count=1)
    html = re.sub(r'<meta name="twitter:description"[^>]*>', f'<meta name="twitter:description" content="{esc(description)}" />', html, count=1)
    html = re.sub(r'<meta name="twitter:image"[^>]*>', f'<meta name="twitter:image" content="{esc(og_image)}" />', html, count=1)
    ld = "\n".join(_ld(o) for o in extra_ld if o)
    inject = (f'<link rel="canonical" href="{esc(canonical)}" data-ssr="1" />\n'
              f'<meta name="robots" content="{esc(robots)}" data-ssr="1" />\n{ld}\n</head>')
    # remove the template's default static robots meta to avoid duplicates
    html = re.sub(r'\s*<meta name="robots"[^>]*>', "", html, count=1)
    return html.replace("</head>", inject, 1)


def _inject_body(template: str, inner: str) -> str:
    return re.sub(r'<div id="root">[\s\S]*?</div>', f'<div id="root">{inner}</div>', template, count=1)


async def render(path: str, host: str, db, seo: dict, template: str) -> dict:
    """Return {status, location?, html?, content_type} for a public path."""
    base = (seo.get("canonical_base") or PREFERRED_BASE).rstrip("/")
    p = normalize(path)

    # 1) www / host canonicalization (defense in depth; nginx also 301s)
    if host and host.lower().startswith("www."):
        return {"status": 301, "location": base + (path if path.startswith("/") else "/" + path)}

    # 2) legacy redirects. Old addresses were not case-sensitive (/Home), so match in lower case.
    legacy = p.lower()
    if legacy in REDIRECTS:
        return {"status": 301, "location": base + REDIRECTS[legacy]}
    for prefix, target in REDIRECT_PREFIXES.items():
        if legacy.startswith(prefix):
            return {"status": 301, "location": base + target}

    # 3) old individual job URLs -> the same role under Careers if it is open, else Careers.
    #    The old job feed is the one exception: it is gone, not moved.
    if p.startswith("/jobs/"):
        slug = p.split("/jobs/", 1)[1]
        if slug == "feed":
            return {"status": 410, "html": _error_html(template, 410, base), "content_type": "text/html; charset=utf-8"}
        job = await db.jobs.find_one({"slug": slug, "published": {"$ne": False}})
        return {"status": 301, "location": base + (f"/careers/{slug}" if job else "/careers")}

    # 3b) one address per page: /careers/ is the same page as /careers, so send the
    #     trailing-slash form to the plain one (Search Console listed /careers/ as a duplicate).
    raw = (path or "/").split("#")[0]
    raw_path, _, query = raw.partition("?")
    if len(raw_path) > 1 and raw_path.endswith("/"):
        return {"status": 301, "location": base + p + (f"?{query}" if query else "")}

    og_title = ((seo.get("pages") or {}).get(p) or {}).get("title") or ROUTES.get(p, {}).get("title", ORG["name"])
    og_default = f"{base}/api/og/page.png?title={_q(og_title)}&label=Intrinsic%20Technology"

    # 4) known static routes
    r = ROUTES.get(p)
    if r:
        meta = page_meta(p, r, seo, base, og_default)
        inner, extra_ld = await _static_body(p, r, base, db, seo)
        html = _meta_head(template, title=meta["title"], description=meta["description"], canonical=meta["canonical"],
                          robots=meta["robots"], og_image=meta["og_image"], og_type=meta["og_type"], extra_ld=extra_ld,
                          keywords=meta["keywords"])
        return {"status": 200, "html": _inject_body(html, inner), "content_type": "text/html; charset=utf-8"}

    # 5) dynamic case studies
    if p.startswith("/case-studies/"):
        slug = p.split("/case-studies/", 1)[1]
        cs = await _find_by_slug(db.case_studies, slug, include_prev=True)
        if cs:
            return _dynamic_page(template, base, p, _case_study_view(cs, base))

    # 6) dynamic blog posts (published only)
    if p.startswith("/blog/"):
        slug = p.split("/blog/", 1)[1]
        post = await _find_by_slug(db.blogs, slug, published_only=True)
        if post:
            return _dynamic_page(template, base, p, _blog_view(post, base))

    # 7) dynamic job detail
    if p.startswith("/careers/") and p != "/careers":
        slug = p.split("/careers/", 1)[1]
        job = await db.jobs.find_one({"slug": slug, "published": {"$ne": False}}, {"_id": 0})
        if job:
            return _dynamic_page(template, base, p, _job_view(job, base))

    # 8) unknown -> genuine 404
    return {"status": 404, "html": _error_html(template, 404, base), "content_type": "text/html; charset=utf-8"}


# ---- helpers ----
def _q(s: str) -> str:
    from urllib.parse import quote
    return quote(str(s or "")[:120])


def _full_title(r: dict, seo: dict, override: dict = None) -> str:
    override = override or {}
    tmpl = seo.get("title_template") or "{title} | Intrinsic Technology"
    custom = (override.get("title") or "").strip()
    if r.get("kind") == "home":
        if custom:
            return tmpl.replace("{title}", custom)
        return (seo.get("default_title") or "").strip() or "Intrinsic Technology | Managed IT, Cybersecurity & Cloud Services"
    return tmpl.replace("{title}", custom or r["title"])


def page_meta(p: str, r: dict, seo: dict, base: str, og_default: str) -> dict:
    """Head tags for a standard page. What the admin enters under SEO & GEO > Per-page overrides
    (seo["pages"][path]) wins over the built-in defaults, exactly as it does in the browser
    (frontend/src/lib/SeoContext.jsx) — so crawlers reading the page source see the same title
    and description that visitors' browsers show."""
    ov = (seo.get("pages") or {}).get(p) or {}
    text = lambda key: (ov.get(key) or "").strip()
    if r.get("kind") == "home":
        description = text("description") or (seo.get("default_description") or "").strip() or r["description"]
    else:
        description = text("description") or r["description"]
    og_image = text("og_image")
    if og_image and not og_image.startswith("http"):
        og_image = base + (og_image if og_image.startswith("/") else f"/api/files/{og_image}")
    return {
        "title": _full_title(r, seo, ov),
        "description": description,
        "keywords": text("keywords") or (seo.get("default_keywords") or "").strip(),
        "canonical": base + p,
        "robots": text("robots") or (seo.get("robots_default") or "").strip() or "index, follow",
        "og_image": og_image or og_default,
        "og_type": "website",
    }


async def _find_by_slug(coll, slug, include_prev=False, published_only=False):
    q = {"published": True} if published_only else {}
    async for doc in coll.find(q, {"_id": 0}):
        if _slug(doc.get("title", "")) == slug or doc.get("id") == slug:
            return doc
        if include_prev and any(_slug(t) == slug for t in (doc.get("previous_titles") or [])):
            return doc
    return None


async def _static_body(p: str, r: dict, base: str, db, seo: dict):
    kind = r.get("kind")
    extra_ld = [] if p == "/" else [breadcrumb_ld(p, base)]
    parts = [_crumbs_html(p), f"<h1>{esc(r['title'])}</h1>"]

    if kind == "home":
        site = await db.site.find_one({"key": "content"}, {"_id": 0}) or {}
        parts = [f"<h1>{esc(site.get('hero_h1') or r['title'])}</h1>"]
        if site.get("hero_h2"):
            parts.append(f"<p><strong>{esc(site['hero_h2'])}</strong></p>")
        parts.append(f"<p>{esc(site.get('hero_paragraph') or r['description'])}</p>")
        faqs = [(f["q"], f["a"]) for f in ((seo.get("geo") or {}).get("faqs") or []) if f.get("q") and f.get("a")]
        parts.append(_faq_html(faqs))
        if faqs:
            extra_ld.append(faq_ld(faqs))
        # case study teasers
        teasers = []
        async for c in db.case_studies.find({}, {"_id": 0, "title": 1, "summary": 1, "stat": 1}).limit(5):
            s = _slug(c.get("title", ""))
            teasers.append(f'<li><a href="/case-studies/{s}">{esc(c.get("title"))}</a> — {esc((c.get("summary") or c.get("stat") or "")[:140])}</li>')
        if teasers:
            parts.append(f'<section aria-label="Case studies"><h2>Client case studies</h2><ul>{"".join(teasers)}</ul></section>')
    else:
        for para in INTRO.get(p, [r["description"]]):
            parts.append(f"<p>{esc(para)}</p>")
        faqs = FAQS.get(p)
        if faqs:
            parts.append(_faq_html(faqs))
            extra_ld.append(faq_ld(faqs))
        if kind in ("service", "location"):
            extra_ld.append({"@context": "https://schema.org", "@type": "Service", "name": r["title"],
                             "description": r["description"], "serviceType": r["title"],
                             "provider": {"@id": base + "/#organization"}, "areaServed": "US", "url": base + p})
        if kind == "careers":
            jobs = []
            async for j in db.jobs.find({"published": {"$ne": False}}, {"_id": 0}):
                if j.get("slug"):
                    jobs.append(f'<li><a href="/careers/{esc(j["slug"])}">{esc(j.get("title"))}</a> — {esc(j.get("type") or "")} · {esc(j.get("location") or "")}</li>')
            parts.append(f'<section aria-label="Open roles"><h2>Open roles</h2><ul>{"".join(jobs) or "<li>No open roles at this time.</li>"}</ul></section>')

    parts.append(_nav_and_contact(base))
    return "\n".join(x for x in parts if x), extra_ld


def _dynamic_page(template, base, p, view):
    title, description, body, ld, og_image = view
    html = _meta_head(template, title=title, description=description, canonical=base + p,
                      robots="index, follow", og_image=og_image or f"{base}/api/og/page.png?title={_q(title)}",
                      og_type="article", extra_ld=[breadcrumb_ld(p, base)] + ld)
    return {"status": 200, "html": _inject_body(html, body), "content_type": "text/html; charset=utf-8"}


def _case_study_view(cs, base):
    slug = _slug(cs.get("title", ""))
    title = (cs.get("seo_title") or cs.get("title")) + " | Intrinsic Technology"
    desc = (cs.get("seo_description") or cs.get("geo_summary") or cs.get("summary") or str(cs.get("body") or "")[:180])[:300]
    og = cs.get("og_image") or f"{base}/api/og/case-studies/{slug}.png"
    sec = [_crumbs_html(f"/case-studies/{slug}"), f"<h1>{esc(cs.get('title'))}</h1>"]
    if cs.get("stat"):
        sec.append(f"<p><strong>{esc(cs['stat'])}</strong></p>")
    for para in _paras(cs.get("body")):
        sec.append(f"<p>{esc(para)}</p>")
    if cs.get("challenge"):
        sec.append("<h2>The Challenge</h2>" + "".join(f"<p>{esc(x)}</p>" for x in _paras(cs["challenge"])))
    if cs.get("approach"):
        sec.append("<h2>The Solution and Impact</h2>" + "".join(f"<p>{esc(x)}</p>" for x in _paras(cs["approach"])))
    if cs.get("results"):
        sec.append("<h2>Results</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in cs["results"]) + "</ul>")
    if cs.get("quote"):
        sec.append(f"<blockquote><p>{esc(cs['quote'])}</p>{('<cite>' + esc(cs.get('quote_author')) + '</cite>') if cs.get('quote_author') else ''}</blockquote>")
    sec.append(_nav_and_contact(base))
    ld = [{"@context": "https://schema.org", "@type": "Article", "headline": cs.get("seo_title") or cs.get("title"),
           "description": desc, "image": og, "author": {"@type": "Organization", "name": ORG["name"]},
           "publisher": {"@type": "Organization", "name": ORG["name"]}, "articleSection": cs.get("tag") or None,
           "mainEntityOfPage": base + f"/case-studies/{slug}"}]
    return title, desc, "\n".join(sec), ld, og


def _blog_view(post, base):
    slug = _slug(post.get("title", ""))
    title = (post.get("seo_title") or post.get("title")) + " | Intrinsic Technology"
    desc = (post.get("seo_description") or post.get("geo_summary") or post.get("excerpt") or str(post.get("content") or "")[:180])[:300]
    og = post.get("og_image") or f"{base}/api/og/blogs/{slug}.png"
    sec = [_crumbs_html(f"/blog/{slug}"), f"<h1>{esc(post.get('title'))}</h1>"]
    if post.get("author"):
        sec.append(f'<p>By {esc(post["author"])}{(" · " + esc(post.get("date"))) if post.get("date") else ""}</p>')
    if post.get("excerpt"):
        sec.append(f"<p>{esc(post['excerpt'])}</p>")
    for para in _paras(post.get("content")):
        sec.append(f"<p>{esc(para)}</p>")
    sec.append(_nav_and_contact(base))
    ld = [{"@context": "https://schema.org", "@type": "BlogPosting", "headline": post.get("seo_title") or post.get("title"),
           "description": desc, "image": og, "datePublished": post.get("date") or post.get("created_at") or None,
           "author": {"@type": "Person", "name": post.get("author") or ORG["name"]},
           "publisher": {"@type": "Organization", "name": ORG["name"]}, "articleSection": post.get("category") or None,
           "mainEntityOfPage": base + f"/blog/{slug}"}]
    return title, desc, "\n".join(sec), ld, og


_EMP = {"full time": "FULL_TIME", "full-time": "FULL_TIME", "part time": "PART_TIME", "part-time": "PART_TIME", "contract": "CONTRACTOR", "internship": "INTERN", "temporary": "TEMPORARY"}


def _job_view(job, base):
    slug = job.get("slug")
    title = job.get("title") + " | Intrinsic Technology"
    descparts = [job.get("overview")] + list(job.get("responsibilities") or []) + list(job.get("requirements") or [])
    desc = (job.get("overview") or f"Open role: {job.get('title')}")[:300]
    sec = [_crumbs_html(f"/careers/{slug}"), f"<h1>{esc(job.get('title'))}</h1>",
           f"<p><strong>{esc(job.get('type') or '')}</strong> · {esc(job.get('location') or '')} · {esc(job.get('category') or '')}</p>"]
    if job.get("overview"):
        sec.append("<h2>Overview</h2><p>" + esc(job["overview"]) + "</p>")
    for label, key in (("What you'll do", "responsibilities"), ("Who you are", "requirements"), ("Preferred", "preferred")):
        if job.get(key):
            sec.append(f"<h2>{label}</h2><ul>" + "".join(f"<li>{esc(x)}</li>" for x in job[key]) + "</ul>")
    sec.append(f'<p><a href="/careers/{esc(slug)}#apply">Apply for this position</a></p>')
    sec.append(_nav_and_contact(base))
    ld = {"@context": "https://schema.org", "@type": "JobPosting", "title": job.get("title"),
          "description": " ".join([x for x in descparts if x]), "datePosted": job.get("created_at") or None,
          "employmentType": _EMP.get(str(job.get("type") or "").lower().strip(), "FULL_TIME"),
          "hiringOrganization": {"@type": "Organization", "name": ORG["name"], "sameAs": base, "logo": base + "/favicon-512.png"},
          "directApply": True}
    loc = str(job.get("location") or "")
    if re.search(r"remote|telecommute", loc, re.I):
        ld["jobLocationType"] = "TELECOMMUTE"
        ld["applicantLocationRequirements"] = {"@type": "Country", "name": "USA"}
    else:
        bits = [s.strip() for s in re.sub(r"^hybrid[\s—-]*", "", loc, flags=re.I).split(",")]
        ld["jobLocation"] = {"@type": "Place", "address": {"@type": "PostalAddress", "addressLocality": bits[0] if bits else "New York", "addressRegion": bits[1] if len(bits) > 1 else "NY", "addressCountry": "US"}}
    return title, desc, "\n".join(sec), [ld], None


def _error_html(template, code, base):
    title = ("Page Not Found (404)" if code == 404 else "Page No Longer Available (410)") + " | Intrinsic Technology"
    msg = ("The page you are looking for could not be found." if code == 404
           else "This page is no longer available.")
    html = _meta_head(template, title=title, description=msg, canonical="", robots="noindex, follow",
                      og_image=f"{base}/api/og/page.png?title=Not%20Found", og_type="website", extra_ld=[])
    body = (f'<main><h1>{code} — {esc(msg)}</h1>'
            f'<p>Try our <a href="/">home page</a>, <a href="/services/managed-it">services</a>, '
            f'<a href="/industries">industries</a>, or <a href="/contact">contact us</a>.</p></main>')
    return _inject_body(html, body)
