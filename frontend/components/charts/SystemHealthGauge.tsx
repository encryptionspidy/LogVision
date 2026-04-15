"use client";

interface SystemHealthGaugeProps {
  score: number; // 0-100 (0 = critical, 100 = healthy)
  label?: string;
}

export default function SystemHealthGauge({ score, label }: SystemHealthGaugeProps) {
  // Clamp score
  const s = Math.max(0, Math.min(100, score));

  // Color based on health (inverse of anomaly - higher = healthier)
  const getColor = (val: number) => {
    if (val >= 80) return { main: "#22c55e", bg: "rgba(34,197,94,0.15)" };
    if (val >= 60) return { main: "#eab308", bg: "rgba(234,179,8,0.15)" };
    if (val >= 40) return { main: "#f97316", bg: "rgba(249,115,22,0.15)" };
    return { main: "#ef4444", bg: "rgba(239,68,68,0.15)" };
  };

  const getLabel = (val: number) => {
    if (val >= 80) return "Healthy";
    if (val >= 60) return "Degraded";
    if (val >= 40) return "Unstable";
    return "Critical";
  };

  const { main, bg } = getColor(s);
  const healthLabel = label || getLabel(s);

  // SVG arc parameters
  const radius = 44;
  const circumference = Math.PI * radius; // Half circle
  const progress = (s / 100) * circumference;

  return (
    <div className="flex flex-col items-center py-3">
      <div className="relative w-[140px] h-[80px]">
        <svg viewBox="0 0 100 55" className="w-full h-full">
          {/* Background arc */}
          <path
            d="M 6 50 A 44 44 0 0 1 94 50"
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="8"
            strokeLinecap="round"
          />
          {/* Progress arc */}
          <path
            d="M 6 50 A 44 44 0 0 1 94 50"
            fill="none"
            stroke={main}
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={circumference - progress}
            style={{
              transition: "stroke-dashoffset 0.8s ease-out, stroke 0.5s ease",
              filter: `drop-shadow(0 0 6px ${main}40)`,
            }}
          />
          {/* Score glow dot at end */}
          <circle
            cx="50"
            cy="50"
            r="3"
            fill={bg}
            style={{ opacity: 0 }}
          />
        </svg>

        {/* Center label */}
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-0">
          <span
            className="text-2xl font-bold tabular-nums"
            style={{ color: main }}
          >
            {Math.round(s)}
          </span>
        </div>
      </div>

      {/* Status label */}
      <div className="mt-1 flex items-center gap-1.5">
        <span
          className="h-2 w-2 rounded-full"
          style={{ backgroundColor: main, boxShadow: `0 0 6px ${main}60` }}
        />
        <span className="text-[11px] font-medium text-gray-400">
          {healthLabel}
        </span>
      </div>

      {/* Scale */}
      <div className="mt-1 flex w-[120px] items-center justify-between">
        <span className="text-[9px] text-gray-600">Critical</span>
        <span className="text-[9px] text-gray-600">Healthy</span>
      </div>
    </div>
  );
}
