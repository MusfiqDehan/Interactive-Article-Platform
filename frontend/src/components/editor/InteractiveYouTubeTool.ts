/**
 * Custom Editor.js Interactive YouTube Block Tool
 * Paste a YouTube URL, then add timed chapters.
 * Each chapter seeks the embedded player and opens a modal on the public page.
 */

interface MediaChapter {
  id: string;
  time: number;
  label: string;
  modal_title: string;
  modal_content: string;
}

interface InteractiveYouTubeToolData {
  source?: string;
  caption?: string;
  chapters?: MediaChapter[];
}

export default class InteractiveYouTubeTool {
  private data: { source: string; caption: string; chapters: MediaChapter[] };
  private wrapper: HTMLElement | null = null;

  static get toolbox() {
    return {
      title: "Interactive YouTube",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46A2.78 2.78 0 0 0 1.46 6.42 29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58A2.78 2.78 0 0 0 3.41 19.6C5.12 20 12 20 12 20s6.88 0 8.59-.46a2.78 2.78 0 0 0 1.95-1.95A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58z"/><polygon points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02" fill="currentColor" stroke="none"/></svg>',
    };
  }

  static get isReadOnlySupported() {
    return true;
  }

  constructor({ data }: { data?: InteractiveYouTubeToolData; api: unknown }) {
    this.data = {
      source: data?.source || "",
      caption: data?.caption || "",
      chapters: data?.chapters || [],
    };
  }

  render(): HTMLElement {
    this.wrapper = document.createElement("div");
    this.wrapper.style.cssText =
      "border:1px solid #e2e8f0;border-radius:12px;padding:16px;background:#f8fafc;";
    if (this.data.source) {
      this._renderEmbedView();
    } else {
      this._renderUrlInput();
    }
    return this.wrapper;
  }

