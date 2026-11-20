// Helpers for the admin visual (Word-like) article editor.
//
// Articles are stored as Markdown — that is what the website renders. The visual editor
// works on rich text, so these two functions sit on either side of it:
//   docToMarkdown(json)   editor document  -> Markdown (on every edit)
//   cleanPastedHtml(html) clipboard HTML   -> tidy HTML the editor understands (on paste,
//                         mainly for text copied from Microsoft Word)
// Both are plain functions with no editor dependency.

const OWN_SITE = /^https?:\/\/(www\.)?intrinsicamerica\.com(?=\/|$|[?#])/i;

/* ------------------------------------------------------------------ *
 * Editor document (TipTap/ProseMirror JSON) -> Markdown
 * ------------------------------------------------------------------ */
const isAlnum = (c) => !!c && /[A-Za-z0-9]/.test(c);

// Escape only what would otherwise be read as Markdown syntax.
const escText = (t = "") =>
  t
    .replace(/\\/g, "\\\\")
    .replace(/([*`[\]])/g, "\\$1")
    .replace(/_/g, (m, i, s) => (isAlnum(s[i - 1]) && isAlnum(s[i + 1]) ? "_" : "\\_")); // intraword "_" is safe

// Emphasis markers must hug the text: keep surrounding spaces outside them.
const wrap = (marker, inner) => {
  if (!inner.trim()) return inner;
  const lead = inner.match(/^\s*/)[0];
  const trail = inner.match(/\s*$/)[0];
  return `${lead}${marker}${inner.trim()}${marker}${trail}`;
};

const lineStartSafe = (text) => text.replace(/^(\s*)(#{1,6}\s|>|[-+]\s|\d+[.)]\s)/, (m, a, b) => `${a}\\${b}`);

const hasMark = (node, type) => (node.marks || []).some((m) => m.type === type);
const linkHref = (node) => {
  const m = (node.marks || []).find((x) => x.type === "link");
  return (m && m.attrs && m.attrs.href) || "";
};

function serializer(opts = {}) {
  const filesPrefix = opts.filesPrefix || "";
  const cleanHref = (href = "") => {
    let h = String(href).trim();
    if (OWN_SITE.test(h)) h = h.replace(OWN_SITE, "") || "/";   // own-site links are stored relative
    return h.replace(/ /g, "%20").replace(/\)/g, "%29");
  };
  // Uploaded images are stored by their storage path, not the full API URL shown in the editor.
  const cleanSrc = (src = "") => (filesPrefix && src.startsWith(filesPrefix) ? src.slice(filesPrefix.length) : src);

  const image = (n) => {
    const src = cleanSrc((n.attrs && n.attrs.src) || "");
    return src ? `![${escText((n.attrs && n.attrs.alt) || "")}](${src.replace(/ /g, "%20")})` : "";
  };

  const textNode = (n) => {
    if (hasMark(n, "code")) return "`" + String(n.text || "").replace(/`/g, "'") + "`";
    let s = escText(n.text || "");
    const b = hasMark(n, "bold"), i = hasMark(n, "italic");
    if (b && i) s = wrap("***", s);
    else if (b) s = wrap("**", s);
    else if (i) s = wrap("*", s);
    if (hasMark(n, "strike")) s = wrap("~~", s);
    return s;
  };

  const inline = (nodes = [], ctx = {}) => {
    let out = "";
    for (let k = 0; k < nodes.length; k++) {
      const n = nodes[k];
      if (n.type === "hardBreak") { out += ctx.cell ? " " : "  \n"; continue; }
      if (n.type === "image") { out += image(n); continue; }
      if (n.type !== "text") continue;
      const href = linkHref(n);
      if (!href) { out += textNode(n); continue; }
      // consecutive pieces of the same link (e.g. partly bold) form one link
      let inner = textNode(n);
      while (k + 1 < nodes.length && nodes[k + 1].type === "text" && linkHref(nodes[k + 1]) === href) inner += textNode(nodes[++k]);
      if (!inner.trim()) { out += inner; continue; }
      const lead = inner.match(/^\s*/)[0];
      const trail = inner.match(/\s*$/)[0];
      out += `${lead}[${inner.trim()}](${cleanHref(href)})${trail}`;
    }
    return out;
  };

  const indent = (text, pad) => text.split("\n").map((l) => (l ? pad + l : l)).join("\n");

  const list = (node) => {
    const ordered = node.type === "orderedList";
    let n = (node.attrs && node.attrs.start) || 1;
    const lines = [];
    (node.content || []).forEach((li) => {
      const marker = ordered ? `${n++}.` : "-";
      const pad = " ".repeat(marker.length + 1);
      let item = "";
      (li.content || []).forEach((child) => {
        const isList = child.type === "bulletList" || child.type === "orderedList";
        const text = isList ? list(child) : block(child);
        if (!text) return;
        if (!item) item = text;
        else item += (isList ? "\n" : "\n\n") + text;
      });
      lines.push(`${marker} ${indent(item, pad).slice(item ? pad.length : 0)}`.trimEnd());
    });
    return lines.join("\n");
  };

  const table = (node) => {
    const rows = (node.content || []).map((row) =>
      (row.content || []).map((cell) =>
        (cell.content || []).map((b) => block(b, { cell: true })).filter(Boolean).join(" ")
          .replace(/\s*\n\s*/g, " ").replace(/\|/g, "\\|")));
    const filled = rows.filter((r) => r.some((c) => c));
    if (!filled.length) return "";
    const width = Math.max(...filled.map((r) => r.length));
    const norm = filled.map((r) => r.concat(Array(width - r.length).fill("")));
    const line = (r) => `| ${r.join(" | ")} |`;
    return [line(norm[0]), line(norm[0].map(() => "---")), ...norm.slice(1).map(line)].join("\n");
  };

  const block = (node, ctx = {}) => {
    switch (node.type) {
      case "paragraph": {
        const text = inline(node.content, ctx).replace(/( {2}\n)+$/, "").trim();
        return ctx.cell ? text : lineStartSafe(text);
      }
      case "heading": {
        const level = Math.min(6, Math.max(1, (node.attrs && node.attrs.level) || 2));
        const text = inline(node.content, { cell: true }).trim().replace(/^\*\*(.+)\*\*$/, "$1"); // headings are already bold
        return text ? `${"#".repeat(level)} ${text}` : "";
      }
      case "bulletList":
      case "orderedList":
        return list(node);
      case "blockquote": {
        const inner = (node.content || []).map((c) => block(c)).filter(Boolean).join("\n\n");
        return inner ? inner.split("\n").map((l) => (l ? `> ${l}` : ">")).join("\n") : "";
      }
      case "codeBlock": {
        const code = (node.content || []).map((c) => c.text || "").join("");
        return "```" + ((node.attrs && node.attrs.language) || "") + "\n" + code + "\n```";
      }
      case "horizontalRule":
        return "---";
      case "image":
        return image(node);
      case "table":
        return table(node);
      default:
        return node.content ? (node.content || []).map((c) => block(c, ctx)).filter(Boolean).join("\n\n") : "";
    }
  };

  return (doc) => {
    const parts = ((doc && doc.content) || []).map((n) => block(n)).filter(Boolean);
    return parts.length ? parts.join("\n\n") + "\n" : "";
  };
}

export const docToMarkdown = (doc, opts) => serializer(opts)(doc);

/* ------------------------------------------------------------------ *
 * Pasted HTML (Word, Google Docs, web pages) -> tidy HTML
 * ------------------------------------------------------------------ */
const styleOf = (el) => (el.getAttribute && el.getAttribute("style")) || "";

// Largest font size (in pt) used by the text of an element; 0 when none is stated.
const fontSizePt = (el) => {
  let max = 0;
  const read = (node) => {
    const m = styleOf(node).match(/font-size\s*:\s*([\d.]+)\s*(pt|px)/i);
    if (m) max = Math.max(max, parseFloat(m[1]) * (m[2].toLowerCase() === "px" ? 0.75 : 1));
  };
  read(el);
  el.querySelectorAll("[style]").forEach(read);
  return max;
};

// True when every piece of visible text in the element is bold.
const allBold = (el) => {
  const walker = el.ownerDocument.createTreeWalker(el, 4 /* SHOW_TEXT */);
  let any = false;
  for (let t = walker.nextNode(); t; t = walker.nextNode()) {
    if (!t.nodeValue.trim()) continue;
    any = true;
    let bold = false;
    for (let p = t.parentNode; p && p !== el.parentNode; p = p.parentNode) {
      const w = (styleOf(p).match(/font-weight\s*:\s*([a-z0-9]+)/i) || [])[1];
      if (w) { bold = /^(bold|bolder|[6-9]00)$/i.test(w); break; }
      if (p.nodeName === "B" || p.nodeName === "STRONG") { bold = true; break; }
    }
    if (!bold) return false;
  }
  return any;
};

const rename = (el, tag) => {
  const next = el.ownerDocument.createElement(tag);
  next.innerHTML = el.innerHTML;
  if (/^h[1-6]$/.test(tag)) next.querySelectorAll("b, strong").forEach((b) => b.replaceWith(...Array.from(b.childNodes)));  // headings are already bold
  el.replaceWith(next);
  return next;
};

// Word pastes list items as paragraphs carrying "mso-list" styles; rebuild real lists.
function convertWordLists(root) {
  const doc = root.ownerDocument;
  const isListP = (el) => /mso-list\s*:[^;]*level\d/i.test(styleOf(el));
  let wrapper = null, stack = [];
  Array.from(root.querySelectorAll("p")).filter(isListP).forEach((p) => {
    const style = styleOf(p);
    const level = parseInt((style.match(/level(\d+)/i) || [])[1] || "1", 10);
    const markerEl = Array.from(p.querySelectorAll("span")).find((s) => /mso-list\s*:\s*ignore/i.test(styleOf(s)));
    const marker = markerEl ? markerEl.textContent.replace(/\s+/g, "") : "";
    const ordered = /^(\d+|[a-zA-Z]{1,2}|[ivxlcIVXLC]+)[.)]$/.test(marker);
    // which Word list this item belongs to: a different list (or bullets vs numbers) starts a new one
    const key = `${(style.match(/mso-list\s*:\s*(l\d+)/i) || [])[1] || ""}:${ordered}`;
    if (markerEl) {                                             // drop the bullet/number glyph and any empty wrappers around it
      let el = markerEl;
      while (el && el !== p) {
        const parent = el.parentNode;
        el.remove();
        el = parent && parent !== p && !parent.textContent && !parent.querySelector("img") ? parent : null;
      }
    }
    const li = doc.createElement("li");
    li.innerHTML = p.innerHTML;
    const newList = () => doc.createElement(ordered ? "ol" : "ul");
    const startTopLevel = () => {
      wrapper = newList();
      p.parentNode.insertBefore(wrapper, p);
      stack = [{ level, key, list: wrapper }];
    };
    if (!wrapper || wrapper.nextElementSibling !== p) startTopLevel();   // not directly after the previous item
    else {
      while (stack.length > 1 && stack[stack.length - 1].level > level) stack.pop();
      const top = stack[stack.length - 1];
      const host = () => (stack.length > 1 ? stack[stack.length - 2].list.lastElementChild : null);
      if (level > top.level && top.list.lastElementChild) {     // deeper level -> nested list
        const nested = newList();
        top.list.lastElementChild.appendChild(nested);
        stack.push({ level, key, list: nested });
      } else if (top.key !== key) {                             // same depth, different list
        if (stack.length === 1 || !host()) startTopLevel();
        else {
          const sibling = newList();
          host().appendChild(sibling);
          stack[stack.length - 1] = { level, key, list: sibling };
        }
      }
    }
    stack[stack.length - 1].list.appendChild(li);
    p.remove();
  });
}

// When Word heading styles were not used, larger (or all-bold) short lines are the headings.
// defaultPt: the size of text that states none (Word keeps the body size in its style sheet).
function convertVisualHeadings(root, defaultPt) {
  const paras = Array.from(root.querySelectorAll("p")).filter((p) => !p.closest("li, td, th, blockquote") && p.textContent.trim());
  if (!paras.length) return;
  const info = paras.map((p) => ({ p, size: fontSizePt(p) || defaultPt, len: p.textContent.trim().length, text: p.textContent.trim() }));
  // the body size is the one carrying the most text
  const weight = {};
  info.forEach((x) => { if (x.size) weight[x.size] = (weight[x.size] || 0) + x.len; });
  const base = Number(Object.keys(weight).sort((a, b) => weight[b] - weight[a])[0] || 0);
  let converted = 0;
  if (base) {
    info.forEach((x) => {
      if (!x.size || x.len > 200 || x.size < base * 1.12) return;
      const ratio = x.size / base;
      x.p = rename(x.p, ratio >= 1.6 ? "h1" : ratio >= 1.25 ? "h2" : "h3");
      x.done = true;
      converted++;
    });
  }
  if (converted || root.querySelector("h1, h2, h3")) return;
  const boldLines = info.filter((x) => !x.done && x.len <= 140 && !/[.:;,]$/.test(x.text) && !x.p.querySelector("a, img") && allBold(x.p));
  if (boldLines.length >= 2 && boldLines.length < info.length) boldLines.forEach((x) => rename(x.p, "h2"));
}

/**
 * Tidy clipboard HTML before the editor reads it.
 * Returns { html, droppedImages } — images copied from Word are local files the browser
 * cannot read, so they are removed (the caller tells the user to add them with the image button).
 */
export function cleanPastedHtml(html) {
  if (!html || typeof DOMParser === "undefined") return { html: html || "", droppedImages: 0 };
  const doc = new DOMParser().parseFromString(html, "text/html");
  const root = doc.body;
  // Word states the body text size once, in its style sheet (usually 11pt); other sources state it per paragraph.
  const fromWord = /class="?Mso|mso-/i.test(html);
  const normal = html.match(/p\.MsoNormal[^{]*\{[^}]*?font-size\s*:\s*([\d.]+)\s*pt/i);
  const defaultPt = normal ? parseFloat(normal[1]) : fromWord ? 11 : 0;

  root.querySelectorAll("style, script, meta, link, title, xml").forEach((n) => n.remove());
  convertWordLists(root);
  root.querySelectorAll("*").forEach((n) => {                 // Word's <o:p> and other namespaced leftovers
    if (n.nodeName.includes(":")) n.replaceWith(...Array.from(n.childNodes).filter((c) => c.nodeType !== 3 || c.nodeValue.replace(/ /g, "").trim()));
  });

  let droppedImages = 0;
  root.querySelectorAll("img").forEach((img) => {
    if (!/^https?:\/\//i.test(img.getAttribute("src") || "")) { img.remove(); droppedImages++; }
  });

  convertVisualHeadings(root, defaultPt);
  root.querySelectorAll("h4, h5, h6").forEach((h) => rename(h, "h3"));   // the site has three heading sizes

  root.querySelectorAll("a[href]").forEach((a) => {
    const href = a.getAttribute("href") || "";
    if (OWN_SITE.test(href)) a.setAttribute("href", href.replace(OWN_SITE, "") || "/");
  });

  root.querySelectorAll("p").forEach((p) => {                 // blank spacer paragraphs
    if (!p.textContent.replace(/ /g, "").trim() && !p.querySelector("img")) p.remove();
  });

  return { html: root.innerHTML, droppedImages };
}
