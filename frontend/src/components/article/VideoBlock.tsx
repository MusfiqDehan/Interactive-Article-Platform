import { normalizeMediaUrl } from "@/lib/media";

export default function VideoBlock({ data }: { data: Record<string, unknown> }) {
  const file = data.file as { url?: string } | undefined;
  const url = normalizeMediaUrl((data.url as string) || file?.url || "");
  const caption = (data.caption as string) || "";

  return (
    <figure className="rounded-xl overflow-hidden">
      <video
        src={url}
        controls
        className="w-full rounded-xl"
        preload="metadata"
      >
        Your browser does not support the video element.
      </video>
      {caption && (
        <figcaption className="text-center text-sm text-slate-500 dark:text-slate-400 mt-3">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}
