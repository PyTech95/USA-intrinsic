/**
 * Tests for the admin visual article editor helpers (lib/richtext.js):
 *  - docToMarkdown: editor document -> the Markdown the website stores and renders
 *  - cleanPastedHtml: text copied from Microsoft Word -> tidy HTML (headings, lists, links)
 */
import { docToMarkdown, cleanPastedHtml } from "../richtext";

const text = (t, ...marks) => ({ type: "text", text: t, ...(marks.length ? { marks: marks.map((m) => (typeof m === "string" ? { type: m } : m)) } : {}) });
const link = (href) => ({ type: "link", attrs: { href } });
const p = (...content) => ({ type: "paragraph", content });
const h = (level, ...content) => ({ type: "heading", attrs: { level }, content });
const li = (...content) => ({ type: "listItem", content });
const doc = (...content) => ({ type: "doc", content });

describe("docToMarkdown", () => {
  test("headings, bold, italic and links", () => {
    const md = docToMarkdown(doc(
      h(2, text("Clear ownership")),
      p(text("Whether you need "), text("managed IT services", link("/services/managed-it")), text(" or "), text("more", "bold"), text(" "), text("help", "italic"), text(".")),
    ));
    expect(md).toBe("## Clear ownership\n\nWhether you need [managed IT services](/services/managed-it) or **more** *help*.\n");
  });

  test("own-site links are stored relative; a partly bold link stays one link", () => {
    const md = docToMarkdown(doc(p(
      text("Speak ", link("https://intrinsicamerica.com/contact")), text("with us", "bold", link("https://intrinsicamerica.com/contact")),
      text(" or read "), text("guidance", link("https://www.cisa.gov/")),
    )));
    expect(md).toBe("[Speak **with us**](/contact) or read [guidance](https://www.cisa.gov/)\n");
  });

  test("nested lists and numbered lists", () => {
    const md = docToMarkdown(doc(
      { type: "bulletList", content: [
        li(p(text("Restore a file")), { type: "bulletList", content: [li(p(text("Record the time")))] }),
        li(p(text("Keep a copy offline"))),
      ] },
      { type: "orderedList", attrs: { start: 1 }, content: [li(p(text("Pick a system"))), li(p(text("Restore it")))] },
    ));
    expect(md).toBe("- Restore a file\n  - Record the time\n- Keep a copy offline\n\n1. Pick a system\n2. Restore it\n");
  });

  test("tables, images (stored by upload path) and skipped empty paragraphs", () => {
    const cell = (type, t) => ({ type, content: [p(text(t))] });
    const md = docToMarkdown(doc(
      p(),
      { type: "table", content: [
        { type: "tableRow", content: [cell("tableHeader", "Phase"), cell("tableHeader", "Time")] },
        { type: "tableRow", content: [cell("tableCell", "Pilot"), cell("tableCell", "3 weeks | approx")] },
      ] },
      { type: "image", attrs: { src: "https://api.example.com/api/files/intrrinsic/uploads/a.png", alt: "Diagram" } },
    ), { filesPrefix: "https://api.example.com/api/files/" });
    expect(md).toBe("| Phase | Time |\n| --- | --- |\n| Pilot | 3 weeks \\| approx |\n\n![Diagram](intrrinsic/uploads/a.png)\n");
  });

  test("characters that look like Markdown are escaped; a fully bold heading is not double-marked", () => {
    const md = docToMarkdown(doc(h(2, text("Bold heading", "bold")), p(text("5 * 3 and snake_case and [note]")), p(text("# not a heading"))));
    expect(md).toBe("## Bold heading\n\n5 \\* 3 and snake_case and \\[note\\]\n\n\\# not a heading\n");
  });
});

