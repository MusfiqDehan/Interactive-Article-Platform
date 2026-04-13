/**
 * Custom Editor.js Interactive Text Block Tool
 *
 * Workflow:
 *  1. Author types a paragraph in the contenteditable area.
 *  2. Author selects some words → a floating "🔗 Add Interactive" button appears.
 *  3. Clicking opens a dialog to choose the annotation type:
 *       Text | Image | Audio | Video | YouTube
 *  4. After saving, the selected words turn blue + a 🔍 icon appears beside them.
 *  5. Clicking an existing annotation in the editor opens its edit dialog.
 *
 * On save: the block emits { text: "<HTML with span markers>", annotations: [...] }
 */

type AnnotationType = "text" | "image" | "audio" | "video" | "youtube";

interface AnnotationRecord {
  id: string;
  type: AnnotationType;
  modal_title: string;
  modal_content?: string;
  image_url?: string;
  image_caption?: string;
  audio_url?: string;
  video_url?: string;
  youtube_source?: string;
}

interface InteractiveTextToolData {
  text?: string;
  annotations?: AnnotationRecord[];
}

const ANNOTATION_STYLE =
  "background:rgba(59,130,246,0.12);color:#1d4ed8;border-bottom:2px solid #3b82f6;border-radius:3px;padding:0 2px;cursor:pointer;";
const ICON_STYLE =
  "color:#3b82f6;font-size:10px;vertical-align:super;margin-left:1px;cursor:pointer;user-select:none;pointer-events:none;";

export default class InteractiveTextTool {
  private data: { text: string; annotations: AnnotationRecord[] };
  private wrapper: HTMLElement | null = null;
  private editor: HTMLDivElement | null = null;
  private savedRange: Range | null = null;
  private toolbar: HTMLElement | null = null;
  private _docMouseDownHandler: ((e: MouseEvent) => void) | null = null;

  static get toolbox() {
    return {
      title: "Interactive Text",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>',
    };
  }

  static get isReadOnlySupported() {
    return true;
  }

  constructor({ data }: { data?: InteractiveTextToolData; api: unknown }) {
    this.data = {
      text: data?.text || "",
      annotations: (data?.annotations as AnnotationRecord[]) || [],
    };
  }

  render(): HTMLElement {
    this.wrapper = document.createElement("div");
    this.wrapper.style.cssText =
      "border:1px solid #e2e8f0;border-radius:12px;padding:16px;background:#f8fafc;";

    // Badge
    const badge = document.createElement("div");
    badge.style.cssText =
      "font-size:12px;font-weight:600;color:#3b82f6;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:8px;display:flex;align-items:center;gap:6px;";
    badge.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Interactive Text';
    this.wrapper.appendChild(badge);

    // Hint
    const hint = document.createElement("p");
    hint.textContent = "Type below, then select words to add interactive annotations.";
    hint.style.cssText = "font-size:12px;color:#94a3b8;margin:0 0 8px;";
    this.wrapper.appendChild(hint);

    // Contenteditable editor area
    this.editor = document.createElement("div");
    this.editor.contentEditable = "true";
    this.editor.style.cssText =
      "min-height:80px;padding:10px 12px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;line-height:1.75;outline:none;color:#1e293b;background:white;word-break:break-word;";
    this.editor.setAttribute("data-placeholder", "Type your paragraph here…");

    // Render existing text with visual annotation styles
    if (this.data.text) {
      this.editor.innerHTML = this._applyEditorStyles(this.data.text);
    }

    // Selection detection
    this.editor.addEventListener("mouseup", () => this._onSelectionChange());

    // Stop Editor.js from swallowing backspace/enter
    this.editor.addEventListener("keydown", (e) => {
      e.stopPropagation();
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        document.execCommand("insertLineBreak");
      }
    });

    // Click on existing annotation span → edit dialog
    this.editor.addEventListener("click", (e) => {
      const target = e.target as Element;
      const span = target.closest("[data-annotation-id]");
      if (!span) return;
      const id = span.getAttribute("data-annotation-id")!;
      const ann = this.data.annotations.find((a) => a.id === id);
      if (ann) {
        e.stopPropagation();
        this._hideToolbar();
        this._showAnnotationForm(null, ann);
      }
    });

