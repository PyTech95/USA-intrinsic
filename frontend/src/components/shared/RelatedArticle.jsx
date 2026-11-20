import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { api } from "../../lib/api";
import { blogSlug, blogPath } from "../../lib/slug";

// The articles service pages link to (slug = the article's URL slug, label = the link text).
export const ARTICLES = {
  partner: { slug: "choosing-it-services-partner", label: "Choosing an IT services partner" },
  cybersecurity: { slug: "cybersecurity-managed-it", label: "Cybersecurity as part of effective IT management" },
};

// "Related reading" links from a service page to published articles.
// Each link renders only while its article is published, so a page never links to a missing post.
// tone="dark" is for sections with a dark background.
export default function RelatedArticle({ items, slug, label, lead = "Related reading:", testId = "related-article", tone = "light" }) {
  const wanted = items || (slug ? [{ slug, label }] : []);
  const key = wanted.map((w) => w.slug).join(",");
  const [posts, setPosts] = useState([]);

  useEffect(() => {
    let active = true;
    api.get("/content/blogs")
      .then(({ data }) => {
        if (!active) return;
        setPosts(wanted.map((w) => ({ ...w, post: (data || []).find((p) => blogSlug(p) === w.slug) })).filter((w) => w.post));
      })
      .catch(() => {});
    return () => { active = false; };
  }, [key]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!posts.length) return null;
  const dark = tone === "dark";
  return (
    <p className={`mt-7 text-[14.5px] leading-[1.7] ${dark ? "text-white/80" : "text-[#4a5568]"}`} data-testid={testId}>
      {lead}{" "}
      {posts.map((w, i) => (
        <React.Fragment key={w.slug}>
          {i > 0 && <span className="mx-2 opacity-60" aria-hidden="true">·</span>}
          <Link to={blogPath(w.post)} data-testid={`${testId}-link${i ? `-${i + 1}` : ""}`}
            className={`group inline-flex items-center gap-1 font-semibold underline underline-offset-4 transition-colors ${dark ? "text-white hover:text-[#f2a91c]" : "text-navy hover:text-royal"}`}>
            {w.label || w.post.title}
            <ArrowUpRight size={14} className="transition-transform duration-300 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
          </Link>
        </React.Fragment>
      ))}
    </p>
  );
}
