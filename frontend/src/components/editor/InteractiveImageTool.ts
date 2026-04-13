/**
 * Custom Editor.js Interactive Image Block Tool
 * Authors upload/paste an image URL, then click directly on the image to place
 * hotspot markers. Each hotspot opens a modal on the public article page.
 */

import { normalizeMediaUrl } from "@/lib/media";

interface ImageHotspot {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  shape: "circle" | "rect";
  modal_title: string;
  modal_content: string;
}

interface InteractiveImageToolData {
  file?: { url: string };
  url?: string;
  caption?: string;
  hotspots?: ImageHotspot[];
}

interface InteractiveImageToolConfig {
  endpoints?: { byFile?: string };
  additionalRequestHeaders?: Record<string, string>;
  field?: string;
}

export default class InteractiveImageTool {
  private data: {
    file?: { url: string };
    url?: string;
    caption: string;
    hotspots: ImageHotspot[];
  };
  private config: InteractiveImageToolConfig;
  private wrapper: HTMLElement | null = null;

  static get toolbox() {
    return {
      title: "Interactive Image",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/><circle cx="17" cy="8" r="2" stroke-dasharray="2 2"/></svg>',
    };
  }

  static get isReadOnlySupported() {
    return true;
  }

  constructor({
    data,
    config,
  }: {
    data?: InteractiveImageToolData;
    config?: InteractiveImageToolConfig;
    api: unknown;
  }) {
    this.data = {
      file: data?.file?.url ? { url: normalizeMediaUrl(data.file.url) } : data?.file,
      url: data?.url ? normalizeMediaUrl(data.url) : data?.url,
      caption: data?.caption || "",
      hotspots: data?.hotspots || [],
    };
    this.config = config || {};
  }

