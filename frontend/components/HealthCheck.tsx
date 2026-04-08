"use client";
import { useState, useEffect } from 'react';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:5000";

export function HealthCheck() {
  const [online, setOnline] = useState<boolean | null>(null);
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        setOnline(res.ok);
      } catch {
        setOnline(false);
      }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  const label = online === null ? "Checking..." : online ? "Backend: Online" : "Backend: Offline";
  const dotColor = online === null ? "bg-yellow-400" : online ? "bg-green-400" : "bg-red-400";
  const borderColor = online === null ? "border-yellow-400/40" : online ? "border-green-400/40" : "border-red-400/40";

  return (
    <div className={`fixed bottom-4 right-4 z-50 flex items-center gap-2 rounded-full bg-[#121214] px-4 py-2 text-xs font-semibold text-gray-300 border ${borderColor} shadow-lg`}>
      <span className={`inline-block h-2 w-2 rounded-full ${dotColor} ${online ? 'animate-pulse' : ''}`} />
      {label}
    </div>
  );
}
