"use client";

import { useRef, useEffect, useCallback } from "react";
import type EditorJS from "@editorjs/editorjs";
import type { OutputData } from "@editorjs/editorjs";

interface EditorProps {
  data?: OutputData;
  onChange?: (data: OutputData) => void;
  holder: string;
}

export default function Editor({ data, onChange, holder }: EditorProps) {
  const editorRef = useRef<EditorJS | null>(null);
  const isReady = useRef(false);

  const initEditor = useCallback(async () => {
    if (isReady.current) return;

    const EditorJS = (await import("@editorjs/editorjs")).default;
    const Header = (await import("@editorjs/header")).default;
    const List = (await import("@editorjs/list")).default;
    const Quote = (await import("@editorjs/quote")).default;
    const Delimiter = (await import("@editorjs/delimiter")).default;
    const ImageTool = (await import("@editorjs/image")).default;
    const Embed = (await import("@editorjs/embed")).default;
    const CodeTool = (await import("@editorjs/code")).default;
    const InlineCode = (await import("@editorjs/inline-code")).default;
    const Marker = (await import("@editorjs/marker")).default;
    const AudioTool = (await import("./AudioTool")).default;
    const VideoTool = (await import("./VideoTool")).default;
    const InteractiveTextTool = (await import("./InteractiveTextTool")).default;
    const InteractiveImageTool = (await import("./InteractiveImageTool")).default;
    const InteractiveAudioTool = (await import("./InteractiveAudioTool")).default;
    const InteractiveVideoTool = (await import("./InteractiveVideoTool")).default;
    const InteractiveYouTubeTool = (await import("./InteractiveYouTubeTool")).default;

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8003/api";
    const tokens = typeof window !== "undefined" ? localStorage.getItem("tokens") : null;
    const accessToken = tokens ? JSON.parse(tokens).access : "";

    const editor = new EditorJS({
      holder,
      placeholder: "Start writing your article...",
      data: data || { blocks: [] },
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
        if (editorRef.current && onChange) {
          const outputData = await editorRef.current.save();
          onChange(outputData);
        }
      },
    });

    editorRef.current = editor;
    isReady.current = true;
  }, [data, holder, onChange]);

  useEffect(() => {
    if (!isReady.current) {
      initEditor();
    }

    return () => {
      if (editorRef.current && isReady.current) {
        try {
          editorRef.current.destroy();
        } catch {
          // ignore destroy errors
        }
        editorRef.current = null;
        isReady.current = false;
      }
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div
      id={holder}
      className="min-h-[400px] bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4"
    />
  );
}
