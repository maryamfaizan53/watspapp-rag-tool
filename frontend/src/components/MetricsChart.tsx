import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

interface Props {
  data: Array<{ date: string; message_count: number; active_users: number }>;
}

export default function MetricsChart({ data }: Props) {
  if (!data.length) return <p style={{ color: "#888", padding: 16 }}>No metrics data available.</p>;
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
        <YAxis tick={{ fontSize: 11 }} />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="message_count" name="Messages" stroke="#0070f3" dot={false} />
        <Line type="monotone" dataKey="active_users" name="Active Users" stroke="#00c853" dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
