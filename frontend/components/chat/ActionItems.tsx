"use client";

import { useState } from "react";
import { CheckCircle, Copy, Check, ChevronDown, ChevronUp, Zap } from "lucide-react";

interface ActionItem {
  priority: number;
  action: string;
  rationale?: string;
  command?: string;
}

interface ActionItemsProps {
  actions: ActionItem[];
}

export default function ActionItems({ actions }: ActionItemsProps) {
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null);

  if (!actions || actions.length === 0) return null;

  const handleCopy = async (text: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 2000);
    } catch {
      // Fallback for insecure contexts
    }
  };

  // Sort by priority
  const sorted = [...actions].sort((a, b) => (a.priority || 99) - (b.priority || 99));

  return (
    <div className="rounded-2xl border border-white/8 bg-[#13131a] overflow-hidden animate-fadeIn">
      <div className="flex items-center gap-2 border-b border-white/5 px-5 py-3">
        <Zap className="h-4 w-4 text-[#ff8a5b]" />
        <span className="text-xs font-semibold text-gray-300">Recommended Actions</span>
        <span className="ml-auto rounded-full bg-[#ff8a5b]/15 px-2 py-0.5 text-[10px] font-semibold text-[#ff8a5b]">
          {sorted.length} action{sorted.length !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="divide-y divide-white/5">
        {sorted.map((action, i) => {
          const isExpanded = expandedIdx === i;
          const hasCommand = action.command && !["optional", "n/a", "none", ""].includes(action.command.toLowerCase());

          return (
            <div key={i} className="px-5 py-3.5 hover:bg-white/[0.02] transition-colors">
              <div className="flex items-start gap-3">
                {/* Priority number */}
                <div className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full bg-[#ff8a5b]/15 text-[11px] font-bold text-[#ff8a5b]">
                  {action.priority || i + 1}
                </div>

                <div className="min-w-0 flex-1">
                  {/* Action text */}
                  <p className="text-sm text-gray-200 leading-relaxed">{action.action}</p>

                  {/* Rationale toggle */}
                  {action.rationale && (
                    <button
                      onClick={() => setExpandedIdx(isExpanded ? null : i)}
                      className="mt-1 flex items-center gap-1 text-[11px] text-gray-500 hover:text-gray-300 transition-colors"
                    >
                      {isExpanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                      {isExpanded ? "Hide rationale" : "Why?"}
                    </button>
                  )}

                  {/* Expanded rationale */}
                  {isExpanded && action.rationale && (
                    <p className="mt-2 text-[11px] text-gray-400 italic leading-relaxed animate-slideDown">
                      {action.rationale}
                    </p>
                  )}

                  {/* Command block with copy button */}
                  {hasCommand && (
                    <div className="mt-2 flex items-center gap-2 rounded-lg bg-black/40 px-3 py-2">
                      <code className="flex-1 font-mono text-[11px] text-gray-300 break-all">
                        {action.command}
                      </code>
                      <button
                        onClick={() => handleCopy(action.command!, i)}
                        className="flex-shrink-0 rounded p-1 text-gray-500 hover:bg-white/5 hover:text-gray-300 transition-colors"
                        title="Copy command"
                      >
                        {copiedIdx === i ? (
                          <Check className="h-3.5 w-3.5 text-green-400" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
