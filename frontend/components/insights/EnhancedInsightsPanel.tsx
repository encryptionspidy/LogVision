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
  Target,
  GitBranch,
  Gauge,
} from "lucide-react";
import SeverityPieChart from "../charts/SeverityPieChart";
import ErrorTimelineChart from "../charts/ErrorTimelineChart";
import PatternBarChart from "../charts/PatternBarChart";
import ComponentImpactChart from "../charts/ComponentImpactChart";
import AnomalyGauge from "../charts/AnomalyGauge";
import SystemHealthGauge from "../charts/SystemHealthGauge";
import CausalFlowMini from "../charts/CausalFlowMini";
import ConfidenceMeter from "../charts/ConfidenceMeter";

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
    // SRE intelligence fields
    key_insight?: string;
    core_problem?: {
      title?: string;
      severity?: string;
    };
    causal_chain?: Array<{
      step: number;
      event: string;
      component?: string;
    }>;
    impact_assessment?: {
      blast_radius?: string;
      stability_score?: number;
      affected_components?: Array<{ component: string; impact: string; error_count: number }>;
    };
    root_cause_hypothesis?: {
      hypothesis?: string;
      confidence?: number;
      uncertainties?: string[];
    };
    recommended_actions?: Array<{
      priority: number;
      action: string;
    }>;
    confidence_explanation?: string;
    risk_level?: string;
    confidence?: number | string;
  } | null;
  compact?: boolean;
}

const RISK_STYLES: Record<string, { bg: string; text: string; border: string; glow: string }> = {
  CRITICAL: { bg: "bg-red-500/15", text: "text-red-400", border: "border-red-500/20", glow: "shadow-red-500/5" },
  HIGH: { bg: "bg-orange-500/15", text: "text-orange-400", border: "border-orange-500/20", glow: "shadow-orange-500/5" },
  MEDIUM: { bg: "bg-yellow-500/15", text: "text-yellow-400", border: "border-yellow-500/20", glow: "shadow-yellow-500/5" },
  LOW: { bg: "bg-green-500/15", text: "text-green-400", border: "border-green-500/20", glow: "shadow-green-500/5" },
};

const SEVERITY_PRIORITY: Record<string, number> = {
  CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, ERROR: 3, WARNING: 2, INFO: 1,
};

