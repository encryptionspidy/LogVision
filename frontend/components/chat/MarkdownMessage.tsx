"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { sanitizeMarkdown } from "@/lib/sanitizeMarkdown";

interface MarkdownMessageProps {
  content: string;
  className?: string;
}

const mdComponents: Components = {
  h1: ({ children }) => (
    <h1 className="mb-3 mt-6 text-xl font-bold text-text-primary first:mt-0">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mb-2 mt-6 text-lg font-semibold text-accent-secondary first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mb-2 mt-4 text-base font-semibold text-text-primary first:mt-0">
      {children}
    </h3>
  ),
  p: ({ children }) => (
    <p className="my-2 leading-relaxed text-gray-200">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="my-2 ml-5 list-disc space-y-1 text-gray-200">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2 ml-5 list-decimal space-y-1 text-gray-200">
      {children}
    </ol>
  ),
  li: ({ children }) => (
    <li className="leading-relaxed text-gray-200">{children}</li>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold text-accent-primary">{children}</strong>
  ),
  em: ({ children }) => (
    <em className="italic text-gray-300">{children}</em>
  ),
  code: ({ children, className }) => {
    // Inline code vs code blocks
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return (
        <code className="block overflow-x-auto rounded-lg bg-zinc-900 p-4 font-mono text-xs text-gray-300">
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-zinc-800 px-1.5 py-0.5 font-mono text-xs text-accent-secondary">
        {children}
      </code>
    );
  },
  pre: ({ children }) => <pre className="my-3">{children}</pre>,
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-accent-primary/50 pl-4 italic text-gray-400">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-t border-white/10" />,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent-secondary underline decoration-accent-secondary/30 hover:decoration-accent-secondary"
    >
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto">
      <table className="min-w-full text-sm text-gray-200">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border-b border-white/10 px-3 py-2 text-left font-semibold text-text-primary">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-white/5 px-3 py-2">{children}</td>
  ),
};

export default function MarkdownMessage({
  content,
  className = "",
}: MarkdownMessageProps) {
  const sanitized = sanitizeMarkdown(content);

  return (
    <div
      className={`markdown-message max-w-[700px] leading-[1.6] ${className}`}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
        {sanitized}
      </ReactMarkdown>
    </div>
  );
}
