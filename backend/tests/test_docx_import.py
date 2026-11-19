"""Unit tests for the admin "Import from Word" converter (docx_import.py) and the
server-side Markdown renderer (md_html.py). No server or database needed:

    cd backend && python -m pytest tests/test_docx_import.py -n 0
"""
import io
import re

import pytest

docx = pytest.importorskip("docx")          # python-docx builds the sample Word files
pytest.importorskip("mammoth")
pytest.importorskip("bs4")

from docx.oxml import OxmlElement            # noqa: E402
from docx.oxml.ns import qn                  # noqa: E402
from docx.opc.constants import RELATIONSHIP_TYPE as RT  # noqa: E402

import docx_import                           # noqa: E402
import md_html                               # noqa: E402

TITLE = "What to Look for in an IT Services Partner"
META = ("What should you look for in an IT services partner? Explore service ownership, "
        "technical expertise, cybersecurity, recovery and ongoing oversight.")


def _link(paragraph, text, url):
    """Add a real Word hyperlink run to a paragraph."""
    rid = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), rid)
    run = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def _heading(doc, text, styled):
    if styled:
        doc.add_heading(text, level=1)
    else:
        doc.add_paragraph().add_run(text).bold = True


def build_article(styled_headings=True, with_brief=True, with_title_style=True) -> bytes:
    """A Word file shaped like the articles Intrinsic sends: title, divider, body, publishing brief."""
    doc = docx.Document()
    if with_title_style:
        doc.add_paragraph(TITLE, style="Title")
    else:
        doc.add_paragraph().add_run(TITLE).bold = True
    doc.add_paragraph("_____")
    doc.add_paragraph("An effective IT services partnership gives leadership confidence that technology is being "
                      "managed with clear ownership and a plan for improvement.")
    p = doc.add_paragraph("Whether you need ")
    _link(p, "managed IT services", "https://intrinsicamerica.com/services/managed-it")
    p.add_run(" for an outsourced IT function or additional expertise, the following considerations can help.")

    _heading(doc, "Clear ownership across the technology environment", styled_headings)
    p = doc.add_paragraph("This is particularly important in a ")
    _link(p, "co-managed IT relationship", "https://www.intrinsicamerica.com/services/co-managed-it")
    p.add_run(". Both teams need agreed escalation procedures.")
    doc.add_paragraph("Responsibilities need to be documented", style="List Bullet")
    doc.add_paragraph("Escalation paths need to be agreed", style="List Bullet")

    _heading(doc, "Reporting that leads to improvement", styled_headings)
    p = doc.add_paragraph("Useful reporting is ")
    p.add_run("especially important").bold = True
    p.add_run(" and should be reviewed against ")
    _link(p, "Google guidance", "https://developers.google.com/search/docs")
    p.add_run(".")

    _heading(doc, "Working with Intrinsic Technology Group", styled_headings)
    p = doc.add_paragraph()
    _link(p, "Speak with our team", "https://intrinsicamerica.com/contact")
    p.add_run(" about your technology environment and what you need from an IT services partner.")

    if with_brief:
        doc.add_paragraph("_______________")
        doc.add_heading("Publishing brief for PyTech", level=1)
        doc.add_paragraph("Publish the preceding article as practical guidance for business leaders.")
        doc.add_heading("Keyword focus", level=2)
        table = doc.add_table(rows=1, cols=3)
        for cell, text in zip(table.rows[0].cells, ("Role", "Keyword or topic", "Purpose")):
            cell.text = text
        for row in (("Primary keyword", "how to choose an IT service provider", "Answer a provider-selection question."),
                    ("Secondary variant", "choosing an IT services partner", "Align with the editorial headline."),
                    ("Supporting topics", "managed IT services; co-managed IT", "Give context.")):
            for cell, text in zip(table.add_row().cells, row):
                cell.text = text
        doc.add_heading("Page setup", level=2)
        doc.add_paragraph(f"H1: {TITLE}")
        p = doc.add_paragraph()                      # label in bold, value in a separate run
        p.add_run("SEO title: ").bold = True
        p.add_run("How to Choose an IT Services Partner | Intrinsic")
        doc.add_paragraph("Proposed path: /resources/choosing-it-services-partner")
        doc.add_paragraph(f"Meta description: {META}")
        doc.add_paragraph("Do not promise rankings or a fixed volume of enquiries.")
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


