import React, { useEffect, useMemo, useRef, useState } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Image from "@tiptap/extension-image";
import { Table, TableRow, TableCell, TableHeader } from "@tiptap/extension-table";
import {
  Bold, Italic, Strikethrough, List, ListOrdered, Quote, Link2, Unlink, Image as ImageIcon, Table as TableIcon,
  Minus, Undo2, Redo2, RemoveFormatting, Code2, Type, Check, X,
} from "lucide-react";
import MarkdownEditor from "./MarkdownEditor";
import { api, API, imgUrl, errMsg } from "../../lib/api";
import { docToMarkdown, cleanPastedHtml } from "../../lib/richtext";
import "./RichTextEditor.css";

// Word-like visual editor for article bodies.
// What you see is what the website shows: type or paste (from Word, Google Docs, a web page),
// select text and make it bold, a heading, a list, a link. The article is still saved as
// Markdown, so the website, the Word import and the "Markdown" tab all work on the same content.

const FILES_PREFIX = `${API}/files/`;

// Stored Markdown -> HTML for the editor (same parser the website uses).
const mdToHtml = (md) =>
  renderToStaticMarkup(
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ img: ({ src, alt }) => <img src={imgUrl(src || "")} alt={alt || ""} /> }}>
      {md || ""}
    </ReactMarkdown>,
  );

const STYLES = [
  { value: "p", label: "Normal text" },
  { value: "h1", label: "Large heading" },
  { value: "h2", label: "Heading" },
  { value: "h3", label: "Subheading" },
];

const Btn = ({ icon: Icon, title, onClick, active, disabled, tid }) => (
  <button type="button" title={title} aria-label={title} aria-pressed={!!active} onMouseDown={(e) => e.preventDefault()} onClick={onClick} disabled={disabled} data-testid={tid}
    className={`h-8 w-8 inline-flex items-center justify-center transition-colors disabled:opacity-35 disabled:cursor-not-allowed ${active ? "bg-navy text-white" : "text-slatesage hover:text-navy hover:bg-ice"}`}>
    <Icon size={16} />
  </button>
);
const Sep = () => <span className="w-px h-5 bg-powder mx-1" />;

