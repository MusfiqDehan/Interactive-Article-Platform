/**
 * Custom Editor.js Video Block Tool
 * Supports file upload, URL input, and YouTube embed for video content.
 */

interface VideoToolData {
  file?: { url: string };
  url?: string;
  caption?: string;
  service?: string;
}

interface VideoToolConfig {
  endpoints?: { byFile?: string };
  additionalRequestHeaders?: Record<string, string>;
  field?: string;
}

interface VideoToolConstructorParams {
  data?: VideoToolData;
  config?: VideoToolConfig;
  api: { styles: { block: string } };
}

export default class VideoTool {
  private data: VideoToolData;
  private config: VideoToolConfig;
  private wrapper: HTMLElement | null = null;

  static get toolbox() {
    return {
      title: "Video",
      icon: '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>',
    };
  }

  static get isReadOnlySupported() {
    return true;
  }

  constructor({ data, config }: VideoToolConstructorParams) {
    this.data = data || {};
    this.config = config || {};
  }

  render(): HTMLElement {
    this.wrapper = document.createElement("div");
    this.wrapper.style.cssText =
      "border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; background: #f8fafc;";

    const videoUrl = this.data.file?.url || this.data.url || "";

    if (videoUrl) {
      this._renderVideoPlayer(videoUrl);
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
      '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>';
    container.appendChild(icon);

    // Upload button
    const uploadBtn = document.createElement("button");
    uploadBtn.textContent = "Upload Video File";
    uploadBtn.type = "button";
    uploadBtn.style.cssText =
      "padding: 8px 20px; background: #3b82f6; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500;";
    uploadBtn.addEventListener("click", () => this._selectFile());
    container.appendChild(uploadBtn);

    // Or divider
    const divider = document.createElement("div");
    divider.textContent = "or paste a video URL";
    divider.style.cssText = "color: #94a3b8; font-size: 13px;";
    container.appendChild(divider);

    // URL input
    const urlInput = document.createElement("input");
    urlInput.type = "url";
    urlInput.placeholder = "https://example.com/video.mp4";
    urlInput.style.cssText =
      "width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 14px; outline: none; box-sizing: border-box;";
    urlInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        const url = urlInput.value.trim();
        if (url) {
          this.data = { url, caption: this.data.caption || "" };
          this._renderVideoPlayer(url);
        }
      }
    });
    container.appendChild(urlInput);

    this.wrapper.appendChild(container);
  }

  private _renderVideoPlayer(url: string): void {
    if (!this.wrapper) return;

    this.wrapper.innerHTML = "";
    this.wrapper.style.position = "relative";

    const videoContainer = document.createElement("div");
    videoContainer.style.cssText =
      "border-radius: 8px; overflow: hidden; background: #0f172a;";

    const video = document.createElement("video");
    video.src = url;
    video.controls = true;
    video.preload = "metadata";
    video.style.cssText = "width: 100%; display: block;";
    videoContainer.appendChild(video);
    this.wrapper.appendChild(videoContainer);

    // Caption input
    const caption = document.createElement("input");
    caption.type = "text";
    caption.placeholder = "Add a caption (optional)";
    caption.value = this.data.caption || "";
    caption.style.cssText =
      "width: 100%; padding: 8px; border: none; border-top: 1px solid #e2e8f0; font-size: 13px; color: #64748b; outline: none; background: transparent; box-sizing: border-box; margin-top: 8px;";
    caption.addEventListener("input", () => {
      this.data.caption = caption.value;
    });
    this.wrapper.appendChild(caption);

    // Remove button
    const removeBtn = document.createElement("button");
    removeBtn.textContent = "✕ Remove";
    removeBtn.type = "button";
    removeBtn.style.cssText =
      "position: absolute; top: 8px; right: 8px; background: #ef4444; color: white; border: none; border-radius: 4px; padding: 2px 8px; font-size: 12px; cursor: pointer; z-index: 1;";
    removeBtn.addEventListener("click", () => {
      this.data = { caption: this.data.caption || "" };
      this._renderUploadUI();
    });
    this.wrapper.appendChild(removeBtn);
  }

  private _selectFile(): void {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "video/*";
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
      console.error("VideoTool: No upload endpoint configured");
      return;
    }

    const formData = new FormData();
    formData.append(this.config.field || "file", file);

    // Show uploading state
    if (this.wrapper) {
      this.wrapper.innerHTML =
        '<div style="text-align:center;padding:40px;color:#94a3b8;">Uploading video…</div>';
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
        this._renderVideoPlayer(result.file.url);
      } else {
        this._renderUploadUI();
        console.error("VideoTool: Upload failed", result);
      }
    } catch (err) {
      this._renderUploadUI();
      console.error("VideoTool: Upload error", err);
    }
  }

  save(): VideoToolData {
    return {
      file: this.data.file,
      url: this.data.url,
      caption: this.data.caption || "",
    };
  }

  validate(savedData: VideoToolData): boolean {
    return !!(savedData.file?.url || savedData.url);
  }
}