    // Hide toolbar when clicking outside
    this._docMouseDownHandler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        this.toolbar &&
        !this.toolbar.contains(target) &&
        !this.editor?.contains(target)
      ) {
        this._hideToolbar();
      }
    };
    document.addEventListener("mousedown", this._docMouseDownHandler);

    this.wrapper.appendChild(this.editor);

    // Placeholder styling via pseudo CSS workaround
    const style = document.createElement("style");
    style.textContent = `[data-placeholder]:empty:before{content:attr(data-placeholder);color:#94a3b8;pointer-events:none;}`;
    this.wrapper.appendChild(style);

    return this.wrapper;
  }

  /** Add visual styles + magnifying glass icons to annotation spans for the editor view */
  private _applyEditorStyles(html: string): string {
    if (typeof window === "undefined") return html;
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, "text/html");

    this.data.annotations.forEach((ann) => {
      const span = doc.querySelector(
        `[data-annotation-id="${ann.id}"]`
      ) as HTMLElement | null;
      if (!span) return;

      span.style.cssText = ANNOTATION_STYLE;
      span.title = `Click to edit: ${ann.modal_title || "annotation"}`;

      // Add icon only if not already present
      if (!span.querySelector("[data-annotation-icon]")) {
        const icon = doc.createElement("span");
        icon.setAttribute("data-annotation-icon", ann.id);
        icon.setAttribute("contenteditable", "false");
        icon.style.cssText = ICON_STYLE;
        icon.textContent = "🔍";
        span.appendChild(icon);
      }
    });

    return doc.body.innerHTML;
  }

  private _onSelectionChange(): void {
    // Slight delay so browser finalises the selection
    setTimeout(() => {
      const sel = window.getSelection();
      if (!sel || sel.rangeCount === 0 || sel.isCollapsed) {
        this._hideToolbar();
        return;
      }

      const range = sel.getRangeAt(0);
      if (!this.editor?.contains(range.commonAncestorContainer)) {
        this._hideToolbar();
        return;
      }

      // Don't offer annotation if selection is inside an existing one
      const ancestor = range.commonAncestorContainer;
      const inExisting =
        ancestor.nodeType === Node.ELEMENT_NODE
          ? (ancestor as Element).closest("[data-annotation-id]")
          : (ancestor as Element).parentElement?.closest(
              "[data-annotation-id]"
            );
      if (inExisting) {
        this._hideToolbar();
        return;
      }

      const rect = range.getBoundingClientRect();
      if (rect.width === 0) {
        this._hideToolbar();
        return;
      }

      this.savedRange = range.cloneRange();
      this._showToolbar(rect);
    }, 10);
  }

  private _showToolbar(rect: DOMRect): void {
    this._hideToolbar();

    const toolbar = document.createElement("div");
    const topPos = Math.max(8, rect.top - 44);
    toolbar.style.cssText = `
      position:fixed;top:${topPos}px;left:${rect.left}px;
      background:#1e293b;color:white;
      padding:6px 14px;border-radius:8px;font-size:12px;font-weight:600;
      cursor:pointer;z-index:99999;display:flex;align-items:center;gap:6px;
      box-shadow:0 4px 16px rgba(0,0,0,0.35);white-space:nowrap;
      animation:ia-fade-in 0.1s ease;
    `;
    toolbar.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg> Add Interactive';

    toolbar.addEventListener("mousedown", (e) => {
      e.preventDefault();
      this._hideToolbar();
      if (this.savedRange) this._showAnnotationForm(this.savedRange);
    });

    document.body.appendChild(toolbar);
    this.toolbar = toolbar;
  }

  private _hideToolbar(): void {
    if (this.toolbar) {
      this.toolbar.remove();
      this.toolbar = null;
    }
  }

  private _insertAnnotationSpan(range: Range, ann: AnnotationRecord): void {
    const span = document.createElement("span");
    span.setAttribute("data-annotation-id", ann.id);
    span.style.cssText = ANNOTATION_STYLE;
    span.title = `Click to edit: ${ann.modal_title}`;

    // Wrap the selected content
    try {
      const fragment = range.extractContents();
      span.appendChild(fragment);
    } catch {
      // surroundContents can fail on cross-element selections; fall back
      const selectedText = range.toString();
      span.textContent = selectedText;
      range.deleteContents();
    }

    // Magnifying glass icon (non-editable)
    const icon = document.createElement("span");
    icon.setAttribute("data-annotation-icon", ann.id);
    icon.setAttribute("contenteditable", "false");
    icon.style.cssText = ICON_STYLE;
    icon.textContent = "🔍";
    span.appendChild(icon);

    range.insertNode(span);

    // Move cursor after the span
    const newRange = document.createRange();
    newRange.setStartAfter(span);
    newRange.collapse(true);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(newRange);

    this.data.annotations.push(ann);
  }

  private _showAnnotationForm(
    range: Range | null,
    existing?: AnnotationRecord
  ): void {
    const vals: AnnotationRecord = {
      id: existing?.id || _genId(),
      type: existing?.type || "text",
      modal_title: existing?.modal_title || "",
      modal_content: existing?.modal_content || "",
      image_url: existing?.image_url || "",
      image_caption: existing?.image_caption || "",
      audio_url: existing?.audio_url || "",
      video_url: existing?.video_url || "",
      youtube_source: existing?.youtube_source || "",
    };

    const { overlay, form } = _createOverlay(
      existing ? "Edit Annotation" : "Add Annotation"
    );

    // ── Type selector ───────────────────────────────────────────────────────
    const typeSelectorLabel = document.createElement("p");
    typeSelectorLabel.textContent = "Content type";
    typeSelectorLabel.style.cssText =
      "font-size:12px;font-weight:600;color:#374151;margin:12px 0 6px;";
    form.appendChild(typeSelectorLabel);

    const typeRow = document.createElement("div");
    typeRow.style.cssText = "display:flex;gap:6px;flex-wrap:wrap;";
    form.appendChild(typeRow);

    const fieldArea = document.createElement("div");
    form.appendChild(fieldArea);

    type TypeDef = [AnnotationType, string];
    const typeDefs: TypeDef[] = [
      ["text", "📝 Text"],
      ["image", "🖼 Image"],
      ["audio", "🎵 Audio"],
      ["video", "🎬 Video"],
      ["youtube", "▶ YouTube"],
    ];

    const renderTypeButtons = () => {
      typeRow.innerHTML = "";
      typeDefs.forEach(([t, label]) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.textContent = label;
        const active = vals.type === t;
        btn.style.cssText = `padding:5px 12px;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;border:2px solid ${active ? "#3b82f6" : "#e2e8f0"};background:${active ? "#eff6ff" : "white"};color:${active ? "#1d4ed8" : "#374151"};`;
        btn.addEventListener("click", () => {
          vals.type = t;
          renderTypeButtons();
          renderFields();
        });
        typeRow.appendChild(btn);
      });
    };

    const renderFields = () => {
      fieldArea.innerHTML = "";

      _label(fieldArea, "Annotation title (shown in modal header)");
      const titleInput = _input(
        fieldArea,
        "e.g. What is photosynthesis?",
        vals.modal_title
      );
      titleInput.addEventListener("input", () => {
        vals.modal_title = titleInput.value;
      });

      switch (vals.type) {
        case "text": {
          _label(fieldArea, "Explanation");
          _hint(fieldArea, "HTML is supported (bold, links, etc.).");
          const ta = _textarea(
            fieldArea,
            "<p>Explanation…</p>",
            vals.modal_content || ""
          );
          ta.addEventListener("input", () => {
            vals.modal_content = ta.value;
          });
          break;
        }
        case "image": {
          _label(fieldArea, "Image URL");
          const imgIn = _input(
            fieldArea,
            "https://example.com/image.jpg",
            vals.image_url || ""
          );
          imgIn.addEventListener("input", () => {
            vals.image_url = imgIn.value;
          });
          _label(fieldArea, "Caption (optional)");
          const capIn = _input(fieldArea, "Describe the image", vals.image_caption || "");
          capIn.addEventListener("input", () => {
            vals.image_caption = capIn.value;
          });
          break;
        }
        case "audio": {
          _label(fieldArea, "Audio URL");
          _hint(fieldArea, "Upload via the Media Library first, then paste the URL.");
          const audIn = _input(
            fieldArea,
            "https://example.com/audio.mp3",
            vals.audio_url || ""
          );
          audIn.addEventListener("input", () => {
            vals.audio_url = audIn.value;
          });
          break;
        }
        case "video": {
          _label(fieldArea, "Video URL");
          _hint(fieldArea, "Upload via the Media Library first, then paste the URL.");
          const vidIn = _input(
            fieldArea,
            "https://example.com/video.mp4",
            vals.video_url || ""
          );
          vidIn.addEventListener("input", () => {
            vals.video_url = vidIn.value;
          });
          break;
        }
        case "youtube": {
          _label(fieldArea, "YouTube URL");
          const ytIn = _input(
            fieldArea,
            "https://www.youtube.com/watch?v=...",
            vals.youtube_source || ""
          );
          ytIn.addEventListener("input", () => {
            vals.youtube_source = ytIn.value;
          });
          break;
        }
      }
    };

    renderTypeButtons();
    renderFields();

    // ── Bottom buttons ──────────────────────────────────────────────────────
    const btnRow = document.createElement("div");
    btnRow.style.cssText =
      "display:flex;align-items:center;justify-content:space-between;margin-top:20px;gap:8px;";

    const leftSide = document.createElement("div");
    if (existing) {
      const delBtn = _btn("🗑 Delete", "#fee2e2", "#dc2626", "1px solid #fecaca");
      delBtn.style.padding = "8px 14px";
      delBtn.addEventListener("click", () => {
        // Remove span from DOM, leaving its text content
        if (this.editor) {
          const span = this.editor.querySelector(
            `[data-annotation-id="${existing.id}"]`
          );
          if (span && span.parentNode) {
            const frag = document.createDocumentFragment();
            span.childNodes.forEach((child) => {
              if (
                !(child as Element).getAttribute?.(
                  "data-annotation-icon"
                )
              ) {
                frag.appendChild(child.cloneNode(true));
              }
            });
            span.parentNode.replaceChild(frag, span);
          }
        }
        this.data.annotations = this.data.annotations.filter(
          (a) => a.id !== existing.id
        );
        overlay.remove();
      });
      leftSide.appendChild(delBtn);
    }
    btnRow.appendChild(leftSide);

    const rightSide = document.createElement("div");
    rightSide.style.cssText = "display:flex;gap:8px;";

    const cancelBtn = _btn("Cancel", "#f1f5f9", "#374151", "1px solid #e2e8f0");
    cancelBtn.style.padding = "8px 16px";
    cancelBtn.addEventListener("click", () => overlay.remove());
    rightSide.appendChild(cancelBtn);

    const saveBtn = _btn(
      existing ? "Save Changes" : "Add Annotation",
      "#3b82f6",
      "white"
    );
    saveBtn.style.padding = "8px 16px";
    saveBtn.addEventListener("click", () => {
      if (!vals.modal_title.trim()) {
        alert("Please enter an annotation title.");
        return;
      }
      const ann: AnnotationRecord = { ...vals };

      if (existing) {
        const idx = this.data.annotations.findIndex(
          (a) => a.id === existing.id
        );
        if (idx !== -1) this.data.annotations[idx] = ann;
        // Refresh title tooltip on the span in DOM
        if (this.editor) {
          const span = this.editor.querySelector(
            `[data-annotation-id="${existing.id}"]`
          ) as HTMLElement | null;
          if (span) span.title = `Click to edit: ${ann.modal_title}`;
        }
      } else if (range) {
        this._insertAnnotationSpan(range, ann);
      }

      overlay.remove();
    });
    rightSide.appendChild(saveBtn);
    btnRow.appendChild(rightSide);
    form.appendChild(btnRow);

    document.body.appendChild(overlay);
  }

  save(): { text: string; annotations: AnnotationRecord[] } {
    if (!this.editor) {
      return { text: this.data.text, annotations: this.data.annotations };
    }

    const clone = this.editor.cloneNode(true) as HTMLElement;

    // Strip editor-only icon spans
    clone
      .querySelectorAll("[data-annotation-icon]")
      .forEach((el) => el.remove());

    // Clean editor-only attrs from annotation spans
    clone.querySelectorAll("[data-annotation-id]").forEach((el) => {
      (el as HTMLElement).removeAttribute("style");
      (el as HTMLElement).removeAttribute("title");
    });

    // Prune orphaned annotations (span was deleted from the text)
    const presentIds = new Set(
      Array.from(clone.querySelectorAll("[data-annotation-id]")).map((el) =>
        el.getAttribute("data-annotation-id")!
      )
    );
    const annotations = this.data.annotations.filter((a) =>
      presentIds.has(a.id)
    );

    return { text: clone.innerHTML, annotations };
  }

  validate(savedData: { text?: string }): boolean {
    return !!savedData.text?.trim();
  }

  // Cleanup when block is destroyed
  destroy(): void {
    if (this._docMouseDownHandler) {
      document.removeEventListener("mousedown", this._docMouseDownHandler);
    }
    this._hideToolbar();
  }
}

