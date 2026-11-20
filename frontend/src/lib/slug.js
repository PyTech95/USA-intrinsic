export const slugify = (s = "") =>
  s.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

// Article URLs: an explicit "slug" set in the admin wins; otherwise the slug is derived from the title.
export const blogSlug = (p) => slugify((p && p.slug) || "") || slugify((p && p.title) || "");
export const blogPath = (p) => `/blog/${blogSlug(p)}`;

// Articles and guides share the blogs collection; "resource_type" decides which list they appear in.
export const isGuide = (p) => ["guide", "checklist"].includes(String((p && p.resource_type) || "").toLowerCase());
