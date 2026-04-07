import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ChannelConfig from "../components/ChannelConfig";
import MetricsChart from "../components/MetricsChart";
import { getTenant, getTenantMetrics } from "../services/api";

export default function TenantDetail() {
  const { id } = useParams<{ id: string }>();
  const [tenant, setTenant] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [tab, setTab] = useState<"overview" | "channels" | "metrics">("overview");

  async function load() {
    if (!id) return;
    const [t, m] = await Promise.all([getTenant(id), getTenantMetrics(id)]);
    setTenant(t);
    setMetrics(m);
  }

  useEffect(() => { load(); }, [id]);

  if (!tenant) return <div style={{ padding: 32 }}>Loading…</div>;

  const tabs = ["overview", "channels", "metrics"] as const;

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 32 }}>
      <div style={{ marginBottom: 24 }}>
        <Link to="/tenants" style={{ color: "#0070f3" }}>← Tenants</Link>
      </div>
      <h1 style={{ marginBottom: 8 }}>{tenant.name}</h1>
      <p style={{ color: "#666", marginBottom: 24, textTransform: "capitalize" }}>{tenant.plan} · {tenant.status}</p>

      <div style={{ display: "flex", gap: 8, marginBottom: 24, borderBottom: "2px solid #f0f0f0", paddingBottom: 0 }}>
        {tabs.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            style={{ padding: "8px 20px", border: "none", background: tab === t ? "#0070f3" : "transparent",
              color: tab === t ? "#fff" : "#333", borderRadius: "4px 4px 0 0", fontWeight: tab === t ? 600 : 400, cursor: "pointer" }}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16, marginBottom: 24 }}>
            {[
              { label: "Messages This Month", value: tenant.usage?.message_count_month ?? 0 },
              { label: "Monthly Quota", value: tenant.quota?.messages_per_month ?? 0 },
              { label: "Rate Limit (msg/min)", value: tenant.quota?.rate_limit_per_minute ?? 60 },
            ].map(({ label, value }) => (
              <div key={label} style={{ background: "#fff", padding: 16, borderRadius: 8, boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
                <div style={{ fontSize: 12, color: "#666", marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 24, fontWeight: 700 }}>{value}</div>
              </div>
            ))}
          </div>
          <Link to={`/tenants/${id}/documents`}
            style={{ display: "inline-block", padding: "8px 20px", background: "#0070f3", color: "#fff", borderRadius: 4 }}>
            Manage Documents →
          </Link>
        </div>
      )}

      {tab === "channels" && (
        <ChannelConfig tenantId={id!} channels={tenant.channels} onSaved={load} />
      )}

      {tab === "metrics" && (
        <div>
          <h3 style={{ marginBottom: 16 }}>Usage (last 30 days)</h3>
          <MetricsChart data={metrics?.daily_breakdown || []} />
        </div>
      )}
    </div>
  );
}