class TestWordImport:
    def test_article_with_publishing_brief(self):
        out = docx_import.docx_to_post(build_article(), "Intrinsic_IT_Partner_Article.docx")
        post, body = out["post"], out["post"]["content"]

        assert post["title"] == TITLE
        assert post["slug"] == "choosing-it-services-partner"            # from "Proposed path"
        assert post["seo_title"] == "How to Choose an IT Services Partner | Intrinsic"
        assert post["seo_description"] == META
        assert post["excerpt"] == META
        assert post["seo_keywords"] == "how to choose an IT service provider, choosing an IT services partner"
        assert post["published"] is False                                # always a draft until the admin publishes
        assert re.fullmatch(r"\d+ min read", post["read"])

        # title and divider lines are not repeated in the body; section headings are "##"
        assert TITLE not in body and "_____" not in body
        assert "## Clear ownership across the technology environment" in body
        assert "## Working with Intrinsic Technology Group" in body

        # links survive; own-site links become relative, external links stay absolute
        assert "[managed IT services](/services/managed-it)" in body
        assert "[co-managed IT relationship](/services/co-managed-it)" in body
        assert "[Speak with our team](/contact)" in body
        assert "[Google guidance](https://developers.google.com/search/docs)" in body
        assert "**especially important**" in body
        assert "- Responsibilities need to be documented" in body and "- Escalation paths need to be agreed" in body

        # nothing from the publishing brief leaks into the article
        for leaked in ("Publishing brief", "Keyword focus", "Page setup", "SEO title", "Proposed path", "Do not promise", "PyTech"):
            assert leaked not in body
        assert any("publishing brief" in n.lower() for n in out["notes"])
        assert out["stats"]["links"] == 4 and out["stats"]["headings"] == 3

    def test_bold_lines_become_headings_when_styles_are_not_used(self):
        out = docx_import.docx_to_post(build_article(styled_headings=False, with_brief=False, with_title_style=False), "a.docx")
        post = out["post"]
        assert post["title"] == TITLE
        assert post["slug"] == "what-to-look-for-in-an-it-services-partner"   # no brief -> slug from the title
        assert "## Reporting that leads to improvement" in post["content"]
        assert "seo_title" not in post
        assert post["excerpt"].startswith("An effective IT services partnership")

    def test_rejects_files_that_are_not_docx(self):
        with pytest.raises(docx_import.DocxImportError):
            docx_import.docx_to_post(b"%PDF-1.7 not a word file", "article.pdf")
        with pytest.raises(docx_import.DocxImportError):
            docx_import.docx_to_post(b"\xd0\xcf\x11\xe0 old binary word", "article.doc")
        with pytest.raises(docx_import.DocxImportError):
            docx_import.docx_to_post(b"", "article.docx")


class TestMarkdownToHtml:
    def test_imported_body_renders_crawlable_html(self):
        body = docx_import.docx_to_post(build_article(), "a.docx")["post"]["content"]
        html = md_html.to_html(body)
        assert '<a href="/services/managed-it">managed IT services</a>' in html
        assert '<a href="/contact">Speak with our team</a>' in html
        assert '<a href="https://developers.google.com/search/docs" rel="noopener noreferrer">Google guidance</a>' in html
        assert "<h2>Clear ownership across the technology environment</h2>" in html
        assert "<strong>especially important</strong>" in html
        assert "<ul><li>Responsibilities need to be documented</li><li>Escalation paths need to be agreed</li></ul>" in html
        assert "](" not in html and "## " not in html                    # no raw Markdown left

    def test_escapes_html_and_blocks_unsafe_links(self):
        html = md_html.to_html("Hello <script>alert(1)</script> [x](javascript:alert(1)) and [ok](https://intrinsicamerica.com/about)")
        assert "<script>" not in html and "javascript:" not in html
        assert '<a href="/about">ok</a>' in html

    def test_tables_and_escapes(self):
        html = md_html.to_html("| A | B |\n| --- | --- |\n| 1 | 2 |\n\nPrice is 5 \\* 3 and snake_case stays.")
        assert "<table><thead><tr><th>A</th><th>B</th></tr></thead><tbody><tr><td>1</td><td>2</td></tr></tbody></table>" in html
        assert "5 * 3" in html and "snake_case" in html

    def test_bold_italic_from_the_visual_editor(self):
        html = md_html.to_html("Costs are *estimates* and ***very important*** and **bold**.")
        assert "<em>estimates</em>" in html and "<strong><em>very important</em></strong>" in html and "<strong>bold</strong>" in html
