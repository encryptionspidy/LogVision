"use client";

import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from "recharts";

interface SeverityItem {
  level: string;
  count: number;
}

const COLORS: Record<string, string> = {
  CRITICAL: "#ef4444",
  HIGH: "#f97316",
  MEDIUM: "#eab308",
  LOW: "#22c55e",
  INFO: "#3b82f6",
  ERROR: "#ef4444",
  WARNING: "#f59e0b",
  DEBUG: "#6b7280",
};

export default function SeverityPieChart({ data }: { data: SeverityItem[] }) {
  if (!data || data.length === 0) return null;

  const total = data.reduce((sum, d) => sum + d.count, 0);
  if (total === 0) return null;

  return (
    <div className="h-[180px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={40}
            outerRadius={65}
            paddingAngle={3}
            dataKey="count"
            nameKey="level"
            stroke="none"
          >
            {data.map((entry, i) => (
              <Cell
                key={`cell-${i}`}
                fill={COLORS[entry.level] || "#6b7280"}
              />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              background: "#1a1a1e",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: "8px",
              fontSize: "12px",
              color: "#f5f5f5",
            }}
          />
          <Legend
            wrapperStyle={{ fontSize: "11px", color: "#b8b8c0" }}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
