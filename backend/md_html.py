"""Small, dependency-free Markdown -> HTML converter for server-rendered article bodies.

Article bodies are stored as Markdown (the admin editor and the Word import both
produce it). The browser renders them with react-markdown; this module produces
the equivalent plain HTML for the crawler-facing page so headings, lists and
links are real, crawlable elements rather than raw Markdown text.

Everything is HTML-escaped first; only a fixed set of tags is ever emitted.
"""
from __future__ import annotations
import html
import re

_SAFE_HREF = re.compile(r"^(https?://|mailto:|tel:|/(?!/)|#)", re.I)
_OWN_SITE = re.compile(r"^https?://(www\.)?intrinsicamerica\.com(?=/|$|[?#])", re.I)
_LINK = re.compile(r"(!?)\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+&quot;.*?&quot;)?\s*\)")
_LIST = re.compile(r"^\s*(?:([-*+])|(\d+)[.)])\s+(.*)$")
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def _href(url: str) -> str:
    """Return a safe href ('' when the scheme is not allowed). Own-site URLs become relative."""
    url = html.unescape(url).strip()
    if not _SAFE_HREF.match(url):
        return ""
    if _OWN_SITE.match(url):
        url = _OWN_SITE.sub("", url) or "/"
    return html.escape(url, quote=True)


def _src(url: str) -> str:
    url = html.unescape(url).strip()
    if re.match(r"^(https?://|/(?!/))", url, re.I):
        return html.escape(url, quote=True)
    if re.match(r"^[\w./-]+$", url):          # uploaded file path -> served by the API
        return "/api/files/" + html.escape(url, quote=True)
    return ""


def inline(text: str) -> str:
    """Inline Markdown (links, images, bold, italic, code) -> HTML."""
    s = html.escape(str(text or ""), quote=True)
    held: list[str] = []

    def hold(fragment: str) -> str:
        held.append(fragment)
        return f"\x00{len(held) - 1}\x00"

    def link(m: re.Match) -> str:
        bang, label, url = m.group(1), m.group(2), m.group(3)
        if bang:
            src = _src(url)
            return hold(f'<img src="{src}" alt="{label}" loading="lazy" />') if src else ""
        href = _href(url)
        if not href:
            return label
        external = href.lower().startswith("http")
        rel = ' rel="noopener noreferrer"' if external else ""
        return hold(f'<a href="{href}"{rel}>') + label + hold("</a>")

    # backslash escapes (\* \_ \[ ...) are literal characters
    s = re.sub(r"\\(&(?:gt|lt|amp|quot|#x27);|[\\`*_{}\[\]()#+\-.!|~])", lambda m: hold(m.group(1)), s)
    s = re.sub(r"`([^`]+)`", lambda m: hold(f"<code>{m.group(1)}</code>"), s)
    s = _LINK.sub(link, s)
    s = re.sub(r"~~(?!\s)(.+?)(?<!\s)~~", r"<s>\1</s>", s)
    s = re.sub(r"\*\*\*(?![\s*])(.+?)(?<![\s*])\*\*\*", r"<strong><em>\1</em></strong>", s)
    s = re.sub(r"\*\*(?!\s)(.+?)(?<!\s)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w_])__(?!\s)(.+?)(?<!\s)__(?![\w_])", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?![\s*])(.+?)(?<![\s*])\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w_])_(?![\s_])(.+?)(?<![\s_])_(?![\w_])", r"<em>\1</em>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: held[int(m.group(1))], s)


def _cells(row: str) -> list[str]:
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", row)]


def to_html(markdown: str, *, min_heading: int = 2) -> str:
    """Block-level Markdown -> HTML. No heading is rendered above <h2>, so the page keeps a single <h1>."""
    lines = str(markdown or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    i, n = 0, len(lines)

    def flush() -> None:
        if para:
            # a line ending in two spaces (or a backslash) is a hard line break
            pieces = []
            for idx, raw in enumerate(para):
                hard = idx < len(para) - 1 and (raw.endswith("  ") or raw.rstrip().endswith("\\"))
                pieces.append(inline(raw.strip().rstrip("\\").rstrip() if hard else raw.strip()) + ("<br />" if hard else " "))
            out.append("<p>" + "".join(pieces).strip() + "</p>")
            para.clear()

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush()
            i += 1
            continue

        if stripped.startswith("```"):                      # fenced code
            flush()
            i += 1
            code = []
            while i < n and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            out.append("<pre><code>" + html.escape("\n".join(code)) + "</code></pre>")
            continue

        m = _HEADING.match(stripped)
        if m:
            flush()
            level = min(6, max(min_heading, len(m.group(1))))    # "#" and "##" both render as <h2>, like the site
            out.append(f"<h{level}>{inline(m.group(2))}</h{level}>")
            i += 1
            continue

        if re.fullmatch(r"(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,}", stripped):
            flush()
            out.append("<hr />")
            i += 1
            continue

        if stripped.startswith(">"):                        # blockquote
            flush()
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append("<blockquote>" + to_html("\n".join(quote), min_heading=min_heading) + "</blockquote>")
            continue

        if "|" in stripped and i + 1 < n and _TABLE_SEP.match(lines[i + 1]) and "|" in lines[i + 1]:
            flush()
            head = _cells(stripped)
            i += 2
            rows = []
            while i < n and lines[i].strip() and "|" in lines[i]:
                rows.append(_cells(lines[i]))
                i += 1
            thead = "<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead>"
            tbody = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f"<table>{thead}<tbody>{tbody}</tbody></table>")
            continue

        m = _LIST.match(line)
        if m:
            flush()
            ordered = m.group(2) is not None
            items: list[str] = []
            while i < n:
                lm = _LIST.match(lines[i])
                if lm and (lm.group(2) is not None) == ordered:
                    items.append(lm.group(3))
                    i += 1
                elif lines[i].strip() and lines[i].startswith((" ", "\t")) and items and not _LIST.match(lines[i]):
                    items[-1] += " " + lines[i].strip()     # continuation line
                    i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue

        para.append(line)
        i += 1

    flush()
    return "\n".join(out)


def to_text(markdown: str) -> str:
    """Plain text of a Markdown body (for word counts, excerpts and descriptions)."""
    s = str(markdown or "")
    s = re.sub(r"```.*?```", " ", s, flags=re.S)
    s = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"^\s{0,3}(#{1,6}|>|[-*+]|\d+[.)])\s+", "", s, flags=re.M)
    s = re.sub(r"^\s*\|?\s*:?-{2,}.*$", " ", s, flags=re.M)
    s = re.sub(r"[*_`|]", "", s)
    return re.sub(r"\s+", " ", s).strip()
