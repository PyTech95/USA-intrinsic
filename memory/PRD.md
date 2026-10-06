# Intrinsic Technology — Website & CMS (React + FastAPI + MongoDB)

## Problem Statement
Production deploy + SEO/GEO hardening of "Intrinsic" — a marketing/CMS site for Intrinsic Technology Group (a women/minority-owned MSP in NYC offering Managed IT, Cybersecurity, Cloud, AI). User supplied a third-party SEO/GEO assessment PDF and asked to verify/complete all fixes so the site performs for both classic SEO and Generative Engine Optimization (visibility to AI crawlers).

## Architecture
- Frontend: React 19 (CRA via craco), react-router 7, Tailwind/shadcn UI.
- Backend: FastAPI + Motor (async MongoDB), JWT admin auth, emergent object storage, emergentintegrations LLM key.
- DB: MongoDB (local in preview). Auto-seeds admin + restores content from backend/seed_data/site_export.json on fresh DB.

## Setup Notes
- backend/.env: MONGO_URL, DB_NAME, CORS_ORIGINS, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD, EMERGENT_LLM_KEY.
- Admin seeded from ADMIN_EMAIL/ADMIN_PASSWORD (see test_credentials.md). Password not reset on restart.

## SEO / GEO — Implemented (verified June 2026)
- Static Organization / ProfessionalService(LocalBusiness) / WebSite JSON-LD @graph in public/index.html.
- Per-route client meta engine (src/lib/SeoContext.jsx + head.js): title, description, keywords, canonical, OG, Twitter, JSON-LD (Service, BreadcrumbList, FAQPage, Article/BlogPosting, JobPosting).
- Backend: GET /api/seo (+PUT admin), /api/sitemap.xml, /api/robots.txt (allows GPTBot, OAI-SearchBot, ChatGPT-User, ClaudeBot, PerplexityBot, Bingbot, Google-Extended + Sitemap), /api/llms.txt, dynamic /api/og/{coll}/{slug}.png social images.
- Animated counters (CountUp) start at the real value, not 0.
- Admin per-page SEO editor: src/components/admin/SeoManager.jsx (editable titles/descriptions per path).
- 404: NotFound page sets robots noindex; catch-all route present.
- **Build-time prerender** (frontend/scripts/prerender.cjs, wired as `postbuild`): writes correct per-page title/description/canonical/OG/Twitter + JSON-LD + answer-first content for EVERY public page. Output: static=34, redirect stubs=7, dynamic=10 (5 case studies + 5 jobs; 0 blogs = all drafts). Total 44 public pages. Dynamic pages fetched best-effort from /api/content/{case-studies,blogs,jobs} at build time (auto-updates as content changes).
- **Legacy URL redirects** (assessment Finding #3): client-side <Navigate> routes in App.js + prerendered redirect stubs (canonical→target + meta-refresh + noindex + JS replace) for /about-us, /help-desk-support, /healthcare, /terms-conditions, /privacy, /contact-us, /jobs.
- **JobPosting schema** on job pages (JobDetail.jsx) with title, description, datePosted, employmentType, hiringOrganization, jobLocation / TELECOMMUTE.
- Testing: iteration_1 (static prerender + SEO endpoints) and iteration_2 (JobPosting, redirects, dynamic prerender) both 100%. Backend SEO suite at backend/tests/test_seo_endpoints.py.
- Checklist items NOT in code scope (owner/account actions): submit sitemap in Google Search Console; register Bing Webmaster Tools + IndexNow; Google Business Profile / LinkedIn / Clutch NAP; www-vs-non-www 301 at DNS/host layer.

## Status
- App installed into /app, services running, `/api/health` ok. First production deploy was prepared and is pending the user's 50-ECU first-deploy confirmation.

## Backlog / Not in codebase (require owner action, out of app scope)
- P1: 301 redirect map for legacy URLs; choose canonical www vs non-www at the host/DNS layer.
- P1: Register Bing Webmaster Tools + IndexNow; claim Google Business Profile per office.
- P2: Dynamic detail pages (blog/case-study/career slugs) are not statically prerendered — they rely on client-side schema + are in the sitemap; add to prerender if AI indexing of those specific URLs is needed.
- P2: Additional location-specific pages (NJ/Boston/DC) and expanded FAQ content for GEO.
