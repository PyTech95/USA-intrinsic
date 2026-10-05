/*
 * Build-time prerender (no headless browser).
 * Writes per-route static HTML so non-JS crawlers (Bing, GPTBot, ClaudeBot,
 * PerplexityBot, link-preview bots) see the correct title, meta, canonical,
 * Open Graph/Twitter tags, JSON-LD and answer-first content for EVERY route
 * instead of the generic homepage shell. The React app still boots normally
 * for real users (createRoot replaces the prerendered #root content).
 *
 * Directly addresses the SEO/GEO assessment findings:
 *   #1 client-side rendering leaves initial HTML empty
 *   #2 per-page titles / meta / social tags missing from HTML
 *   #8 structured data missing per page
 *   #9 content not structured for AI answers
 */
const fs = require("fs");
const path = require("path");

const BUILD_DIR = path.resolve(__dirname, "..", "build");
const BASE = (process.env.PRERENDER_BASE_URL || "https://intrinsicamerica.com").replace(/\/+$/, "");
const SITE_NAME = "Intrinsic Technology";
const TITLE_TMPL = "{title} | Intrinsic Technology";
const OG_IMAGE = BASE + "/favicon-512.png";

// Source of truth for per-route SEO copy (mirrors src/lib/seoRoutes.js).
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

const esc = (s) => String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const titleCase = (seg) => seg.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function breadcrumbLd(route) {
  const parts = route.path.split("/").filter(Boolean);
  const items = [{ "@type": "ListItem", position: 1, name: "Home", item: BASE + "/" }];
  let acc = "";
  parts.forEach((seg, i) => {
    acc += "/" + seg;
    const def = ROUTES.find((r) => r.path === acc);
    items.push({ "@type": "ListItem", position: i + 2, name: (def && def.label) || titleCase(seg), item: BASE + acc });
  });
  return { "@context": "https://schema.org", "@type": "BreadcrumbList", itemListElement: items };
}

function routeJsonLd(route) {
  const out = [];
  if (!route.home) out.push(breadcrumbLd(route));
  if (route.path.startsWith("/services/")) {
    out.push({
      "@context": "https://schema.org",
      "@type": "Service",
      name: route.title,
      description: route.description,
      serviceType: route.title,
      provider: { "@id": BASE + "/#organization" },
      areaServed: "US",
      url: BASE + route.path,
    });
  }
  return out;
}

// Answer-first visible content for crawlers; React replaces #root on client load.
function contentBlock(route) {
  const crumbs = (() => {
    if (route.home) return "";
    const parts = route.path.split("/").filter(Boolean);
    let acc = "";
    const links = ['<a href="/">Home</a>'];
    parts.forEach((seg) => {
      acc += "/" + seg;
      const def = ROUTES.find((r) => r.path === acc);
      links.push(`<a href="${acc}">${esc((def && def.label) || titleCase(seg))}</a>`);
    });
    return `<nav aria-label="Breadcrumb">${links.join(" / ")}</nav>`;
  })();
  const primaryLinks = ROUTES.filter((r) => ["/services/managed-it", "/services/cybersecurity", "/services/cloud", "/services/ai", "/services/vcio-vciso", "/industries", "/about", "/contact"].includes(r.path))
    .map((r) => `<li><a href="${r.path}">${esc(r.label)}</a></li>`).join("");
  return `
      <main>
        ${crumbs}
        <h1>${esc(route.title)}</h1>
        <p>${esc(route.description)}</p>
        <p>Intrinsic Technology is a women-owned and minority-owned managed service provider (MSP) in New York City serving healthcare, financial services, legal, construction, and nonprofit organizations. <a href="/contact">Talk to an expert</a>.</p>
        <nav aria-label="Primary"><ul>${primaryLinks}</ul></nav>
      </main>`;
}

function renderRoute(template, route) {
  const canonical = BASE + route.path;
  const fullTitle = route.home ? "Intrinsic Technology | Managed IT, Cybersecurity & Cloud Services" : TITLE_TMPL.replace("{title}", route.title);
  let html = template;

  // <title>
  html = html.replace(/<title>[\s\S]*?<\/title>/, `<title>${esc(fullTitle)}</title>`);
  // description
  html = html.replace(/<meta name="description"[^>]*>/, `<meta name="description" content="${esc(route.description)}" />`);
  // Open Graph + Twitter title/description/url
  html = html.replace(/<meta property="og:title"[^>]*>/, `<meta property="og:title" content="${esc(fullTitle)}" />`);
  html = html.replace(/<meta property="og:description"[^>]*>/, `<meta property="og:description" content="${esc(route.description)}" />`);
  html = html.replace(/<meta property="og:url"[^>]*>/, `<meta property="og:url" content="${esc(canonical)}" />`);
  html = html.replace(/<meta name="twitter:title"[^>]*>/, `<meta name="twitter:title" content="${esc(fullTitle)}" />`);
  html = html.replace(/<meta name="twitter:description"[^>]*>/, `<meta name="twitter:description" content="${esc(route.description)}" />`);

  // Inject canonical + per-route JSON-LD before </head>
  const extraLd = routeJsonLd(route).map((o) => `<script type="application/ld+json">${JSON.stringify(o)}</script>`).join("\n");
  const headInject = `<link rel="canonical" href="${esc(canonical)}" data-prerender="1" />\n${extraLd}\n</head>`;
  html = html.replace("</head>", headInject);

  // Inject crawler-visible content into #root (replaced by React for real users)
  html = html.replace(/<div id="root">\s*<\/div>/, `<div id="root">${contentBlock(route)}</div>`);
  return html;
}

function main() {
  const indexPath = path.join(BUILD_DIR, "index.html");
  if (!fs.existsSync(indexPath)) {
    console.error("[prerender] build/index.html not found — run after craco build");
    process.exit(1);
  }
  const template = fs.readFileSync(indexPath, "utf8");
  let count = 0;
  for (const route of ROUTES) {
    const html = renderRoute(template, route);
    const outDir = route.home ? BUILD_DIR : path.join(BUILD_DIR, route.path);
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, "index.html"), html, "utf8");
    count++;
  }
  console.log(`[prerender] wrote ${count} route HTML files to build/`);
}

main();