  private _renderUrlInput(): void {
    if (!this.wrapper) return;
    this.wrapper.innerHTML = "";

    const container = document.createElement("div");
    container.style.cssText =
      "display:flex;flex-direction:column;align-items:center;gap:12px;padding:24px;";

    container.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22.54 6.42a2.78 2.78 0 0 0-1.95-1.96C18.88 4 12 4 12 4s-6.88 0-8.59.46A2.78 2.78 0 0 0 1.46 6.42 29 29 0 0 0 1 12a29 29 0 0 0 .46 5.58A2.78 2.78 0 0 0 3.41 19.6C5.12 20 12 20 12 20s6.88 0 8.59-.46a2.78 2.78 0 0 0 1.95-1.95A29 29 0 0 0 23 12a29 29 0 0 0-.46-5.58z"/><polygon points="9.75 15.02 15.5 12 9.75 8.98 9.75 15.02"/></svg>
      <div style="font-size:13px;font-weight:600;color:#374151;">Interactive YouTube</div>
      <div style="font-size:12px;color:#94a3b8;text-align:center;">Paste a YouTube URL and add chapters that open info modals when clicked.</div>
    `;

    const urlInput = document.createElement("input");
    urlInput.type = "url";
    urlInput.placeholder = "https://www.youtube.com/watch?v=...";
    urlInput.style.cssText =
      "width:100%;padding:8px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;box-sizing:border-box;";

    const embedBtn = document.createElement("button");
    embedBtn.textContent = "Embed Video";
    embedBtn.type = "button";
    embedBtn.style.cssText =
      "padding:8px 20px;background:#3b82f6;color:white;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:500;";

    const embed = () => {
      const url = urlInput.value.trim();
      if (url) {
        this.data.source = url;
        this._renderEmbedView();
      }
    };

    urlInput.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); embed(); } });
    embedBtn.addEventListener("click", embed);

    container.appendChild(urlInput);
    container.appendChild(embedBtn);
    this.wrapper.appendChild(container);
  }

  private _renderEmbedView(): void {
    if (!this.wrapper) return;
    this.wrapper.innerHTML = "";
    this.wrapper.style.position = "relative";

    const badge = document.createElement("div");
    badge.style.cssText =
      "font-size:12px;font-weight:600;color:#3b82f6;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px;";
    badge.textContent = "Interactive YouTube";
    this.wrapper.appendChild(badge);

    const embedUrl = _toEmbedUrl(this.data.source);

    // Preview iframe
    const iframeWrap = document.createElement("div");
    iframeWrap.style.cssText =
      "position:relative;width:100%;aspect-ratio:16/9;border-radius:8px;overflow:hidden;background:#0f172a;";
    const iframe = document.createElement("iframe");
    iframe.src = embedUrl;
    iframe.style.cssText = "position:absolute;inset:0;width:100%;height:100%;border:none;";
    iframe.allow =
      "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
    iframe.setAttribute("allowfullscreen", "");
    iframeWrap.appendChild(iframe);
    this.wrapper.appendChild(iframeWrap);

    const captionInput = document.createElement("input");
    captionInput.type = "text";
    captionInput.placeholder = "Add a caption (optional)";
    captionInput.value = this.data.caption;
    captionInput.style.cssText =
      "width:100%;padding:6px 8px;border:none;border-bottom:1px solid #e2e8f0;font-size:13px;color:#64748b;outline:none;background:transparent;box-sizing:border-box;margin-top:8px;margin-bottom:12px;";
    captionInput.addEventListener("input", () => { this.data.caption = captionInput.value; });
    this.wrapper.appendChild(captionInput);

    this._renderChapterSection();

    const replaceBtn = document.createElement("button");
    replaceBtn.textContent = "✕ Replace";
    replaceBtn.type = "button";
    replaceBtn.style.cssText =
      "position:absolute;top:8px;right:8px;background:#ef4444;color:white;border:none;border-radius:4px;padding:2px 8px;font-size:12px;cursor:pointer;z-index:1;";
    replaceBtn.addEventListener("click", () => {
      this.data = { source: "", caption: "", chapters: [] };
      this._renderUrlInput();
    });
    this.wrapper.appendChild(replaceBtn);
  }

  private _renderChapterSection(): void {
    if (!this.wrapper) return;
    this.wrapper.querySelectorAll(".chapter-section").forEach((el) => el.remove());

    const section = document.createElement("div");
    section.className = "chapter-section";

    const header = document.createElement("div");
    header.style.cssText =
      "display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;";
    const label = document.createElement("span");
    label.style.cssText = "font-size:12px;font-weight:600;color:#374151;";
    label.textContent = `Chapters (${this.data.chapters.length})`;
    header.appendChild(label);
    const addBtn = _btn("+ Add Chapter", "#3b82f6", "white");
    addBtn.addEventListener("click", () => this._showChapterForm());
    header.appendChild(addBtn);
    section.appendChild(header);

    if (this.data.chapters.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText =
        "text-align:center;padding:10px;color:#94a3b8;font-size:12px;border:1px dashed #e2e8f0;border-radius:8px;";
      empty.textContent = "No chapters yet. Add chapters to create interactive timestamps.";
      section.appendChild(empty);
    } else {
      const sorted = [...this.data.chapters].sort((a, b) => a.time - b.time);
      const list = document.createElement("div");
      list.style.cssText = "display:flex;flex-direction:column;gap:4px;";
      sorted.forEach((ch) => {
        const row = document.createElement("div");
        row.style.cssText =
          "display:flex;align-items:center;gap:8px;padding:7px 10px;background:white;border:1px solid #e2e8f0;border-radius:8px;";
        row.innerHTML = `
          <span style="font-size:12px;font-family:monospace;background:#eff6ff;color:#1d4ed8;padding:2px 6px;border-radius:4px;flex-shrink:0;">${_formatTime(ch.time)}</span>
          <div style="flex:1;min-width:0;">
            <div style="font-size:13px;font-weight:500;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${_esc(ch.label)}</div>
            <div style="font-size:11px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${_esc(ch.modal_title) || "(no modal title)"}</div>
          </div>
        `;
        const editBtn = _btn("Edit", "#f1f5f9", "#374151", "1px solid #e2e8f0");
        editBtn.addEventListener("click", () => this._showChapterForm(ch));
        row.appendChild(editBtn);
        const delBtn = _btn("✕", "#fee2e2", "#dc2626");
        delBtn.addEventListener("click", () => {
          this.data.chapters = this.data.chapters.filter((c) => c.id !== ch.id);
          this._renderChapterSection();
        });
        row.appendChild(delBtn);
        list.appendChild(row);
      });
      section.appendChild(list);
    }

    this.wrapper.appendChild(section);
  }

  private _showChapterForm(existing?: MediaChapter): void {
    const vals = {
      timeStr: existing ? _formatTime(existing.time) : "",
      label: existing?.label || "",
      modal_title: existing?.modal_title || "",
      modal_content: existing?.modal_content || "",
    };

    const { overlay, form } = _createOverlay(existing ? "Edit Chapter" : "Add Chapter");

    _label(form, "Timestamp");
    _hint(form, "Enter the time in MM:SS format (e.g. 1:30 for 1 minute 30 seconds).");
    const timeInput = _input(form, "e.g. 1:30", vals.timeStr);
    timeInput.addEventListener("input", () => { vals.timeStr = timeInput.value; });

    _label(form, "Chapter label");
    const labelInput = _input(form, "e.g. Introduction", vals.label);
    labelInput.addEventListener("input", () => { vals.label = labelInput.value; });

    _label(form, "Modal title");
    const titleInput = _input(form, "e.g. About the introduction", vals.modal_title);
    titleInput.addEventListener("input", () => { vals.modal_title = titleInput.value; });

    _label(form, "Modal content");
    _hint(form, "HTML is supported.");
    const contentArea = _textarea(form, "<p>Details shown when this chapter is opened…</p>", vals.modal_content);
    contentArea.addEventListener("input", () => { vals.modal_content = contentArea.value; });

    const { cancelBtn, saveBtn } = _formButtons(form, existing ? "Save Changes" : "Add Chapter");
    cancelBtn.addEventListener("click", () => overlay.remove());
    saveBtn.addEventListener("click", () => {
      const time = _parseTime(vals.timeStr);
      if (time === null) { alert("Please enter a valid time in MM:SS format."); return; }
      if (!vals.label.trim()) { alert("Please enter a chapter label."); return; }
      if (existing) {
        const idx = this.data.chapters.findIndex((c) => c.id === existing.id);
        if (idx !== -1) this.data.chapters[idx] = { id: existing.id, time, label: vals.label, modal_title: vals.modal_title, modal_content: vals.modal_content };
      } else {
        this.data.chapters.push({ id: Math.random().toString(36).slice(2), time, label: vals.label, modal_title: vals.modal_title, modal_content: vals.modal_content });
      }
      overlay.remove();
      this._renderChapterSection();
    });

    document.body.appendChild(overlay);
  }

  save(): InteractiveYouTubeToolData {
    return { source: this.data.source, caption: this.data.caption, chapters: this.data.chapters };
  }

  validate(savedData: InteractiveYouTubeToolData): boolean {
    return !!savedData.source?.trim();
  }
}

// ─── Shared helpers ───────────────────────────────────────────────────────────

function _esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function _formatTime(s: number): string {
  const m = Math.floor(s / 60), sec = Math.floor(s % 60);
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
function _parseTime(str: string): number | null {
  const clean = str.trim();
  if (/^\d+$/.test(clean)) return parseInt(clean, 10);
  const match = clean.match(/^(\d+):(\d{1,2})$/);
  if (!match) return null;
  const m = parseInt(match[1], 10), s = parseInt(match[2], 10);
  if (s > 59) return null;
  return m * 60 + s;
}
function _toEmbedUrl(source: string): string {
  try {
    if (source.includes("youtube.com/watch")) return `https://www.youtube-nocookie.com/embed/${new URL(source).searchParams.get("v") || ""}`;
    if (source.includes("youtu.be/")) return `https://www.youtube-nocookie.com/embed/${source.split("youtu.be/")[1]?.split("?")[0] || ""}`;
    if (source.includes("youtube.com/embed/")) return source;
  } catch { /* ignore */ }
  return source;
}
function _label(parent: HTMLElement, text: string): void {
  const el = document.createElement("label");
  el.textContent = text;
  el.style.cssText = "display:block;font-size:12px;font-weight:500;color:#6b7280;margin-bottom:4px;margin-top:12px;";
  parent.appendChild(el);
}
function _hint(parent: HTMLElement, text: string): void {
  const el = document.createElement("p");
  el.textContent = text;
  el.style.cssText = "font-size:11px;color:#94a3b8;margin:0 0 4px;";
  parent.appendChild(el);
}
function _input(parent: HTMLElement, placeholder: string, value = ""): HTMLInputElement {
  const el = document.createElement("input");
  el.type = "text"; el.placeholder = placeholder; el.value = value;
  el.style.cssText = "width:100%;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;outline:none;box-sizing:border-box;color:#1e293b;";
  parent.appendChild(el);
  return el;
}
function _textarea(parent: HTMLElement, placeholder: string, value = ""): HTMLTextAreaElement {
  const el = document.createElement("textarea");
  el.placeholder = placeholder; el.value = value; el.rows = 4;
  el.style.cssText = "width:100%;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;resize:vertical;outline:none;box-sizing:border-box;font-family:inherit;color:#1e293b;";
  parent.appendChild(el);
  return el;
}
function _btn(text: string, bg: string, color: string, border = "none"): HTMLButtonElement {
  const el = document.createElement("button");
  el.textContent = text; el.type = "button";
  el.style.cssText = `padding:4px 12px;background:${bg};color:${color};border:${border};border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;flex-shrink:0;white-space:nowrap;`;
  return el;
}
function _createOverlay(title: string): { overlay: HTMLElement; form: HTMLElement } {
  const overlay = document.createElement("div");
  overlay.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;";
  const form = document.createElement("div");
  form.style.cssText = "background:white;border-radius:14px;padding:24px;width:480px;max-width:100%;max-height:90vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.25);";
  const h3 = document.createElement("h3");
  h3.textContent = title;
  h3.style.cssText = "margin:0 0 4px;font-size:16px;font-weight:600;color:#111827;";
  form.appendChild(h3);
  overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.remove(); });
  overlay.appendChild(form);
  return { overlay, form };
}
function _formButtons(form: HTMLElement, saveLabel: string): { cancelBtn: HTMLButtonElement; saveBtn: HTMLButtonElement } {
  const row = document.createElement("div");
  row.style.cssText = "display:flex;gap:8px;justify-content:flex-end;margin-top:20px;";
  const cancelBtn = _btn("Cancel", "#f1f5f9", "#374151", "1px solid #e2e8f0");
  cancelBtn.style.padding = "8px 16px";
  row.appendChild(cancelBtn);
  const saveBtn = _btn(saveLabel, "#3b82f6", "white");
  saveBtn.style.padding = "8px 16px";
  row.appendChild(saveBtn);
  form.appendChild(row);
  return { cancelBtn, saveBtn };
}
