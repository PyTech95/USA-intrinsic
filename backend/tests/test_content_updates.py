"""Tests for the one-time content update that publishes the IT-partner article, and for how
that article is server-rendered. Runs against an in-memory database (no server needed):

    cd backend && python -m pytest tests/test_content_updates.py -n 0
"""
import asyncio
import re

import pytest

mongomock_motor = pytest.importorskip("mongomock_motor")

import content_updates                        # noqa: E402
import ssr_render                             # noqa: E402
from scripts.seed_it_partner_article import ARTICLE   # noqa: E402

BASE = "https://intrinsicamerica.com"
SEO = {"canonical_base": BASE, "title_template": "{title} | Intrinsic Technology", "geo": {"faqs": []}}
TEMPLATE = ('<html><head><title>x</title><meta name="description" content="x" /><meta property="og:title" content="x" />'
            '<meta property="og:description" content="x" /><meta property="og:url" content="x" /><meta property="og:type" content="x" />'
            '<meta property="og:image" content="x" /><meta name="twitter:title" content="x" /><meta name="twitter:description" content="x" />'
            '<meta name="twitter:image" content="x" /><meta name="robots" content="index" /></head><body><div id="root"></div></body></html>')
SLUG = "choosing-it-services-partner"


def run(coro):
    return asyncio.run(coro)


def fresh_db():
    return mongomock_motor.AsyncMongoMockClient()["intrinsic_test"]


class TestArticleUpdate:
    def test_article_is_inserted_once_and_published(self):
        async def go():
            db = fresh_db()
            await db.blogs.insert_one({"id": "draft-1", "title": "Old placeholder", "published": False, "order": 2})
            first = await content_updates.apply_content_updates(db)
            second = await content_updates.apply_content_updates(db)
            posts = await db.blogs.find({"slug": SLUG}).to_list(10)
            other = await db.blogs.find_one({"slug": "cybersecurity-managed-it"})
            return first, second, posts, other
        first, second, posts, second_article = run(go())
        assert first == ["article-choosing-it-services-partner-v1", "article-cybersecurity-managed-it-v1",
                         "article-choosing-it-services-partner-v2"] and second == []
        assert len(posts) == 1
        post = posts[0]
        assert post["published"] is True and post["order"] == 3
        assert second_article["published"] is True and second_article["order"] == 4
        assert second_article["seo_title"] == "Cybersecurity in Managed IT | Intrinsic"
        assert post["title"] == "What to Look for in an IT Services Partner"
        assert post["seo_title"] == "How to Choose an IT Services Partner | Intrinsic"
        assert post["seo_description"].startswith("What should you look for in an IT services partner?")
        assert re.fullmatch(r"\d{2} [A-Z][a-z]{2} \d{4}", post["date"])
        assert post["id"] and post["created_at"]

    def test_admin_changes_are_never_overwritten_or_recreated(self):
        async def go():
            db = fresh_db()
            await content_updates.apply_content_updates(db)
            await db.blogs.delete_many({"slug": SLUG})          # admin deletes the article
            await content_updates.apply_content_updates(db)       # next restart
            return await db.blogs.count_documents({"slug": SLUG})
        assert run(go()) == 0

    def test_published_article_with_same_title_is_left_alone(self):
        async def go():
            db = fresh_db()
            await db.blogs.insert_one({"id": "x", "title": ARTICLE["title"], "content": "Admin's own version", "published": True, "order": 0})
            await content_updates.apply_content_updates(db)
            return await db.blogs.find({}).to_list(10), await db.content_backups.count_documents({})
        posts, backups = run(go())
        partner = [p for p in posts if p["title"] == ARTICLE["title"]]
        assert len(partner) == 1 and partner[0]["content"] == "Admin's own version"     # not duplicated, not overwritten
        assert len(posts) == 2 and backups == 0                                          # the other article is still added

    def test_unpublished_draft_is_backed_up_replaced_and_published(self):
        """What happened on the live site on 20 Nov 2026: the first update found a draft with this
        title, skipped it, and the article never went live. The second update publishes it."""
        async def go():
            db = fresh_db()
            # state of the live database before the fix: v1 recorded as applied, an unpublished draft in place
            await db.content_updates.create_index("key", unique=True)
            await db.content_updates.insert_many([{"key": "article-choosing-it-services-partner-v1", "inserted": False},
                                                  {"key": "article-cybersecurity-managed-it-v1", "inserted": True}])
            await db.blogs.insert_one({"id": "draft-9", "title": ARTICLE["title"], "content": "Half-finished draft", "published": False, "order": 4})
            first = await content_updates.apply_content_updates(db)
            second = await content_updates.apply_content_updates(db)
            return first, second, await db.blogs.find({}).to_list(10), await db.content_backups.find({}).to_list(10)
        first, second, posts, backups = run(go())
        assert first == ["article-choosing-it-services-partner-v2"] and second == []
        assert len(posts) == 1                                         # replaced in place, not duplicated
        post = posts[0]
        assert post["published"] is True and post["slug"] == SLUG and post["id"] == "draft-9" and post["order"] == 4
        assert post["content"] == ARTICLE["content"] and post["seo_title"] == ARTICLE["seo_title"]
        assert re.fullmatch(r"\d{2} [A-Z][a-z]{2} \d{4}", post["date"])
        assert len(backups) == 1 and backups[0]["doc"]["content"] == "Half-finished draft"      # nothing is lost
        assert backups[0]["update_key"] == "article-choosing-it-services-partner-v2"

    def test_draft_unpublished_after_the_fix_stays_unpublished(self):
        async def go():
            db = fresh_db()
            await content_updates.apply_content_updates(db)
            await db.blogs.update_one({"slug": SLUG}, {"$set": {"published": False}})       # admin takes it down later
            await content_updates.apply_content_updates(db)                                   # next restart
            return await db.blogs.find_one({"slug": SLUG})
        assert run(go())["published"] is False

    def test_the_six_links_from_the_publishing_brief_are_in_the_body(self):
        body = ARTICLE["content"]
        for anchor, href in (("managed IT services", "/services/managed-it"),
                             ("co-managed IT relationship", "/services/co-managed-it"),
                             ("Cybersecurity", "/services/cybersecurity"),
                             ("backup and disaster recovery", "/services/backup-disaster-recovery"),
                             ("technology planning", "/services/vcio-vciso"),
                             ("Speak with our team", "/contact")):
            assert f"[{anchor}]({href})" in body
        # ...plus one link to the second article, in the security section (asked for in that article's brief)
        assert "[defined procedures and appropriate oversight](/blog/cybersecurity-managed-it)" in body
        assert body.count("](") == 7 and body.count("\n## ") == 9
        assert "Publishing brief" not in body and "PyTech" not in body


