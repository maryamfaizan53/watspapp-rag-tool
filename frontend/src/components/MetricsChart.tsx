import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

interface Props {
  data: Array<{ date: string; message_count: number; active_users: number }>;
}

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "#0e1628",
      border: "1px solid rgba(255,255,255,0.1)",
      borderRadius: 14, padding: "14px 18px",
      boxShadow: "0 16px 40px rgba(0,0,0,0.6)",
      backdropFilter: "blur(8px)",
    }}>
      <p style={{ fontSize: 12, color: "#475569", marginBottom: 10, fontWeight: 600 }}>
        {label}
      </p>
      {payload.map((p: any, i: number) => (
        <div key={i} style={{
          display: "flex", alignItems: "center", gap: 8,
          fontSize: 14, fontWeight: 600, color: p.color, marginBottom: i < payload.length - 1 ? 6 : 0,
        }}>
          <span style={{
            width: 10, height: 10, borderRadius: "50%",
            background: p.color, display: "inline-block",
            boxShadow: `0 0 6px ${p.color}`,
          }} />
          <span style={{ color: "#94a3b8", fontWeight: 500 }}>{p.name}:</span>
          <span>{p.value}</span>
        </div>
      ))}
    </div>
  );
};

export default function MetricsChart({ data }: Props) {
  if (!data.length) return (
    <div style={{
      display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center",
      height: 220, color: "#475569", gap: 14,
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: 16,
        background: "rgba(255,255,255,0.04)",
        border: "1px solid rgba(255,255,255,0.07)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 28,
      }}>📈</div>
      <p style={{ fontSize: 14, color: "#475569" }}>No metrics data available yet.</p>
      <p style={{ fontSize: 12, color: "#2d3a50" }}>Data appears once messages are exchanged.</p>
    </div>
  );

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: -8, bottom: 0 }}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="rgba(255,255,255,0.04)"
          vertical={false}
        />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "#475569" }}
          axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
          tickLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: "#475569" }}
          axisLine={false}
          tickLine={false}
        />
        <Tooltip content={<CustomTooltip />} cursor={{ stroke: "rgba(255,255,255,0.05)", strokeWidth: 1 }} />
        <Legend
          wrapperStyle={{
            fontSize: 13, color: "#94a3b8", paddingTop: 20,
          }}
          iconType="circle"
        />
        <Line
          type="monotone"
          dataKey="message_count"
          name="Messages"
          stroke="#06b6d4"
          strokeWidth={2.5}
          dot={false}
          activeDot={{ r: 5, fill: "#06b6d4", stroke: "#080d1a", strokeWidth: 2 }}
        />
        <Line
          type="monotone"
          dataKey="active_users"
          name="Active Users"
          stroke="#8b5cf6"
          strokeWidth={2.5}
          dot={false}
          activeDot={{ r: 5, fill: "#8b5cf6", stroke: "#080d1a", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