// ─── Shared DOM helpers ────────────────────────────────────────────────────────

function _genId(): string {
  return Math.random().toString(36).slice(2, 10);
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

function _input(
  parent: HTMLElement,
  placeholder: string,
  value = ""
): HTMLInputElement {
  const el = document.createElement("input");
  el.type = "text";
  el.placeholder = placeholder;
  el.value = value;
  el.style.cssText =
    "width:100%;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;outline:none;box-sizing:border-box;color:#1e293b;";
  parent.appendChild(el);
  return el;
}

function _textarea(
  parent: HTMLElement,
  placeholder: string,
  value = ""
): HTMLTextAreaElement {
  const el = document.createElement("textarea");
  el.placeholder = placeholder;
  el.value = value;
  el.rows = 4;
  el.style.cssText =
    "width:100%;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;resize:vertical;outline:none;box-sizing:border-box;font-family:inherit;color:#1e293b;";
  parent.appendChild(el);
  return el;
}

function _btn(
  text: string,
  bg: string,
  color: string,
  border = "none"
): HTMLButtonElement {
  const el = document.createElement("button");
  el.textContent = text;
  el.type = "button";
  el.style.cssText = `padding:4px 12px;background:${bg};color:${color};border:${border};border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;flex-shrink:0;white-space:nowrap;`;
  return el;
}

function _createOverlay(
  title: string
): { overlay: HTMLElement; form: HTMLElement } {
  const overlay = document.createElement("div");
  overlay.style.cssText =
    "position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;";
  const form = document.createElement("div");
  form.style.cssText =
    "background:white;border-radius:14px;padding:24px;width:480px;max-width:100%;max-height:90vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.3);";
  const h3 = document.createElement("h3");
  h3.textContent = title;
  h3.style.cssText =
    "margin:0 0 4px;font-size:16px;font-weight:700;color:#111827;";
  form.appendChild(h3);
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });
  overlay.appendChild(form);
  return { overlay, form };
}