class TestArticleServerRendering:
    def _render(self, path):
        async def go():
            db = fresh_db()
            await db.case_studies.insert_one({"id": "c1", "title": "A Case Study", "summary": "Summary", "order": 0})
            await content_updates.apply_content_updates(db)
            return await ssr_render.render(path, "intrinsicamerica.com", db, SEO, TEMPLATE)
        return run(go())

    def test_article_page(self):
        r = self._render(f"/blog/{SLUG}")
        html = r["html"]
        assert r["status"] == 200
        assert "<title>How to Choose an IT Services Partner | Intrinsic</title>" in html      # exact SEO title from the brief
        assert f'<link rel="canonical" href="{BASE}/blog/{SLUG}"' in html
        assert 'name="description" content="What should you look for in an IT services partner?' in html
        assert html.count("<h1>") == 1 and "<h1>What to Look for in an IT Services Partner</h1>" in html
        assert html.count("<h2>") >= 9
        for href in ("/services/managed-it", "/services/co-managed-it", "/services/cybersecurity",
                     "/services/backup-disaster-recovery", "/services/vcio-vciso", "/contact"):
            assert f'<article>' in html and re.search(rf'<article>.*<a href="{href}">.*</article>', html, re.S)
        assert "](/" not in html                                  # no raw Markdown reaches crawlers
        assert '"@type": "BlogPosting"' in html

    def test_title_based_url_redirects_to_the_canonical_slug(self):
        r = self._render("/blog/what-to-look-for-in-an-it-services-partner")
        assert r["status"] == 301 and r["location"] == f"{BASE}/blog/{SLUG}"

    def test_resources_page_lists_the_article(self):
        html = self._render("/resources")["html"]
        assert "<title>Resources and Insights | Intrinsic Technology</title>" in html
        assert f'<a href="/blog/{SLUG}">What to Look for in an IT Services Partner</a>' in html
        assert '<a href="/case-studies/a-case-study">A Case Study</a>' in html

    def test_managed_it_pages_link_to_the_article(self):
        for path in ("/services/managed-it", "/services/co-managed-it"):
            html = self._render(path)["html"]
            assert f'<a href="/blog/{SLUG}">Choosing an IT services partner</a>' in html
            assert '<a href="/blog/cybersecurity-managed-it">Cybersecurity as part of effective IT management</a>' in html
        cyber = self._render("/services/cybersecurity")["html"]
        assert '<a href="/blog/cybersecurity-managed-it">' in cyber and f"/blog/{SLUG}" not in cyber

    def test_cybersecurity_article_page(self):
        r = self._render("/blog/cybersecurity-managed-it")
        html = r["html"]
        assert r["status"] == 200
        assert "<title>Cybersecurity in Managed IT | Intrinsic</title>" in html
        assert 'name="description" content="Explore how managed IT supports cybersecurity' in html
        assert "<h1>Cybersecurity as Part of Effective IT Management</h1>" in html and html.count("<h2>") >= 5
        for href in ("/services/co-managed-it", "/services/managed-it", "/services/cybersecurity", "/contact"):
            assert re.search(rf'<article>.*<a href="{href}">.*</article>', html, re.S)
        # the three linked NIST references are kept
        for n, url in ((1, "https://csrc.nist.gov/pubs/sp/800/40/r4/final"), (2, "https://csrc.nist.gov/pubs/sp/800/61/r3/final"),
                       (3, "https://doi.org/10.6028/NIST.CSWP.29")):
            assert f'<a href="{url}" rel="noopener noreferrer">[{n}]</a>' in html
        assert "Publishing brief" not in html and "PyTech" not in html

    def test_first_article_links_to_the_second(self):
        html = self._render(f"/blog/{SLUG}")["html"]
        assert '<a href="/blog/cybersecurity-managed-it">defined procedures and appropriate oversight</a>' in html

    def test_no_link_when_the_article_is_unpublished(self):
        async def go():
            db = fresh_db()
            await content_updates.apply_content_updates(db)
            await db.blogs.update_many({}, {"$set": {"published": False}})
            page = await ssr_render.render("/services/managed-it", "intrinsicamerica.com", db, SEO, TEMPLATE)
            post = await ssr_render.render(f"/blog/{SLUG}", "intrinsicamerica.com", db, SEO, TEMPLATE)
            return page, post
        page, post = run(go())
        assert f"/blog/{SLUG}" not in page["html"] and post["status"] == 404
