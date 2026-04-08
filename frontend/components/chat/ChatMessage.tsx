"use client";

import MarkdownMessage from "./MarkdownMessage";
import { Bot, User } from "lucide-react";

interface ChatMessageProps {
  role: "user" | "assistant";
  content: string;
}

export default function ChatMessage({ role, content }: ChatMessageProps) {
  const isUser = role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-accent-primary to-accent-secondary shadow-lg shadow-accent-glow/20">
          <Bot className="h-4 w-4 text-[#111]" />
        </div>
      )}

      <div
        className={`max-w-[80%] rounded-2xl px-5 py-3.5 ${
          isUser
            ? "bg-gradient-to-br from-accent-primary/90 to-accent-secondary/90 text-[#111]"
            : "bg-[#1a1a1e] border border-white/5 text-gray-100"
        }`}
      >
        {isUser ? (
          <p className="text-sm leading-relaxed font-medium">{content}</p>
        ) : (
          <MarkdownMessage content={content} className="text-sm" />
        )}
      </div>

      {isUser && (
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-white/10 border border-white/10">
          <User className="h-4 w-4 text-gray-300" />
        </div>
      )}
    </div>
  );
}
