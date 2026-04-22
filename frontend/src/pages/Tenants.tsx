import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import Sidebar from "../components/Sidebar";
import { createTenant, deleteTenant, listTenants, logout } from "../services/api";

const PLAN_COLOR: Record<string, string> = {
  starter: "#06b6d4",
  growth: "#8b5cf6",
  enterprise: "#f59e0b",
};

const PLAN_LABEL: Record<string, string> = {
  starter: "Starter",
  growth: "Growth",
  enterprise: "Enterprise",
};

export default function Tenants() {
  const [tenants, setTenants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPlan, setNewPlan] = useState("starter");
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const location = useLocation();

  async function load() {
    setLoading(true);
    try {
      const r = await listTenants();
      setTenants(r.items);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function handleLogout() {
    await logout();
    window.location.href = "/login";
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setCreating(true);
    try {
      await createTenant({ name: newName, plan: newPlan });
      setNewName("");
      setShowForm(false);
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create tenant");
    } finally {
      setCreating(false);
    }
  }

  async function handleDelete(id: string) {
    setDeletingId(id);
    try {
      await deleteTenant(id);
      setConfirmDeleteId(null);
      await load();
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh", background: "#080d1a" }}>
      <Sidebar currentPath={location.pathname} onLogout={handleLogout} />

      {/* Add Tenant Modal */}
      {showForm && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 50,
          background: "rgba(0,0,0,0.65)", backdropFilter: "blur(6px)",
          display: "flex", alignItems: "center", justifyContent: "center",
          animation: "fadeIn 0.2s ease",
        }} onClick={() => setShowForm(false)}>
          <div style={{
            background: "#0e1628",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 24, padding: "40px 40px 36px",
            width: "100%", maxWidth: 460,
            boxShadow: "0 32px 80px rgba(0,0,0,0.7)",
            animation: "fadeInUp 0.3s ease",
          }} onClick={e => e.stopPropagation()}>
            {/* Modal header */}
            <div style={{
              display: "flex", alignItems: "center",
              justifyContent: "space-between", marginBottom: 32,
            }}>
              <div>
                <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 4 }}>Create Tenant</h2>
                <p style={{ fontSize: 13, color: "#475569" }}>Add a new client to the platform</p>
              </div>
              <button onClick={() => setShowForm(false)} style={{
                width: 34, height: 34, borderRadius: 9,
                background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.08)",
                color: "#94a3b8", fontSize: 16, cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>✕</button>
            </div>

            {error && (
              <div style={{
                background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)",
                borderRadius: 10, padding: "13px 16px", marginBottom: 24,
                fontSize: 14, color: "#fca5a5", display: "flex", alignItems: "center", gap: 8,
              }}>⚠️ {error}</div>
            )}

            <form onSubmit={handleCreate}>
              <div style={{ marginBottom: 20 }}>
                <label style={{
                  display: "block", fontSize: 13, fontWeight: 600,
                  color: "#94a3b8", marginBottom: 8,
                }}>Tenant Name</label>
                <input
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  onFocus={() => setFocusedField("name")}
                  onBlur={() => setFocusedField(null)}
                  placeholder="e.g. ABC Securities"
                  required
                  style={{
                    width: "100%", background: "rgba(255,255,255,0.04)",
                    border: `1px solid ${focusedField === "name" ? "#06b6d4" : "rgba(255,255,255,0.09)"}`,
                    borderRadius: 11, color: "#f1f5f9",
                    padding: "13px 16px", fontSize: 14, outline: "none",
                    transition: "border-color 0.2s, box-shadow 0.2s",
                    boxShadow: focusedField === "name" ? "0 0 0 3px rgba(6,182,212,0.1)" : "none",
                  }}
                />
              </div>

              <div style={{ marginBottom: 32 }}>
                <label style={{
                  display: "block", fontSize: 13, fontWeight: 600,
                  color: "#94a3b8", marginBottom: 8,
                }}>Plan</label>
                <select
                  value={newPlan}
                  onChange={e => setNewPlan(e.target.value)}
                  style={{
                    width: "100%", background: "#0e1628",
                    border: "1px solid rgba(255,255,255,0.09)",
                    borderRadius: 11, color: "#f1f5f9",
                    padding: "13px 16px", fontSize: 14, outline: "none",
                    cursor: "pointer",
                  }}
                >
                  <option value="starter">Starter — Rs 10,000/mo</option>
                  <option value="growth">Growth — Rs 18,000/mo</option>
                  <option value="enterprise">Enterprise — Custom</option>
                </select>
              </div>

              <div style={{ display: "flex", gap: 12 }}>
                <button
                  type="submit"
                  disabled={creating}
                  className="btn-primary"
                  style={{ flex: 1, opacity: creating ? 0.7 : 1 }}
                >
                  {creating ? "Creating…" : "Create Tenant"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  style={{
                    padding: "14px 20px", borderRadius: 12,
                    background: "rgba(255,255,255,0.05)",
                    border: "1px solid rgba(255,255,255,0.09)",
                    color: "#94a3b8", fontSize: 14, fontWeight: 500, cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                  onMouseEnter={e => (e.currentTarget.style.background = "rgba(255,255,255,0.09)")}
                  onMouseLeave={e => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Main content */}
      <main style={{ flex: 1, padding: "36px 40px", overflowY: "auto" }}>
        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center",
          justifyContent: "space-between", marginBottom: 36,
        }}>
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-0.5px", marginBottom: 4 }}>
              Tenants
            </h1>
            <p style={{ color: "#475569", fontSize: 14 }}>
              {loading ? "Loading…" : `${tenants.length} tenant${tenants.length !== 1 ? "s" : ""} configured`}
            </p>
          </div>
          <button
            className="btn-primary"
            onClick={() => { setShowForm(true); setError(""); }}
            style={{ padding: "11px 24px", fontSize: 14 }}
          >
            + New Tenant
          </button>
        </div>

        {/* Tenant grid */}
        {loading ? (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} style={{
                height: 200, borderRadius: 18,
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.05)",
                backgroundImage: "linear-gradient(90deg, transparent, rgba(255,255,255,0.03), transparent)",
                backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
              }} />
            ))}
          </div>
        ) : tenants.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "80px 40px",
            background: "rgba(255,255,255,0.02)", borderRadius: 20,
            border: "1px dashed rgba(255,255,255,0.08)",
          }}>
            <div style={{ fontSize: 52, marginBottom: 20 }}>🏢</div>
            <h3 style={{ fontSize: 22, fontWeight: 700, marginBottom: 10 }}>No tenants yet</h3>
            <p style={{ color: "#475569", marginBottom: 28, fontSize: 15 }}>
              Create your first tenant to get started.
            </p>
            <button className="btn-primary" onClick={() => setShowForm(true)}>
              Create First Tenant
            </button>
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
            {tenants.map((t, i) => {
              const planColor = PLAN_COLOR[t.plan] || "#06b6d4";
              const isConfirming = confirmDeleteId === t.id;
              return (
                <div key={t.id} style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: 18, padding: "24px",
                  animation: `fadeInUp 0.5s ease ${i * 0.07}s both`,
                  transition: "all 0.3s ease",
                  boxShadow: "0 4px 24px rgba(0,0,0,0.15)",
                }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLDivElement).style.borderColor = `${planColor}44`;
                    (e.currentTarget as HTMLDivElement).style.transform = "translateY(-3px)";
                    (e.currentTarget as HTMLDivElement).style.boxShadow = "0 12px 40px rgba(0,0,0,0.3)";
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.07)";
                    (e.currentTarget as HTMLDivElement).style.transform = "translateY(0)";
                    (e.currentTarget as HTMLDivElement).style.boxShadow = "0 4px 24px rgba(0,0,0,0.15)";
                  }}
                >
                  {/* Top row */}
                  <div style={{
                    display: "flex", alignItems: "flex-start",
                    justifyContent: "space-between", marginBottom: 18,
                  }}>
                    <div style={{
                      width: 46, height: 46, borderRadius: 13,
                      background: `${planColor}18`, border: `1px solid ${planColor}33`,
                      display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
                    }}>🏢</div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      {/* Status */}
                      <div style={{ display: "flex", alignItems: "center", gap: 5 }}>
                        <span style={{
                          width: 7, height: 7, borderRadius: "50%",
                          background: t.status === "active" ? "#10b981" : "#ef4444",
                          display: "inline-block",
                          boxShadow: t.status === "active" ? "0 0 6px rgba(16,185,129,0.5)" : "none",
                        }} />
                        <span style={{ fontSize: 11, color: "#475569", textTransform: "capitalize" }}>
                          {t.status}
                        </span>
                      </div>
                      {/* Plan badge */}
                      <span style={{
                        padding: "3px 10px", borderRadius: 100, fontSize: 11, fontWeight: 600,
                        background: `${planColor}18`, color: planColor,
                        border: `1px solid ${planColor}33`, textTransform: "capitalize",
                      }}>{PLAN_LABEL[t.plan] || t.plan}</span>
                    </div>
                  </div>

                  <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 6, color: "#f1f5f9" }}>
                    {t.name}
                  </h3>
                  <p style={{ fontSize: 13, color: "#475569", marginBottom: 20 }}>
                    {t.usage?.message_count_month ?? 0} messages this month
                  </p>

                  {/* Actions */}
                  {isConfirming ? (
                    <div style={{
                      background: "rgba(239,68,68,0.07)",
                      border: "1px solid rgba(239,68,68,0.2)",
                      borderRadius: 11, padding: "14px",
                    }}>
                      <p style={{ fontSize: 13, color: "#fca5a5", marginBottom: 12 }}>
                        Delete this tenant?
                      </p>
                      <div style={{ display: "flex", gap: 8 }}>
                        <button
                          onClick={() => handleDelete(t.id)}
                          disabled={deletingId === t.id}
                          style={{
                            flex: 1, padding: "8px 0", borderRadius: 8, border: "none",
                            background: "#ef4444", color: "#fff",
                            fontWeight: 600, fontSize: 13, cursor: "pointer",
                          }}
                        >
                          {deletingId === t.id ? "Deleting…" : "Confirm"}
                        </button>
                        <button
                          onClick={() => setConfirmDeleteId(null)}
                          style={{
                            flex: 1, padding: "8px 0", borderRadius: 8,
                            border: "1px solid rgba(255,255,255,0.1)",
                            background: "transparent", color: "#94a3b8",
                            fontSize: 13, cursor: "pointer",
                          }}
                        >Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: "flex", gap: 8 }}>
                      <Link to={`/tenants/${t.id}`} style={{ flex: 1 }}>
                        <button style={{
                          width: "100%", padding: "10px 0", borderRadius: 10,
                          background: `${planColor}18`, border: `1px solid ${planColor}33`,
                          color: planColor, fontWeight: 600, fontSize: 13, cursor: "pointer",
                          transition: "all 0.2s",
                        }}
                          onMouseEnter={e => (e.currentTarget.style.background = `${planColor}28`)}
                          onMouseLeave={e => (e.currentTarget.style.background = `${planColor}18`)}
                        >
                          View Details
                        </button>
                      </Link>
                      <button
                        onClick={() => setConfirmDeleteId(t.id)}
                        title="Delete tenant"
                        style={{
                          padding: "10px 14px", borderRadius: 10,
                          border: "1px solid rgba(239,68,68,0.2)",
                          background: "rgba(239,68,68,0.07)", color: "#ef4444",
                          fontSize: 14, cursor: "pointer", transition: "all 0.2s",
                          fontWeight: 500,
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = "rgba(239,68,68,0.15)")}
                        onMouseLeave={e => (e.currentTarget.style.background = "rgba(239,68,68,0.07)")}
                      >🗑</button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
