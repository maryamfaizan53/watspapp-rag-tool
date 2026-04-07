import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import DocumentUploader from "../components/DocumentUploader";
import { deleteDocument, listDocuments } from "../services/api";

const STATUS_COLORS: Record<string, string> = {
  pending: "#fff3cd",
  processing: "#cce5ff",
  ready: "#d4edda",
  failed: "#f8d7da",
};

export default function Documents() {
  const { id: tenantId } = useParams<{ id: string }>();
  const [docs, setDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function load() {
    if (!tenantId) return;
    const r = await listDocuments(tenantId);
    setDocs(r.items);
    setLoading(false);
  }

  useEffect(() => {
    load();
    // Poll every 10s for processing documents
    intervalRef.current = setInterval(load, 10_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [tenantId]);

  async function handleDelete(docId: string, name: string) {
    if (!confirm(`Delete "${name}"?`)) return;
    await deleteDocument(tenantId!, docId);
    await load();
  }

  return (
    <div style={{ maxWidth: 900, margin: "0 auto", padding: 32 }}>
      <div style={{ marginBottom: 16 }}>
        <Link to={`/tenants/${tenantId}`} style={{ color: "#0070f3" }}>← Tenant Detail</Link>
      </div>
      <h1 style={{ marginBottom: 24 }}>Knowledge Base Documents</h1>

      <DocumentUploader tenantId={tenantId!} onUploaded={load} />

      {loading ? <p>Loading…</p> : docs.length === 0 ? (
        <p style={{ color: "#888" }}>No documents yet. Upload a PDF or TXT file to get started.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", background: "#fff", borderRadius: 8, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,.08)" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid #f0f0f0" }}>
              {["Name","Status","Size","Chunks","Uploaded",""].map(h => (
                <th key={h} style={{ padding: "12px 16px", textAlign: "left", fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id} style={{ borderBottom: "1px solid #f0f0f0" }}>
                <td style={{ padding: "12px 16px", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.name}</td>
                <td style={{ padding: "12px 16px" }}>
                  <span style={{ background: STATUS_COLORS[d.status] || "#eee", padding: "2px 8px", borderRadius: 12, fontSize: 12 }}>{d.status}</span>
                </td>
                <td style={{ padding: "12px 16px", fontSize: 13, color: "#555" }}>{(d.file_size_bytes / 1024).toFixed(1)} KB</td>
                <td style={{ padding: "12px 16px", fontSize: 13, color: "#555" }}>{d.chunk_count ?? "—"}</td>
                <td style={{ padding: "12px 16px", fontSize: 12, color: "#888" }}>{new Date(d.uploaded_at).toLocaleDateString()}</td>
                <td style={{ padding: "12px 16px" }}>
                  <button onClick={() => handleDelete(d.id, d.name)} style={{ color: "#c00", background: "none", border: "none", cursor: "pointer" }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
