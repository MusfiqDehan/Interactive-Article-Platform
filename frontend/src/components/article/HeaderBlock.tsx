import React from "react";

export default function HeaderBlock({ data }: { data: Record<string, unknown> }) {
  const text = (data.text as string) || "";
  const level = (data.level as number) || 2;

  const Tag = `h${level}` as keyof React.JSX.IntrinsicElements;
  const sizeClasses: Record<number, string> = {
    1: "text-4xl font-bold",
    2: "text-3xl font-bold",
    3: "text-2xl font-semibold",
    4: "text-xl font-semibold",
    5: "text-lg font-medium",
    6: "text-base font-medium",
  };

  return (
    <Tag
      className={`${sizeClasses[level] || sizeClasses[2]} text-slate-900 dark:text-white`}
      dangerouslySetInnerHTML={{ __html: text }}
    />
  );
}
