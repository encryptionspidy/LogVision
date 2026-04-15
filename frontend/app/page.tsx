"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Upload, FileText, Search, AlertTriangle, Shield, BarChart3, Zap, HelpCircle } from "lucide-react";
import HistorySidebar from "@/components/sidebar/HistorySidebar";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

const SAMPLE_LOG = `2024-03-27 10:15:32 WARN [ConnectionPool] Connection timeout retrying...
2024-03-27 10:15:33 ERROR [AuthService] Failed to authenticate user id=1092 - InvalidToken
2024-03-27 10:15:34 ERROR [AuthService] Failed to authenticate user id=1093 - InvalidToken
2024-03-27 10:15:35 ERROR [Database] Connection refused to primary replica
2024-03-27 10:15:36 FATAL [Database] System out of memory exception during query
2024-03-27 10:15:37 WARN [ConnectionPool] Connection timeout retrying...
2024-03-27 10:15:38 ERROR [PaymentService] Transaction failed: timeout after 30s
2024-03-27 10:15:39 INFO [System] Initiating automatic failover...
2024-03-27 10:15:40 INFO [System] Restarting database service...
2024-03-27 10:15:42 INFO [System] Database service restarted successfully`;

const QUICK_PROMPTS = [
  { label: "Find anomalies", icon: Search, description: "Detect unusual patterns" },
  { label: "Root cause analysis", icon: AlertTriangle, description: "Trace failure chains" },
  { label: "Security assessment", icon: Shield, description: "Identify threats" },
  { label: "System health report", icon: BarChart3, description: "Full diagnostic" },
];

export default function HomePage() {
  const router = useRouter();
  const [logInput, setLogInput] = useState("");
  const [queryText, setQueryText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = async (quickPrompt = "") => {
    const text = logInput.trim();
    if (!text || loading) return;

    setError(null);
    setLoading(true);

    const question = quickPrompt || queryText.trim();

    try {
      const features = ["anomaly", "root-cause"];
      const res = await fetch(`${API_BASE}/api/analysis/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          log_text: text,
          instruction: question,
          question: question,
          features,
        }),
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      if (data.analysis_id) {
        router.push(`/analysis/${data.analysis_id}`);
      } else {
        setError("No analysis ID returned");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => setLogInput(ev.target?.result as string);
    reader.readAsText(file);
    e.target.value = "";
  };

  return (
    <div className="flex h-screen bg-[#0b0b0c]">
      {/* History Sidebar */}
      <HistorySidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content */}
      <div className="flex flex-1 flex-col items-center justify-center p-6 overflow-y-auto">
        <div className="w-full max-w-2xl">
          {/* Hero */}
          <div className="mb-10 text-center">
            <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-[#ff8a5b] to-[#ffb38a] shadow-lg shadow-[rgba(255,138,91,0.35)]/40 animate-pulseGlow">
              <Sparkles className="h-8 w-8 text-[#111]" />
            </div>
            <h1 className="mb-2 text-4xl font-bold text-[#f5f5f5] sm:text-5xl">
              LogVision
            </h1>
            <p className="mb-1 text-lg text-gray-400">
              AI-powered log intelligence assistant
            </p>
            <p className="text-sm text-gray-600">
              Detect anomalies • Trace root causes • Get actionable fixes
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-4 rounded-xl border border-red-500/20 bg-red-500/8 p-3 text-center text-sm text-red-300">
              {error}
            </div>
          )}

          {/* Log Input Area */}
          <div className="rounded-2xl border border-white/8 bg-[#121214] p-1 shadow-2xl shadow-black/30 focus-within:border-[#ff8a5b]/25 transition-colors">
            <textarea
              ref={textareaRef}
              value={logInput}
              onChange={(e) => setLogInput(e.target.value)}
              placeholder="Paste your logs or upload a file to begin analysis..."
              rows={6}
              className="w-full resize-none rounded-xl bg-transparent p-4 text-sm text-[#f5f5f5] placeholder-gray-600 focus:outline-none leading-relaxed font-mono"
            />
            <div className="flex items-center justify-between border-t border-white/5 px-3 py-2">
              <div className="flex items-center gap-2">
                <input
                  ref={fileRef}
                  type="file"
                  accept=".txt,.log,.csv"
                  onChange={handleFileUpload}
                  className="hidden"
                />
                <button
                  onClick={() => fileRef.current?.click()}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300 transition-colors"
                >
                  <Upload className="h-3.5 w-3.5" />
                  Upload
                </button>
                <button
                  onClick={() => setLogInput(SAMPLE_LOG)}
                  className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs text-gray-500 hover:bg-white/5 hover:text-gray-300 transition-colors"
                >
                  <FileText className="h-3.5 w-3.5" />
                  Load Example
                </button>
              </div>
            </div>
          </div>

          {/* Query Input */}
          <div className="mt-3 rounded-xl border border-white/8 bg-[#121214] p-1 focus-within:border-[#ff8a5b]/25 transition-colors">
            <div className="flex items-center gap-3 px-4 py-2.5">
              <HelpCircle className="h-4 w-4 flex-shrink-0 text-gray-600" />
              <input
                type="text"
                value={queryText}
                onChange={(e) => setQueryText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                placeholder="What do you want to analyze? (optional)"
                className="w-full bg-transparent text-sm text-[#f5f5f5] placeholder-gray-600 focus:outline-none"
              />
              <button
                onClick={() => handleSubmit()}
                disabled={!logInput.trim() || loading}
                className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-[#ff8a5b] to-[#ffb38a] px-5 py-2 text-sm font-semibold text-[#111] shadow-lg shadow-[rgba(255,138,91,0.35)]/30 transition-all hover:shadow-[rgba(255,138,91,0.35)]/50 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
              >
                {loading ? (
                  <>
                    <Zap className="h-4 w-4 animate-pulse" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4" />
                    Analyze
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Quick Prompts */}
          <div className="mt-4 flex flex-wrap justify-center gap-2">
            {QUICK_PROMPTS.map(({ label, icon: Icon, description }) => (
              <button
                key={label}
                onClick={() => {
                  if (logInput.trim()) handleSubmit(label);
                }}
                disabled={!logInput.trim() || loading}
                className="group flex items-center gap-2 rounded-full border border-white/8 px-4 py-2 text-xs text-gray-500 transition-all hover:border-[#ff8a5b]/20 hover:text-gray-300 hover:bg-white/[0.02] disabled:opacity-30"
                title={description}
              >
                <Icon className="h-3.5 w-3.5 transition-colors group-hover:text-[#ff8a5b]" />
                {label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
