"use client";

interface AnomalyGaugeProps {
  score: number; // 0-100
  confidence?: number;
}

export default function AnomalyGauge({ score, confidence }: AnomalyGaugeProps) {
  // Determine color based on score
  const getColor = (s: number) => {
    if (s >= 80) return "#ef4444"; // Critical - red
    if (s >= 60) return "#f97316"; // High - orange
    if (s >= 40) return "#eab308"; // Medium - yellow
    return "#22c55e"; // Low - green
  };

  const color = getColor(score);
  const circumference = 2 * Math.PI * 40; // radius = 40
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center justify-center py-4">
      <div className="relative w-[140px] h-[80px]">
        {/* Background arc */}
        <svg
          viewBox="0 0 100 60"
          className="absolute inset-0 w-full h-full"
        >
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke="rgba(255,255,255,0.08)"
            strokeWidth="10"
            strokeLinecap="round"
          />
          {/* Progress arc */}
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke={color}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference / 2}
            strokeDashoffset={strokeDashoffset / 2}
            style={{ transition: "stroke-dashoffset 0.5s ease" }}
          />
        </svg>
        
        {/* Center value */}
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-2">
          <span className="text-3xl font-bold" style={{ color }}>
            {Math.round(score)}%
          </span>
        </div>
      </div>
      
      {/* Labels */}
      <div className="flex items-center justify-between w-full px-4 mt-2">
        <span className="text-[10px] text-gray-500">Normal</span>
        <span className="text-[10px] text-gray-500">Critical</span>
      </div>
      
      {confidence && (
        <p className="mt-2 text-[11px] text-gray-500">
          {confidence}% confidence
        </p>
      )}
    </div>
  );
}
