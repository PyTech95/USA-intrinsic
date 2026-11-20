"""Turn a Microsoft Word (.docx) article into the fields of a blog post.

Used by the admin "Import from Word" button. Given the bytes of a .docx file it returns
a draft post: title, URL slug, excerpt, Markdown body (headings, bold/italic, links, lists,
tables and images preserved), read time and — when the document carries a "Publishing
brief" section — the SEO title, meta description, URL path and keywords from that brief.

The brief itself (notes for whoever publishes the article) is never included in the body.

Pure function: no database or network access. Images are returned to the caller, which
decides where to store them (see `image_placeholder`).
"""
from __future__ import annotations
import io
import math
import re
import zipfile

MAX_DOCX_BYTES = 20 * 1024 * 1024            # upload limit
MAX_UNZIPPED_BYTES = 200 * 1024 * 1024       # guard against zip bombs
WORDS_PER_MINUTE = 220
DEFAULT_AUTHOR = "Intrinsic Technology Group"

_OWN_SITE = re.compile(r"^https?://(www\.)?intrinsicamerica\.com(?=/|$|[?#])", re.I)
_RULE = re.compile(r"^[\s_\-–—=*·.]{3,}$")                                  # "_____" style divider lines
_BRIEF_START = re.compile(r"^\s*(publishing|publication|publisher'?s?|editorial|seo)\s+(brief|notes?)\b", re.I)
_FIELD = re.compile(
    r"^\s*(h1|headline|seo\s*title|title\s*tag|meta\s*title|page\s*title|proposed\s*path|url\s*path|path|url|slug|"
    r"meta\s*description|seo\s*description)\s*[:：]\s*(\S.*?)\s*$", re.I)
_BLOCKS = ("p", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "blockquote")
_STYLE_MAP = "\n".join([
    "p[style-name='Title'] => h1:fresh",
    "p[style-name='title'] => h1:fresh",
    "p[style-name='Subtitle'] => p:fresh",
    "p[style-name='Quote'] => blockquote > p:fresh",
    "p[style-name='Intense Quote'] => blockquote > p:fresh",
])


class DocxImportError(ValueError):
    """Raised with a message that is safe to show to the admin."""


def image_placeholder(index: int) -> str:
    return f"docx-image-{index}"


def slugify(text: str) -> str:
    s = (text or "").lower().replace("&", "and")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def _check_file(data: bytes, filename: str) -> None:
    name = (filename or "").lower()
    if name.endswith(".doc") and not name.endswith(".docx"):
        raise DocxImportError("This is an older .doc file. In Word choose File > Save As > Word Document (.docx) and upload that.")
    if not data:
        raise DocxImportError("The file is empty.")
    if len(data) > MAX_DOCX_BYTES:
        raise DocxImportError("The file is too large (limit 20 MB). Compress the images in Word and try again.")
    if not data.startswith(b"PK"):
        raise DocxImportError("This is not a Word .docx file. Upload the Word document itself (not a PDF or a link).")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            names = set(z.namelist())
            if sum(i.file_size for i in z.infolist()) > MAX_UNZIPPED_BYTES:
                raise DocxImportError("The file is too large to import.")
    except zipfile.BadZipFile as exc:
        raise DocxImportError("The file could not be read. Re-save it from Word as .docx and try again.") from exc
    if "word/document.xml" not in names:
        raise DocxImportError("This is not a Word .docx file. Upload the Word document itself (not a PDF or a link).")


# ---------------------------------------------------------------------------
# HTML (from mammoth) -> Markdown
# ---------------------------------------------------------------------------
def _clean_href(href: str) -> str:
    href = (href or "").strip()
    if _OWN_SITE.match(href):                 # links to our own site become relative (same-tab, crawlable)
        href = _OWN_SITE.sub("", href) or "/"
    return href


def _esc(text: str) -> str:
    """Escape the few characters that would otherwise be read as Markdown syntax."""
    text = text.replace("\\", "\\\\")
    text = re.sub(r"([*`\[\]])", r"\\\1", text)
    return re.sub(r"(?<![A-Za-z0-9])_|_(?![A-Za-z0-9])", r"\\_", text)   # intraword underscores are safe


