/*
 * Build-time prerender (no headless browser).
 * Writes per-route static HTML so non-JS crawlers (Bing, GPTBot, ClaudeBot,
 * PerplexityBot, link-preview bots) see the correct title, meta, canonical,
 * Open Graph/Twitter tags, JSON-LD and answer-first content for EVERY public
 * page instead of the generic homepage shell.
 *
 * Covers: static routes, legacy-URL redirect stubs (301-style via canonical +
 * meta-refresh), and dynamic detail pages (case studies, published blog posts,
 * open job postings) fetched best-effort from the backend API at build time.
 *
 * Addresses SEO/GEO assessment: client-side rendering empty HTML (#1),
 * per-page meta/titles (#2), legacy 301 redirects (#3), structured data (#8),
 * content for AI answers (#9).
 */
const fs = require("fs");
const path = require("path");

const BUILD_DIR = path.resolve(__dirname, "..", "build");
const BASE = (process.env.PRERENDER_BASE_URL || "https://intrinsicamerica.com").replace(/\/+$/, "");
const TITLE_TMPL = "{title} | Intrinsic Technology";

// Backend API base for best-effort dynamic fetch (build time).
function readApiBase() {
  if (process.env.PRERENDER_API_URL) return process.env.PRERENDER_API_URL.replace(/\/+$/, "");
  try {
    const env = fs.readFileSync(path.resolve(__dirname, "..", ".env"), "utf8");
    const m = env.match(/^REACT_APP_BACKEND_URL\s*=\s*(.+)$/m);
    if (m) return m[1].trim().replace(/\/+$/, "") + "/api";
  } catch (e) {}
  return "";
}
const API = readApiBase();

const slugify = (s = "") => s.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
const esc = (s) => String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const titleCase = (seg) => seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

