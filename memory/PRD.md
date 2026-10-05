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
- Per-route client meta engine (src/lib/SeoContext.jsx + head.js): title, description, keywords, canonical, OG, Twitter, JSON-LD (Service, BreadcrumbList, FAQPage, Article/BlogPosting).
- Backend: GET /api/seo (+PUT admin), /api/sitemap.xml (current routes + published blog/case-study/career slugs), /api/robots.txt (allows GPTBot, OAI-SearchBot, ClaudeBot, PerplexityBot, Bingbot, Google-Extended + Sitemap), /api/llms.txt, dynamic /api/og/{coll}/{slug}.png social images.
- Animated counters (CountUp) start at the real value, not 0 (assessment Finding 7).
- **NEW — build-time prerender** (frontend/scripts/prerender.cjs, wired as `postbuild`): writes 34 per-route static index.html files with correct per-page title, description, canonical, OG/Twitter, per-route JSON-LD (Service + BreadcrumbList) and answer-first content — fixes assessment Findings 1, 2, 8, 9 (client-side rendering left per-route HTML generic for non-JS/AI crawlers). Global <noscript> block removed so each route has a single accurate <h1>.
- Testing agent: 100% backend (6/6), 100% frontend. Backend SEO suite at backend/tests/test_seo_endpoints.py.

## Status
- App installed into /app, services running, `/api/health` ok. First production deploy was prepared and is pending the user's 50-ECU first-deploy confirmation.

## Backlog / Not in codebase (require owner action, out of app scope)
- P1: 301 redirect map for legacy URLs; choose canonical www vs non-www at the host/DNS layer.
- P1: Register Bing Webmaster Tools + IndexNow; claim Google Business Profile per office.
- P2: Dynamic detail pages (blog/case-study/career slugs) are not statically prerendered — they rely on client-side schema + are in the sitemap; add to prerender if AI indexing of those specific URLs is needed.
- P2: Additional location-specific pages (NJ/Boston/DC) and expanded FAQ content for GEO.
