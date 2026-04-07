import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listTenants, logout } from "../services/api";

export default function Dashboard() {
  const [tenants, setTenants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listTenants({ status: "active" })
      .then((r) => setTenants(r.items))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleLogout() {
    await logout();
    window.location.href = "/login";
  }

  const totalMessages = tenants.reduce((s, t) => s + (t.usage?.message_count_month || 0), 0);

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 32 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 32 }}>
        <h1>Dashboard</h1>
        <button onClick={handleLogout} style={{ padding: "6px 16px", border: "1px solid #ccc", borderRadius: 4 }}>Log out</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16, marginBottom: 32 }}>
        {[
          { label: "Active Tenants", value: loading ? "…" : tenants.length },
          { label: "Messages This Month", value: loading ? "…" : totalMessages },
          { label: "Platform", value: "PSX Chatbot" },
        ].map(({ label, value }) => (
          <div key={label} style={{ background: "#fff", padding: 20, borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
            <div style={{ fontSize: 13, color: "#666", marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 28, fontWeight: 700 }}>{value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <h2>Tenants</h2>
        <Link to="/tenants" style={{ color: "#0070f3" }}>Manage tenants →</Link>
      </div>
    </div>
  );
}
