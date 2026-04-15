"use client";

import { Shield, AlertTriangle, Info, CheckCircle } from "lucide-react";

interface InsightBannerProps {
  keyInsight: string;
  riskLevel?: string;
  confidence?: number;
}

const RISK_CONFIG: Record<string, { icon: React.ReactNode; gradient: string; glow: string; label: string }> = {
  CRITICAL: {
    icon: <AlertTriangle className="h-5 w-5" />,
    gradient: "from-red-500/20 via-red-500/5 to-transparent",
    glow: "shadow-red-500/10",
    label: "Critical Risk",
  },
  HIGH: {
    icon: <Shield className="h-5 w-5" />,
    gradient: "from-orange-500/20 via-orange-500/5 to-transparent",
    glow: "shadow-orange-500/10",
    label: "High Risk",
  },
  MEDIUM: {
    icon: <Info className="h-5 w-5" />,
    gradient: "from-yellow-500/15 via-yellow-500/5 to-transparent",
    glow: "shadow-yellow-500/10",
    label: "Medium Risk",
  },
  LOW: {
    icon: <CheckCircle className="h-5 w-5" />,
    gradient: "from-green-500/15 via-green-500/5 to-transparent",
    glow: "shadow-green-500/10",
    label: "Low Risk",
  },
};

const RISK_BORDER: Record<string, string> = {
  CRITICAL: "border-red-500/30",
  HIGH: "border-orange-500/30",
  MEDIUM: "border-yellow-500/25",
  LOW: "border-green-500/25",
};

const RISK_TEXT: Record<string, string> = {
  CRITICAL: "text-red-400",
  HIGH: "text-orange-400",
  MEDIUM: "text-yellow-400",
  LOW: "text-green-400",
};

export default function InsightBanner({ keyInsight, riskLevel = "MEDIUM", confidence }: InsightBannerProps) {
  const config = RISK_CONFIG[riskLevel] || RISK_CONFIG.MEDIUM;
  const borderColor = RISK_BORDER[riskLevel] || RISK_BORDER.MEDIUM;
  const textColor = RISK_TEXT[riskLevel] || RISK_TEXT.MEDIUM;

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border ${borderColor} bg-gradient-to-r ${config.gradient} p-5 shadow-lg ${config.glow} animate-fadeIn`}
    >
      {/* Subtle background pattern */}
      <div className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)`,
          backgroundSize: '20px 20px'
        }}
      />

      <div className="relative flex items-start gap-4">
        {/* Risk icon */}
        <div className={`flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-white/5 ${textColor}`}>
          {config.icon}
        </div>

        <div className="min-w-0 flex-1">
          {/* Risk badge row */}
          <div className="mb-2 flex items-center gap-3">
            <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${textColor} bg-white/5`}>
              {config.label}
            </span>
            {confidence != null && confidence > 0 && (
              <span className="text-[11px] text-gray-500">
                {confidence}% confidence
              </span>
            )}
          </div>

          {/* Key insight text */}
          <p className="text-sm leading-relaxed text-gray-200 font-medium">
            {keyInsight}
          </p>
        </div>
      </div>
    </div>
  );
}
