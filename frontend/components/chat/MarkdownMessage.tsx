"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { sanitizeMarkdown } from "@/lib/sanitizeMarkdown";
import { Copy, Check } from "lucide-react";

interface MarkdownMessageProps {
  content: string;
  className?: string;
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch { /* ignore */ }
  };

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 rounded-md p-1.5 text-gray-500 hover:bg-white/10 hover:text-gray-300 transition-all opacity-0 group-hover:opacity-100"
      title="Copy code"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-green-400" />
      ) : (
        <Copy className="h-3.5 w-3.5" />
      )}
    </button>
  );
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
        <code className="block overflow-x-auto rounded-lg bg-zinc-900/80 p-4 font-mono text-xs text-gray-300 leading-relaxed">
          {children}
        </code>
      );
    }
    return (
      <code className="rounded bg-zinc-800/80 px-1.5 py-0.5 font-mono text-xs text-accent-secondary">
        {children}
      </code>
    );
  },
  pre: ({ children }) => {
    // Extract text content for copy button
    const extractText = (node: any): string => {
      if (typeof node === "string") return node;
      if (Array.isArray(node)) return node.map(extractText).join("");
      if (node?.props?.children) return extractText(node.props.children);
      return "";
    };
    const codeText = extractText(children);

    return (
      <pre className="group relative my-3 rounded-xl border border-white/5 overflow-hidden">
        <CopyButton text={codeText} />
        {children}
      </pre>
    );
  },
  blockquote: ({ children }) => (
    <blockquote className="my-3 rounded-lg border-l-2 border-accent-primary/50 bg-white/[0.02] pl-4 pr-3 py-2 italic text-gray-400">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-t border-white/10" />,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent-secondary underline decoration-accent-secondary/30 hover:decoration-accent-secondary transition-colors"
    >
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-lg border border-white/8">
      <table className="min-w-full text-sm text-gray-200">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-white/[0.03]">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="border-b border-white/10 px-3 py-2 text-left font-semibold text-text-primary text-xs">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border-b border-white/5 px-3 py-2 text-xs">{children}</td>
  ),
  tr: ({ children }) => (
    <tr className="hover:bg-white/[0.02] transition-colors">{children}</tr>
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
