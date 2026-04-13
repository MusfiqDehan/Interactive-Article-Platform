/**
 * Custom Editor.js Interactive Video Block Tool
 * Upload or paste a video URL, then add timed chapters.
 * Each chapter seeks the video player and opens a modal on the public page.
 */

interface MediaChapter {
  id: string;
  time: number;
  label: string;
  modal_title: string;
  modal_content: string;
}

interface InteractiveVideoToolData {
  file?: { url: string };
  url?: string;
  caption?: string;
  chapters?: MediaChapter[];
}

interface InteractiveVideoToolConfig {
  endpoints?: { byFile?: string };
  additionalRequestHeaders?: Record<string, string>;
  field?: string;
}

export default class InteractiveVideoTool {
  private data: {
    file?: { url: string };
    url?: string;
    caption: string;
    chapters: MediaChapter[];
  };
  private config: InteractiveVideoToolConfig;
  private wrapper: HTMLElement | null = null;

  static get toolbox() {
    return {
      title: "Interactive Video",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/><line x1="8" y1="10" x2="8" y2="14"/></svg>',
    };
  }

  static get isReadOnlySupported() {
    return true;
  }

  constructor({
    data,
    config,
  }: {
    data?: InteractiveVideoToolData;
    config?: InteractiveVideoToolConfig;
    api: unknown;
  }) {
    this.data = {
      file: data?.file,
      url: data?.url,
      caption: data?.caption || "",
      chapters: data?.chapters || [],
    };
    this.config = config || {};
  }

  render(): HTMLElement {
    this.wrapper = document.createElement("div");
    this.wrapper.style.cssText =
      "border:1px solid #e2e8f0;border-radius:12px;padding:16px;background:#f8fafc;";
    const videoUrl = this.data.file?.url || this.data.url || "";
    if (videoUrl) {
      this._renderVideoView(videoUrl);
    } else {
      this._renderUploadUI();
    }
    return this.wrapper;
  }

  private _renderUploadUI(): void {
    if (!this.wrapper) return;
    this.wrapper.innerHTML = "";

    const container = document.createElement("div");
    container.style.cssText =
      "display:flex;flex-direction:column;align-items:center;gap:12px;padding:24px;";

    container.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
      <div style="font-size:13px;font-weight:600;color:#374151;">Interactive Video</div>
    `;

    const uploadBtn = document.createElement("button");
    uploadBtn.textContent = "Upload Video File";
    uploadBtn.type = "button";
    uploadBtn.style.cssText =
      "padding:8px 20px;background:#3b82f6;color:white;border:none;border-radius:8px;cursor:pointer;font-size:14px;font-weight:500;";
    uploadBtn.addEventListener("click", () => this._selectFile());
    container.appendChild(uploadBtn);

    const divider = document.createElement("div");
    divider.textContent = "or paste a URL";
    divider.style.cssText = "color:#94a3b8;font-size:13px;";
    container.appendChild(divider);

    const urlInput = document.createElement("input");
    urlInput.type = "url";
    urlInput.placeholder = "https://example.com/video.mp4";
    urlInput.style.cssText =
      "width:100%;padding:8px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;box-sizing:border-box;";
    urlInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const url = urlInput.value.trim();
        if (url) {
          this.data.url = url;
          this._renderVideoView(url);
        }
      }
    });
    container.appendChild(urlInput);
    this.wrapper.appendChild(container);
  }

  private _renderVideoView(videoUrl: string): void {
    if (!this.wrapper) return;
    this.wrapper.innerHTML = "";
    this.wrapper.style.position = "relative";

    const badge = document.createElement("div");
    badge.style.cssText =
      "font-size:12px;font-weight:600;color:#3b82f6;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px;";
    badge.textContent = "Interactive Video";
    this.wrapper.appendChild(badge);

    const videoWrap = document.createElement("div");
    videoWrap.style.cssText = "border-radius:8px;overflow:hidden;background:#0f172a;";
    const video = document.createElement("video");
    video.src = videoUrl;
    video.controls = true;
    video.preload = "metadata";
    video.style.cssText = "width:100%;display:block;";
    videoWrap.appendChild(video);
    this.wrapper.appendChild(videoWrap);

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
      this.data = { file: undefined, url: undefined, caption: "", chapters: [] };
      this._renderUploadUI();
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

  private _selectFile(): void {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "video/*";
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (file) this._uploadFile(file);
    });
    input.click();
  }

  private async _uploadFile(file: File): Promise<void> {
    const endpoint = this.config.endpoints?.byFile;
    if (!endpoint) return;
    const formData = new FormData();
    formData.append(this.config.field || "file", file);
    if (this.wrapper) this.wrapper.innerHTML = '<div style="text-align:center;padding:40px;color:#94a3b8;">Uploading video…</div>';
    try {
      const response = await fetch(endpoint, { method: "POST", body: formData, headers: this.config.additionalRequestHeaders || {} });
      const result = await response.json();
      if (result.success === 1 && result.file?.url) {
        this.data.file = { url: result.file.url };
        this._renderVideoView(result.file.url);
      } else {
        this._renderUploadUI();
      }
    } catch {
      this._renderUploadUI();
    }
  }

  save(): InteractiveVideoToolData {
    return { file: this.data.file, url: this.data.url, caption: this.data.caption, chapters: this.data.chapters };
  }

  validate(savedData: InteractiveVideoToolData): boolean {
    return !!(savedData.file?.url || savedData.url);
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