  render(): HTMLElement {
    this.wrapper = document.createElement("div");
    this.wrapper.style.cssText =
      "border:1px solid #e2e8f0;border-radius:12px;padding:16px;background:#f8fafc;";
    const imageUrl = normalizeMediaUrl(this.data.file?.url || this.data.url || "");
    if (imageUrl) {
      this._renderImageView(imageUrl);
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

    const icon = document.createElement("div");
    icon.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>';
    container.appendChild(icon);

    const label = document.createElement("div");
    label.style.cssText = "font-size:13px;font-weight:600;color:#374151;";
    label.textContent = "Interactive Image";
    container.appendChild(label);

    const uploadBtn = document.createElement("button");
    uploadBtn.textContent = "Upload Image";
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
    urlInput.placeholder = "https://example.com/image.jpg";
    urlInput.style.cssText =
      "width:100%;padding:8px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;outline:none;box-sizing:border-box;";
    urlInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const url = urlInput.value.trim();
        if (url) {
          this.data.url = url;
          this._renderImageView(url);
        }
      }
    });
    container.appendChild(urlInput);

    this.wrapper.appendChild(container);
  }

  private _renderImageView(imageUrl: string): void {
    if (!this.wrapper) return;
    this.wrapper.innerHTML = "";

    // Title badge
    const badge = document.createElement("div");
    badge.style.cssText =
      "font-size:12px;font-weight:600;color:#3b82f6;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:10px;";
    badge.textContent = "Interactive Image — Click on the image to add hotspots";
    this.wrapper.appendChild(badge);

    // Image container (relative for hotspot overlays)
    const imgWrap = document.createElement("div");
    imgWrap.style.cssText = "position:relative;display:inline-block;width:100%;cursor:crosshair;border-radius:10px;overflow:hidden;";

    const img = document.createElement("img");
    img.src = imageUrl;
    img.alt = this.data.caption || "Interactive image";
    img.style.cssText = "width:100%;display:block;border-radius:10px;";
    img.draggable = false;
    imgWrap.appendChild(img);

    // Render existing hotspots as overlays
    this._renderHotspotOverlays(imgWrap);

    // Click handler: place a new hotspot
    img.addEventListener("click", (e) => {
      const rect = img.getBoundingClientRect();
      const x = parseFloat(((e.clientX - rect.left) / rect.width * 100).toFixed(1));
      const y = parseFloat(((e.clientY - rect.top) / rect.height * 100).toFixed(1));
      this._showHotspotForm(imgWrap, imageUrl, undefined, x, y);
    });

    this.wrapper.appendChild(imgWrap);

    // Caption
    const captionInput = document.createElement("input");
    captionInput.type = "text";
    captionInput.placeholder = "Add a caption (optional)";
    captionInput.value = this.data.caption;
    captionInput.style.cssText =
      "width:100%;padding:6px 8px;margin-top:8px;border:none;border-top:1px solid #e2e8f0;font-size:13px;color:#64748b;outline:none;background:transparent;box-sizing:border-box;";
    captionInput.addEventListener("input", () => {
      this.data.caption = captionInput.value;
    });
    this.wrapper.appendChild(captionInput);

    // Hotspot list
    this._renderHotspotList(imgWrap, imageUrl);

    // Replace button
    const replaceBtn = document.createElement("button");
    replaceBtn.textContent = "✕ Replace image";
    replaceBtn.type = "button";
    replaceBtn.style.cssText =
      "position:absolute;top:8px;right:8px;background:#ef4444;color:white;border:none;border-radius:4px;padding:2px 8px;font-size:12px;cursor:pointer;";
    replaceBtn.addEventListener("click", () => {
      this.data = { file: undefined, url: undefined, caption: "", hotspots: [] };
      this._renderUploadUI();
    });
    imgWrap.style.position = "relative";
    imgWrap.appendChild(replaceBtn);
  }

  private _renderHotspotOverlays(imgWrap: HTMLElement): void {
    // Remove existing overlay buttons (keep img and replace btn)
    imgWrap.querySelectorAll(".hs-overlay").forEach((el) => el.remove());

    this.data.hotspots.forEach((hs) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "hs-overlay";
      btn.title = `${hs.modal_title || "Hotspot"} — click to edit`;
      btn.style.cssText = `
        position:absolute;
        left:${hs.x}%;top:${hs.y}%;
        width:${hs.width}%;height:${hs.height}%;
        border:2px solid #3b82f6;
        background:rgba(59,130,246,0.2);
        ${hs.shape === "circle" ? "border-radius:50%;" : "border-radius:6px;"}
        cursor:pointer;display:flex;align-items:center;justify-content:center;
        z-index:10;
      `;
      btn.innerHTML =
        '<span style="width:20px;height:20px;background:#3b82f6;border-radius:50%;display:flex;align-items:center;justify-content:center;color:white;font-size:12px;font-weight:700;pointer-events:none;">+</span>';
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        this._showHotspotForm(imgWrap, this.data.file?.url || this.data.url || "", hs);
      });
      imgWrap.appendChild(btn);
    });
  }

  private _renderHotspotList(imgWrap: HTMLElement, imageUrl: string): void {
    if (!this.wrapper) return;
    const existing = this.wrapper.querySelector(".hs-list");
    if (existing) existing.remove();

    const section = document.createElement("div");
    section.className = "hs-list";
    section.style.cssText = "margin-top:12px;";

    const header = document.createElement("div");
    header.style.cssText =
      "display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;";
    header.innerHTML = `<span style="font-size:12px;font-weight:600;color:#374151;">Hotspots (${this.data.hotspots.length})</span>`;
    const hint = document.createElement("span");
    hint.textContent = "Click on the image above to add";
    hint.style.cssText = "font-size:11px;color:#94a3b8;";
    header.appendChild(hint);
    section.appendChild(header);

    if (this.data.hotspots.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText =
        "text-align:center;padding:10px;color:#94a3b8;font-size:12px;border:1px dashed #e2e8f0;border-radius:8px;";
      empty.textContent = "No hotspots yet — click anywhere on the image to add one.";
      section.appendChild(empty);
    } else {
      const list = document.createElement("div");
      list.style.cssText = "display:flex;flex-direction:column;gap:4px;";
      this.data.hotspots.forEach((hs) => {
        const row = document.createElement("div");
        row.style.cssText =
          "display:flex;align-items:center;gap:8px;padding:7px 10px;background:white;border:1px solid #e2e8f0;border-radius:8px;";
        row.innerHTML = `
          <span style="font-size:12px;background:#eff6ff;color:#1d4ed8;padding:2px 6px;border-radius:4px;">${hs.shape === "circle" ? "◯" : "▭"}</span>
          <div style="flex:1;min-width:0;">
            <div style="font-size:13px;font-weight:500;color:#1e293b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${_esc(hs.modal_title) || "(no title)"}</div>
            <div style="font-size:11px;color:#94a3b8;">x:${hs.x}% y:${hs.y}% w:${hs.width}% h:${hs.height}%</div>
          </div>
        `;
        const editBtn = _btn("Edit", "#f1f5f9", "#374151", "1px solid #e2e8f0");
        editBtn.addEventListener("click", () => this._showHotspotForm(imgWrap, imageUrl, hs));
        row.appendChild(editBtn);
        const delBtn = _btn("✕", "#fee2e2", "#dc2626");
        delBtn.addEventListener("click", () => {
          this.data.hotspots = this.data.hotspots.filter((h) => h.id !== hs.id);
          this._renderHotspotOverlays(imgWrap);
          this._renderHotspotList(imgWrap, imageUrl);
        });
        row.appendChild(delBtn);
        list.appendChild(row);
      });
      section.appendChild(list);
    }

    this.wrapper.appendChild(section);
  }

  private _showHotspotForm(
    imgWrap: HTMLElement,
    imageUrl: string,
    existing?: ImageHotspot,
    defaultX = 10,
    defaultY = 10
  ): void {
    const vals = {
      x: String(existing?.x ?? defaultX),
      y: String(existing?.y ?? defaultY),
      width: String(existing?.width ?? 15),
      height: String(existing?.height ?? 15),
      shape: existing?.shape ?? "rect",
      modal_title: existing?.modal_title ?? "",
      modal_content: existing?.modal_content ?? "",
    };

    const { overlay, form } = _createOverlay(existing ? "Edit Hotspot" : "Add Hotspot");
    _hint(form, "Position and size are in % of the image dimensions.");

    // Position row
    const posRow = document.createElement("div");
    posRow.style.cssText = "display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:8px;margin-top:12px;";
    for (const [key, label] of [["x", "Left (%)"], ["y", "Top (%)"], ["width", "Width (%)"], ["height", "Height (%)"]] as const) {
      const wrap = document.createElement("div");
      const lbl = document.createElement("label");
      lbl.textContent = label;
      lbl.style.cssText = "display:block;font-size:11px;color:#6b7280;margin-bottom:3px;font-weight:500;";
      wrap.appendChild(lbl);
      const input = document.createElement("input");
      input.type = "number";
      input.min = "0";
      input.max = "100";
      input.step = "0.5";
      input.value = vals[key];
      input.style.cssText =
        "width:100%;padding:6px 8px;border:1px solid #e2e8f0;border-radius:6px;font-size:13px;outline:none;box-sizing:border-box;";
      input.addEventListener("input", () => { vals[key] = input.value; });
      wrap.appendChild(input);
      posRow.appendChild(wrap);
    }
    form.appendChild(posRow);

    // Shape
    _label(form, "Shape");
    const shapeSelect = document.createElement("select");
    shapeSelect.style.cssText =
      "width:100%;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;outline:none;background:white;color:#1e293b;";
    [["rect", "Rectangle"], ["circle", "Circle"]].forEach(([val, label]) => {
      const opt = document.createElement("option");
      opt.value = val;
      opt.textContent = label;
      opt.selected = vals.shape === val;
      shapeSelect.appendChild(opt);
    });
    shapeSelect.addEventListener("change", () => { vals.shape = shapeSelect.value as "circle" | "rect"; });
    form.appendChild(shapeSelect);

    _label(form, "Modal title");
    const titleInput = _input(form, "e.g. The nucleus", vals.modal_title);
    titleInput.addEventListener("input", () => { vals.modal_title = titleInput.value; });

    _label(form, "Modal content");
    _hint(form, "HTML is supported.");
    const contentArea = _textarea(form, "<p>Description of this area…</p>", vals.modal_content);
    contentArea.addEventListener("input", () => { vals.modal_content = contentArea.value; });

    const { cancelBtn, saveBtn } = _formButtons(form, existing ? "Save Changes" : "Add Hotspot");
    cancelBtn.addEventListener("click", () => overlay.remove());
    saveBtn.addEventListener("click", () => {
      if (existing) {
        const idx = this.data.hotspots.findIndex((h) => h.id === existing.id);
        if (idx !== -1) {
          this.data.hotspots[idx] = {
            id: existing.id,
            x: parseFloat(vals.x),
            y: parseFloat(vals.y),
            width: parseFloat(vals.width),
            height: parseFloat(vals.height),
            shape: vals.shape as "circle" | "rect",
            modal_title: vals.modal_title,
            modal_content: vals.modal_content,
          };
        }
      } else {
        this.data.hotspots.push({
          id: Math.random().toString(36).slice(2),
          x: parseFloat(vals.x),
          y: parseFloat(vals.y),
          width: parseFloat(vals.width),
          height: parseFloat(vals.height),
          shape: vals.shape as "circle" | "rect",
          modal_title: vals.modal_title,
          modal_content: vals.modal_content,
        });
      }
      overlay.remove();
      this._renderHotspotOverlays(imgWrap);
      this._renderHotspotList(imgWrap, imageUrl);
    });

    document.body.appendChild(overlay);
  }

  private _selectFile(): void {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/*";
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
    formData.append(this.config.field || "image", file);
    if (this.wrapper) {
      this.wrapper.innerHTML =
        '<div style="text-align:center;padding:40px;color:#94a3b8;">Uploading image…</div>';
    }
    try {
      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
        headers: this.config.additionalRequestHeaders || {},
      });
      const result = await response.json();
      if (result.success === 1 && result.file?.url) {
        const mediaUrl = normalizeMediaUrl(result.file.url);
        this.data.file = { url: mediaUrl };
        this._renderImageView(mediaUrl);
      } else {
        this._renderUploadUI();
      }
    } catch {
      this._renderUploadUI();
    }
  }

  save(): InteractiveImageToolData {
    return {
      file: this.data.file,
      url: this.data.url,
      caption: this.data.caption,
      hotspots: this.data.hotspots,
    };
  }

  validate(savedData: InteractiveImageToolData): boolean {
    return !!(savedData.file?.url || savedData.url);
  }
}

// ─── Shared DOM helpers (duplicated from InteractiveTextTool) ─────────────────

function _esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function _label(parent: HTMLElement, text: string): void {
  const el = document.createElement("label");
  el.textContent = text;
  el.style.cssText =
    "display:block;font-size:12px;font-weight:500;color:#6b7280;margin-bottom:4px;margin-top:12px;";
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
  el.type = "text";
  el.placeholder = placeholder;
  el.value = value;
  el.style.cssText =
    "width:100%;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;outline:none;box-sizing:border-box;color:#1e293b;";
  parent.appendChild(el);
  return el;
}

function _textarea(parent: HTMLElement, placeholder: string, value = ""): HTMLTextAreaElement {
  const el = document.createElement("textarea");
  el.placeholder = placeholder;
  el.value = value;
  el.rows = 4;
  el.style.cssText =
    "width:100%;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;resize:vertical;outline:none;box-sizing:border-box;font-family:inherit;color:#1e293b;";
  parent.appendChild(el);
  return el;
}

function _btn(text: string, bg: string, color: string, border = "none"): HTMLButtonElement {
  const el = document.createElement("button");
  el.textContent = text;
  el.type = "button";
  el.style.cssText = `padding:4px 12px;background:${bg};color:${color};border:${border};border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;flex-shrink:0;white-space:nowrap;`;
  return el;
}

function _createOverlay(title: string): { overlay: HTMLElement; form: HTMLElement } {
  const overlay = document.createElement("div");
  overlay.style.cssText =
    "position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;";
  const form = document.createElement("div");
  form.style.cssText =
    "background:white;border-radius:14px;padding:24px;width:500px;max-width:100%;max-height:90vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.25);";
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
