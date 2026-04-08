"use client";

import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface ComponentItem {
  component: string;
  failures: number;
  severity?: string;
}

const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "#ef4444",
  HIGH: "#f97316", 
  MEDIUM: "#eab308",
  LOW: "#22c55e",
  ERROR: "#ef4444",
  WARNING: "#f59e0b",
  default: "#ff8a5b",
};

export default function ComponentImpactChart({ data }: { data: ComponentItem[] }) {
  if (!data || data.length === 0) return null;

  // Sort by failures desc, take top 6
  const sorted = [...data]
    .sort((a, b) => b.failures - a.failures)
    .slice(0, 6)
    .map((item) => ({
      ...item,
      // Truncate long component names
      component: item.component.length > 20 
        ? item.component.slice(0, 20) + "..." 
        : item.component,
    }));

  return (
    <div className="h-[180px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={sorted} layout="vertical" margin={{ left: 0, right: 20 }}>
          <XAxis
            type="number"
            tick={{ fontSize: 10, fill: "#6b7280" }}
            tickLine={false}
            axisLine={false}
          />
          <YAxis
            type="category"
            dataKey="component"
            tick={{ fontSize: 10, fill: "#b8b8c0" }}
            tickLine={false}
            axisLine={false}
            width={100}
          />
          <Tooltip
            contentStyle={{
              background: "#1a1a1e",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#f5f5f5",
            }}
            formatter={(value: number) => [`${value} failures`, "Impact"]
            }
          />
          <Bar dataKey="failures" radius={[0, 4, 4, 0]} barSize={16}>
            {sorted.map((entry, i) => (
              <Cell
                key={`cell-${i}`}
                fill={SEVERITY_COLORS[entry.severity || "default"]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
