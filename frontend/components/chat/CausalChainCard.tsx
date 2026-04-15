"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

interface CausalStep {
  step: number;
  event: string;
  evidence?: string;
  component?: string;
}

interface CausalChainCardProps {
  chain: CausalStep[];
}

const STEP_COLORS = [
  "border-yellow-500/40 bg-yellow-500/8",
  "border-orange-500/40 bg-orange-500/8",
  "border-red-500/40 bg-red-500/8",
  "border-red-600/40 bg-red-600/8",
  "border-red-700/40 bg-red-700/8",
];

const DOT_COLORS = [
  "bg-yellow-500",
  "bg-orange-500",
  "bg-red-500",
  "bg-red-600",
  "bg-red-700",
];

export default function CausalChainCard({ chain }: CausalChainCardProps) {
  const [expandedStep, setExpandedStep] = useState<number | null>(null);

  if (!chain || chain.length === 0) return null;

  return (
    <div className="rounded-2xl border border-white/8 bg-[#13131a] p-5 animate-fadeIn">
      <h3 className="mb-4 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
        <svg className="h-4 w-4 text-[#ff8a5b]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M12 2v6m0 8v6M4.93 4.93l4.24 4.24m5.66 5.66l4.24 4.24M2 12h6m8 0h6M4.93 19.07l4.24-4.24m5.66-5.66l4.24-4.24" />
        </svg>
        Failure Propagation Chain
      </h3>

      <div className="relative ml-3">
        {/* Connecting line */}
        <div className="absolute left-[7px] top-2 bottom-2 w-[2px] bg-gradient-to-b from-yellow-500/40 via-orange-500/40 to-red-500/40" />

        <div className="space-y-3">
          {chain.map((step, i) => {
            const colorClass = STEP_COLORS[Math.min(i, STEP_COLORS.length - 1)];
            const dotColor = DOT_COLORS[Math.min(i, DOT_COLORS.length - 1)];
            const isExpanded = expandedStep === i;

            return (
              <div
                key={i}
                className={`relative rounded-xl border ${colorClass} p-3.5 ml-6 transition-all duration-200`}
                style={{ animationDelay: `${i * 100}ms` }}
              >
                {/* Timeline dot */}
                <div className={`absolute -left-[30px] top-4 h-4 w-4 rounded-full ${dotColor} ring-4 ring-[#13131a] z-10 flex items-center justify-center`}>
                  <span className="text-[8px] font-bold text-white">{step.step || i + 1}</span>
                </div>

                {/* Step content */}
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    {step.component && (
                      <span className="mb-1 inline-block rounded-md bg-white/8 px-2 py-0.5 text-[10px] font-medium text-gray-400">
                        {step.component}
                      </span>
                    )}
                    <p className="text-sm text-gray-200 leading-relaxed">{step.event}</p>
                  </div>
                  {step.evidence && (
                    <button
                      onClick={() => setExpandedStep(isExpanded ? null : i)}
                      className="flex-shrink-0 rounded-lg p-1 text-gray-500 hover:bg-white/5 hover:text-gray-300 transition-colors"
                    >
                      {isExpanded ? (
                        <ChevronUp className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronDown className="h-3.5 w-3.5" />
                      )}
                    </button>
                  )}
                </div>

                {/* Evidence (expandable) */}
                {isExpanded && step.evidence && (
                  <div className="mt-2 rounded-lg bg-black/30 px-3 py-2 font-mono text-[11px] text-gray-400 animate-slideDown">
                    {step.evidence}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
