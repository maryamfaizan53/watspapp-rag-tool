import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ChannelConfig from "../components/ChannelConfig";
import MetricsChart from "../components/MetricsChart";
import Sidebar from "../components/Sidebar";
import { getTenant, getTenantMetrics, logout } from "../services/api";

const PLAN_COLOR: Record<string, string> = {
  starter: "#06b6d4",
  growth: "#8b5cf6",
  enterprise: "#f59e0b",
};

type Tab = "overview" | "channels" | "metrics";

export default function TenantDetail() {
  const { id } = useParams<{ id: string }>();
  const [tenant, setTenant] = useState<any>(null);
  const [metrics, setMetrics] = useState<any>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const tabBarRef = useRef<HTMLDivElement>(null);
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0 });

  async function load() {
    if (!id) return;
    const [t, m] = await Promise.all([getTenant(id), getTenantMetrics(id)]);
    setTenant(t);
    setMetrics(m);
  }

  useEffect(() => { load(); }, [id]);

  useEffect(() => {
    if (!tabBarRef.current) return;
    const tabs = tabBarRef.current.querySelectorAll<HTMLButtonElement>("[data-tab]");
    tabs.forEach(btn => {
      if (btn.getAttribute("data-tab") === tab) {
        setIndicatorStyle({ left: btn.offsetLeft, width: btn.offsetWidth });
      }
    });
  }, [tab]);

  async function handleLogout() {
    await logout();
    window.location.href = "/login";
  }

  if (!tenant) return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#080d1a" }}>
      <Sidebar currentPath={`/tenants/${id}`} onLogout={handleLogout} />
      <main style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{
            width: 42, height: 42, borderRadius: "50%",
            border: "3px solid rgba(6,182,212,0.2)", borderTopColor: "#06b6d4",
            animation: "spin 1s linear infinite", margin: "0 auto 16px",
          }} />
          <p style={{ color: "#475569", fontSize: 15 }}>Loading tenant…</p>
        </div>
      </main>
    </div>
  );

  const planColor = PLAN_COLOR[tenant.plan] || "#06b6d4";
  const TABS: { key: Tab; label: string; icon: string }[] = [
    { key: "overview", label: "Overview", icon: "📊" },
    { key: "channels", label: "Channels", icon: "📱" },
    { key: "metrics", label: "Metrics", icon: "📈" },
  ];

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#080d1a" }}>
      <Sidebar currentPath="/tenants" onLogout={handleLogout} />

      <main style={{ flex: 1, padding: "36px 40px", overflowY: "auto" }}>
        {/* Breadcrumb */}
        <div style={{
          display: "flex", alignItems: "center", gap: 8,
          marginBottom: 28, fontSize: 13, color: "#475569",
        }}>
          <Link to="/tenants"
            style={{ color: "#475569", transition: "color 0.2s" }}
            onMouseEnter={e => (e.currentTarget.style.color = "#94a3b8")}
            onMouseLeave={e => (e.currentTarget.style.color = "#475569")}
          >Tenants</Link>
          <span style={{ color: "#2d3a50" }}>/</span>
          <span style={{ color: "#94a3b8" }}>{tenant.name}</span>
        </div>

        {/* Tenant header card */}
        <div style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          marginBottom: 32, padding: "28px 32px",
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderRadius: 20,
          boxShadow: "0 4px 24px rgba(0,0,0,0.2)",
          animation: "fadeInUp 0.5s ease both",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            <div style={{
              width: 56, height: 56, borderRadius: 16,
              background: `${planColor}18`, border: `1px solid ${planColor}33`,
              display: "flex", alignItems: "center", justifyContent: "center", fontSize: 26,
            }}>🏢</div>
            <div>
              <h1 style={{ fontSize: 24, fontWeight: 800, letterSpacing: "-0.5px", marginBottom: 8 }}>
                {tenant.name}
              </h1>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <span style={{
                  padding: "3px 12px", borderRadius: 100, fontSize: 12, fontWeight: 600,
                  background: `${planColor}18`, color: planColor,
                  border: `1px solid ${planColor}33`, textTransform: "capitalize",
                }}>{tenant.plan}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: "50%",
                    background: tenant.status === "active" ? "#10b981" : "#ef4444",
                    display: "inline-block",
                    boxShadow: tenant.status === "active" ? "0 0 6px rgba(16,185,129,0.5)" : "none",
                  }} />
                  <span style={{ fontSize: 12, color: "#475569", textTransform: "capitalize" }}>
                    {tenant.status}
                  </span>
                </div>
              </div>
            </div>
          </div>
          <Link to={`/tenants/${id}/documents`}>
            <button className="btn-primary" style={{ padding: "11px 22px", fontSize: 14 }}>
              📁 Manage Docs
            </button>
          </Link>
        </div>

        {/* Tabs */}
        <div style={{ marginBottom: 32 }}>
          <div ref={tabBarRef} style={{
            display: "flex", gap: 4,
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.07)",
            borderRadius: 14, padding: 4, position: "relative",
          }}>
            {/* Sliding indicator */}
            <div style={{
              position: "absolute", top: 4, bottom: 4,
              left: indicatorStyle.left, width: indicatorStyle.width,
              background: "linear-gradient(135deg, rgba(6,182,212,0.15), rgba(139,92,246,0.1))",
              border: "1px solid rgba(6,182,212,0.25)", borderRadius: 10,
              transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
              pointerEvents: "none",
            }} />
            {TABS.map(t => (
              <button
                key={t.key}
                data-tab={t.key}
                onClick={() => setTab(t.key)}
                style={{
                  flex: 1, padding: "11px 20px", border: "none", background: "transparent",
                  color: tab === t.key ? "#06b6d4" : "#94a3b8",
                  fontWeight: tab === t.key ? 700 : 500, fontSize: 14,
                  cursor: "pointer", borderRadius: 10, position: "relative", zIndex: 1,
                  transition: "color 0.2s",
                  display: "flex", alignItems: "center", justifyContent: "center", gap: 7,
                }}
              >
                <span>{t.icon}</span>
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tab content */}
        <div style={{ animation: "fadeIn 0.3s ease" }}>

          {/* Overview */}
          {tab === "overview" && (
            <div>
              <div style={{
                display: "grid", gridTemplateColumns: "repeat(3, 1fr)",
                gap: 20, marginBottom: 28,
              }}>
                {[
                  { icon: "💬", label: "Messages This Month", value: tenant.usage?.message_count_month ?? 0, color: "#06b6d4" },
                  { icon: "📊", label: "Monthly Quota", value: (tenant.quota?.messages_per_month ?? 0).toLocaleString(), color: "#8b5cf6" },
                  { icon: "⚡", label: "Rate Limit (msg/min)", value: tenant.quota?.rate_limit_per_minute ?? 60, color: "#10b981" },
                ].map((m, i) => (
                  <div key={i} style={{
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.07)",
                    borderRadius: 16, padding: "24px",
                    animation: `fadeInUp 0.4s ease ${i * 0.1}s both`,
                    boxShadow: "0 4px 24px rgba(0,0,0,0.15)",
                  }}>
                    <div style={{
                      width: 42, height: 42, borderRadius: 11,
                      background: `${m.color}18`, border: `1px solid ${m.color}33`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 20, marginBottom: 14,
                    }}>{m.icon}</div>
                    <div style={{
                      fontSize: 11, color: "#475569", fontWeight: 700,
                      letterSpacing: "1px", textTransform: "uppercase", marginBottom: 6,
                    }}>{m.label}</div>
                    <div style={{
                      fontSize: 32, fontWeight: 800, color: m.color, letterSpacing: "-0.8px",
                    }}>{m.value}</div>
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", gap: 14 }}>
                <Link to={`/tenants/${id}/documents`}>
                  <button className="btn-primary" style={{ fontSize: 14, padding: "12px 24px" }}>
                    📁 Manage Documents →
                  </button>
                </Link>
                <button
                  onClick={() => setTab("channels")}
                  style={{
                    padding: "12px 24px", borderRadius: 12, fontSize: 14, fontWeight: 600,
                    background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)",
                    color: "#f1f5f9", cursor: "pointer", transition: "all 0.2s",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.1)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "rgba(255,255,255,0.06)")}
                >
                  📱 Configure Channels
                </button>
              </div>
            </div>
          )}

          {/* Channels */}
          {tab === "channels" && (
            <ChannelConfig tenantId={id!} channels={tenant.channels} onSaved={load} />
          )}

          {/* Metrics */}
          {tab === "metrics" && (
            <div style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.07)",
              borderRadius: 20, padding: 28,
              boxShadow: "0 4px 24px rgba(0,0,0,0.15)",
            }}>
              <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 24, color: "#f1f5f9" }}>
                📈 Usage — Last 30 Days
              </h3>
              <MetricsChart data={metrics?.daily_breakdown || []} />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