const ROUTES = [
  { path: "/", label: "Home", title: "Managed IT, Cybersecurity & Cloud Services", description: "Complete oversight of your technology environment—proactive monitoring, infrastructure management, and strategic guidance to keep operations secure and resilient.", home: true },
  { path: "/about", label: "About Us", title: "About Intrinsic Technology", description: "A women-owned and minority-owned managed service provider in New York City delivering accountable, coordinated technology services." },
  { path: "/resources", label: "Resources", title: "Resources, Insights & Case Studies", description: "Practical insights, service briefs, and client case studies to help you make better technology decisions." },
  { path: "/careers", label: "Careers", title: "Careers at Intrinsic Technology", description: "Join a technology team focused on security, reliability, and real client outcomes." },
  { path: "/contact", label: "Contact", title: "Talk to an Expert", description: "Get in touch with Intrinsic Technology to discuss managed IT, cybersecurity, cloud, and AI services." },
  { path: "/privacy-policy", label: "Privacy Policy", title: "Privacy Policy", description: "How Intrinsic Technology collects, uses, and protects your information." },
  { path: "/terms-of-service", label: "Terms of Service", title: "Terms of Service", description: "The terms governing use of the Intrinsic Technology website." },
  { path: "/security-risk-assessment", label: "Security Risk Assessment", title: "Security Risk Assessment", description: "Identify gaps and prioritize remediation with a structured security risk assessment." },
  { path: "/services/ai", label: "AI Services", title: "AI Services & Automation", description: "Adopt AI responsibly with readiness assessments, managed AI, and governance aligned to your business." },
  { path: "/services/ai-readiness-assessment", label: "AI Readiness Assessment", title: "AI Readiness Assessment", description: "A comprehensive view of your AI readiness across business, data, security, governance, and organizational preparedness." },
  { path: "/services/managed-ai", label: "Managed AI", title: "Managed AI", description: "Ongoing management of AI tools, access, and governance so your organization benefits safely." },
  { path: "/services/ai-governance-compliance", label: "AI Governance & Compliance", title: "AI Governance & Compliance", description: "Establish policy, oversight, and controls for responsible AI adoption." },
  { path: "/services/cybersecurity", label: "Cybersecurity", title: "Cybersecurity Services", description: "Coordinated security management across users, devices, networks, cloud, applications, and data." },
  { path: "/services/threat-detection-response", label: "Threat Detection & Response", title: "Threat Detection & Response", description: "Continuous monitoring, detection, and rapid response to security threats." },
  { path: "/services/identity-endpoint-security", label: "Identity & Endpoint Security", title: "User, Identity & Endpoint Security", description: "Protect identities and endpoints with layered controls and patch compliance." },
  { path: "/services/network-perimeter-security", label: "Network & Perimeter Security", title: "Network & Perimeter Security", description: "Secure your network edge with firewalls, segmentation, and monitoring." },
  { path: "/services/security-monitoring-siem", label: "Security Monitoring & SIEM", title: "Security Monitoring & Analytics (SIEM)", description: "Centralized logging, correlation, and analytics for faster threat insight." },
  { path: "/services/security-assessments", label: "Security Assessments", title: "Security Assessments & Vulnerability Management", description: "Regular assessments and vulnerability management to reduce risk." },
  { path: "/services/security-governance-compliance", label: "Security Governance & Compliance", title: "Security Governance & Compliance", description: "Governance aligned to NIST CSF, HIPAA, NYDFS, and SOC 2." },
  { path: "/services/networking", label: "Networking", title: "Networking Services", description: "Design, deployment, and management of reliable business networks." },
  { path: "/services/cloud", label: "Cloud", title: "Cloud Services", description: "Cloud infrastructure, migration, and management built for resilience." },
  { path: "/services/cloud-infrastructure-migration", label: "Cloud Infrastructure & Migration", title: "Cloud Infrastructure & Migration", description: "Migrate and modernize on Microsoft Azure and Microsoft 365 without the chaos." },
  { path: "/services/backup-disaster-recovery", label: "Backup & Disaster Recovery", title: "Backup & Disaster Recovery", description: "Protect your data and operations with tested backup and recovery." },
  { path: "/services/managed-it", label: "Managed IT", title: "Managed IT Services", description: "Complete oversight of your IT environment with proactive support and management." },
  { path: "/services/co-managed-it", label: "Co-Managed IT", title: "Co-Managed IT", description: "Extend your internal IT team with coordinated managed services." },
  { path: "/services/remote-monitoring-management", label: "Remote Monitoring & Management", title: "Remote Monitoring & Management", description: "24/7 monitoring and management of devices and systems." },
  { path: "/services/microsoft-365", label: "Microsoft 365", title: "Microsoft 365 Services", description: "Deploy, secure, and manage Microsoft 365 for productivity and compliance." },
  { path: "/services/vcio-vciso", label: "vCIO & vCISO", title: "vCIO & vCISO", description: "Strategic technology and security leadership that guides priorities and investment." },
  { path: "/industries", label: "Industries", title: "Industries We Serve", description: "Technology services tailored to healthcare, financial, legal, construction, nonprofit, and professional services." },
  { path: "/industries/construction", label: "Construction", title: "IT for Construction", description: "Technology that extends to the field for construction and manufacturing." },
  { path: "/industries/professional-services", label: "Professional Services", title: "IT for Professional Services", description: "Secure, reliable technology for professional services firms." },
  { path: "/industries/financial-services", label: "Financial Services", title: "IT for Financial Services", description: "Compliance-ready managed IT and security for financial services." },
  { path: "/industries/non-profit", label: "Non-Profit", title: "IT for Non-Profits", description: "Affordable, dependable technology for nonprofit organizations." },
  { path: "/industries/healthcare", label: "Healthcare", title: "IT for Healthcare", description: "HIPAA-aligned managed IT and security for healthcare providers." },
];

// Legacy URL -> current URL (assessment Finding #3). Served to crawlers as
// canonical + meta-refresh + JS redirect from a static stub at build/<old>/.
const REDIRECTS = {
  "/about-us": "/about",
  "/help-desk-support": "/services/managed-it",
  "/healthcare": "/industries/healthcare",
  "/terms-conditions": "/terms-of-service",
  "/privacy": "/privacy-policy",
  "/contact-us": "/contact",
  "/jobs": "/careers",
};

