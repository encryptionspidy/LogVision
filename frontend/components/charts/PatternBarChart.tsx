"use client";

import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
} from "recharts";

interface PatternItem {
  pattern: string;
  count: number;
}

export default function PatternBarChart({ data }: { data: PatternItem[] }) {
  if (!data || data.length === 0) return null;

  // Take top 6 patterns
  const top = [...data].sort((a, b) => b.count - a.count).slice(0, 6);

  return (
    <div className="h-[160px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={top} layout="vertical" margin={{ left: 10 }}>
          <XAxis
            type="number"
            tick={{ fontSize: 10, fill: "#6b7280" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="pattern"
            tick={{ fontSize: 10, fill: "#b8b8c0" }}
            tickLine={false}
            axisLine={false}
            width={110}
          />
          <Tooltip
            contentStyle={{
              background: "#1a1a1e",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#f5f5f5",
            }}
          />
          <Bar
            dataKey="count"
            fill="#ff8a5b"
            radius={[0, 4, 4, 0]}
            barSize={14}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
