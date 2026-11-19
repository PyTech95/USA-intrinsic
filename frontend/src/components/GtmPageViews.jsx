import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";

// Records a page view in Google Tag Manager each time a visitor moves to another page.
//
// This is a single-page site: only the first page of a visit is a real page load (GTM counts
// that one itself). Every later page change happens inside the browser, so we tell GTM about it
// by pushing a "virtual_page_view" event to the dataLayer once the new page has set its title.
//
// GTM set-up that goes with this (one time):
//   Trigger  - Custom Event, event name: virtual_page_view
//   Tag      - GA4 Event, event name: page_view, parameters
//                page_location = {{DLV - page_location}}, page_title = {{DLV - page_title}}
//   GA4      - Admin > Data streams > Enhanced measurement > Page views > Advanced:
//                untick "Page changes based on browser history events" (otherwise each
//                page change is counted twice).
const TITLE_SETTLE_MS = 600;   // article and case-study pages set their title after loading their content

export const GtmPageViews = () => {
  const { pathname, search } = useLocation();
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return undefined; }   // the landing page is counted by GTM itself
    if (pathname.startsWith("/admin")) return undefined;
    const timer = setTimeout(() => {
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({
        event: "virtual_page_view",
        page_path: pathname + search,
        page_location: window.location.origin + pathname + search,
        page_title: document.title,
      });
    }, TITLE_SETTLE_MS);
    return () => clearTimeout(timer);
  }, [pathname]);   // eslint-disable-line react-hooks/exhaustive-deps -- a new page = a new path; query/hash changes are not page views
  return null;
};

export default GtmPageViews;