interface InternalAnnotation {
  id: string;
  phrase: string;
  modal_title: string;
  modal_content: string;
}

interface AnnotationData {
  start: number;
  end: number;
  modal_title: string;
  modal_content: string;
}

interface InteractiveTextToolData {
  text: string;
  annotations: AnnotationData[];
}

export default class InteractiveTextTool {
  private data: { text: string; internalAnnotations: InternalAnnotation[] };
  private wrapper: HTMLElement | null = null;

  static get toolbox() {
    return {
      title: "Interactive Text",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>',
    };
  }

  static get isReadOnlySupported() {
    return true;
  }

  constructor({ data }: { data?: InteractiveTextToolData; api: unknown }) {
    const internalAnnotations: InternalAnnotation[] = [];
    if (data?.annotations && data?.text) {
      for (const ann of data.annotations) {
        internalAnnotations.push({
          id: Math.random().toString(36).slice(2),
          phrase: data.text.slice(ann.start, ann.end),
          modal_title: ann.modal_title,
          modal_content: ann.modal_content,
        });
      }
    }
    this.data = { text: data?.text || "", internalAnnotations };
  }

  render(): HTMLElement {
    this.wrapper = document.createElement("div");
    this.wrapper.style.cssText =
      "border:1px solid #e2e8f0;border-radius:12px;padding:16px;background:#f8fafc;";
    this._renderMain();
    return this.wrapper;
  }