const EMP_TYPE = { "full time": "FULL_TIME", "full-time": "FULL_TIME", "part time": "PART_TIME", "part-time": "PART_TIME", contract: "CONTRACTOR", contractor: "CONTRACTOR", internship: "INTERN", temporary: "TEMPORARY" };

function breadcrumbLd(route) {
  const parts = route.path.split("/").filter(Boolean);
  const items = [{ "@type": "ListItem", position: 1, name: "Home", item: BASE + "/" }];
  let acc = "";
  parts.forEach((seg, i) => {
    acc += "/" + seg;
    const def = ROUTES.find((r) => r.path === acc);
    items.push({ "@type": "ListItem", position: i + 2, name: (def && def.label) || route.crumbName || titleCase(seg), item: BASE + acc });
  });
  return { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: items };
}

function routeJsonLd(route) {
  const out = [];
  if (!route.home) out.push(breadcrumbLd(route));
  if (route.path.startsWith("/services/")) {
    out.push({ "@context": "https://schema.org", "@type": "Service", name: route.title, description: route.description, serviceType: route.title, provider: { "@id": BASE + "/#organization" }, areaServed: "US", url: BASE + route.path });
  }
  (route.extraLd || []).forEach((l) => l && out.push(l));
  return out;
}

function contentBlock(route) {
  const crumbs = (() => {
    if (route.home) return "";
    const parts = route.path.split("/").filter(Boolean);
    let acc = "";
    const links = ['<a href="/">Home</a>'];
    parts.forEach((seg) => {
      acc += "/" + seg;
      const def = ROUTES.find((r) => r.path === acc);
      links.push(`<a href="${acc}">${esc((def && def.label) || route.crumbName || titleCase(seg))}</a>`);
    });
    return `<nav aria-label="Breadcrumb">${links.join(" / ")}</nav>`;
  })();
  const primaryLinks = ROUTES.filter((r) => ["/services/managed-it", "/services/cybersecurity", "/services/cloud", "/services/ai", "/services/vcio-vciso", "/industries", "/about", "/contact"].includes(r.path))
    .map((r) => `<li><a href="${r.path}">${esc(r.label)}</a></li>`).join("");
  const extra = route.bodyHtml || `<p>Intrinsic Technology is a women-owned and minority-owned managed service provider (MSP) in New York City serving healthcare, financial services, legal, construction, and nonprofit organizations. <a href="/contact">Talk to an expert</a>.</p>`;
  return `
      <main>
        ${crumbs}
        <h1>${esc(route.title)}</h1>
        <p>${esc(route.description)}</p>
        ${extra}
        <nav aria-label="Primary"><ul>${primaryLinks}</ul></nav>
      </main>`;
}

function renderRoute(template, route) {
  const canonical = BASE + route.path;
  const fullTitle = route.home ? "Intrinsic Technology | Managed IT, Cybersecurity & Cloud Services" : TITLE_TMPL.replace("{title}", route.title);
  let html = template;
  html = html.replace(/<title>[\s\S]*?<\/title>/, `<title>${esc(fullTitle)}</title>`);
  html = html.replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${esc(route.description)}" />`);
  html = html.replace(/<meta property="og:title"[^>]*>/, `<meta property="og:title" content="${esc(fullTitle)}" />`);
  html = html.replace(/<meta property="og:description"[^>]*>/, `<meta property="og:description" content="${esc(route.description)}" />`);
  html = html.replace(/<meta property="og:url"[^>]*>/, `<meta property="og:url" content="${esc(canonical)}" />`);
  html = html.replace(/<meta name="twitter:title"[^>]*>/, `<meta name="twitter:title" content="${esc(fullTitle)}" />`);
  html = html.replace(/<meta name="twitter:description"[^>]*>/, `<meta name="twitter:description" content="${esc(route.description)}" />`);
  if (route.ogImage) {
    html = html.replace(/<meta property="og:image"[^>]*>/, `<meta property="og:image" content="${esc(route.ogImage)}" />`);
    html = html.replace(/<meta name="twitter:image"[^>]*>/, `<meta name="twitter:image" content="${esc(route.ogImage)}" />`);
  }
  const extraLd = routeJsonLd(route).map((o) => `<script type="application/ld+json">${JSON.stringify(o)}</script>`).join("\n");
  html = html.replace("</head>", `<link rel="canonical" href="${esc(canonical)}" data-prerender="1" />\n${extraLd}\n</head>`);
  html = html.replace(/<div id="root">\s*<\/div>/, `<div id="root">${contentBlock(route)}</div>`);
  return html;
}

