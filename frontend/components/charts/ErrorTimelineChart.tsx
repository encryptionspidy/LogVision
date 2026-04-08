"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer,
} from "recharts";

interface TimelinePoint {
  time?: string;
  timestamp?: string;
  errors: number;
}

export default function ErrorTimelineChart({ data }: { data: TimelinePoint[] }) {
  if (!data || data.length === 0) return null;

  const formatted = data.map((d) => ({
    time: d.time || d.timestamp || "",
    errors: d.errors,
  }));

  return (
    <div className="h-[160px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={formatted}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="time"
            tick={{ fontSize: 10, fill: "#6b7280" }}
            tickLine={false}
            axisLine={{ stroke: "rgba(255,255,255,0.08)" }}
          />
          <YAxis
            tick={{ fontSize: 10, fill: "#6b7280" }}
            tickLine={false}
            axisLine={false}
            width={30}
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
          <Line
            type="monotone"
            dataKey="errors"
            stroke="#ff8a5b"
            strokeWidth={2}
            dot={{ fill: "#ff8a5b", r: 3 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
