"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp, FileCode } from "lucide-react";

interface EvidenceItem {
  log_line?: string;
  line_number?: number;
  significance?: string;
}

interface EvidenceBlockProps {
  evidence: EvidenceItem[] | string[];
  title?: string;
  maxVisible?: number;
}

export default function EvidenceBlock({
  evidence,
  title = "Supporting Evidence",
  maxVisible = 3,
}: EvidenceBlockProps) {
  const [expanded, setExpanded] = useState(false);

  if (!evidence || evidence.length === 0) return null;

  // Normalize evidence items
  const items: EvidenceItem[] = evidence.map((e) =>
    typeof e === "string" ? { log_line: e } : e
  );

  const visibleItems = expanded ? items : items.slice(0, maxVisible);
  const hasMore = items.length > maxVisible;

  return (
    <div className="rounded-xl border border-white/8 bg-[#0f0f14] overflow-hidden animate-fadeIn">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-white/5 px-4 py-2.5">
        <FileCode className="h-3.5 w-3.5 text-[#ff8a5b]" />
        <span className="text-[11px] font-semibold uppercase tracking-wider text-gray-500">
          {title}
        </span>
        <span className="ml-auto text-[10px] text-gray-600">
          {items.length} item{items.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Evidence lines */}
      <div className="divide-y divide-white/3">
        {visibleItems.map((item, i) => (
          <div key={i} className="px-4 py-2.5 hover:bg-white/[0.02] transition-colors">
            <div className="flex items-start gap-3">
              {item.line_number && (
                <span className="mt-0.5 flex-shrink-0 rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-gray-600">
                  L{item.line_number}
                </span>
              )}
              <code className="flex-1 font-mono text-xs text-gray-300 break-all leading-relaxed">
                {item.log_line}
              </code>
            </div>
            {item.significance && (
              <p className="mt-1 ml-8 text-[11px] italic text-gray-500">
                {item.significance}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Expand/collapse */}
      {hasMore && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex w-full items-center justify-center gap-1.5 border-t border-white/5 px-4 py-2 text-[11px] text-gray-500 hover:bg-white/[0.02] hover:text-gray-300 transition-colors"
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3 w-3" />
              Show less
            </>
          ) : (
            <>
              <ChevronDown className="h-3 w-3" />
              Show {items.length - maxVisible} more
            </>
          )}
        </button>
      )}
    </div>
  );
}