export default function InsightsPanel({ data, compact = false }: InsightsPanelProps) {
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div className="text-center">
          <Activity className="h-8 w-8 mx-auto mb-2 text-gray-600 animate-pulse" />
          <p className="text-sm text-gray-500">Insights will appear after analysis</p>
          <p className="text-[11px] text-gray-600 mt-1">Submit logs to begin</p>
        </div>
      </div>
    );
  }

  const metrics = data.metrics || {};
  const charts = data.charts || {};
  const insights = data.insights || [];
  const riskLevel = data.risk_level || "";
  const confidence = typeof data.confidence === "number" ? data.confidence : parseInt(String(data.confidence)) || 0;
  const anomalyScore = metrics.anomaly_score ?? 0;

  // SRE intelligence
  const keyInsight = data.key_insight || "";
  const coreProblem = data.core_problem;
  const causalChain = data.causal_chain || [];
  const impactAssessment = data.impact_assessment;
  const rootCauseHypothesis = data.root_cause_hypothesis;
  const recommendedActions = data.recommended_actions || [];
  const confidenceExplanation = data.confidence_explanation || "";

  // Calculate system health (inverse of anomaly score)
  const systemHealth = Math.max(0, 100 - anomalyScore);

  const toggleSection = (id: string) => {
    setExpandedSection(expandedSection === id ? null : id);
  };

  if (compact) {
    return renderCompactView();
  }

  return (
    <div className="flex h-full flex-col overflow-y-auto scrollbar-thin">
      {/* Risk Assessment Header */}
      {riskLevel && riskLevel !== "UNKNOWN" && (
        <div className="border-b border-white/5 p-4">
          <div className="flex items-center justify-between">
            <div
              className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold shadow-lg ${
                RISK_STYLES[riskLevel]?.bg || "bg-gray-500/15"
              } ${RISK_STYLES[riskLevel]?.text || "text-gray-400"} ${
                RISK_STYLES[riskLevel]?.border || "border-gray-500/20"
              } ${RISK_STYLES[riskLevel]?.glow || ""}`}
            >
              <Shield className="h-3.5 w-3.5" />
              {riskLevel} RISK
            </div>
            {confidence > 0 && (
              <span className="text-[11px] text-gray-500 tabular-nums">
                {confidence}% conf.
              </span>
            )}
          </div>
          {keyInsight && (
            <p className="mt-2 text-[12px] text-gray-300 leading-relaxed">
              {keyInsight}
            </p>
          )}
        </div>
      )}

      <div className="p-4 space-y-3">
        {/* System Health Gauge */}
        {anomalyScore > 0 && (
          <SectionCard
            id="health"
            title="System Health"
            icon={<Gauge className="h-4 w-4" />}
            expanded={expandedSection === "health"}
            onToggle={() => toggleSection("health")}
            priority={systemHealth < 50 ? "high" : "medium"}
            preview={`${Math.round(systemHealth)}% stability`}
          >
            <SystemHealthGauge score={systemHealth} />
          </SectionCard>
        )}

        {/* Confidence Meter */}
        {confidence > 0 && (
          <SectionCard
            id="confidence"
            title="Analysis Confidence"
            icon={<Target className="h-4 w-4" />}
            expanded={expandedSection === "confidence"}
            onToggle={() => toggleSection("confidence")}
            priority="medium"
            preview={`${confidence}% confidence`}
          >
            <ConfidenceMeter confidence={confidence} explanation={confidenceExplanation} />
          </SectionCard>
        )}

        {/* Causal Chain Flow */}
        {causalChain.length > 0 && (
          <SectionCard
            id="causal"
            title="Failure Chain"
            icon={<GitBranch className="h-4 w-4" />}
            expanded={expandedSection === "causal"}
            onToggle={() => toggleSection("causal")}
            priority="high"
            preview={`${causalChain.length} steps identified`}
          >
            <CausalFlowMini chain={causalChain} />
          </SectionCard>
        )}

        {/* Severity Distribution */}
        {hasSeverityData(charts.severity_distribution) && (
          <SectionCard
            id="severity"
            title="Severity Distribution"
            icon={<Shield className="h-4 w-4" />}
            expanded={expandedSection === "severity"}
            onToggle={() => toggleSection("severity")}
            priority={hasCriticalSeverity(charts.severity_distribution) ? "high" : "medium"}
            preview={getTopSeverity(charts.severity_distribution)}
          >
            <SeverityPieChart data={charts.severity_distribution!} />
          </SectionCard>
        )}

        {/* Error Timeline */}
        {hasTimelineData(charts.timeline) && (
          <SectionCard
            id="timeline"
            title="Error Timeline"
            icon={<TrendingUp className="h-4 w-4" />}
            expanded={expandedSection === "timeline"}
            onToggle={() => toggleSection("timeline")}
            priority="medium"
            preview={getTimelineInsight(charts.timeline)}
          >
            <ErrorTimelineChart data={charts.timeline!} />
          </SectionCard>
        )}

        {/* Component Impact */}
        {hasComponentData(charts.affected_components) && (
          <SectionCard
            id="components"
            title="Component Impact"
            icon={<Layers className="h-4 w-4" />}
            expanded={expandedSection === "components"}
            onToggle={() => toggleSection("components")}
            priority="medium"
            preview={getTopComponent(charts.affected_components)}
          >
            <ComponentImpactChart data={charts.affected_components!} />
          </SectionCard>
        )}

        {/* Top Patterns */}
        {hasPatternData(charts.top_patterns) && (
          <SectionCard
            id="patterns"
            title="Top Patterns"
            icon={<BarChart3 className="h-4 w-4" />}
            expanded={expandedSection === "patterns"}
            onToggle={() => toggleSection("patterns")}
            priority="low"
            preview={getTopPattern(charts.top_patterns)}
          >
            <PatternBarChart data={charts.top_patterns!} />
          </SectionCard>
        )}

        {/* No data fallback */}
        {!anomalyScore && !causalChain.length && !hasSeverityData(charts.severity_distribution) && (
          <p className="text-xs text-gray-500 text-center py-4">
            No visual data available for these logs
          </p>
        )}
      </div>

      {/* Key Findings */}
      {insights.length > 0 && (
        <div className="border-t border-white/5 p-4">
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <AlertTriangle className="h-3.5 w-3.5" />
            Key Findings
          </h3>
          <div className="space-y-2">
            {insights.slice(0, 5).map((item, i) => {
              const severityColor = item.severity === "CRITICAL" ? "border-red-500/40" :
                item.severity === "HIGH" ? "border-orange-500/40" :
                item.severity === "MEDIUM" ? "border-yellow-500/40" : "border-[#ff8a5b]";
              return (
                <div
                  key={i}
                  className={`rounded-lg bg-white/3 p-2.5 border-l-2 ${severityColor}`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs font-medium text-gray-200">{item.title}</p>
                    {item.confidence && (
                      <span className="flex-shrink-0 text-[10px] text-gray-500 tabular-nums">
                        {item.confidence}%
                      </span>
                    )}
                  </div>
                  {item.description && (
                    <p className="mt-0.5 text-[11px] text-gray-500 line-clamp-2">
                      {item.description}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recommended Actions Summary */}
      {recommendedActions.length > 0 && (
        <div className="border-t border-white/5 p-4">
          <h3 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <Zap className="h-3.5 w-3.5" />
            Quick Actions
          </h3>
          <div className="space-y-1.5">
            {recommendedActions.slice(0, 3).map((action, i) => (
              <div key={i} className="flex items-start gap-2 rounded-lg bg-white/3 p-2">
                <span className="flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full bg-[#ff8a5b]/15 text-[9px] font-bold text-[#ff8a5b]">
                  {action.priority || i + 1}
                </span>
                <p className="text-[11px] text-gray-300 leading-snug line-clamp-2">
                  {action.action}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Root Cause Hypothesis Summary */}
      {rootCauseHypothesis?.hypothesis && (
        <div className="border-t border-white/5 p-4">
          <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-gray-500">
            <Target className="h-3.5 w-3.5" />
            Root Cause
          </h3>
          <p className="text-[12px] text-gray-300 leading-relaxed">
            {rootCauseHypothesis.hypothesis}
          </p>
          {rootCauseHypothesis.confidence && (
            <div className="mt-2 flex items-center gap-2">
              <div className="h-1 flex-1 rounded-full bg-white/8 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${rootCauseHypothesis.confidence}%`,
                    backgroundColor: rootCauseHypothesis.confidence >= 70 ? "#22c55e" :
                      rootCauseHypothesis.confidence >= 50 ? "#eab308" : "#f97316",
                  }}
                />
              </div>
              <span className="text-[10px] text-gray-500 tabular-nums">
                {rootCauseHypothesis.confidence}%
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );

  function renderCompactView() {
    return (
      <div className="flex h-full flex-col">
        {keyInsight && (
          <div className="px-3 py-2 border-b border-white/5">
            <p className="text-[11px] text-gray-300 line-clamp-2">{keyInsight}</p>
          </div>
        )}
        {causalChain.length > 0 && (
          <div className="px-3 py-2 border-b border-white/5">
            <div className="flex items-center gap-2 mb-1">
              <GitBranch className="h-3 w-3 text-[#ff8a5b]" />
              <span className="text-[10px] text-gray-500">{causalChain.length}-step failure chain</span>
            </div>
          </div>
        )}
        {anomalyScore > 0 && (
          <div className="px-3 py-2 border-b border-white/5">
            <div className="flex items-center gap-2">
              <Gauge className="h-3 w-3 text-[#ff8a5b]" />
              <span className="text-[10px] text-gray-400">Health: {Math.round(100 - anomalyScore)}%</span>
            </div>
          </div>
        )}
      </div>
    );
  }
}

