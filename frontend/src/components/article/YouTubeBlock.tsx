export default function YouTubeBlock({ data }: { data: Record<string, unknown> }) {
  const source = (data.source as string) || (data.url as string) || (data.embed as string) || "";
  const caption = (data.caption as string) || "";

  // Extract YouTube video ID from various URL formats
  let videoId = "";
  try {
    if (source.includes("youtube.com/watch")) {
      const url = new URL(source);
      videoId = url.searchParams.get("v") || "";
    } else if (source.includes("youtu.be/")) {
      videoId = source.split("youtu.be/")[1]?.split("?")[0] || "";
    } else if (source.includes("youtube.com/embed/")) {
      videoId = source.split("embed/")[1]?.split("?")[0] || "";
    } else if (source.includes("youtube.com")) {
      // Try to extract from other YouTube URL formats
      const url = new URL(source);
      videoId = url.searchParams.get("v") || "";
    }
  } catch {
    // If URL parsing fails, use the source as-is for the embed
  }

  const embedUrl = videoId
    ? `https://www.youtube-nocookie.com/embed/${videoId}`
    : source;

  if (!embedUrl) return null;

  return (
    <figure>
      <div className="relative w-full aspect-video rounded-xl overflow-hidden bg-slate-900">
        <iframe
          src={embedUrl}
          title={caption || "YouTube Video"}
          className="absolute inset-0 w-full h-full"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          loading="lazy"
        />
      </div>
      {caption && (
        <figcaption
          className="text-center text-sm text-slate-500 dark:text-slate-400 mt-3"
          dangerouslySetInnerHTML={{ __html: caption }}
        />
      )}
    </figure>
  );
}
