/**
 * Editor.js Inline Tool – Add Interactive Annotation
 *
 * Appears in the inline toolbar (text selection popover). Lets the author
 * select text in any paragraph / list / quote block and attach an interactive
 * annotation (text, image, audio, video, YouTube) that readers can click to
 * open a modal.
 *
 * Annotation metadata is stored as JSON in a `data-annotation` attribute on
 * the wrapping `<span>`, so each paragraph block is self-contained.
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

const ANNOTATION_STYLE =
  "background:rgba(59,130,246,0.12);color:#1d4ed8;border-bottom:2px solid #3b82f6;border-radius:3px;padding:0 2px;cursor:pointer;";
const ICON_STYLE =
  "color:#3b82f6;font-size:10px;vertical-align:super;margin-left:1px;cursor:pointer;user-select:none;pointer-events:none;";

function genId(): string {
  return Math.random().toString(36).slice(2, 10);
}

export default class InteractiveInlineTool {
  private button: HTMLButtonElement | null = null;
  private _state = false;
  private existingSpan: HTMLElement | null = null;

  /* ── Editor.js Inline Tool API ───────────────────────────────────────── */

  static get isInline() {
    return true;
  }

  static get title() {
    return "Add Interactive";
  }

  /**
   * Tell Editor.js to keep <span> elements with these data-attributes when
   * the block content is sanitised on save.
   */
  static get sanitize() {
    return {
      span: {
        class: true,
        style: true,
        title: true,
        contenteditable: true,
        "data-annotation-id": true,
        "data-annotation": true,
        "data-annotation-icon": true,
      },
    };
  }

  render(): HTMLButtonElement {
    this.button = document.createElement("button");
    this.button.type = "button";
    this.button.classList.add("ce-inline-tool");
    this.button.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>';
    return this.button;
  }

  /**
   * Called when the user clicks the toolbar button.
   * - If the cursor is already inside an annotation → open the edit dialog.
   * - Otherwise → wrap the selected text in a temporary span and open the
   *   "Add Annotation" dialog.
   */
  surround(range: Range): void {
    if (this._state && this.existingSpan) {
      const dataStr = this.existingSpan.getAttribute("data-annotation");
      if (dataStr) {
        try {
          const ann = JSON.parse(dataStr) as AnnotationRecord;
          this._showAnnotationForm(ann, this.existingSpan, false);
          return;
        } catch {
          /* corrupted – fall through to create fresh */
        }
      }
    }

    if (!range || range.collapsed) return;

    const annId = genId();
    const span = document.createElement("span");
    span.setAttribute("data-annotation-id", annId);
    span.style.cssText = ANNOTATION_STYLE;

    try {
      range.surroundContents(span);
    } catch {
      const text = range.toString();
      range.deleteContents();
      span.textContent = text;
      range.insertNode(span);
    }

    // Show form; mark this as a *new* annotation so Cancel can undo the wrap.
    const freshAnn: AnnotationRecord = {
      id: annId,
      type: "text",
      modal_title: "",
    };
    this._showAnnotationForm(freshAnn, span, true);
  }

  /**
   * Called on every selection change so we can highlight the button when the
   * caret is inside an existing annotation.
   */
  checkState(selection: Selection): boolean {
    const anchor = selection.anchorNode;
    if (!anchor) {
      this._state = false;
      this.existingSpan = null;
      return false;
    }

    const el =
      anchor.nodeType === Node.ELEMENT_NODE
        ? (anchor as Element)
        : anchor.parentElement;

    const annotationSpan = el?.closest(
      "[data-annotation-id]"
    ) as HTMLElement | null;

    this._state = !!annotationSpan;
    this.existingSpan = annotationSpan;

    if (this.button) {
      this.button.classList.toggle("ce-inline-tool--active", this._state);
    }

    return this._state;
  }

  /* ── Annotation form dialog ──────────────────────────────────────────── */

  private _showAnnotationForm(
    vals: AnnotationRecord,
    span: HTMLElement,
    isNew: boolean
  ): void {
    const working = { ...vals };

    const overlay = document.createElement("div");
    overlay.style.cssText =
      "position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:9999;display:flex;align-items:center;justify-content:center;padding:16px;";

    const form = document.createElement("div");
    form.style.cssText =
      "background:white;border-radius:14px;padding:24px;width:480px;max-width:100%;max-height:90vh;overflow-y:auto;box-shadow:0 20px 60px rgba(0,0,0,0.3);";

    const h3 = document.createElement("h3");
    h3.textContent = isNew ? "Add Annotation" : "Edit Annotation";
    h3.style.cssText =
      "margin:0 0 4px;font-size:16px;font-weight:700;color:#111827;";
    form.appendChild(h3);

    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) {
        if (isNew) this._unwrapSpan(span);
        overlay.remove();
      }
    });
    overlay.appendChild(form);

    // ── Type selector ─────────────────────────────────────────────────────
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
        const active = working.type === t;
        btn.style.cssText = `padding:5px 12px;border-radius:6px;font-size:12px;font-weight:500;cursor:pointer;border:2px solid ${active ? "#3b82f6" : "#e2e8f0"};background:${active ? "#eff6ff" : "white"};color:${active ? "#1d4ed8" : "#374151"};`;
        btn.addEventListener("click", () => {
          working.type = t;
          renderTypeButtons();
          renderFields();
        });
        typeRow.appendChild(btn);
      });
    };

    const renderFields = () => {
      fieldArea.innerHTML = "";

      mkLabel(fieldArea, "Annotation title (shown in modal header)");
      const titleInput = mkInput(
        fieldArea,
        "e.g. What is photosynthesis?",
        working.modal_title
      );
      titleInput.addEventListener("input", () => {
        working.modal_title = titleInput.value;
      });

      switch (working.type) {
        case "text": {
          mkLabel(fieldArea, "Explanation");
          mkHint(fieldArea, "HTML is supported (bold, links, etc.).");
          const ta = mkTextarea(
            fieldArea,
            "<p>Explanation…</p>",
            working.modal_content || ""
          );
          ta.addEventListener("input", () => {
            working.modal_content = ta.value;
          });
          break;
        }
        case "image": {
          mkLabel(fieldArea, "Image URL");
          const imgIn = mkInput(
            fieldArea,
            "https://example.com/image.jpg",
            working.image_url || ""
          );
          imgIn.addEventListener("input", () => {
            working.image_url = imgIn.value;
          });
          mkLabel(fieldArea, "Caption (optional)");
          const capIn = mkInput(
            fieldArea,
            "Describe the image",
            working.image_caption || ""
          );
          capIn.addEventListener("input", () => {
            working.image_caption = capIn.value;
          });
          break;
        }
        case "audio": {
          mkLabel(fieldArea, "Audio URL");
          mkHint(
            fieldArea,
            "Upload via the Media Library first, then paste the URL."
          );
          const audIn = mkInput(
            fieldArea,
            "https://example.com/audio.mp3",
            working.audio_url || ""
          );
          audIn.addEventListener("input", () => {
            working.audio_url = audIn.value;
          });
          break;
        }
        case "video": {
          mkLabel(fieldArea, "Video URL");
          mkHint(
            fieldArea,
            "Upload via the Media Library first, then paste the URL."
          );
          const vidIn = mkInput(
            fieldArea,
            "https://example.com/video.mp4",
            working.video_url || ""
          );
          vidIn.addEventListener("input", () => {
            working.video_url = vidIn.value;
          });
          break;
        }
        case "youtube": {
          mkLabel(fieldArea, "YouTube URL");
          const ytIn = mkInput(
            fieldArea,
            "https://www.youtube.com/watch?v=...",
            working.youtube_source || ""
          );
          ytIn.addEventListener("input", () => {
            working.youtube_source = ytIn.value;
          });
          break;
        }
      }
    };

    renderTypeButtons();
    renderFields();

    // ── Bottom buttons ────────────────────────────────────────────────────
    const btnRow = document.createElement("div");
    btnRow.style.cssText =
      "display:flex;align-items:center;justify-content:space-between;margin-top:20px;gap:8px;";

    const leftSide = document.createElement("div");
    if (!isNew) {
      const delBtn = mkBtn(
        "🗑 Delete",
        "#fee2e2",
        "#dc2626",
        "1px solid #fecaca"
      );
      delBtn.style.padding = "8px 14px";
      delBtn.addEventListener("click", () => {
        this._unwrapSpan(span);
        overlay.remove();
      });
      leftSide.appendChild(delBtn);
    }
    btnRow.appendChild(leftSide);

    const rightSide = document.createElement("div");
    rightSide.style.cssText = "display:flex;gap:8px;";

    const cancelBtn = mkBtn("Cancel", "#f1f5f9", "#374151", "1px solid #e2e8f0");
    cancelBtn.style.padding = "8px 16px";
    cancelBtn.addEventListener("click", () => {
      if (isNew) this._unwrapSpan(span);
      overlay.remove();
    });
    rightSide.appendChild(cancelBtn);

    const saveBtn = mkBtn(
      isNew ? "Add Annotation" : "Save Changes",
      "#3b82f6",
      "white"
    );
    saveBtn.style.padding = "8px 16px";
    saveBtn.addEventListener("click", () => {
      if (!working.modal_title.trim()) {
        alert("Please enter an annotation title.");
        return;
      }

      // Persist annotation data on the span
      span.setAttribute("data-annotation", JSON.stringify(working));
      span.setAttribute("data-annotation-id", working.id);
      span.style.cssText = ANNOTATION_STYLE;
      span.title = `Click to edit: ${working.modal_title}`;

      // Add icon if not already present
      if (!span.querySelector("[data-annotation-icon]")) {
        const icon = document.createElement("span");
        icon.setAttribute("data-annotation-icon", working.id);
        icon.setAttribute("contenteditable", "false");
        icon.style.cssText = ICON_STYLE;
        icon.textContent = "🔍";
        span.appendChild(icon);
      }

      overlay.remove();
    });
    rightSide.appendChild(saveBtn);
    btnRow.appendChild(rightSide);
    form.appendChild(btnRow);

    document.body.appendChild(overlay);
  }

  /**
   * Remove the annotation span, keeping the text content in place.
   */
  private _unwrapSpan(span: HTMLElement): void {
    const parent = span.parentNode;
    if (!parent) return;
    const frag = document.createDocumentFragment();
    while (span.firstChild) {
      const child = span.firstChild;
      // Skip the icon span
      if (
        child.nodeType === Node.ELEMENT_NODE &&
        (child as Element).hasAttribute("data-annotation-icon")
      ) {
        span.removeChild(child);
        continue;
      }
      frag.appendChild(child);
    }
    parent.replaceChild(frag, span);
  }
}

/* ── Tiny DOM helpers (local to this module) ────────────────────────────── */

function mkLabel(parent: HTMLElement, text: string): void {
  const el = document.createElement("label");
  el.textContent = text;
  el.style.cssText =
    "display:block;font-size:12px;font-weight:500;color:#6b7280;margin-bottom:4px;margin-top:12px;";
  parent.appendChild(el);
}

function mkHint(parent: HTMLElement, text: string): void {
  const el = document.createElement("p");
  el.textContent = text;
  el.style.cssText = "font-size:11px;color:#94a3b8;margin:0 0 4px;";
  parent.appendChild(el);
}

function mkInput(
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

function mkTextarea(
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

function mkBtn(
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
