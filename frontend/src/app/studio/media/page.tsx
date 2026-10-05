"use client";

import { AlertTriangle, FileText, Music, Upload, Video } from "lucide-react";
import { useRef, useState } from "react";

import { MediaDrawer } from "@/components/studio/MediaDrawer";
import { PageShell, QueryState } from "@/components/studio/PageShell";
import { useStudioQuery } from "@/components/studio/useStudioQuery";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/cn";
import { normalizeMediaUrl } from "@/lib/media";
import { publicEnvFromWindow } from "@/lib/runtime-config";
import { listMedia, type MediaRow } from "@/lib/studio-api";

const TYPES = [
  { value: "", label: "All" },
  { value: "image", label: "Images" },
  { value: "video", label: "Video" },
  { value: "audio", label: "Audio" },
  { value: "document", label: "Documents" },
];

export default function MediaPage() {
  const [type, setType] = useState("");
  const [search, setSearch] = useState("");
  const [missingAltOnly, setMissingAltOnly] = useState(false);
  const [open, setOpen] = useState<MediaRow | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const { data, loading, error, refresh } = useStudioQuery(
    () =>
      listMedia({
        ...(type ? { file_type: type } : {}),
        ...(search ? { search } : {}),
      }),
    [type, search],
  );

  const all = data?.results ?? [];
  const missingAlt = all.filter(
    (item) => isImage(item) && !item.alt_text?.trim(),
  ).length;
  const rows = missingAltOnly
    ? all.filter((item) => isImage(item) && !item.alt_text?.trim())
    : all;

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    setUploading(true);
    const base =
      publicEnvFromWindow()?.apiBase || process.env.NEXT_PUBLIC_API_BASE_URL || "";
    const tokens = localStorage.getItem("tokens");
    const access = tokens ? JSON.parse(tokens).access : null;
    try {
      for (const file of Array.from(files)) {
        const body = new FormData();
        body.append("file", file);
        await fetch(`${base.replace(/\/$/, "")}/v1/studio/media/upload/`, {
          method: "POST",
          headers: access ? { Authorization: `Bearer ${access}` } : undefined,
          body,
        });
      }
      refresh();
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = "";
    }
  };

  return (
    <PageShell
      title="Media"
      description="Everything uploaded to this site. Alt text lives here, not in the article — one description per file, wherever it is used."
      actions={
        <>
          <input
            ref={fileInput}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => upload(e.target.files)}
          />
          <Button size="sm" onClick={() => fileInput.current?.click()} disabled={uploading}>
            <Upload size={14} /> {uploading ? "Uploading…" : "Upload"}
          </Button>
        </>
      }
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <input
          className="input-field max-w-xs"
          placeholder="Search by title or alt text…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="input-field h-10 w-36 py-0"
          value={type}
          onChange={(e) => setType(e.target.value)}
        >
          {TYPES.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>

        {missingAlt > 0 && (
          // A count, not a badge on each tile: the useful question is "how much
          // work is left", and the answer has to be visible without scrolling.
          <button
            onClick={() => setMissingAltOnly((prev) => !prev)}
            className={cn(
              "flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition",
              missingAltOnly
                ? "border-amber-500 bg-amber-500 text-white"
                : "border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300",
            )}
          >
            <AlertTriangle size={13} />
            {missingAlt} image{missingAlt === 1 ? "" : "s"} without alt text
          </button>
        )}
      </div>

      <QueryState
        loading={loading}
        error={error}
        isEmpty={rows.length === 0}
        empty={
          missingAltOnly
            ? "Every image on this page has alt text."
            : "Nothing uploaded yet."
        }
      >
        <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {rows.map((item) => (
            <li key={item.id}>
              <button
                onClick={() => setOpen(item)}
                className="group block w-full overflow-hidden rounded-lg border border-[var(--sl-line)] bg-[var(--sl-card)] text-left transition hover:border-[var(--sl-soft)] hover:shadow-sm"
              >
                <div className="relative flex aspect-square items-center justify-center bg-[var(--sl-soft)] bg-[var(--sl-card)]">
                  {isImage(item) ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={normalizeMediaUrl(item.url || item.file)}
                      alt={item.alt_text || ""}
                      className="h-full w-full object-cover"
                      loading="lazy"
                    />
                  ) : (
                    <TypeIcon type={item.file_type} />
                  )}
                  {isImage(item) && !item.alt_text?.trim() && (
                    <span
                      title="No alt text"
                      className="absolute right-1.5 top-1.5 rounded-full bg-amber-500 p-1 text-white shadow"
                    >
                      <AlertTriangle size={11} />
                    </span>
                  )}
                </div>
                <p className="truncate px-2 py-1.5 text-xs text-[var(--sl-ink)]">
                  {item.title || "Untitled"}
                </p>
              </button>
            </li>
          ))}
        </ul>
      </QueryState>

      {open && (
        <MediaDrawer item={open} onClose={() => setOpen(null)} onChanged={refresh} />
      )}
    </PageShell>
  );
}

function isImage(item: MediaRow) {
  return item.file_type === "image" || Boolean(item.mime_type?.startsWith("image/"));
}

function TypeIcon({ type }: { type: string }) {
  const Icon = type === "video" ? Video : type === "audio" ? Music : FileText;
  return <Icon size={28} className="text-[var(--sl-muted)]" />;
}