// Reusable section card component
function SectionCard({
  id,
  title,
  icon,
  expanded,
  onToggle,
  priority,
  preview,
  children,
}: {
  id: string;
  title: string;
  icon: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  priority: "high" | "medium" | "low";
  preview?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-white/8 bg-[#121214] overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full px-3 py-2.5 flex items-center justify-between hover:bg-white/[0.02] transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-[#ff8a5b]">{icon}</span>
          <span className="text-xs font-medium text-gray-300">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          {priority === "high" && (
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
          )}
          {expanded ? (
            <ChevronUp className="h-3.5 w-3.5 text-gray-500" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 text-gray-500" />
          )}
        </div>
      </button>

      {/* Preview when collapsed */}
      {!expanded && preview && (
        <div className="px-3 pb-2">
          <p className="text-[11px] text-gray-500 truncate">{preview}</p>
        </div>
      )}

      {/* Expanded content */}
      {expanded && (
        <div className="px-3 pb-3 border-t border-white/5 animate-slideDown">
          {preview && (
            <p className="text-[11px] text-gray-400 mt-2 mb-1 italic">{preview}</p>
          )}
          {children}
        </div>
      )}
    </div>
  );
}

// Helper functions
function hasSeverityData(data?: Array<{ level: string; count: number }>) {
  return data && data.length > 0 && data.some((d) => d.count > 0);
}

function hasCriticalSeverity(data?: Array<{ level: string; count: number }>) {
  return data?.some((d) => (d.level === "CRITICAL" || d.level === "ERROR") && d.count > 0);
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
  return top ? `${Math.round((top.count / total) * 100)}% are ${top.level}` : undefined;
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
  return `${sorted[0]?.component}: ${sorted[0]?.failures} failures`;
}

function getTopPattern(data?: Array<{ pattern: string; count: number }>) {
  if (!data || data.length === 0) return undefined;
  const sorted = [...data].sort((a, b) => b.count - a.count);
  return `${sorted[0]?.pattern} (${sorted[0]?.count}×)`;
}
