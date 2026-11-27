// Title tags and meta descriptions built from content the admin writes (case studies, jobs).
// Google shows about 60 characters of a title and about 155 of a description, so longer text
// is fitted here instead of being cut off mid-word in the search result.
const BRAND_LONG = " | Intrinsic Technology";
const BRAND_SHORT = " | Intrinsic";

// The full title tag: with the long brand if it fits in 60 characters, else the short brand,
// else the title alone. The title itself is never shortened.
export function fitTitle(title, limit = 60) {
  const t = String(title || "").trim();
  if (!t) return "";
  if ((t + BRAND_LONG).length <= limit) return t + BRAND_LONG;
  if ((t + BRAND_SHORT).length <= limit) return t + BRAND_SHORT;
  return t;
}

// A description of at most `limit` characters: whole sentences if they fill enough of it,
// otherwise cut at the last whole word with an ellipsis.
export function fitDescription(text, limit = 155) {
  const t = String(text || "").replace(/\s+/g, " ").trim();
  if (t.length <= limit) return t;
  const head = t.slice(0, limit + 1);
  const stop = Math.max(head.lastIndexOf(". "), head.lastIndexOf("! "), head.lastIndexOf("? "));
  if (stop >= 90) return head.slice(0, stop + 1);
  const cut = t.slice(0, limit - 1);
  const space = cut.lastIndexOf(" ");
  return (space > 60 ? cut.slice(0, space) : cut).replace(/[\s,;:.\-\u2013\u2014]+$/, "") + "\u2026";
}