  private _renderMain(): void {
    if (!this.wrapper) return;
    this.wrapper.innerHTML = "";

    // Title
    const title = document.createElement("div");
    title.style.cssText =
      "font-size:12px;font-weight:600;color:#3b82f6;text-transform:uppercase;letter-spacing:0.05em;margin-bottom:12px;display:flex;align-items:center;gap:6px;";
    title.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> Interactive Text';
    this.wrapper.appendChild(title);

    // Text area
    _label(this.wrapper, "Paragraph text");
    const textarea = document.createElement("textarea");
    textarea.value = this.data.text;
    textarea.placeholder = "Enter the paragraph text here…";
    textarea.rows = 4;
    textarea.style.cssText =
      "width:100%;padding:8px 10px;border:1px solid #e2e8f0;border-radius:8px;font-size:14px;resize:vertical;outline:none;box-sizing:border-box;font-family:inherit;background:white;color:#1e293b;";
    textarea.addEventListener("input", () => {
      this.data.text = textarea.value;
    });
    this.wrapper.appendChild(textarea);

    // Annotations header
    const annHeader = document.createElement("div");
    annHeader.style.cssText =
      "display:flex;align-items:center;justify-content:space-between;margin-top:16px;margin-bottom:8px;";
    const annLabel = document.createElement("span");
    annLabel.style.cssText = "font-size:12px;font-weight:600;color:#374151;";
    annLabel.textContent = `Clickable Annotations (${this.data.internalAnnotations.length})`;
    annHeader.appendChild(annLabel);

    const addBtn = _btn("+ Add Annotation", "#3b82f6", "white");
    addBtn.addEventListener("click", () => this._showAnnotationForm());
    annHeader.appendChild(addBtn);
    this.wrapper.appendChild(annHeader);

    // Annotations list
    const annList = document.createElement("div");
    annList.style.cssText = "display:flex;flex-direction:column;gap:6px;";
    if (this.data.internalAnnotations.length === 0) {
      const empty = document.createElement("div");
      empty.style.cssText =
        "text-align:center;padding:12px;color:#94a3b8;font-size:13px;border:1px dashed #e2e8f0;border-radius:8px;";
      empty.textContent = "No annotations yet. Add one to make words clickable.";
      annList.appendChild(empty);
    } else {
      this.data.internalAnnotations.forEach((ann) => {
        annList.appendChild(this._renderAnnotationRow(ann));
      });
    }
    this.wrapper.appendChild(annList);
  }

