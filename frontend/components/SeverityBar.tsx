"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

const SEGMENT_COLORS: Record<string, string> = {
  aging: "#f59e0b",
  exposure: "#ef4444",
  reminders_ignored: "#38bdf8",
  client_signal: "#8b5cf6",
  tier: "#22c55e",
};

const SEGMENT_LABELS: Record<string, string> = {
  aging: "Aging",
  exposure: "Exposure",
  reminders_ignored: "Reminders ignored",
  client_signal: "Client signal",
  tier: "Tier risk",
};

export function SeverityBar({ breakdown }: { breakdown: Record<string, number> }) {
  const data = Object.entries(breakdown).map(([key, value]) => ({
    key,
    label: SEGMENT_LABELS[key] ?? key,
    value: Math.round(value * 10) / 10,
  }));

  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
          <XAxis type="number" hide />
          <YAxis
            type="category"
            dataKey="label"
            width={110}
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            cursor={{ fill: "rgba(255,255,255,0.04)" }}
            contentStyle={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              borderRadius: 8,
              fontSize: 12,
            }}
          />
          <Bar dataKey="value" radius={4}>
            {data.map((entry) => (
              <Cell key={entry.key} fill={SEGMENT_COLORS[entry.key] ?? "#8b90a3"} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
