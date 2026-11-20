(function () {
  'use strict';
  // Exclude prerender runs and private account/review pages.
  if (navigator.webdriver) return;
  if (/^\/(admin|feedback|review)(\/|$)/i.test(location.pathname)) return;
  if (window.__intrinsicGtmLoaded) return;
  window.__intrinsicGtmLoaded = true;
  window.dataLayer = window.dataLayer || [];
  window.dataLayer.push({'gtm.start': Date.now(), event: 'gtm.js'});
  var script = document.createElement('script');
  script.async = true;
  script.src = 'https://www.googletagmanager.com/gtm.js?id=GTM-5WKXBHW8';
  document.head.appendChild(script);
})();