describe("cleanPastedHtml (Microsoft Word clipboard)", () => {
  const WORD = `<html xmlns:o="urn:schemas-microsoft-com:office:office"><head><style><!-- p.MsoNormal {font-size:11.0pt;} --></style></head><body>
<p class=MsoNormal><b><span style='font-size:18.0pt'>Why Backups Fail<o:p></o:p></span></b></p>
<p class=MsoNormal>Most organizations <b>assume</b> their backups work. Read our <a href="https://intrinsicamerica.com/services/backup-disaster-recovery">backup page</a>.<o:p></o:p></p>
<p class=MsoNormal><o:p>&nbsp;</o:p></p>
<p class=MsoNormal><b><span style='font-size:14.0pt'>Three checks<o:p></o:p></span></b></p>
<p class=MsoListParagraphCxSpFirst style='text-indent:-.25in;mso-list:l0 level1 lfo1'><span style='font-family:Symbol'><span style='mso-list:Ignore'>·<span style='font:7.0pt "Times New Roman"'>&nbsp;&nbsp; </span></span></span>Restore a file<o:p></o:p></p>
<p class=MsoListParagraphCxSpMiddle style='text-indent:-.25in;mso-list:l0 level2 lfo1'><span style='mso-list:Ignore'>o<span style='font:7.0pt "Times New Roman"'>&nbsp; </span></span>Record the time<o:p></o:p></p>
<p class=MsoListParagraphCxSpLast style='text-indent:-.25in;mso-list:l0 level1 lfo1'><span style='mso-list:Ignore'>·<span style='font:7.0pt "Times New Roman"'>&nbsp; </span></span>Keep a copy offline<o:p></o:p></p>
<p class=MsoListParagraphCxSpFirst style='text-indent:-.25in;mso-list:l1 level1 lfo2'><span style='mso-list:Ignore'>1.<span style='font:7.0pt "Times New Roman"'>&nbsp; </span></span>Pick a system<o:p></o:p></p>
<p class=MsoNormal><img src="file:///C:/Users/x/clip_image002.png"></p>
<h4>Small Word heading</h4>
</body></html>`;

  test("headings by size, real lists, relative own-site links, no Word leftovers", () => {
    const { html, droppedImages } = cleanPastedHtml(WORD);
    const box = document.createElement("div");
    box.innerHTML = html;
    expect(box.querySelector("h1").textContent).toBe("Why Backups Fail");            // 18pt on an 11pt body
    expect(box.querySelector("h1 b, h1 strong")).toBeNull();
    expect(box.querySelector("h2").textContent).toBe("Three checks");                 // 14pt
    expect(box.querySelector("h3").textContent).toBe("Small Word heading");           // h4 -> smallest size the site has
    expect(Array.from(box.querySelectorAll(":scope > ul > li")).map((x) => x.firstChild.textContent)).toEqual(["Restore a file", "Keep a copy offline"]);
    expect(box.querySelector("ul ul li").textContent).toBe("Record the time");
    expect(box.querySelector("ol li").textContent).toBe("Pick a system");
    expect(box.querySelector("a").getAttribute("href")).toBe("/services/backup-disaster-recovery");
    expect(box.querySelector("b").textContent).toBe("assume");
    expect(html).not.toMatch(/o:p|mso-list|Symbol|file:\/\//);
    expect(droppedImages).toBe(1);
    expect(Array.from(box.querySelectorAll("p")).every((x) => x.textContent.trim())).toBe(true);   // spacer paragraphs removed
  });

  test("bold-only lines become headings when no sizes or heading styles are present", () => {
    const { html } = cleanPastedHtml("<p><b>First section</b></p><p>Some body text that is long enough.</p><p><strong>Second section</strong></p><p>More body text.</p>");
    const box = document.createElement("div");
    box.innerHTML = html;
    expect(Array.from(box.querySelectorAll("h2")).map((x) => x.textContent)).toEqual(["First section", "Second section"]);
  });

  test("ordinary web HTML passes through unchanged in structure", () => {
    const { html, droppedImages } = cleanPastedHtml('<h2>Title</h2><p>Text with <a href="https://example.com/x">a link</a>.</p><ul><li>One</li></ul>');
    expect(html).toBe('<h2>Title</h2><p>Text with <a href="https://example.com/x">a link</a>.</p><ul><li>One</li></ul>');
    expect(droppedImages).toBe(0);
  });
});