function renderRedirect(template, from, to) {
  const target = BASE + to;
  let html = template;
  html = html.replace(/<title>[\s\S]*?<\/title>/, `<title>Redirecting… | Intrinsic Technology</title>`);
  html = html.replace(/\s*<meta name="robots"[^>]*>/g, "");
  const head = `<link rel="canonical" href="${esc(target)}" data-prerender="1" />\n<meta http-equiv="refresh" content="0; url=${esc(to)}" />\n<meta name="robots" content="noindex, follow" />\n<script>window.location.replace(${JSON.stringify(to)});</script>\n</head>`;
  html = html.replace("</head>", head);
  html = html.replace(/<div id="root">\s*<\/div>/, `<div id="root"><main><p>This page has moved. Redirecting to <a href="${esc(to)}">${esc(target)}</a>.</p></main></div>`);
  return html;
}

function writeRoute(template, route) {
  const html = renderRoute(template, route);
  const outDir = route.home ? BUILD_DIR : path.join(BUILD_DIR, route.path);
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, "index.html"), html, "utf8");
}

async function fetchJson(url) {
  if (typeof fetch !== "function" || !API) return null;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), 8000);
    const res = await fetch(url, { signal: ctrl.signal });
    clearTimeout(t);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}

async function dynamicRoutes() {
  const routes = [];
  if (!API) {
    console.log("[prerender] no API base — skipping dynamic (case studies / blog / jobs) pages");
    return routes;
  }
  const [caseStudies, blogs, jobs] = await Promise.all([
    fetchJson(`${API}/content/case-studies`),
    fetchJson(`${API}/content/blogs`),
    fetchJson(`${API}/content/jobs`),
  ]);

  (caseStudies || []).forEach((c) => {
    const slug = slugify(c.title || "");
    if (!slug) return;
    const title = c.seo_title || c.title;
    const description = (c.seo_description || c.geo_summary || c.summary || String(c.body || "").slice(0, 180) || "Client case study from Intrinsic Technology.").slice(0, 300);
    routes.push({
      path: `/case-studies/${slug}`, title, description, crumbName: "Case Studies",
      ogImage: c.og_image ? c.og_image : `${API}/og/case-studies/${slug}.png`,
      bodyHtml: `<p>${esc(String(c.body || "").slice(0, 600))}</p>`,
      extraLd: [{ "@context": "https://schema.org", "@type": "Article", headline: title, description, image: c.og_image || `${API}/og/case-studies/${slug}.png`, author: { "@type": "Organization", name: "Intrinsic Technology" }, publisher: { "@type": "Organization", name: "Intrinsic Technology" }, articleSection: c.tag || undefined, mainEntityOfPage: BASE + `/case-studies/${slug}` }],
    });
  });

  (blogs || []).forEach((b) => {
    const slug = slugify(b.title || "");
    if (!slug) return;
    const title = b.seo_title || b.title;
    const description = (b.seo_description || b.geo_summary || b.excerpt || String(b.content || "").slice(0, 180) || "Insight from Intrinsic Technology.").slice(0, 300);
    routes.push({
      path: `/blog/${slug}`, title, description, crumbName: "Resources",
      ogImage: b.og_image ? b.og_image : `${API}/og/blogs/${slug}.png`,
      bodyHtml: `<p>${esc(b.excerpt || "")}</p>`,
      extraLd: [{ "@context": "https://schema.org", "@type": "BlogPosting", headline: title, description, image: b.og_image || `${API}/og/blogs/${slug}.png`, author: { "@type": "Person", name: b.author || "Intrinsic Technology" }, publisher: { "@type": "Organization", name: "Intrinsic Technology" }, articleSection: b.category || undefined, mainEntityOfPage: BASE + `/blog/${slug}` }],
    });
  });

  (jobs || []).filter((j) => j.published !== false && j.slug).forEach((j) => {
    const descParts = [j.overview, ...(j.responsibilities || []), ...(j.requirements || [])].filter(Boolean);
    const description = (j.overview || `Open role: ${j.title}`).slice(0, 300);
    const ld = {
      "@context": "https://schema.org", "@type": "JobPosting", title: j.title,
      description: descParts.join(" "), datePosted: j.created_at || undefined,
      employmentType: EMP_TYPE[String(j.type || "").toLowerCase().trim()] || "FULL_TIME",
      hiringOrganization: { "@type": "Organization", name: "Intrinsic Technology", sameAs: BASE, logo: BASE + "/favicon-512.png" },
      directApply: true,
    };
    const loc = String(j.location || "");
    if (/remote|telecommute/i.test(loc)) { ld.jobLocationType = "TELECOMMUTE"; ld.applicantLocationRequirements = { "@type": "Country", name: "USA" }; }
    else { const [city, region] = loc.replace(/^hybrid[\s—-]*/i, "").split(",").map((s) => s.trim()); ld.jobLocation = { "@type": "Place", address: { "@type": "PostalAddress", addressLocality: city || "New York", addressRegion: region || "NY", addressCountry: "US" } }; }
    routes.push({
      path: `/careers/${j.slug}`, title: j.title, description, crumbName: "Careers",
      bodyHtml: `<p><strong>${esc(j.type || "")}</strong> · ${esc(j.location || "")}</p><p>${esc(descParts.slice(0, 4).join(" ").slice(0, 600))}</p><p><a href="/careers/${j.slug}#apply">Apply for this position</a></p>`,
      extraLd: [ld],
    });
  });

  return routes;
}