  private _renderAnnotationRow(ann: InternalAnnotation): HTMLElement {
    const row = document.createElement("div");
    row.style.cssText =
      "display:flex;align-items:center;gap:8px;padding:8px 12px;background:white;border:1px solid #e2e8f0;border-radius:8px;";

    const info = document.createElement("div");
    info.style.cssText = "flex:1;min-width:0;";
    info.innerHTML = `
      <span style="font-size:13px;font-weight:500;color:#1e293b;background:#eff6ff;color:#1d4ed8;padding:1px 6px;border-radius:4px;font-family:monospace;">"${_esc(ann.phrase)}"</span>
      <span style="display:block;font-size:11px;color:#64748b;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${_esc(ann.modal_title) || "(no modal title)"}</span>
    `;
    row.appendChild(info);

    const editBtn = _btn("Edit", "#f1f5f9", "#374151", "1px solid #e2e8f0");
    editBtn.addEventListener("click", () => this._showAnnotationForm(ann));
    row.appendChild(editBtn);

    const delBtn = _btn("✕", "#fee2e2", "#dc2626");
    delBtn.addEventListener("click", () => {
      this.data.internalAnnotations = this.data.internalAnnotations.filter(
        (a) => a.id !== ann.id
      );
      this._renderMain();
    });
    row.appendChild(delBtn);
    return row;
  }