export default function RichTextEditor({ value, onChange, testId }) {
  const [mode, setMode] = useState("visual");
  const [linkOpen, setLinkOpen] = useState(false);
  const [linkUrl, setLinkUrl] = useState("");
  const [uploading, setUploading] = useState(false);
  const [notice, setNotice] = useState("");
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  const lastMd = useRef(value || "");          // the Markdown the editor content currently stands for
  const noticeRef = useRef(setNotice);
  noticeRef.current = setNotice;

  const extensions = useMemo(() => [
    StarterKit.configure({
      heading: { levels: [1, 2, 3] },
      underline: false,                          // not kept by the website, so not offered
      link: { openOnClick: false, autolink: true, linkOnPaste: true, HTMLAttributes: { target: null, rel: null } },
    }),
    Image.configure({ inline: false }),
    Table.configure({ resizable: false }),
    TableRow, TableHeader, TableCell,
  ], []);

  const editor = useEditor({
    extensions,
    content: mdToHtml(value),
    shouldRerenderOnTransaction: true,           // keeps the toolbar's active states in step with the selection
    editorProps: {
      attributes: { class: "rte-content", "data-testid": `${testId}-visual`, "aria-label": "Article body" },
      transformPastedHTML: (html) => {
        const cleaned = cleanPastedHtml(html);
        noticeRef.current(cleaned.droppedImages
          ? `${cleaned.droppedImages} picture(s) could not be pasted — pictures copied from Word stay on your computer. Add them with the picture button.`
          : "");
        return cleaned.html;
      },
    },
    onUpdate: ({ editor: ed }) => {
      const md = docToMarkdown(ed.getJSON(), { filesPrefix: FILES_PREFIX });
      lastMd.current = md;
      onChangeRef.current(md);
    },
  });

  // Content changed from outside (Word import, the Markdown tab, a reload): show it in the editor.
  useEffect(() => {
    if (!editor || (value || "") === lastMd.current) return;
    lastMd.current = value || "";
    editor.commands.setContent(mdToHtml(value), { emitUpdate: false });
  }, [value, editor]);

  if (mode === "markdown") {
    return (
      <div data-testid={`${testId}-editor`}>
        <ModeTabs mode={mode} setMode={setMode} testId={testId} />
        <MarkdownEditor value={value} onChange={onChange} testId={testId} />
      </div>
    );
  }
  if (!editor) return null;

  const chain = () => editor.chain().focus();
  const style = editor.isActive("heading", { level: 1 }) ? "h1" : editor.isActive("heading", { level: 2 }) ? "h2" : editor.isActive("heading", { level: 3 }) ? "h3" : "p";
  const setStyle = (v) => (v === "p" ? chain().setParagraph().run() : chain().setHeading({ level: Number(v[1]) }).run());
  const inTable = editor.isActive("table");

  const openLink = () => { setLinkUrl(editor.getAttributes("link").href || ""); setLinkOpen(true); };
  const applyLink = () => {
    const url = linkUrl.trim();
    if (!url) chain().extendMarkRange("link").unsetLink().run();
    else {
      const href = /^(https?:\/\/|mailto:|tel:|\/|#)/i.test(url) ? url : `https://${url}`;
      if (editor.state.selection.empty && !editor.isActive("link")) chain().insertContent({ type: "text", text: href, marks: [{ type: "link", attrs: { href } }] }).run();
      else chain().extendMarkRange("link").setLink({ href }).run();
    }
    setLinkOpen(false);
  };

  const insertImage = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
      chain().setImage({ src: imgUrl(data.path), alt: "" }).run();
    } catch (err) { setNotice(errMsg(err)); } finally { setUploading(false); }
  };

  return (
    <div data-testid={`${testId}-editor`}>
      <ModeTabs mode={mode} setMode={setMode} testId={testId} />
      <div className="border border-powder bg-white">
        <div className="flex items-center gap-0.5 flex-wrap border-b border-powder bg-white px-1.5 py-1" data-testid={`${testId}-toolbar`}>
          <label className="inline-flex items-center gap-1.5 text-slatesage pl-1 pr-1" title="Text size / style">
            <Type size={15} />
            <select value={style} onChange={(e) => setStyle(e.target.value)} data-testid={`${testId}-style`} aria-label="Text size and style"
              className="h-8 border border-powder bg-white px-2 text-[13px] text-midnight focus:outline-none focus:border-navy">
              {STYLES.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </label>
          <Sep />
          <Btn icon={Bold} title="Bold (Ctrl+B)" tid={`${testId}-bold`} active={editor.isActive("bold")} onClick={() => chain().toggleBold().run()} />
          <Btn icon={Italic} title="Italic (Ctrl+I)" tid={`${testId}-italic`} active={editor.isActive("italic")} onClick={() => chain().toggleItalic().run()} />
          <Btn icon={Strikethrough} title="Strikethrough" tid={`${testId}-strike`} active={editor.isActive("strike")} onClick={() => chain().toggleStrike().run()} />
          <Sep />
          <Btn icon={List} title="Bulleted list" tid={`${testId}-ul`} active={editor.isActive("bulletList")} onClick={() => chain().toggleBulletList().run()} />
          <Btn icon={ListOrdered} title="Numbered list" tid={`${testId}-ol`} active={editor.isActive("orderedList")} onClick={() => chain().toggleOrderedList().run()} />
          <Btn icon={Quote} title="Quote" tid={`${testId}-quote`} active={editor.isActive("blockquote")} onClick={() => chain().toggleBlockquote().run()} />
          <Btn icon={Minus} title="Divider line" tid={`${testId}-hr`} onClick={() => chain().setHorizontalRule().run()} />
          <Sep />
          <Btn icon={Link2} title="Add or edit link" tid={`${testId}-link`} active={editor.isActive("link")} onClick={openLink} />
          <Btn icon={Unlink} title="Remove link" tid={`${testId}-unlink`} disabled={!editor.isActive("link")} onClick={() => chain().extendMarkRange("link").unsetLink().run()} />
          <label className="h-8 w-8 inline-flex items-center justify-center text-slatesage hover:text-navy hover:bg-ice transition-colors cursor-pointer" title="Insert picture" data-testid={`${testId}-image`}>
            <ImageIcon size={16} />
            <input type="file" accept="image/*" className="hidden" onChange={insertImage} />
          </label>
          <Btn icon={TableIcon} title="Insert table" tid={`${testId}-table`} disabled={inTable} onClick={() => chain().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()} />
          <Sep />
          <Btn icon={RemoveFormatting} title="Clear formatting" tid={`${testId}-clear`} onClick={() => chain().unsetAllMarks().clearNodes().run()} />
          <Btn icon={Undo2} title="Undo (Ctrl+Z)" tid={`${testId}-undo`} disabled={!editor.can().undo()} onClick={() => chain().undo().run()} />
          <Btn icon={Redo2} title="Redo (Ctrl+Y)" tid={`${testId}-redo`} disabled={!editor.can().redo()} onClick={() => chain().redo().run()} />
          {uploading && <span className="text-[11px] text-slatesage ml-1">Uploading…</span>}
        </div>

        {inTable && (
          <div className="flex items-center gap-1.5 flex-wrap border-b border-powder bg-ice px-2 py-1.5 text-[12px]" data-testid={`${testId}-table-tools`}>
            <span className="font-semibold text-slatesage mr-1">Table:</span>
            {[
              ["Add row", () => chain().addRowAfter().run()],
              ["Add column", () => chain().addColumnAfter().run()],
              ["Delete row", () => chain().deleteRow().run()],
              ["Delete column", () => chain().deleteColumn().run()],
              ["Delete table", () => chain().deleteTable().run()],
            ].map(([label, run]) => (
              <button key={label} type="button" onMouseDown={(e) => e.preventDefault()} onClick={run} className="border border-powder bg-white px-2 py-1 text-midnight hover:border-navy transition-colors">{label}</button>
            ))}
          </div>
        )}

        {linkOpen && (
          <div className="flex items-center gap-2 flex-wrap border-b border-powder bg-ice px-2 py-1.5" data-testid={`${testId}-link-bar`}>
            <span className="text-[12px] font-semibold text-slatesage">Link address:</span>
            <input autoFocus value={linkUrl} onChange={(e) => setLinkUrl(e.target.value)} placeholder="https://… or /services/managed-it"
              onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); applyLink(); } if (e.key === "Escape") setLinkOpen(false); }}
              className="flex-1 min-w-[220px] border border-powder bg-white px-2 py-1 text-[13px] focus:outline-none focus:border-navy" data-testid={`${testId}-link-input`} />
            <button type="button" onClick={applyLink} className="inline-flex items-center gap-1 bg-navy text-white px-2.5 py-1 text-[12px] font-semibold" data-testid={`${testId}-link-apply`}><Check size={13} />Apply</button>
            <button type="button" onClick={() => setLinkOpen(false)} className="inline-flex items-center gap-1 border border-powder bg-white px-2.5 py-1 text-[12px]" aria-label="Cancel link"><X size={13} />Cancel</button>
          </div>
        )}

        {notice && <p className="border-b border-amber-200 bg-amber-50 text-amber-900 text-[12.5px] px-3 py-2" data-testid={`${testId}-notice`}>{notice}</p>}

        <EditorContent editor={editor} className="rte-scroll" />
      </div>
      <p className="mt-1.5 text-[12px] text-slatesage">
        Type here or paste from Word — bold, italic, headings, lists, tables and links are kept. Select text to change it; use the first box to make a line bigger
        (Large heading, Heading, Subheading). The website shows the article with the same formatting you see here.
      </p>
    </div>
  );
}

function ModeTabs({ mode, setMode, testId }) {
  const tab = (key, label, Icon) => (
    <button type="button" onClick={() => setMode(key)} data-testid={`${testId}-mode-${key}`} aria-pressed={mode === key}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-[12px] font-semibold border border-b-0 transition-colors ${mode === key ? "bg-white border-powder text-navy" : "bg-transparent border-transparent text-slatesage hover:text-navy"}`}>
      <Icon size={13} />{label}
    </button>
  );
  return <div className="flex items-end gap-1 -mb-px relative z-[1]">{tab("visual", "Editor", Type)}{tab("markdown", "Markdown (advanced)", Code2)}</div>;
}
