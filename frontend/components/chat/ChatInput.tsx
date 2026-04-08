"use client";

import { useState, useRef, KeyboardEvent } from "react";
import { Send, Upload, Loader2 } from "lucide-react";

interface ChatInputProps {
  onSend: (text: string) => void;
  onFileUpload?: (text: string) => void;
  loading?: boolean;
  placeholder?: string;
  showUpload?: boolean;
  suggestions?: string[];
}

export default function ChatInput({
  onSend,
  onFileUpload,
  loading = false,
  placeholder = "Ask a question about your logs...",
  showUpload = false,
  suggestions = [],
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSend = () => {
    const text = input.trim();
    if (!text || loading) return;
    onSend(text);
    setInput("");
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      onFileUpload?.(text);
    };
    reader.readAsText(file);
    // Reset so same file can be reselected
    e.target.value = "";
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-resize
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  };

  return (
    <div className="border-t border-white/5 bg-[#0b0b0c]/80 p-4 backdrop-blur-sm">
      <div className="mx-auto max-w-3xl">
        <div className="flex items-end gap-2 rounded-2xl border border-white/10 bg-[#121214] px-4 py-3 focus-within:border-accent-primary/30 transition-colors">
          {showUpload && (
            <>
              <input
                ref={fileRef}
                type="file"
                accept=".txt,.log,.csv"
                onChange={handleFileChange}
                className="hidden"
              />
              <button
                onClick={() => fileRef.current?.click()}
                className="flex-shrink-0 rounded-lg p-2 text-gray-500 hover:bg-white/5 hover:text-gray-300 transition-colors"
                title="Upload log file"
              >
                <Upload className="h-4 w-4" />
              </button>
            </>
          )}

          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            rows={1}
            className="max-h-[200px] flex-1 resize-none bg-transparent text-sm text-text-primary placeholder-gray-600 focus:outline-none leading-relaxed"
            disabled={loading}
          />

          <button
            onClick={handleSend}
            disabled={loading || !input.trim()}
            className="flex-shrink-0 rounded-lg bg-accent-primary p-2 text-[#111] transition-all hover:bg-accent-secondary disabled:opacity-30 disabled:cursor-not-allowed"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </div>

        {suggestions.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {suggestions.map((s) => (
              <button
                key={s}
                onClick={() => onSend(s)}
                disabled={loading}
                className="rounded-lg border border-white/8 px-3 py-1.5 text-xs text-gray-400 transition-colors hover:border-white/15 hover:text-gray-200 disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
