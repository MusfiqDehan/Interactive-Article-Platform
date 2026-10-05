"use client";

import { AlertTriangle, Check, Crop, Loader2, Trash2 } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/primitives";
import { normalizeMediaUrl } from "@/lib/media";
import { deleteMedia, saveMedia, type MediaRow } from "@/lib/studio-api";

/**
 * Detail drawer for one media item.
 *
 * A drawer rather than a modal so the library stays visible behind it — the
 * common task is auditing alt text across many images, and a modal that hides
 * the grid makes each one feel like a separate errand.
 *
 * The alt-text field is the reason this screen exists. It is missing on most
 * uploads, it is one of the SEO checks, and it is the difference between an
 * article being usable with a screen reader or not. So it leads, it is
 * pre-focused, and its absence is stated rather than left blank.
 */

/** Aspect ratios the front end crops to. Shown live so the focal point is
 *  chosen against the crops it actually affects, not in the abstract. */
const CROPS = [
  { label: "16:9", ratio: 16 / 9 },
  { label: "1:1", ratio: 1 },
  { label: "4:5", ratio: 4 / 5 },
];

export function MediaDrawer({
  item,
  onClose,
  onChanged,
}: {
  item: MediaRow;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [alt, setAlt] = useState(item.alt_text ?? "");
  const [title, setTitle] = useState(item.title ?? "");
  const [focal, setFocal] = useState({ x: 0.5, y: 0.5 });
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const imageRef = useRef<HTMLDivElement>(null);

  const url = normalizeMediaUrl(item.url || item.file);
  const isImage = item.file_type === "image" || item.mime_type?.startsWith("image/");

  const pickFocal = (event: React.MouseEvent<HTMLDivElement>) => {
    const box = imageRef.current?.getBoundingClientRect();
    if (!box) return;
    setFocal({
      x: clamp((event.clientX - box.left) / box.width),
      y: clamp((event.clientY - box.top) / box.height),
    });
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await saveMedia(item.id, { alt_text: alt, title });
      setSaved(true);
      onChanged();
    } catch {
      setError("Could not save this.");
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    setError(null);
    try {
      await deleteMedia(item.id);
      onChanged();
      onClose();
    } catch {
      // The backend refuses when the file is still referenced; without that
      // context a failed delete looks like a bug rather than a safeguard.
      setError("Could not delete this — it may still be used by an article.");
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent side="right" className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="truncate">{item.title || "Untitled file"}</DialogTitle>
          <DialogDescription>
            {item.mime_type} · {formatBytes(item.file_size)}
          </DialogDescription>
        </DialogHeader>

        <DialogBody className="space-y-5">
          {isImage && (
            <div>
              <div
                ref={imageRef}
                onClick={pickFocal}
                className="relative cursor-crosshair overflow-hidden rounded-lg border border-[var(--sl-line)] bg-[var(--sl-soft)] bg-[var(--sl-card)]"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={url} alt={alt} className="block max-h-64 w-full object-contain" />
                <span
                  className="pointer-events-none absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-[var(--sl-soft)] shadow"
                  style={{ left: `${focal.x * 100}%`, top: `${focal.y * 100}%` }}
                />
              </div>
              <p className="mt-1.5 flex items-center gap-1.5 text-xs text-[var(--sl-muted)]">
                <Crop size={12} /> Click the subject. Crops keep that point in
                frame.
              </p>

              <div className="mt-3 flex gap-2">
                {CROPS.map((crop) => (
                  <div key={crop.label} className="flex-1">
                    <div
                      className="overflow-hidden rounded border border-[var(--sl-line)] bg-[var(--sl-soft)]"
                      style={{ aspectRatio: String(crop.ratio) }}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={url}
                        alt=""
                        className="h-full w-full object-cover"
                        style={{
                          objectPosition: `${focal.x * 100}% ${focal.y * 100}%`,
                        }}
                      />
                    </div>
                    <p className="mt-0.5 text-center text-[10px] text-[var(--sl-muted)]">
                      {crop.label}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <label className="block">
            <span className="mb-1 flex items-center gap-1.5 text-sm font-medium text-[var(--sl-ink)]">
              Alt text
              {!alt.trim() && (
                <span className="flex items-center gap-1 text-xs font-normal text-amber-600">
                  <AlertTriangle size={12} /> missing
                </span>
              )}
            </span>
            <textarea
              className="input-field h-20 resize-y"
              value={alt}
              onChange={(e) => {
                setAlt(e.target.value);
                setSaved(false);
              }}
              placeholder="What is in this image, for someone who cannot see it?"
              autoFocus
            />
            <span className="mt-1 block text-xs text-[var(--sl-muted)]">
              Describe the content, not the file. Skip “image of” — a screen
              reader already announces that.
            </span>
          </label>

          <label className="block">
            <span className="mb-1 block text-sm font-medium text-[var(--sl-ink)]">
              Title
            </span>
            <input
              className="input-field"
              value={title}
              onChange={(e) => {
                setTitle(e.target.value);
                setSaved(false);
              }}
            />
          </label>

          <div>
            <span className="mb-1 block text-xs font-medium text-[var(--sl-muted)]">URL</span>
            <code className="block break-all rounded bg-[var(--sl-soft)] p-2 font-mono text-xs text-[var(--sl-ink)] bg-[var(--sl-card)]">
              {url}
            </code>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}
        </DialogBody>

        <DialogFooter>
          <Button
            variant="ghost"
            className="mr-auto text-red-600"
            onClick={remove}
            disabled={busy}
          >
            <Trash2 size={14} /> Delete
          </Button>
          {saved && (
            <span className="flex items-center gap-1 text-sm text-emerald-600">
              <Check size={14} /> Saved
            </span>
          )}
          <Button onClick={submit} disabled={busy}>
            {busy && <Loader2 size={14} className="animate-spin" />} Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function clamp(value: number) {
  return Math.min(1, Math.max(0, value));
}

function formatBytes(bytes: number) {
  if (!bytes) return "unknown size";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  return `${(bytes / 1024 ** index).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}
