"use client";

import { useEffect, useRef } from "react";
import type EditorJS from "@editorjs/editorjs";
import type { OutputData } from "@editorjs/editorjs";

import { publicEnvFromWindow } from "@/lib/runtime-config";

interface EditorProps {
  /**
   * Initial blocks. **Leave `undefined` until loaded.** Initialisation waits for
   * this to be defined; passing `{blocks: []}` as a placeholder makes the editor
   * mount empty and it will not pick the real content up afterwards, because
   * Editor.js reads `data` exactly once.
   *
   * After mount, changes must not flow back in through this prop -- that would
   * destroy and recreate the instance (the plus button and placeholder blink,
   * and toolbox clicks never land). Remount with `key` when loading a different
   * article or restoring a revision.
   */
  data?: OutputData;
  onChange?: (data: OutputData) => void;
  holder: string;
}

function Editor({ data, onChange, holder }: EditorProps) {
  const editorRef = useRef<EditorJS | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  /**
   * `init` closes over `onChange`, but this effect must not re-run when the
   * parent passes a new callback. A ref always points at the latest handler
   * without tearing the Editor.js instance down.
   */
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;
  /**
   * Capture the first defined payload for construction. Later `data` identity
   * changes (autosave, outline) must not re-init.
   */
  const bootDataRef = useRef<OutputData | undefined>(undefined);
  if (data !== undefined && bootDataRef.current === undefined) {
    bootDataRef.current = data;
  }

  useEffect(() => {
    if (data === undefined) return;

    let cancelled = false;
    let instance: EditorJS | null = null;

    const boot = async () => {
      const EditorJSCtor = (await import("@editorjs/editorjs")).default;
      const Header = (await import("@editorjs/header")).default;
      const List = (await import("@editorjs/list")).default;
      const Quote = (await import("@editorjs/quote")).default;
      const Delimiter = (await import("@editorjs/delimiter")).default;
      const ImageTool = (await import("@editorjs/image")).default;
      const Embed = (await import("@editorjs/embed")).default;
      const CodeTool = (await import("@editorjs/code")).default;
      const InlineCode = (await import("@editorjs/inline-code")).default;
      const Marker = (await import("@editorjs/marker")).default;
      const InteractiveInlineTool = (await import("./InteractiveInlineTool")).default;
      const AudioTool = (await import("./AudioTool")).default;
      const VideoTool = (await import("./VideoTool")).default;
      const InteractiveTextTool = (await import("./InteractiveTextTool")).default;
      const InteractiveImageTool = (await import("./InteractiveImageTool")).default;
      const InteractiveAudioTool = (await import("./InteractiveAudioTool")).default;
      const InteractiveVideoTool = (await import("./InteractiveVideoTool")).default;
      const InteractiveYouTubeTool = (await import("./InteractiveYouTubeTool")).default;

      if (cancelled) return;

      const apiBaseUrl = `${(
        publicEnvFromWindow()?.apiBase ||
        process.env.NEXT_PUBLIC_API_BASE_URL ||
        "http://localhost:8003/api"
      ).replace(/\/$/, "")}/v1/studio`;
      const tokens = typeof window !== "undefined" ? localStorage.getItem("tokens") : null;
      const accessToken = tokens ? JSON.parse(tokens).access : "";

      const root = rootRef.current;
      if (cancelled || !root) return;

      instance = new EditorJSCtor({
        holder: root,
        autofocus: false,
        minHeight: 400,
        placeholder: "Start writing your article...",
        data: bootDataRef.current || { blocks: [] },
        tools: {
          header: {
            class: Header,
            config: {
              levels: [1, 2, 3, 4],
              defaultLevel: 2,
            },
          },
          list: {
            class: List,
            inlineToolbar: true,
          },
          quote: {
            class: Quote,
            inlineToolbar: true,
          },
          delimiter: Delimiter,
          image: {
            class: ImageTool,
            config: {
              endpoints: {
                byFile: `${apiBaseUrl}/media/upload/`,
              },
              additionalRequestHeaders: {
                Authorization: `Bearer ${accessToken}`,
              },
              field: "image",
            },
          },
          embed: {
            class: Embed,
            config: {
              services: {
                youtube: true,
                vimeo: true,
                coub: true,
                codepen: true,
                instagram: true,
              },
            },
          },
          audio: {
            class: AudioTool,
            config: {
              endpoints: {
                byFile: `${apiBaseUrl}/media/upload/`,
              },
              additionalRequestHeaders: {
                Authorization: `Bearer ${accessToken}`,
              },
              field: "file",
            },
          },
          video: {
            class: VideoTool,
            config: {
              endpoints: {
                byFile: `${apiBaseUrl}/media/upload/`,
              },
              additionalRequestHeaders: {
                Authorization: `Bearer ${accessToken}`,
              },
              field: "file",
            },
          },
          code: CodeTool,
          inlineCode: {
            class: InlineCode,
          },
          marker: {
            class: Marker,
          },
          interactiveAnnotation: {
            class: InteractiveInlineTool,
          },
          interactive_text: {
            class: InteractiveTextTool,
          },
          interactive_image: {
            class: InteractiveImageTool,
            config: {
              endpoints: {
                byFile: `${apiBaseUrl}/media/upload/`,
              },
              additionalRequestHeaders: {
                Authorization: `Bearer ${accessToken}`,
              },
              field: "image",
            },
          },
          interactive_audio: {
            class: InteractiveAudioTool,
            config: {
              endpoints: {
                byFile: `${apiBaseUrl}/media/upload/`,
              },
              additionalRequestHeaders: {
                Authorization: `Bearer ${accessToken}`,
              },
              field: "file",
            },
          },
          interactive_video: {
            class: InteractiveVideoTool,
            config: {
              endpoints: {
                byFile: `${apiBaseUrl}/media/upload/`,
              },
              additionalRequestHeaders: {
                Authorization: `Bearer ${accessToken}`,
              },
              field: "file",
            },
          },
          interactive_youtube: {
            class: InteractiveYouTubeTool,
          },
        },
        onChange: async () => {
          const handler = onChangeRef.current;
          if (!instance || !handler) return;
          try {
            const outputData = await instance.save();
            if (!cancelled) handler(outputData);
          } catch {
            // save() rejects if destroy() raced the plus-button click.
          }
        },
      });

      editorRef.current = instance;

      if (cancelled) {
        instance.destroy();
        editorRef.current = null;
        return;
      }

      try {
        await instance.isReady;
      } catch {
        return;
      }

      if (cancelled) {
        try {
          instance.destroy();
        } catch {
          // ignore destroy errors
        }
        editorRef.current = null;
      }
    };

    void boot();

    return () => {
      cancelled = true;
      if (instance) {
        try {
          instance.destroy();
        } catch {
          // ignore destroy errors
        }
        instance = null;
      }
      editorRef.current = null;
    };
    // Only holder / "data has arrived". `data` itself must stay out: autosave
    // and outline updates would otherwise destroy the editor on every keystroke.
  }, [holder, data === undefined]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      ref={rootRef}
      id={holder}
      className="codex-holder min-h-[400px] rounded-xl border border-slate-200 bg-white py-4 pl-14 pr-12 dark:border-slate-700 dark:bg-slate-800"
    />
  );
}

export default Editor;
