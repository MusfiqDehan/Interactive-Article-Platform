export default function ListBlock({ data }: { data: Record<string, unknown> }) {
  const style = (data.style as string) || "unordered";
  const items = (data.items as string[]) || [];

  const Tag = style === "ordered" ? "ol" : "ul";

  return (
    <Tag
      className={`${
        style === "ordered" ? "list-decimal" : "list-disc"
      } pl-6 space-y-1 text-slate-700 dark:text-slate-300`}
    >
      {items.map((item, index) => (
        <li key={index} dangerouslySetInnerHTML={{ __html: item }} />
      ))}
    </Tag>
  );
}
