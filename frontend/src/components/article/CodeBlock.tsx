export default function CodeBlock({ data }: { data: Record<string, unknown> }) {
  const code = (data.code as string) || "";

  return (
    <pre className="bg-slate-900 dark:bg-slate-800 text-slate-100 rounded-xl p-6 overflow-x-auto text-sm leading-relaxed">
      <code>{code}</code>
    </pre>
  );
}
