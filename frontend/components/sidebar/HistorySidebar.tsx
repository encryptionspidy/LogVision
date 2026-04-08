"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { Plus, MessageSquare, Sparkles, ChevronLeft, MoreVertical, Pencil, Trash2, X, Check } from "lucide-react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

interface Session {
  id: string;
  created_at: string | null;
  summary: string;
  risk_level: string;
}

const RISK_COLORS: Record<string, string> = {
  CRITICAL: "bg-red-500",
  HIGH: "bg-orange-500",
  MEDIUM: "bg-yellow-500",
  LOW: "bg-green-500",
  UNKNOWN: "bg-gray-500",
};

export default function HistorySidebar({
  collapsed = false,
  onToggle,
}: {
  collapsed?: boolean;
  onToggle?: () => void;
}) {
  const router = useRouter();
  const params = useParams();
  const activeId = params?.id as string | undefined;
  const [sessions, setSessions] = useState<Session[]>([]);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [menuOpenId, setMenuOpenId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchSessions();
    const interval = setInterval(fetchSessions, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpenId(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fetchSessions = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/analysis/history`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch {
      // silent fail
    }
  };

  const handleDelete = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this session?")) return;

    try {
      const res = await fetch(`${API_BASE}/api/analysis/${sessionId}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setSessions((prev) => prev.filter((s) => s.id !== sessionId));
        if (activeId === sessionId) {
          router.push("/");
        }
      }
    } catch {
      alert("Failed to delete session");
    }
    setMenuOpenId(null);
  };

  const handleEdit = (session: Session, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(session.id);
    setEditValue(session.summary || "Analysis session");
    setMenuOpenId(null);
  };

  const handleSaveEdit = async (sessionId: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/analysis/${sessionId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ summary: editValue }),
      });
      if (res.ok) {
        setSessions((prev) =>
          prev.map((s) => (s.id === sessionId ? { ...s, summary: editValue } : s))
        );
      }
    } catch {
      alert("Failed to update session");
    }
    setEditingId(null);
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditValue("");
  };

  const toggleMenu = (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setMenuOpenId(menuOpenId === sessionId ? null : sessionId);
  };

  if (collapsed) {
    return (
      <div className="flex w-14 flex-col items-center border-r border-white/5 bg-[#0a0a0b] py-4">
        <button
          onClick={onToggle}
          className="mb-4 rounded-lg p-2 text-gray-400 hover:bg-white/5 hover:text-white transition-colors"
        >
          <MessageSquare className="h-5 w-5" />
        </button>
        <button
          onClick={() => router.push("/")}
          className="rounded-lg p-2 text-[#ff8a5b] hover:bg-white/5 transition-colors"
        >
          <Plus className="h-5 w-5" />
        </button>
      </div>
    );
  }

  return (
    <div className="flex w-[280px] flex-col border-r border-white/5 bg-[#0a0a0b]">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 p-4">
        <div className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-[#ff8a5b]" />
          <span className="text-sm font-semibold text-[#f5f5f5]">LogVision</span>
        </div>
        <button
          onClick={onToggle}
          className="rounded-lg p-1.5 text-gray-500 hover:bg-white/5 hover:text-white transition-colors"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      </div>

      {/* New Analysis */}
      <div className="p-3">
        <button
          onClick={() => router.push("/")}
          className="flex w-full items-center gap-2 rounded-xl border border-white/10 px-4 py-3 text-sm font-medium text-[#f5f5f5] transition-all hover:border-[#ff8a5b]/30 hover:bg-white/5"
        >
          <Plus className="h-4 w-4 text-[#ff8a5b]" />
          New Analysis
        </button>
      </div>

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4">
        <p className="mb-2 px-2 text-xs font-medium uppercase tracking-wider text-gray-600">
          History
        </p>
        {sessions.length === 0 ? (
          <p className="px-2 text-xs text-gray-600">No sessions yet</p>
        ) : (
          <div className="space-y-0.5">
            {sessions.map((s) => {
              const isActive = s.id === activeId;
              const isEditing = editingId === s.id;
              const shortSummary =
                s.summary?.replace(/^##?\s*/gm, "").slice(0, 60) || "Analysis session";
              const dateStr = s.created_at
                ? new Date(s.created_at).toLocaleDateString(undefined, {
                    month: "short",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })
                : "";

              return (
                <div
                  key={s.id}
                  className={`group relative flex w-full items-start gap-2 rounded-lg px-3 py-2.5 text-left transition-colors ${
                    isActive
                      ? "bg-white/10 text-[#f5f5f5]"
                      : "text-gray-400 hover:bg-white/5 hover:text-gray-200"
                  }`}
                >
                  <button
                    onClick={() => router.push(`/analysis/${s.id}`)}
                    className="flex flex-1 items-start gap-2 min-w-0"
                  >
                    <MessageSquare className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" />
                    <div className="min-w-0 flex-1">
                      {isEditing ? (
                        <div className="flex items-center gap-1">
                          <input
                            type="text"
                            value={editValue}
                            onChange={(e) => setEditValue(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") {
                                e.preventDefault();
                                handleSaveEdit(s.id);
                              } else if (e.key === "Escape") {
                                handleCancelEdit();
                              }
                            }}
                            onClick={(e) => e.stopPropagation()}
                            className="w-full bg-transparent text-xs font-medium text-[#f5f5f5] border border-[#ff8a5b]/30 rounded px-1 py-0.5 focus:outline-none focus:border-[#ff8a5b]"
                            autoFocus
                          />
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleSaveEdit(s.id);
                            }}
                            className="p-0.5 text-green-400 hover:text-green-300"
                          >
                            <Check className="h-3 w-3" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleCancelEdit();
                            }}
                            className="p-0.5 text-gray-400 hover:text-gray-300"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      ) : (
                        <p className="truncate text-xs font-medium">{shortSummary}</p>
                      )}
                      {!isEditing && (
                        <div className="mt-1 flex items-center gap-2">
                          <span className="text-[10px] text-gray-600">{dateStr}</span>
                          {s.risk_level && s.risk_level !== "UNKNOWN" && (
                            <span
                              className={`inline-block h-1.5 w-1.5 rounded-full ${
                                RISK_COLORS[s.risk_level] || RISK_COLORS.UNKNOWN
                              }`}
                            />
                          )}
                        </div>
                      )}
                    </div>
                  </button>

                  {/* Menu Button */}
                  {!isEditing && (
                    <div className="relative" ref={menuOpenId === s.id ? menuRef : null}>
                      <button
                        onClick={(e) => toggleMenu(s.id, e)}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded text-gray-500 hover:text-gray-300 hover:bg-white/5 transition-all"
                      >
                        <MoreVertical className="h-3 w-3" />
                      </button>

                      {/* Dropdown Menu */}
                      {menuOpenId === s.id && (
                        <div className="absolute right-0 top-6 z-50 w-32 rounded-lg border border-white/10 bg-[#1a1a1e] shadow-lg">
                          <button
                            onClick={(e) => handleEdit(s, e)}
                            className="flex w-full items-center gap-2 px-3 py-2 text-xs text-gray-300 hover:bg-white/5 transition-colors"
                          >
                            <Pencil className="h-3 w-3" />
                            Rename
                          </button>
                          <button
                            onClick={(e) => handleDelete(s.id, e)}
                            className="flex w-full items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors"
                          >
                            <Trash2 className="h-3 w-3" />
                            Delete
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
