import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import { listTenants, logout } from "../services/api";

const PLAN_COLOR: Record<string, string> = {
  starter: "#06b6d4",
  growth: "#8b5cf6",
  enterprise: "#f59e0b",
};

export default function Dashboard() {
  const [tenants, setTenants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const location = useLocation();

  useEffect(() => {
    listTenants({ status: "active" })
      .then((r) => {
        const items = r?.items ?? r;
        setTenants(Array.isArray(items) ? items : []);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleLogout() {
    await logout();
    window.location.href = "/login";
  }

  const totalMessages = Array.isArray(tenants) ? tenants.reduce((s, t) => s + (t.usage?.message_count_month || 0), 0) : 0;

  const greeting = () => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  };

  const today = new Date().toLocaleDateString("en-US", {
    weekday: "long", year: "numeric", month: "long", day: "numeric",
  });

  const metrics = [
    {
      icon: "🏢", label: "Active Tenants",
      value: loading ? "—" : tenants.length,
      color: "#06b6d4", bg: "rgba(6,182,212,0.1)", border: "rgba(6,182,212,0.2)",
      sub: "across all plans",
    },
    {
      icon: "💬", label: "Messages This Month",
      value: loading ? "—" : totalMessages.toLocaleString(),
      color: "#8b5cf6", bg: "rgba(139,92,246,0.1)", border: "rgba(139,92,246,0.2)",
      sub: "total across tenants",
    },
    {
      icon: "✅", label: "Platform Status",
      value: "Operational",
      color: "#10b981", bg: "rgba(16,185,129,0.1)", border: "rgba(16,185,129,0.2)",
      sub: "all systems normal",
    },
  ];

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#080d1a" }}>
      <Sidebar currentPath={location.pathname} onLogout={handleLogout} />

      <main style={{ flex: 1, padding: "36px 40px", overflowY: "auto" }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 36,
        }}>
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-0.5px", marginBottom: 6 }}>
              {greeting()}, Admin 👋
            </h1>
            <p style={{ color: "#475569", fontSize: 14 }}>{today}</p>
          </div>
          <Link to="/tenants">
            <button className="btn-primary" style={{ padding: "11px 24px", fontSize: 14 }}>
              + New Tenant
            </button>
          </Link>
        </div>

        {/* Metric cards */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20, marginBottom: 40 }}>
          {metrics.map((m, i) => (
            <div key={i} style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.07)",
              borderRadius: 16, padding: "26px 24px",
              animation: `fadeInUp 0.5s ease ${i * 0.1}s both`,
              transition: "all 0.3s",
              boxShadow: "0 4px 24px rgba(0,0,0,0.2)",
            }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLDivElement).style.borderColor = m.border;
                (e.currentTarget as HTMLDivElement).style.background = m.bg;
                (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)";
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.07)";
                (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.03)";
                (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
              }}
            >
              <div style={{
                width: 46, height: 46, borderRadius: 13,
                background: m.bg, border: `1px solid ${m.border}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 22, marginBottom: 18,
              }}>{m.icon}</div>
              <div style={{
                fontSize: 11, color: "#475569", fontWeight: 700,
                letterSpacing: "1.2px", textTransform: "uppercase", marginBottom: 6,
              }}>{m.label}</div>
              <div style={{
                fontSize: 32, fontWeight: 800, color: m.color,
                marginBottom: 4, letterSpacing: "-0.8px",
              }}>{m.value}</div>
              <div style={{ fontSize: 12, color: "#475569" }}>{m.sub}</div>
            </div>
          ))}
        </div>

        {/* Recent tenants */}
        <div>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20,
          }}>
            <h2 style={{ fontSize: 19, fontWeight: 700 }}>Recent Tenants</h2>
            <Link to="/tenants" style={{ fontSize: 13, color: "#06b6d4", fontWeight: 500 }}>
              View all →
            </Link>
          </div>

          {loading ? (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {[1, 2, 3].map(i => (
                <div key={i} style={{
                  background: "rgba(255,255,255,0.03)", borderRadius: 16, height: 130,
                  border: "1px solid rgba(255,255,255,0.05)",
                  backgroundImage: "linear-gradient(90deg, transparent, rgba(255,255,255,0.04), transparent)",
                  backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
                }} />
              ))}
            </div>
          ) : tenants.length === 0 ? (
            <div style={{
              textAlign: "center", padding: "70px 40px",
              background: "rgba(255,255,255,0.03)", borderRadius: 18,
              border: "1px dashed rgba(255,255,255,0.08)",
            }}>
              <div style={{ fontSize: 44, marginBottom: 16 }}>🏢</div>
              <p style={{ color: "#475569", marginBottom: 20, fontSize: 15 }}>
                No tenants yet. Create your first one to get started.
              </p>
              <Link to="/tenants">
                <button className="btn-primary" style={{ padding: "11px 24px", fontSize: 14 }}>
                  Create First Tenant
                </button>
              </Link>
            </div>
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {tenants.slice(0, 6).map((t, i) => {
                const planColor = PLAN_COLOR[t.plan] || "#06b6d4";
                return (
                  <div key={t.id} style={{
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.07)",
                    borderRadius: 16, padding: "20px",
                    animation: `fadeInUp 0.5s ease ${i * 0.08}s both`,
                    transition: "all 0.3s",
                    boxShadow: "0 4px 24px rgba(0,0,0,0.15)",
                  }}
                    onMouseEnter={e => {
                      (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.06)";
                      (e.currentTarget as HTMLDivElement).style.borderColor = `${planColor}33`;
                      (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)";
                    }}
                    onMouseLeave={e => {
                      (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.03)";
                      (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.07)";
                      (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
                    }}
                  >
                    <div style={{
                      display: "flex", alignItems: "flex-start",
                      justifyContent: "space-between", marginBottom: 14,
                    }}>
                      <div style={{
                        width: 40, height: 40, borderRadius: 10,
                        background: `${planColor}18`, border: `1px solid ${planColor}33`,
                        display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18,
                      }}>🏢</div>
                      <span style={{
                        padding: "3px 10px", borderRadius: 100, fontSize: 11, fontWeight: 600,
                        background: `${planColor}18`, color: planColor,
                        border: `1px solid ${planColor}33`, textTransform: "capitalize",
                      }}>{t.plan}</span>
                    </div>
                    <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 6, color: "#f1f5f9" }}>
                      {t.name}
                    </div>
                    <div style={{ fontSize: 13, color: "#475569", marginBottom: 16 }}>
                      {t.usage?.message_count_month ?? 0} messages this month
                    </div>
                    <Link to={`/tenants/${t.id}`}>
                      <button style={{
                        width: "100%", padding: "9px 0", borderRadius: 9,
                        border: "1px solid rgba(255,255,255,0.08)",
                        background: "rgba(255,255,255,0.04)", color: "#94a3b8",
                        fontSize: 13, fontWeight: 500, cursor: "pointer", transition: "all 0.2s",
                      }}
                        onMouseEnter={e => {
                          e.currentTarget.style.background = `${planColor}15`;
                          e.currentTarget.style.borderColor = `${planColor}33`;
                          e.currentTarget.style.color = planColor;
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.background = "rgba(255,255,255,0.04)";
                          e.currentTarget.style.borderColor = "rgba(255,255,255,0.08)";
                          e.currentTarget.style.color = "#94a3b8";
                        }}
                      >
                        View Details →
                      </button>
                    </Link>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
