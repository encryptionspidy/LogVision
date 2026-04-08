"use client";

import { useParams, useRouter } from "next/navigation";
import { useState, useEffect, useRef } from "react";
import { Loader2, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import HistorySidebar from "@/components/sidebar/HistorySidebar";
import ChatMessage from "@/components/chat/ChatMessage";
import ChatInput from "@/components/chat/ChatInput";
import InsightsPanel from "@/components/insights/EnhancedInsightsPanel";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function AnalysisChatPage() {
  const params = useParams();
  const router = useRouter();
  const analysisId = params.id as string;
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [insightsData, setInsightsData] = useState<any>(null);
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

      // Set insights data from session metadata
      setInsightsData({
        metrics: data.metrics,
        charts: data.charts,
        insights: data.insights,
        anomalies: data.anomalies,
        risk_level: data.risk_level,
        confidence: data.confidence,
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
    }
  };

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
          <div>
            <h1 className="text-sm font-semibold text-text-primary">
              Log Analysis
            </h1>
            <p className="text-[11px] text-gray-600">
              Session {analysisId.slice(0, 8)}
            </p>
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
                <Loader2 className="h-6 w-6 animate-spin text-accent-primary" />
              </div>
            ) : (
              <>
                {messages.map((msg, idx) => (
                  <ChatMessage
                    key={idx}
                    role={msg.role}
                    content={msg.content}
                  />
                ))}

                {loading && (
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-accent-primary to-accent-secondary">
                      <Loader2 className="h-4 w-4 animate-spin text-[#111]" />
                    </div>
                    <div className="rounded-2xl bg-[#1a1a1e] border border-white/5 px-5 py-3">
                      <span className="text-sm text-gray-400">Thinking...</span>
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
            "What caused most errors?",
            "Show critical issues",
            "Explain security concerns",
          ]}
        />
      </div>

      {/* Insights Panel (desktop) */}
      <div className="hidden w-[340px] border-l border-white/5 bg-[#0a0a0b] lg:block">
        <div className="border-b border-white/5 px-4 py-3">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
            Analysis Insights
          </h2>
        </div>
        <InsightsPanel data={insightsData} />
      </div>
    </div>
  );
}
