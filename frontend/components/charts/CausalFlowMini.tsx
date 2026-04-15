"use client";

interface CausalStep {
  step: number;
  event: string;
  component?: string;
}

interface CausalFlowMiniProps {
  chain: CausalStep[];
  maxSteps?: number;
}

const STEP_COLORS = ["#eab308", "#f97316", "#ef4444", "#dc2626", "#b91c1c"];

export default function CausalFlowMini({ chain, maxSteps = 4 }: CausalFlowMiniProps) {
  if (!chain || chain.length === 0) return null;

  const steps = chain.slice(0, maxSteps);

  return (
    <div className="py-2">
      <div className="relative ml-2">
        {/* Connecting line */}
        <div className="absolute left-[5px] top-1 bottom-1 w-[2px] bg-gradient-to-b from-yellow-500/30 via-orange-500/30 to-red-500/30" />

        <div className="space-y-2">
          {steps.map((step, i) => {
            const color = STEP_COLORS[Math.min(i, STEP_COLORS.length - 1)];

            return (
              <div key={i} className="relative flex items-start gap-3 ml-4">
                {/* Dot */}
                <div
                  className="absolute -left-[17px] top-1.5 h-3 w-3 rounded-full ring-2 ring-[#0a0a0b] z-10"
                  style={{ backgroundColor: color }}
                />

                <div className="min-w-0">
                  {step.component && (
                    <span className="text-[9px] font-medium text-gray-500 uppercase tracking-wide">
                      {step.component}
                    </span>
                  )}
                  <p className="text-[11px] text-gray-300 leading-snug line-clamp-2">
                    {step.event}
                  </p>
                </div>
              </div>
            );
          })}

          {chain.length > maxSteps && (
            <div className="relative ml-4">
              <div className="absolute -left-[17px] top-1 h-3 w-3 rounded-full bg-gray-600 ring-2 ring-[#0a0a0b]" />
              <p className="text-[10px] text-gray-600 italic">
                +{chain.length - maxSteps} more steps
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
