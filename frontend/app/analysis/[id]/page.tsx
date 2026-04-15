"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect, useRef } from "react";
import { Loader2, PanelLeftClose, PanelLeftOpen, Shield } from "lucide-react";
import HistorySidebar from "@/components/sidebar/HistorySidebar";
import ChatMessage from "@/components/chat/ChatMessage";
import ChatInput from "@/components/chat/ChatInput";
import InsightsPanel from "@/components/insights/EnhancedInsightsPanel";
import InsightBanner from "@/components/chat/InsightBanner";
import CausalChainCard from "@/components/chat/CausalChainCard";
import EvidenceBlock from "@/components/chat/EvidenceBlock";
import ActionItems from "@/components/chat/ActionItems";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const RISK_COLORS: Record<string, string> = {
  CRITICAL: "text-red-400",
  HIGH: "text-orange-400",
  MEDIUM: "text-yellow-400",
  LOW: "text-green-400",
};

export default function AnalysisChatPage() {
  const params = useParams();
  const router = useRouter();
  const analysisId = params.id as string;
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadingStage, setLoadingStage] = useState("");
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [insightsData, setInsightsData] = useState<any>(null);
  // SRE intelligence state
  const [keyInsight, setKeyInsight] = useState("");
  const [riskLevel, setRiskLevel] = useState("");
  const [confidence, setConfidence] = useState(0);
  const [causalChain, setCausalChain] = useState<any[]>([]);
  const [recommendedActions, setRecommendedActions] = useState<any[]>([]);
  const [evidence, setEvidence] = useState<any[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    loadAnalysis();
  }, [analysisId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const loadAnalysis = async () => {
    setInitialLoading(true);
    try {
      const res = await fetch(
        `${API_BASE}/api/analysis/${analysisId}`
      );
      if (!res.ok) throw new Error(`Failed to load: ${res.status}`);
      const data = await res.json();

      // Set SRE intelligence data
      setKeyInsight(data.key_insight || "");
      setRiskLevel(data.risk_level || "");
      setConfidence(
        data.root_cause_hypothesis?.confidence ||
        (typeof data.confidence === "number" ? data.confidence : parseInt(data.confidence) || 0)
      );
      setCausalChain(data.causal_chain || []);
      setRecommendedActions(data.recommended_actions || []);

      // Extract evidence from insights
      const allEvidence: any[] = [];
      (data.insights || []).forEach((insight: any) => {
        (insight.evidence || []).forEach((ev: string) => {
          allEvidence.push({ log_line: ev, significance: insight.title });
        });
      });
      setEvidence(allEvidence.slice(0, 8));

      // Set insights panel data
      setInsightsData({
        metrics: data.metrics,
        charts: data.charts,
        insights: data.insights,
        anomalies: data.anomalies,
        risk_level: data.risk_level,
        confidence: data.confidence,
        // SRE fields for insights panel
        key_insight: data.key_insight,
        core_problem: data.core_problem,
        causal_chain: data.causal_chain,
        impact_assessment: data.impact_assessment,
        root_cause_hypothesis: data.root_cause_hypothesis,
        recommended_actions: data.recommended_actions,
        confidence_explanation: data.confidence_explanation,
      });

      // Load messages from DB
      if (data.messages && data.messages.length > 0) {
        setMessages(
          data.messages.map((m: any) => ({
            role: m.role,
            content: m.content,
          }))
        );
      } else if (data.summary) {
        setMessages([{ role: "assistant", content: data.summary }]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load analysis");
    } finally {
      setInitialLoading(false);
    }
  };

  const handleSend = async (text: string) => {
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setLoading(true);
    setLoadingStage("Processing question...");
    setError(null);

    try {
      const res = await fetch(
        `${API_BASE}/api/analysis/${analysisId}/chat`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: text }),
        }
      );
      setLoadingStage("Generating response...");
      
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.answer || "No response received" },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, an error occurred. Please try again.",
        },
      ]);
    } finally {
      setLoading(false);
      setLoadingStage("");
    }
  };

  // Determine if this is the first assistant message (for showing structured cards)
  const firstAssistantIndex = messages.findIndex((m) => m.role === "assistant");

  return (
    <div className="flex h-screen bg-[#0b0b0c]">
      {/* Sidebar */}
      <HistorySidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Chat Area */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-white/5 px-6 py-3">
          <button
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
            className="rounded-lg p-1.5 text-gray-500 hover:bg-white/5 hover:text-white transition-colors md:hidden"
          >
            {sidebarCollapsed ? (
              <PanelLeftOpen className="h-4 w-4" />
            ) : (
              <PanelLeftClose className="h-4 w-4" />
            )}
          </button>
          <div className="flex items-center gap-3 flex-1">
            <div>
              <h1 className="text-sm font-semibold text-text-primary">
                Log Analysis
              </h1>
              <p className="text-[11px] text-gray-600">
                Session {analysisId.slice(0, 8)}
              </p>
            </div>
            {/* Risk level badge in header */}
            {riskLevel && riskLevel !== "UNKNOWN" && (
              <div className={`ml-auto flex items-center gap-1.5 rounded-full border border-white/10 px-2.5 py-1 text-[10px] font-semibold ${RISK_COLORS[riskLevel] || "text-gray-400"}`}>
                <Shield className="h-3 w-3" />
                {riskLevel}
                {confidence > 0 && (
                  <span className="text-gray-500 font-normal ml-1">
                    {confidence}%
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="mx-auto max-w-3xl space-y-5">
            {error && (
              <div className="rounded-xl border border-red-500/20 bg-red-500/8 p-3 text-sm text-red-300">
                {error}
              </div>
            )}

            {initialLoading ? (
              <div className="flex items-center justify-center py-20">
                <div className="text-center">
                  <Loader2 className="h-6 w-6 animate-spin text-accent-primary mx-auto mb-3" />
                  <p className="text-sm text-gray-500">{loadingStage || "Loading analysis..."}</p>
                </div>
              </div>
            ) : (
              <>
                {messages.map((msg, idx) => (
                  <div key={idx}>
                    <ChatMessage
                      role={msg.role}
                      content={msg.content}
                    />

                    {/* Render structured intelligence cards after first assistant message */}
                    {msg.role === "assistant" && idx === firstAssistantIndex && (
                      <div className="mt-4 space-y-4 animate-fadeIn">
                        {/* Key Insight Banner */}
                        {keyInsight && (
                          <InsightBanner
                            keyInsight={keyInsight}
                            riskLevel={riskLevel}
                            confidence={confidence}
                          />
                        )}

                        {/* Causal Chain */}
                        {causalChain.length > 0 && (
                          <CausalChainCard chain={causalChain} />
                        )}

                        {/* Evidence */}
                        {evidence.length > 0 && (
                          <EvidenceBlock evidence={evidence} />
                        )}

                        {/* Action Items */}
                        {recommendedActions.length > 0 && (
                          <ActionItems actions={recommendedActions} />
                        )}
                      </div>
                    )}
                  </div>
                ))}

                {loading && (
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-accent-primary to-accent-secondary">
                      <Loader2 className="h-4 w-4 animate-spin text-[#111]" />
                    </div>
                    <div className="rounded-2xl bg-[#1a1a1e] border border-white/5 px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-400">{loadingStage || "Analyzing"}</span>
                        <span className="flex gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: "0ms" }} />
                          <span className="h-1.5 w-1.5 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: "150ms" }} />
                          <span className="h-1.5 w-1.5 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: "300ms" }} />
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input */}
        <ChatInput
          onSend={handleSend}
          loading={loading}
          suggestions={[
            "What caused the root failure?",
            "How do I fix this?",
            "Show critical issues",
            "What's the blast radius?",
          ]}
        />
      </div>

      {/* Insights Panel (desktop) */}
      <div className="hidden w-[340px] border-l border-white/5 bg-[#0a0a0b] lg:block">
        <div className="border-b border-white/5 px-4 py-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            System Intelligence
          </h2>
        </div>
        <InsightsPanel data={insightsData} />
      </div>
    </div>
  );
}
