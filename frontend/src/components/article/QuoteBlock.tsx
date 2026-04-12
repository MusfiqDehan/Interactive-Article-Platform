export default function QuoteBlock({ data }: { data: Record<string, unknown> }) {
  const text = (data.text as string) || "";
  const caption = (data.caption as string) || "";

  return (
    <blockquote className="border-l-4 border-primary-500 pl-6 py-2 my-6 bg-primary-50/50 dark:bg-primary-900/10 rounded-r-lg">
      <p
        className="text-lg italic text-slate-700 dark:text-slate-300"
        dangerouslySetInnerHTML={{ __html: text }}
      />
      {caption && (
        <cite className="block mt-2 text-sm text-slate-500 dark:text-slate-400 not-italic">
          — {caption}
        </cite>
      )}
    </blockquote>
  );
}
