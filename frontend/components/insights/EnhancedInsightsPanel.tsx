"use client";

import { useState } from "react";
import {
  Shield,
  AlertTriangle,
  Activity,
  TrendingUp,
  BarChart3,
  Layers,
  Zap,
  ChevronDown,
  ChevronUp,
  Maximize2,
  X
} from "lucide-react";
import SeverityPieChart from "../charts/SeverityPieChart";
import ErrorTimelineChart from "../charts/ErrorTimelineChart";
import PatternBarChart from "../charts/PatternBarChart";
import ComponentImpactChart from "../charts/ComponentImpactChart";
import AnomalyGauge from "../charts/AnomalyGauge";

// Card types for visual intelligence
interface ChartCard {
  id: string;
  title: string;
  icon: React.ReactNode;
  insight?: string;
  priority: "high" | "medium" | "low";
  hasData: boolean;
}

interface InsightsPanelProps {
  data: {
    metrics?: {
      total_logs?: number;
      error_rate?: number;
      unique_ips?: number;
      time_span?: string;
      anomaly_score?: number;
    };
    charts?: {
      severity_distribution?: Array<{ level: string; count: number }>;
      timeline?: Array<{ time?: string; timestamp?: string; errors: number; severity?: string }>;
      top_patterns?: Array<{ pattern: string; count: number }>;
      affected_components?: Array<{ component: string; failures: number; severity?: string }>;
    };
    insights?: Array<{
      title: string;
      description?: string;
      severity?: string;
      confidence?: number;
    }>;
    anomalies?: Array<{
      pattern: string;
      count?: number;
      severity?: string;
    }>;
    risk_level?: string;
    confidence?: number | string;
  } | null;
  compact?: boolean;
}

const RISK_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  CRITICAL: { bg: "bg-red-500/15", text: "text-red-400", border: "border-red-500/20" },
  HIGH: { bg: "bg-orange-500/15", text: "text-orange-400", border: "border-orange-500/20" },
  MEDIUM: { bg: "bg-yellow-500/15", text: "text-yellow-400", border: "border-yellow-500/20" },
  LOW: { bg: "bg-green-500/15", text: "text-green-400", border: "border-green-500/20" },
};

const SEVERITY_PRIORITY: Record<string, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MEDIUM: 2,
  LOW: 1,
  ERROR: 3,
  WARNING: 2,
  INFO: 1,
};