def _wrap(marker: str, inner: str) -> str:
    """Wrap text in emphasis markers, keeping surrounding spaces outside them (Markdown needs that)."""
    if not inner.strip():
        return inner
    lead = inner[: len(inner) - len(inner.lstrip())]
    trail = inner[len(inner.rstrip()):]
    return f"{lead}{marker}{inner.strip()}{marker}{trail}"


def _inline(node) -> str:
    from bs4 import NavigableString, Tag
    if isinstance(node, NavigableString):
        return _esc(re.sub(r"\s+", " ", str(node)))
    if not isinstance(node, Tag):
        return ""
    name = node.name.lower()
    if name == "br":
        return "  \n"
    if name == "img":
        src = (node.get("src") or "").strip()
        alt = _esc(node.get("alt") or "")
        return f"![{alt}]({src})" if src else ""
    inner = "".join(_inline(c) for c in node.children)
    if name in ("strong", "b"):
        return _wrap("**", inner)
    if name in ("em", "i"):
        return _wrap("*", inner)
    if name in ("s", "strike", "del"):
        return _wrap("~~", inner)
    if name == "a":
        href = _clean_href(node.get("href"))
        if not href or not inner.strip():
            return inner
        return f"[{inner.strip()}]({href.replace(' ', '%20').replace(')', '%29')})"
    if name in ("p", "div") and inner:          # block inside inline context (e.g. table cell paragraphs)
        return inner + "  \n"
    return inner


def _line_start_safe(text: str) -> str:
    """A paragraph must not accidentally start like a heading, list item or quote."""
    return re.sub(r"^(\s*)(#{1,6}\s|>|[-+]\s|\d+[.)]\s)", lambda m: m.group(1) + "\\" + m.group(2), text)


def _list(node, depth: int) -> list[str]:
    from bs4 import Tag
    ordered = node.name.lower() == "ol"
    lines: list[str] = []
    n = 0
    for li in node.find_all("li", recursive=False):
        n += 1
        marker = f"{n}." if ordered else "-"
        text_parts, nested = [], []
        for child in li.children:
            if isinstance(child, Tag) and child.name.lower() in ("ul", "ol"):
                nested.append(child)
            else:
                text_parts.append(_inline(child))
        text = re.sub(r"\s*\n\s*", " ", "".join(text_parts)).strip()
        lines.append(f"{'  ' * depth}{marker} {text}".rstrip())
        for sub in nested:
            lines.extend(_list(sub, depth + 1))
    return lines


def _cell(td) -> str:
    text = _inline(td).strip()
    text = re.sub(r"(\s{2}\n)+$", "", text)
    return re.sub(r"\s*\n\s*", " ", text).replace("|", "\\|")      # one line per cell


