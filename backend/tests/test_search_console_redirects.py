"""Old addresses Google Search Console reported for intrinsicamerica.com on 19 Nov 2026.

"Not found (404)" listed 23 addresses. 20 are answered here by the page renderer, 4 are PDF
downloads that nginx must serve (see deploy/nginx-intrinsic.conf), and 3 are not real pages
(/wp-admin/admin-ajax.php, /wp-admin/*, /*) and correctly stay "not found".
Runs against an in-memory database (no server needed):

    cd backend && python -m pytest tests/test_search_console_redirects.py -n 0
"""
import asyncio

import pytest

mongomock_motor = pytest.importorskip("mongomock_motor")

import ssr_render                       # noqa: E402
from ssr import ROUTES, is_api_data     # noqa: E402

BASE = "https://intrinsicamerica.com"
TEMPLATE = '<html><head><title>x</title></head><body><div id="root"></div></body></html>'
SEO = {"canonical_base": BASE, "title_template": "{title} | Intrinsic Technology", "geo": {"faqs": []}, "pages": {}}


def render(path, jobs=()):
    async def go():
        db = mongomock_motor.AsyncMongoMockClient()["t"]
        for slug in jobs:
            await db.jobs.insert_one({"slug": slug, "title": slug, "published": True})
        return await ssr_render.render(path, "intrinsicamerica.com", db, SEO, TEMPLATE)
    return asyncio.run(go())


# Search Console > Pages > Not found (404), 19 Nov 2026 (as listed, trailing slashes included)
NOT_FOUND_REDIRECTS = [
    ("/non-profit-organizations/", "/industries/non-profit"),
    ("/privacy/", "/privacy-policy"),
    ("/job-location/new-york/", "/careers"),
    ("/cost-calculator/", "/contact"),
    ("/infrastructure-management/", "/services/remote-monitoring-management"),
    ("/Home", "/"),
    ("/strategic-projects/", "/services/vcio-vciso"),
    ("/jobs/accounting-and-administrative-assistant/", "/careers"),
    ("/cyber-security/", "/services/cybersecurity"),
    ("/jobs/accounting-specialist/", "/careers"),
    ("/banking-finance/", "/industries/financial-services"),
    ("/cloud-services/", "/services/cloud"),
    ("/application-cloud-support/", "/services/cloud"),
    ("/job-category/sales/", "/careers"),
    ("/case-studies", "/resources"),
    ("/services", "/"),
]
# Old addresses found under other Search Console headings on the same day
OTHER_OLD_ADDRESSES = [
    ("/legal-professional-services/", "/industries/professional-services"),   # still in Google's index
    ("/cookie-policy/", "/privacy-policy"),                                    # crawled, not indexed
    ("/job-type/full-time/", "/careers"),                                      # crawled, not indexed
    ("/service-areas", "/service-areas/new-york"),                             # from the breadcrumb trail
]


class TestSearchConsoleRedirects:
    @pytest.mark.parametrize("old,new", NOT_FOUND_REDIRECTS + OTHER_OLD_ADDRESSES)
    def test_old_address_goes_to_a_current_page(self, old, new):
        result = render(old)
        assert result["status"] == 301, f"{old}: {result['status']}"
        assert result["location"] == BASE + new
        # the destination is a real page, not another redirect or a 404
        assert new in ROUTES, f"{old} points at {new}, which is not a page"

    def test_old_job_goes_to_the_same_role_when_it_is_open(self):
        result = render("/jobs/it-support-level-2/", jobs=["it-support-level-2"])
        assert (result["status"], result["location"]) == (301, BASE + "/careers/it-support-level-2")

    def test_old_job_feed_is_gone(self):
        assert render("/jobs/feed/")["status"] == 410

    @pytest.mark.parametrize("path", ["/wp-admin/admin-ajax.php", "/wp-admin/*", "/*", "/this-page-does-not-exist"])
    def test_addresses_that_were_never_pages_stay_not_found(self, path):
        assert render(path)["status"] == 404


class TestOneAddressPerPage:
    def test_trailing_slash_goes_to_the_plain_address(self):
        result = render("/careers/")          # Search Console: "Duplicate, Google chose different canonical"
        assert (result["status"], result["location"]) == (301, BASE + "/careers")

    def test_query_string_is_kept(self):
        result = render("/services/managed-it/?utm_source=google&utm_medium=cpc")
        assert result["location"] == BASE + "/services/managed-it?utm_source=google&utm_medium=cpc"

    def test_plain_addresses_are_served_as_before(self):
        assert render("/")["status"] == 200
        assert render("/careers")["status"] == 200
        assert render("/services/managed-it?utm_source=google")["status"] == 200

    def test_old_address_with_trailing_slash_takes_one_step_not_two(self):
        assert render("/about-us/")["location"] == BASE + "/about"


class TestApiDataIsNotIndexed:
    """Search Console's "Crawled - currently not indexed" list held 46 /api/ data addresses."""

    @pytest.mark.parametrize("path", ["/api/live-edits", "/api/live-blocks", "/api/seo", "/api/theme",
                                      "/api/custom-css", "/api/content-site", "/api/content/case-studies"])
    def test_json_data_is_marked_noindex(self, path):
        assert is_api_data(path, "application/json")

    @pytest.mark.parametrize("path,content_type", [
        ("/api/ssr", "text/html; charset=utf-8"),        # every public page is served through here
        ("/api/sitemap.xml", "application/xml"),
        ("/api/robots.txt", "text/plain; charset=utf-8"),
        ("/api/llms.txt", "text/plain; charset=utf-8"),
        ("/api/og/page.png", "image/png"),
        ("/services/managed-it", "text/html; charset=utf-8"),
        ("/", "application/json"),
    ])
    def test_pages_and_crawler_files_are_never_marked(self, path, content_type):
        assert not is_api_data(path, content_type)