export default function InsightsPanel({ data, compact = false }: InsightsPanelProps) {
  const [expandedCard, setExpandedCard] = useState<string | null>(null);

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="text-center">
          <Activity className="h-8 w-8 mx-auto mb-2 text-gray-600" />
          <p className="text-sm text-gray-500">Insights will appear after analysis</p>
        </div>
      </div>
    );
  }

  const metrics = data.metrics || {};
  const charts = data.charts || {};
  const insights = data.insights || [];
  const anomalies = data.anomalies || [];
  const riskLevel = data.risk_level || "";
  const confidence = data.confidence;
  const anomalyScore = metrics.anomaly_score ?? 0;

  // Determine card visibility based on available data
  const cards = [
    {
      id: "severity" as const,
      title: "Severity Distribution",
      icon: <Shield className="h-4 w-4" />,
      insight: getTopSeverity(charts.severity_distribution),
      priority: hasSeverityData(charts.severity_distribution) ? ("high" as const) : ("low" as const),
      hasData: hasSeverityData(charts.severity_distribution),
    },
    {
      id: "anomaly" as const,
      title: "Anomaly Score",
      icon: <Zap className="h-4 w-4" />,
      insight: anomalyScore > 50 ? "Unusual patterns detected" : "System appears stable",
      priority: anomalyScore > 50 ? ("high" as const) : ("medium" as const),
      hasData: anomalyScore > 0,
    },
    {
      id: "timeline" as const,
      title: "Error Timeline",
      icon: <TrendingUp className="h-4 w-4" />,
      insight: getTimelineInsight(charts.timeline),
      priority: hasTimelineData(charts.timeline) ? ("high" as const) : ("low" as const),
      hasData: hasTimelineData(charts.timeline),
    },
    {
      id: "components" as const,
      title: "Component Impact",
      icon: <Layers className="h-4 w-4" />,
      insight: getTopComponent(charts.affected_components),
      priority: hasComponentData(charts.affected_components) ? ("high" as const) : ("low" as const),
      hasData: hasComponentData(charts.affected_components),
    },
    {
      id: "patterns" as const,
      title: "Top Patterns",
      icon: <BarChart3 className="h-4 w-4" />,
      insight: getTopPattern(charts.top_patterns),
      priority: hasPatternData(charts.top_patterns) ? ("medium" as const) : ("low" as const),
      hasData: hasPatternData(charts.top_patterns),
    },
  ].filter((c): c is typeof c & { hasData: true } => !!c.hasData);

  // Sort by priority
  const priorityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
  cards.sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);

  if (compact) {
    return renderCompactView(cards, data, expandedCard, setExpandedCard);
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {/* Risk Header */}
      {riskLevel && riskLevel !== "UNKNOWN" && (
        <div className="border-b border-white/5 p-4">
          <div
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${
              RISK_STYLES[riskLevel]?.bg || "bg-gray-500/15"
            } ${RISK_STYLES[riskLevel]?.text || "text-gray-400"} ${
              RISK_STYLES[riskLevel]?.border || "border-gray-500/20"
            }`}
          >
            <Shield className="h-3.5 w-3.5" />
            {riskLevel} RISK
          </div>
          {confidence && (
            <p className="mt-1 text-[11px] text-gray-500">
              {confidence}% confidence
            </p>
          )}
        </div>
      )}

      {/* Visual Intelligence Cards */}
      <div className="p-4 space-y-3">
        {cards.length === 0 && (
          <p className="text-xs text-gray-500 text-center py-4">
            No visual data available for these logs
          </p>
        )}

        {cards.map((card) => (
          <div
            key={card.id}
            className="rounded-xl border border-white/8 bg-[#121214] overflow-hidden"
          >
            {/* Card Header */}
            <button
              onClick={() => setExpandedCard(expandedCard === card.id ? null : card.id)}
              className="w-full px-3 py-2.5 flex items-center justify-between hover:bg-white/3 transition-colors"
            >
              <div className="flex items-center gap-2">
                <span className="text-[#ff8a5b]">{card.icon}</span>
                <span className="text-xs font-medium text-gray-300">{card.title}</span>
              </div>
              <div className="flex items-center gap-2">
                {card.priority === "high" && (
                  <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
                )}
                {expandedCard === card.id ? (
                  <ChevronUp className="h-3.5 w-3.5 text-gray-500" />
                ) : (
                  <ChevronDown className="h-3.5 w-3.5 text-gray-500" />
                )}
              </div>
            </button>

            {/* Card Preview (when collapsed) */}
            {expandedCard !== card.id && card.insight && (
              <div className="px-3 pb-2">
                <p className="text-[11px] text-gray-500 truncate">{card.insight}</p>
                <MiniChart cardId={card.id} data={data} />
              </div>
            )}

            {/* Expanded Content */}
            {expandedCard === card.id && (
              <div className="px-3 pb-3 border-t border-white/5">
                {card.insight && (
                  <p className="text-[11px] text-gray-400 mt-2 mb-2 italic">
                    {card.insight}
                  </p>
                )}
                <FullChart cardId={card.id} data={data} />
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Key Findings */}
      {insights.length > 0 && (
        <div className="border-t border-white/5 p-4">
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <AlertTriangle className="h-3.5 w-3.5" />
            Key Findings
          </h3>
          <div className="space-y-2">
            {insights.slice(0, 5).map((item, i) => (
              <div
                key={i}
                className="rounded-lg bg-white/3 p-2.5 border-l-2 border-[#ff8a5b]"
              >
                <p className="text-xs font-medium text-gray-200">{item.title}</p>
                {item.description && (
                  <p className="mt-0.5 text-[11px] text-gray-500 line-clamp-2">
                    {item.description}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Compact view for sidebar
function renderCompactView(
  cards: ChartCard[],
  data: InsightsPanelProps["data"],
  expandedCard: string | null,
  setExpandedCard: (id: string | null) => void
) {
  return (
    <div className="flex h-full flex-col">
      {cards.slice(0, 3).map((card) => (
        <div
          key={card.id}
          className="px-3 py-2 border-b border-white/5 hover:bg-white/3 cursor-pointer"
          onClick={() => setExpandedCard(expandedCard === card.id ? null : card.id)}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-[#ff8a5b]">{card.icon}</span>
              <span className="text-[11px] text-gray-400">{card.title}</span>
            </div>
            {card.priority === "high" && (
              <span className="w-1 h-1 rounded-full bg-red-500" />
            )}
          </div>
          {card.insight && (
            <p className="text-[10px] text-gray-500 mt-0.5 truncate">{card.insight}</p>
          )}
        </div>
      ))}
    </div>
  );
}

// Mini chart preview (when collapsed)
function MiniChart({ cardId, data }: { cardId: string; data: InsightsPanelProps["data"] }) {
  const charts = data?.charts || {};
  const metrics = data?.metrics || {};

  switch (cardId) {
    case "severity":
      if (!charts.severity_distribution?.length) return null;
      const total = charts.severity_distribution.reduce((s, d) => s + d.count, 0);
      const maxSeverity = [...charts.severity_distribution].sort(
        (a, b) => (SEVERITY_PRIORITY[b.level] || 0) - (SEVERITY_PRIORITY[a.level] || 0)
      )[0];
      return (
        <div className="flex items-center gap-2 mt-1">
          <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
            {charts.severity_distribution.map((d, i) => (
              <div
                key={i}
                className="h-full inline-block"
                style={{
                  width: `${(d.count / total) * 100}%`,
                  backgroundColor:
                    d.level === "CRITICAL"
                      ? "#ef4444"
                      : d.level === "HIGH"
                      ? "#f97316"
                      : d.level === "MEDIUM"
                      ? "#eab308"
                      : "#22c55e",
                }}
              />
            ))}
          </div>
          <span className="text-[10px] text-gray-500">
            {Math.round((maxSeverity?.count || 0) / total * 100)}% {maxSeverity?.level}
          </span>
        </div>
      );

    case "anomaly":
      const score = metrics.anomaly_score || 0;
      return (
        <div className="flex items-center gap-2 mt-1">
          <div className="flex-1 h-1.5 bg-white/10 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${score}%`,
                backgroundColor:
                  score >= 80 ? "#ef4444" : score >= 60 ? "#f97316" : score >= 40 ? "#eab308" : "#22c55e",
              }}
            />
          </div>
          <span className="text-[10px] text-gray-500">{Math.round(score)}%</span>
        </div>
      );

    case "timeline":
      if (!charts.timeline?.length) return null;
      const maxErrors = Math.max(...charts.timeline.map((t) => t.errors || 0));
      return (
        <div className="flex items-end gap-0.5 mt-1 h-6">
          {charts.timeline.slice(0, 10).map((t, i) => (
            <div
              key={i}
              className="flex-1 bg-[#ff8a5b]/60 rounded-t"
              style={{ height: `${((t.errors || 0) / (maxErrors || 1)) * 100}%` }}
            />
          ))}
        </div>
      );

    case "components":
      if (!charts.affected_components?.length) return null;
      const topComp = [...charts.affected_components].sort((a, b) => b.failures - a.failures)[0];
      return (
        <div className="flex items-center gap-2 mt-1">
          <Layers className="h-3 w-3 text-gray-500" />
          <span className="text-[10px] text-gray-500 truncate">
            {topComp.component}: {topComp.failures} issues
          </span>
        </div>
      );

    case "patterns":
      if (!charts.top_patterns?.length) return null;
      const topPattern = [...charts.top_patterns].sort((a, b) => b.count - a.count)[0];
      return (
        <div className="flex items-center gap-2 mt-1">
          <BarChart3 className="h-3 w-3 text-gray-500" />
          <span className="text-[10px] text-gray-500 truncate">
            {topPattern.pattern}: {topPattern.count}×
          </span>
        </div>
      );

    default:
      return null;
  }
}