def _table(node) -> str:
    rows = [[_cell(c) for c in tr.find_all(["td", "th"], recursive=False)] for tr in node.find_all("tr")]
    rows = [r for r in rows if any(c for c in r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    head, body = rows[0], rows[1:]
    lines = ["| " + " | ".join(head) + " |", "| " + " | ".join("---" for _ in head) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in body]
    return "\n".join(lines)


def _block(node, shift: int) -> str:
    name = node.name.lower()
    if re.fullmatch(r"h[1-6]", name):
        level = min(6, max(2, int(name[1]) + shift))
        text = re.sub(r"\s*\n\s*", " ", _inline(node)).strip()
        text = re.sub(r"^\*\*(.+)\*\*$", r"\1", text)          # headings are already bold
        return f"{'#' * level} {text}" if text else ""
    if name == "p":
        text = _inline(node).strip()
        text = re.sub(r"(\s{2}\n)+$", "", text)
        return _line_start_safe(text)
    if name in ("ul", "ol"):
        return "\n".join(_list(node, 0))
    if name == "table":
        return _table(node)
    if name == "blockquote":
        inner = "\n\n".join(b for b in (_block(c, shift) for c in _block_children(node)) if b)
        return "\n".join(("> " + ln) if ln else ">" for ln in inner.split("\n"))
    return _inline(node).strip()


def _block_children(parent):
    from bs4 import Tag
    return [c for c in parent.children if isinstance(c, Tag)]


def _text(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ")).strip()


def _is_rule(node) -> bool:
    return node.name == "p" and not node.find("img") and bool(_RULE.match(node.get_text() or "")) and bool(node.get_text().strip())


def _bold_only(node) -> bool:
    """A short paragraph that is entirely bold — how headings look when Word styles were not used."""
    if node.name != "p" or node.find(["img", "a"]):
        return False
    text = _text(node)
    if not text or len(text) > 140 or text.endswith((".", ":", ";", ",")):
        return False
    from bs4 import NavigableString
    for child in node.children:
        if isinstance(child, NavigableString):
            if str(child).strip():
                return False
        elif child.name not in ("strong", "b"):
            return False
    return True


# ---------------------------------------------------------------------------
# Publishing brief
# ---------------------------------------------------------------------------
def _lines(node) -> list[str]:
    """Text lines of a block: only real line breaks split lines (a bold label and its value stay together)."""
    from bs4 import NavigableString
    parts = []
    for d in node.descendants:
        if isinstance(d, NavigableString):
            parts.append(str(d))
        elif d.name == "br":
            parts.append("\n")
    return [re.sub(r"\s+", " ", ln).strip() for ln in "".join(parts).split("\n")]


def _parse_brief(blocks) -> dict:
    out: dict = {}
    keywords: list[str] = []
    for node in blocks:
        if node.name == "table":
            for tr in node.find_all("tr"):
                cells = [_text(c) for c in tr.find_all(["td", "th"], recursive=False)]
                if len(cells) >= 2 and re.search(r"\b(primary|secondary)\b", cells[0], re.I) and cells[1]:
                    keywords.append(cells[1])
            continue
        for line in _lines(node):
            m = _FIELD.match(line)
            if not m:
                continue
            key, value = re.sub(r"\s+", " ", m.group(1).lower()), m.group(2).strip()
            if key in ("h1", "headline"):
                out.setdefault("h1", value)
            elif key in ("seo title", "seotitle", "title tag", "meta title", "page title"):
                out.setdefault("seo_title", value)
            elif key in ("meta description", "seo description"):
                out.setdefault("seo_description", value)
            elif key in ("proposed path", "url path", "path", "url", "slug"):
                path = re.sub(r"^https?://[^/]+", "", value.split()[0]).split("?")[0].split("#")[0]
                slug = slugify(path.rstrip("/").rsplit("/", 1)[-1])
                if slug:
                    out.setdefault("slug", slug)
                    out.setdefault("proposed_path", path)
    if keywords:
        seen, unique = set(), []
        for k in keywords:
            if k.lower() not in seen:
                seen.add(k.lower())
                unique.append(k)
        out["seo_keywords"] = ", ".join(unique)
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _excerpt(paragraphs: list[str], limit: int = 220) -> str:
    for p in paragraphs:
        if len(p) < 40:
            continue
        if len(p) <= limit:
            return p
        cut = p[:limit]
        end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
        return cut[: end + 1] if end > 80 else cut.rsplit(" ", 1)[0].rstrip(",;:") + "…"
    return paragraphs[0] if paragraphs else ""


def docx_to_post(data: bytes, filename: str = "") -> dict:
    """Convert .docx bytes into {"post": {...fields...}, "images": [...], "notes": [...], "stats": {...}}."""
    _check_file(data, filename)
    try:
        import mammoth
        from bs4 import BeautifulSoup
    except ImportError as exc:                      # pragma: no cover - deployment problem, not user error
        raise DocxImportError("Word import is not installed on the server. Run: pip install -r backend/requirements.txt") from exc

    images: list[dict] = []

    def keep_image(image):
        with image.open() as fh:
            blob = fh.read()
        images.append({"data": blob, "content_type": image.content_type or "image/png"})
        return {"src": image_placeholder(len(images) - 1), "alt": (getattr(image, "alt_text", None) or "").strip()}

    try:
        result = mammoth.convert_to_html(io.BytesIO(data), style_map=_STYLE_MAP,
                                         convert_image=mammoth.images.img_element(keep_image))
    except Exception as exc:
        raise DocxImportError("The Word file could not be read. Open it in Word, save it again as .docx and retry.") from exc

    soup = BeautifulSoup(result.value or "", "html.parser")
    blocks = [b for b in _block_children(soup) if b.name in _BLOCKS]
    blocks = [b for b in blocks if _text(b) or b.find("img")]
    if not blocks:
        raise DocxImportError("The Word file has no text to import.")
    notes: list[str] = []

    # 1) Split off the publishing brief (notes for the publisher, not part of the article).
    brief: dict = {}
    for i, b in enumerate(blocks):
        if b.name != "table" and _BRIEF_START.match(_text(b)):
            brief = _parse_brief(blocks[i + 1:])
            blocks = blocks[:i]
            notes.append("A publishing brief was found at the end of the document. It was left out of the article; "
                         "its SEO title, meta description, URL and keywords were filled in below.")
            break

    # 2) Divider lines such as "_____" are decoration.
    blocks = [b for b in blocks if not _is_rule(b)]
    if not blocks:
        raise DocxImportError("The Word file has no article text to import.")

    # 3) Title: the first Heading 1 / Title-style paragraph, else a short first line, else the file name.
    title = ""
    first_h1 = next((b for b in blocks if b.name == "h1"), None)
    if first_h1 is not None and blocks.index(first_h1) <= 2:
        title = _text(first_h1)
        blocks.remove(first_h1)
    elif len(_text(blocks[0])) <= 160 and not _text(blocks[0]).endswith(".") and blocks[0].name in ("p", "h2", "h3") and len(blocks) > 1:
        title = _text(blocks[0])
        blocks = blocks[1:]
    else:
        title = re.sub(r"[_\-]+", " ", re.sub(r"\.docx$", "", filename or "", flags=re.I)).strip()
        notes.append("No title was found in the document, so the file name was used. Check the title.")
    if brief.get("h1"):
        title = brief["h1"]

    # 4) Headings. If Word heading styles were not used, short all-bold lines are the section headings.
    headings = [b for b in blocks if re.fullmatch(r"h[1-6]", b.name)]
    if len(headings) < 2:
        bold = [b for b in blocks if _bold_only(b)]
        if len(bold) >= 2:
            for b in bold:
                b.name = "h2"
            headings = [b for b in blocks if re.fullmatch(r"h[1-6]", b.name)]
            notes.append("The document does not use Word heading styles, so bold lines were treated as section headings.")
    top = min((int(h.name[1]) for h in headings), default=2)
    shift = 2 - top                                   # top-level section headings become "##"

    # 5) Body -> Markdown.
    parts = [p for p in (_block(b, shift) for b in blocks) if p]
    content = "\n\n".join(parts).strip() + "\n"

    paragraphs = [_text(b) for b in blocks if b.name == "p" and _text(b)]
    words = len(re.findall(r"[A-Za-z0-9][\w’'-]*", " ".join(_text(b) for b in blocks)))
    links = sum(1 for b in blocks for a in b.find_all("a") if (a.get("href") or "").strip())
    excerpt = brief.get("seo_description") or _excerpt(paragraphs)

    post = {
        "title": title,
        "slug": brief.get("slug") or slugify(title),
        "excerpt": excerpt,
        "content": content,
        "author": DEFAULT_AUTHOR,
        "catColor": "#c8d2de",
        "read": f"{max(1, math.ceil(words / WORDS_PER_MINUTE))} min read",
        "resource_type": "article",
        "published": False,
    }
    for key in ("seo_title", "seo_description", "seo_keywords"):
        if brief.get(key):
            post[key] = brief[key]

    if images:
        notes.append(f"{len(images)} image(s) in the document were added to the article body.")
    if not links:
        notes.append("No links were found in the document.")
    for message in result.messages or []:
        text = getattr(message, "message", "")
        if getattr(message, "type", "") == "warning" and "Unrecognised paragraph style" not in text and "Unrecognised run style" not in text:
            notes.append(f"Word: {text}")

    stats = {"words": words, "headings": len(headings), "links": links, "images": len(images), "paragraphs": len(paragraphs)}
    return {"post": post, "images": images, "notes": notes, "stats": stats, "proposed_path": brief.get("proposed_path", "")}