async function fetchSeo() {
  if (!API) return null;
  return await fetchJson(`${API}/seo`);
}

async function main() {
  const indexPath = path.join(BUILD_DIR, "index.html");
  if (!fs.existsSync(indexPath)) {
    console.error("[prerender] build/index.html not found — run after craco build");
    process.exit(1);
  }
  const template = fs.readFileSync(indexPath, "utf8");

  // Enrich the home route with FAQPage schema + visible FAQ content (assessment #8/#9).
  const seo = await fetchSeo();
  const faqs = ((seo && seo.geo && seo.geo.faqs) || []).filter((f) => f && f.q && f.a);
  const home = ROUTES.find((r) => r.home);
  if (home && faqs.length) {
    home.extraLd = [{ "@context": "https://schema.org", "@type": "FAQPage", mainEntity: faqs.map((f) => ({ "@type": "Question", name: f.q, acceptedAnswer: { "@type": "Answer", text: f.a } })) }];
    const faqHtml = faqs.map((f) => `<div><h3>${esc(f.q)}</h3><p>${esc(f.a)}</p></div>`).join("");
    home.bodyHtml = `<p>Intrinsic Technology is a women-owned and minority-owned managed service provider (MSP) in New York City serving healthcare, financial services, legal, construction, and nonprofit organizations. <a href="/contact">Talk to an expert</a>.</p><section aria-label="Frequently Asked Questions"><h2>Frequently Asked Questions</h2>${faqHtml}</section>`;
  }

  let staticCount = 0;
  for (const route of ROUTES) { writeRoute(template, route); staticCount++; }

  let redirectCount = 0;
  for (const [from, to] of Object.entries(REDIRECTS)) {
    const outDir = path.join(BUILD_DIR, from);
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, "index.html"), renderRedirect(template, from, to), "utf8");
    redirectCount++;
  }

  let dynCount = 0;
  const dyn = await dynamicRoutes();
  for (const route of dyn) { writeRoute(template, route); dynCount++; }

  console.log(`[prerender] static=${staticCount} redirects=${redirectCount} dynamic=${dynCount} (total pages=${staticCount + dynCount})`);
}

main();
