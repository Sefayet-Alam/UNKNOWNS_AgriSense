"use client";

import { memo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// Dense Tailwind overrides so assistant markdown reads as a tight prose column.
const components: Components = {
  p: ({ children }) => (
    <p className="mb-3 leading-relaxed last:mb-0">{children}</p>
  ),
  h1: ({ children }) => (
    <h1 className="mb-2 mt-3 font-display text-xl font-semibold tracking-tight">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-3 font-display text-lg font-semibold tracking-tight">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-1.5 mt-2 font-display text-base font-semibold tracking-tight">
      {children}
    </h3>
  ),
  ul: ({ children }) => (
    <ul className="mb-3 list-disc space-y-1 pl-5 last:mb-0">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-3 list-decimal space-y-1 pl-5 last:mb-0">{children}</ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary-700 underline underline-offset-2 hover:text-primary-800"
    >
      {children}
    </a>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-text-primary">{children}</strong>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mb-3 border-l-2 border-primary-300 pl-3 italic text-text-muted">
      {children}
    </blockquote>
  ),
  code: ({ className, children }) => {
    const isBlock = /language-/.test(className ?? "");
    if (isBlock) {
      return (
        <code className="font-mono text-xs">{children}</code>
      );
    }
    return (
      <code className="rounded bg-surface-muted px-1.5 py-0.5 font-mono text-[0.85em] text-primary-800">
        {children}
      </code>
    );
  },
  pre: ({ children }) => (
    <pre className="mb-3 max-w-full overflow-x-auto rounded-lg border border-border bg-surface-muted p-3 last:mb-0">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="mb-3 max-w-full overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-border bg-surface-muted px-2.5 py-1.5 text-left font-semibold">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-border px-2.5 py-1.5">{children}</td>
  ),
  hr: () => <hr className="my-3 border-border" />,
};

function MarkdownImpl({ content }: { content: string }) {
  return (
    <div className="text-[0.95rem] text-text-primary">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

// Memoized on the content string to avoid re-parsing markdown on every render.
export const Markdown = memo(
  MarkdownImpl,
  (prev, next) => prev.content === next.content,
);
