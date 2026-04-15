"use client";

interface ConfidenceMeterProps {
  confidence: number; // 0-100
  explanation?: string;
}

export default function ConfidenceMeter({ confidence, explanation }: ConfidenceMeterProps) {
  const c = Math.max(0, Math.min(100, confidence));

  const getColor = (val: number) => {
    if (val >= 80) return "#22c55e";
    if (val >= 60) return "#eab308";
    if (val >= 40) return "#f97316";
    return "#ef4444";
  };

  const getLabel = (val: number) => {
    if (val >= 80) return "High confidence";
    if (val >= 60) return "Moderate confidence";
    if (val >= 40) return "Limited confidence";
    return "Low confidence";
  };

  const color = getColor(c);
  const label = getLabel(c);

  return (
    <div className="py-2">
      {/* Label row */}
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] text-gray-400">{label}</span>
        <span className="text-[11px] font-semibold tabular-nums" style={{ color }}>
          {Math.round(c)}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="relative h-2 w-full overflow-hidden rounded-full bg-white/8">
        <div
          className="absolute inset-y-0 left-0 rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${c}%`,
            backgroundColor: color,
            boxShadow: `0 0 8px ${color}40`,
          }}
        />
        {/* Tick marks */}
        <div className="absolute inset-0 flex items-center justify-between px-[1px]">
          {[25, 50, 75].map((tick) => (
            <div
              key={tick}
              className="h-full w-[1px] bg-white/10"
              style={{ marginLeft: `${tick}%`, position: "absolute", left: 0 }}
            />
          ))}
        </div>
      </div>

      {/* Explanation */}
      {explanation && (
        <p className="mt-2 text-[10px] text-gray-500 leading-relaxed line-clamp-3">
          {explanation}
        </p>
      )}
    </div>
  );
}
