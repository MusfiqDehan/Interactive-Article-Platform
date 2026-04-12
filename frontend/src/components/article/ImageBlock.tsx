/* eslint-disable @next/next/no-img-element */
export default function ImageBlock({ data }: { data: Record<string, unknown> }) {
  const file = data.file as { url?: string } | undefined;
  const url = (data.url as string) || file?.url || "";
  const caption = (data.caption as string) || "";
  const withBorder = data.withBorder as boolean;
  const stretched = data.stretched as boolean;
  const withBackground = data.withBackground as boolean;

  return (
    <figure
      className={`${withBackground ? "bg-slate-100 dark:bg-slate-800 p-4 rounded-xl" : ""} ${
        stretched ? "w-full" : "max-w-2xl mx-auto"
      }`}
    >
      <img
        src={url}
        alt={caption || "Article image"}
        className={`rounded-xl w-full object-cover ${
          withBorder ? "border-2 border-slate-200 dark:border-slate-700" : ""
        }`}
        loading="lazy"
      />
      {caption && (
        <figcaption
          className="text-center text-sm text-slate-500 dark:text-slate-400 mt-3"
          dangerouslySetInnerHTML={{ __html: caption }}
        />
      )}
    </figure>
  );
}
