import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createTenant, deleteTenant, listTenants } from "../services/api";

export default function Tenants() {
  const [tenants, setTenants] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPlan, setNewPlan] = useState("starter");
  const [error, setError] = useState("");

  async function load() {
    setLoading(true);
    const r = await listTenants();
    setTenants(r.items);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await createTenant({ name: newName, plan: newPlan });
      setNewName(""); setCreating(false);
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to create tenant");
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete tenant "${name}" and all its data? This cannot be undone.`)) return;
    await deleteTenant(id);
    await load();
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 32 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1>Tenants</h1>
        <button onClick={() => setCreating(true)}
          style={{ padding: "8px 20px", background: "#0070f3", color: "#fff", border: "none", borderRadius: 4 }}>
          + New Tenant
        </button>
      </div>

      {creating && (
        <form onSubmit={handleCreate} style={{ background: "#fff", padding: 20, borderRadius: 8, marginBottom: 24, boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
          <h3 style={{ marginBottom: 12 }}>Create Tenant</h3>
          {error && <p style={{ color: "#c00", marginBottom: 8 }}>{error}</p>}
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="Tenant name" required
            style={{ padding: 8, border: "1px solid #ccc", borderRadius: 4, marginRight: 8, width: 200 }} />
          <select value={newPlan} onChange={(e) => setNewPlan(e.target.value)}
            style={{ padding: 8, border: "1px solid #ccc", borderRadius: 4, marginRight: 8 }}>
            <option value="starter">Starter</option>
            <option value="growth">Growth</option>
            <option value="enterprise">Enterprise</option>
          </select>
          <button type="submit" style={{ padding: "8px 16px", background: "#0070f3", color: "#fff", border: "none", borderRadius: 4, marginRight: 8 }}>Create</button>
          <button type="button" onClick={() => setCreating(false)} style={{ padding: "8px 16px", border: "1px solid #ccc", borderRadius: 4 }}>Cancel</button>
        </form>
      )}

      {loading ? <p>Loading…</p> : (
        <table style={{ width: "100%", borderCollapse: "collapse", background: "#fff", borderRadius: 8, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #f0f0f0" }}>
              {["Name","Plan","Status","Messages","Actions"].map(h => (
                <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tenants.map((t) => (
              <tr key={t.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                <td style={{ padding: "12px 16px" }}><Link to={`/tenants/${t.id}`} style={{ color: "#0070f3" }}>{t.name}</Link></td>
                <td style={{ padding: "12px 16px", textTransform: "capitalize" }}>{t.plan}</td>
                <td style={{ padding: "12px 16px" }}><span style={{ background: t.status === "active" ? "#d4edda" : "#f8d7da", padding: "2px 8px", borderRadius: 12, fontSize: 12 }}>{t.status}</span></td>
                <td style={{ padding: "12px 16px" }}>{t.usage?.message_count_month ?? 0}</td>
                <td style={{ padding: "12px 16px" }}>
                  <Link to={`/tenants/${t.id}/documents`} style={{ color: "#0070f3", marginRight: 12 }}>Docs</Link>
                  <button onClick={() => handleDelete(t.id, t.name)} style={{ color: "#c00", background: "none", border: "none", cursor: "pointer" }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
