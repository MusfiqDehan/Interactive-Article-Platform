/**
 * Custom Editor.js Audio Block Tool
 * Supports file upload and URL input for audio content.
 */

interface AudioToolData {
  file?: { url: string };
  url?: string;
  caption?: string;
}

interface AudioToolConfig {
  endpoints?: { byFile?: string };
  additionalRequestHeaders?: Record<string, string>;
  field?: string;
}

interface AudioToolConstructorParams {
  data?: AudioToolData;
  config?: AudioToolConfig;
  api: { styles: { block: string } };
}

export default class AudioTool {
  private data: AudioToolData;
  private config: AudioToolConfig;
  private wrapper: HTMLElement | null = null;

  static get toolbox() {
    return {
      title: "Audio",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
    };
  }

  static get isReadOnlySupported() {
    return true;
  }

  constructor({ data, config }: AudioToolConstructorParams) {
    this.data = data || {};
    this.config = config || {};
  }

  render(): HTMLElement {
    this.wrapper = document.createElement("div");
    this.wrapper.style.cssText =
      "border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; background: #f8fafc;";

    const audioUrl = this.data.file?.url || this.data.url || "";

    if (audioUrl) {
      this._renderAudioPlayer(audioUrl);
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
      "display: flex; flex-direction: column; align-items: center; gap: 12px; padding: 20px;";

    // Icon
    const icon = document.createElement("div");
    icon.innerHTML =
      '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>';
    container.appendChild(icon);

    // Upload button
    const uploadBtn = document.createElement("button");
    uploadBtn.textContent = "Upload Audio File";
    uploadBtn.type = "button";
    uploadBtn.style.cssText =
      "padding: 8px 20px; background: #3b82f6; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500;";
    uploadBtn.addEventListener("click", () => this._selectFile());
    container.appendChild(uploadBtn);

    // Or divider
    const divider = document.createElement("div");
    divider.textContent = "or paste a URL";
    divider.style.cssText = "color: #94a3b8; font-size: 13px;";
    container.appendChild(divider);

    // URL input
    const urlInput = document.createElement("input");
    urlInput.type = "url";
    urlInput.placeholder = "https://example.com/audio.mp3";
    urlInput.style.cssText =
      "width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px; outline: none; box-sizing: border-box;";
    urlInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const url = urlInput.value.trim();
        if (url) {
          this.data = { url, caption: this.data.caption || "" };
          this._renderAudioPlayer(url);
        }
      }
    });
    container.appendChild(urlInput);

    this.wrapper.appendChild(container);
  }

  private _renderAudioPlayer(url: string): void {
    if (!this.wrapper) return;

    this.wrapper.innerHTML = "";

    const audio = document.createElement("audio");
    audio.src = url;
    audio.controls = true;
    audio.preload = "metadata";
    audio.style.cssText = "width: 100%; margin-bottom: 8px;";
    this.wrapper.appendChild(audio);

    // Caption input
    const caption = document.createElement("input");
    caption.type = "text";
    caption.placeholder = "Add a caption (optional)";
    caption.value = this.data.caption || "";
    caption.style.cssText =
      "width: 100%; padding: 6px 8px; border: none; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b; outline: none; background: transparent; box-sizing: border-box;";
    caption.addEventListener("input", () => {
      this.data.caption = caption.value;
    });
    this.wrapper.appendChild(caption);

    // Remove button
    const removeBtn = document.createElement("button");
    removeBtn.textContent = "✕ Remove";
    removeBtn.type = "button";
    removeBtn.style.cssText =
      "position: absolute; top: 8px; right: 8px; background: #ef4444; color: white; border: none; border-radius: 4px; padding: 2px 8px; font-size: 12px; cursor: pointer;";
    removeBtn.addEventListener("click", () => {
      this.data = { caption: this.data.caption || "" };
      this._renderUploadUI();
    });
    this.wrapper.style.position = "relative";
    this.wrapper.appendChild(removeBtn);
  }

  private _selectFile(): void {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "audio/*";
    input.addEventListener("change", () => {
      const file = input.files?.[0];
      if (file) {
        this._uploadFile(file);
      }
    });
    input.click();
  }

  private async _uploadFile(file: File): Promise<void> {
    const endpoint = this.config.endpoints?.byFile;
    if (!endpoint) {
      console.error("AudioTool: No upload endpoint configured");
      return;
    }

    const formData = new FormData();
    formData.append(this.config.field || "file", file);

    // Show uploading state
    if (this.wrapper) {
      this.wrapper.innerHTML =
        '<div style="text-align:center;padding:20px;color:#94a3b8;">Uploading audio…</div>';
    }

    try {
      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
        headers: this.config.additionalRequestHeaders || {},
      });

      const result = await response.json();

      if (result.success === 1 && result.file?.url) {
        this.data = {
          file: { url: result.file.url },
          caption: this.data.caption || "",
        };
        this._renderAudioPlayer(result.file.url);
      } else {
        this._renderUploadUI();
        console.error("AudioTool: Upload failed", result);
      }
    } catch (err) {
      this._renderUploadUI();
      console.error("AudioTool: Upload error", err);
    }
  }

  save(): AudioToolData {
    return {
      file: this.data.file,
      url: this.data.url,
      caption: this.data.caption || "",
    };
  }

  validate(savedData: AudioToolData): boolean {
    return !!(savedData.file?.url || savedData.url);
  }
}