  private _showAnnotationForm(existing?: InternalAnnotation): void {
    const values: Record<string, string> = {
      phrase: existing?.phrase || "",
      modal_title: existing?.modal_title || "",
      modal_content: existing?.modal_content || "",
    };

    const { overlay, form } = _createOverlay(existing ? "Edit Annotation" : "Add Annotation");

    _label(form, "Phrase to annotate");
    _hint(form, "Type the exact word or phrase from your text that readers can click.");
    const phraseInput = _input(form, "e.g. photosynthesis", values.phrase);
    phraseInput.addEventListener("input", () => { values.phrase = phraseInput.value; });

    _label(form, "Modal title");
    const titleInput = _input(form, "e.g. What is photosynthesis?", values.modal_title);
    titleInput.addEventListener("input", () => { values.modal_title = titleInput.value; });

    _label(form, "Modal content");
    _hint(form, "HTML is supported.");
    const contentArea = _textarea(form, "<p>Explanation goes here…</p>", values.modal_content);
    contentArea.addEventListener("input", () => { values.modal_content = contentArea.value; });

    const { cancelBtn, saveBtn } = _formButtons(form, existing ? "Save Changes" : "Add Annotation");
    cancelBtn.addEventListener("click", () => overlay.remove());
    saveBtn.addEventListener("click", () => {
      if (!values.phrase.trim()) {
        alert("Please enter the phrase to annotate.");
        return;
      }
      if (existing) {
        const idx = this.data.internalAnnotations.findIndex((a) => a.id === existing.id);
        if (idx !== -1) {
          this.data.internalAnnotations[idx] = {
            ...existing,
            phrase: values.phrase,
            modal_title: values.modal_title,
            modal_content: values.modal_content,
          };
        }
      } else {
        this.data.internalAnnotations.push({
          id: Math.random().toString(36).slice(2),
          phrase: values.phrase,
          modal_title: values.modal_title,
          modal_content: values.modal_content,
        });
      }
      overlay.remove();
      this._renderMain();
    });

    document.body.appendChild(overlay);
  }

  save(): InteractiveTextToolData {
    const text = this.data.text;
    const annotations: AnnotationData[] = [];
    for (const ann of this.data.internalAnnotations) {
      const start = text.indexOf(ann.phrase);
      if (start !== -1) {
        annotations.push({
          start,
          end: start + ann.phrase.length,
          modal_title: ann.modal_title,
          modal_content: ann.modal_content,
        });
      }
    }
    return { text, annotations };
  }

  validate(savedData: InteractiveTextToolData): boolean {
    return !!savedData.text?.trim();
  }
}

// ─── Shared DOM helpers ────────────────────────────────────────────────────────

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

function _btn(
  text: string,
  bg: string,
  color: string,
  border = "none"
): HTMLButtonElement {
  const el = document.createElement("button");
  el.textContent = text;
  el.type = "button";
  el.style.cssText = `padding:4px 12px;background:${bg};color:${color};border:${border};border-radius:6px;cursor:pointer;font-size:12px;font-weight:500;flex-shrink:0;white-space:nowrap;`;
  return el;
}

function _createOverlay(
  title: string
): { overlay: HTMLElement; form: HTMLElement } {
  const overlay = document.createElement("div");
  overlay.style.cssText =
    "position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;";

  const form = document.createElement("div");
  form.style.cssText =
    "background:white;border-radius:14px;padding:24px;width:480px;max-width:100%;max-height:90vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.25);";

  const h3 = document.createElement("h3");
  h3.textContent = title;
  h3.style.cssText = "margin:0 0 4px;font-size:16px;font-weight:600;color:#111827;";
  form.appendChild(h3);

  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) overlay.remove();
  });
  overlay.appendChild(form);
  return { overlay, form };
}

function _formButtons(
  form: HTMLElement,
  saveLabel: string
): { cancelBtn: HTMLButtonElement; saveBtn: HTMLButtonElement } {
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
