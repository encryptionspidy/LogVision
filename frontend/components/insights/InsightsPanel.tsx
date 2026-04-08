"use client";

import { Shield, AlertTriangle, Activity, TrendingUp, BarChart3 } from "lucide-react";
import SeverityPieChart from "../charts/SeverityPieChart";
import ErrorTimelineChart from "../charts/ErrorTimelineChart";
import PatternBarChart from "../charts/PatternBarChart";

interface InsightsPanelProps {
  data: {
    metrics?: {
      total_logs?: number;
      error_rate?: number;
      unique_ips?: number;
      time_span?: string;
    };
    charts?: {
      severity_distribution?: Array<{ level: string; count: number }>;
      timeline?: Array<{ time?: string; timestamp?: string; errors: number }>;
      top_patterns?: Array<{ pattern: string; count: number }>;
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
}

const RISK_STYLES: Record<string, string> = {
  CRITICAL: "bg-red-500/15 text-red-400 border-red-500/20",
  HIGH: "bg-orange-500/15 text-orange-400 border-orange-500/20",
  MEDIUM: "bg-yellow-500/15 text-yellow-400 border-yellow-500/20",
  LOW: "bg-green-500/15 text-green-400 border-green-500/20",
};

export default function InsightsPanel({ data }: InsightsPanelProps) {
  if (!data) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <p className="text-sm text-gray-600">Insights will appear after analysis</p>
      </div>
    );
  }

  const metrics = data.metrics || {};
  const charts = data.charts || {};
  const insights = data.insights || [];
  const anomalies = data.anomalies || [];
  const riskLevel = data.risk_level || "";
  const confidence = data.confidence;

  const errRate =
    typeof metrics.error_rate === "number"
      ? `${(metrics.error_rate * 100).toFixed(1)}%`
      : metrics.error_rate || "—";

  return (
    <div className="flex h-full flex-col overflow-y-auto">
      {/* Risk Badge */}
      {riskLevel && riskLevel !== "UNKNOWN" && (
        <div className="border-b border-white/5 p-4">
          <div
            className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold ${
              RISK_STYLES[riskLevel] || "bg-gray-500/15 text-gray-400 border-gray-500/20"
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

      {/* Metrics */}
      {Object.keys(metrics).length > 0 && (
        <div className="border-b border-white/5 p-4">
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <Activity className="h-3.5 w-3.5" />
            Metrics
          </h3>
          <div className="grid grid-cols-2 gap-2">
            <MetricCard label="Total Logs" value={metrics.total_logs?.toLocaleString() || "—"} />
            <MetricCard label="Error Rate" value={errRate} />
            <MetricCard label="Unique IPs" value={metrics.unique_ips?.toString() || "—"} />
            <MetricCard label="Time Span" value={metrics.time_span || "—"} />
          </div>
        </div>
      )}

      {/* Severity Chart */}
      {charts.severity_distribution && charts.severity_distribution.length > 0 && (
        <div className="border-b border-white/5 p-4">
          <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <BarChart3 className="h-3.5 w-3.5" />
            Severity Distribution
          </h3>
          <SeverityPieChart data={charts.severity_distribution} />
        </div>
      )}

      {/* Timeline Chart */}
      {charts.timeline && charts.timeline.length > 0 && (
        <div className="border-b border-white/5 p-4">
          <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <TrendingUp className="h-3.5 w-3.5" />
            Error Timeline
          </h3>
          <ErrorTimelineChart data={charts.timeline} />
        </div>
      )}

      {/* Top Patterns Chart */}
      {charts.top_patterns && charts.top_patterns.length > 0 && (
        <div className="border-b border-white/5 p-4">
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Top Patterns
          </h3>
          <PatternBarChart data={charts.top_patterns} />
        </div>
      )}

      {/* Key Findings */}
      {insights.length > 0 && (
        <div className="border-b border-white/5 p-4">
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <AlertTriangle className="h-3.5 w-3.5" />
            Key Findings
          </h3>
          <div className="space-y-2">
            {insights.slice(0, 5).map((item, i) => (
              <div key={i} className="rounded-lg bg-white/3 p-2.5">
                <p className="text-xs font-medium text-text-primary">{item.title}</p>
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

      {/* Anomalies */}
      {anomalies.length > 0 && (
        <div className="p-4">
          <h3 className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Anomalies
          </h3>
          <div className="space-y-1.5">
            {anomalies.slice(0, 8).map((a, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg bg-white/3 px-2.5 py-2"
              >
                <span className="text-[11px] text-gray-300 truncate max-w-[180px]">
                  {a.pattern}
                </span>
                <span className="text-[10px] font-medium text-gray-500">
                  {a.count || ""} {a.severity || ""}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-white/3 p-2.5">
      <p className="text-[10px] uppercase tracking-wider text-gray-600">{label}</p>
      <p className="mt-0.5 text-sm font-semibold text-text-primary truncate">{value}</p>
    </div>
  );
}