// Full chart (when expanded)
function FullChart({ cardId, data }: { cardId: string; data: InsightsPanelProps["data"] }) {
  const charts = data?.charts || {};
  const metrics = data?.metrics || {};

  switch (cardId) {
    case "severity":
      return charts.severity_distribution ? (
        <SeverityPieChart data={charts.severity_distribution} />
      ) : null;

    case "anomaly":
      return <AnomalyGauge score={metrics.anomaly_score || 0} confidence={data?.confidence as number} />;

    case "timeline":
      return charts.timeline ? <ErrorTimelineChart data={charts.timeline} /> : null;

    case "components":
      return charts.affected_components ? (
        <ComponentImpactChart data={charts.affected_components} />
      ) : null;

    case "patterns":
      return charts.top_patterns ? <PatternBarChart data={charts.top_patterns} /> : null;

    default:
      return null;
  }
}

// Helper functions
function hasSeverityData(data?: Array<{ level: string; count: number }>) {
  return data && data.length > 0 && data.some((d) => d.count > 0);
}

function hasTimelineData(data?: Array<{ errors: number }>) {
  return data && data.length > 1;
}

function hasComponentData(data?: Array<{ component: string; failures: number }>) {
  return data && data.length > 0;
}

function hasPatternData(data?: Array<{ pattern: string; count: number }>) {
  return data && data.length > 0;
}

function getTopSeverity(data?: Array<{ level: string; count: number }>) {
  if (!data || data.length === 0) return undefined;
  const sorted = [...data].sort(
    (a, b) => (SEVERITY_PRIORITY[b.level] || 0) - (SEVERITY_PRIORITY[a.level] || 0)
  );
  const total = data.reduce((s, d) => s + d.count, 0);
  const top = sorted[0];
  return top ? `${Math.round((top.count / total) * 100)}% are ${top.level} severity` : undefined;
}

function getTimelineInsight(data?: Array<{ time?: string; timestamp?: string; errors: number }>) {
  if (!data || data.length === 0) return undefined;
  const maxErrors = Math.max(...data.map((d) => d.errors || 0));
  const peakTime = data.find((d) => d.errors === maxErrors);
  return peakTime ? `Peak: ${maxErrors} errors at ${peakTime.time || peakTime.timestamp}` : undefined;
}

function getTopComponent(data?: Array<{ component: string; failures: number }>) {
  if (!data || data.length === 0) return undefined;
  const sorted = [...data].sort((a, b) => b.failures - a.failures);
  return `${sorted[0]?.component} most affected (${sorted[0]?.failures} failures)`;
}

function getTopPattern(data?: Array<{ pattern: string; count: number }>) {
  if (!data || data.length === 0) return undefined;
  const sorted = [...data].sort((a, b) => b.count - a.count);
  return `${sorted[0]?.pattern} most frequent (${sorted[0]?.count} occurrences)`;
}
