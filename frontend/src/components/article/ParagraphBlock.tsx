export default function ParagraphBlock({ data }: { data: Record<string, unknown> }) {
  const text = (data.text as string) || "";
  return (
    <p
      className="text-slate-700 dark:text-slate-300 leading-relaxed"
      dangerouslySetInnerHTML={{ __html: text }}
    />
  );
}
