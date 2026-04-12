export default function AudioBlock({ data }: { data: Record<string, unknown> }) {
  const file = data.file as { url?: string } | undefined;
  const url = (data.url as string) || file?.url || "";
  const caption = (data.caption as string) || "";

  return (
    <figure className="bg-slate-50 dark:bg-slate-800/50 rounded-xl p-6">
      <audio src={url} controls className="w-full" preload="metadata">
        Your browser does not support the audio element.
      </audio>
      {caption && (
        <figcaption className="text-center text-sm text-slate-500 dark:text-slate-400 mt-3">
          {caption}
        </figcaption>
      )}
    </figure>
  );
}
