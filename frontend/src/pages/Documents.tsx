import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import DocumentUploader from "../components/DocumentUploader";
import Sidebar from "../components/Sidebar";
import { deleteDocument, getTenant, listDocuments, logout } from "../services/api";

const STATUS_CONFIG: Record<string, { color: string; bg: string; border: string; dot: string; label: string }> = {
  pending:    { color: "#f59e0b", bg: "rgba(245,158,11,0.1)",  border: "rgba(245,158,11,0.3)",  dot: "#f59e0b", label: "Pending" },
  processing: { color: "#06b6d4", bg: "rgba(6,182,212,0.1)",   border: "rgba(6,182,212,0.3)",   dot: "#06b6d4", label: "Processing" },
  ready:      { color: "#10b981", bg: "rgba(16,185,129,0.1)",  border: "rgba(16,185,129,0.3)",  dot: "#10b981", label: "Ready" },
  failed:     { color: "#ef4444", bg: "rgba(239,68,68,0.1)",   border: "rgba(239,68,68,0.3)",   dot: "#ef4444", label: "Failed" },
};

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function Documents() {
  const { id: tenantId } = useParams<{ id: string }>();
  const [docs, setDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [tenantName, setTenantName] = useState("Tenant");
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  async function load() {
    if (!tenantId) return;
    const r = await listDocuments(tenantId);
    setDocs(r.items);
    setLoading(false);
  }

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, 10_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [tenantId]);

  useEffect(() => {
    if (!tenantId) return;
    getTenant(tenantId).then(t => setTenantName(t.name)).catch(() => {});
  }, [tenantId]);

  async function handleLogout() {
    await logout();
    window.location.href = "/login";
  }

  async function handleDelete(docId: string) {
    setDeletingId(docId);
    try {
      await deleteDocument(tenantId!, docId);
      setConfirmDeleteId(null);
      await load();
    } finally {
      setDeletingId(null);
    }
  }

  const processingCount = docs.filter(d => d.status === "processing" || d.status === "pending").length;

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
          <Link to={`/tenants/${tenantId}`}
            style={{ color: "#475569", transition: "color 0.2s" }}
            onMouseEnter={e => (e.currentTarget.style.color = "#94a3b8")}
            onMouseLeave={e => (e.currentTarget.style.color = "#475569")}
          >{tenantName}</Link>
          <span style={{ color: "#2d3a50" }}>/</span>
          <span style={{ color: "#94a3b8" }}>Documents</span>
        </div>

        {/* Header */}
        <div style={{
          display: "flex", alignItems: "center",
          justifyContent: "space-between", marginBottom: 32,
        }}>
          <div>
            <h1 style={{ fontSize: 28, fontWeight: 800, letterSpacing: "-0.5px", marginBottom: 4 }}>
              Knowledge Base
            </h1>
            <p style={{ color: "#475569", fontSize: 14 }}>
              {tenantName} · {loading ? "…" : `${docs.length} document${docs.length !== 1 ? "s" : ""}`}
              {processingCount > 0 && (
                <span style={{ marginLeft: 10, color: "#06b6d4" }}>
                  · {processingCount} processing
                  <span style={{
                    display: "inline-block", marginLeft: 6, width: 12, height: 12,
                    border: "2px solid rgba(6,182,212,0.3)", borderTopColor: "#06b6d4",
                    borderRadius: "50%", verticalAlign: "middle",
                    animation: "spin 1s linear infinite",
                  }} />
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Upload zone */}
        <div style={{
          background: "rgba(255,255,255,0.03)",
          border: "1px dashed rgba(6,182,212,0.25)",
          borderRadius: 18, padding: "28px 32px",
          marginBottom: 32,
          display: "flex", alignItems: "center",
          justifyContent: "space-between", flexWrap: "wrap", gap: 20,
          transition: "border-color 0.2s, background 0.2s",
        }}
          onMouseEnter={e => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(6,182,212,0.4)";
            (e.currentTarget as HTMLDivElement).style.background = "rgba(6,182,212,0.03)";
          }}
          onMouseLeave={e => {
            (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(6,182,212,0.25)";
            (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.03)";
          }}
        >
          <div>
            <h3 style={{ fontWeight: 700, fontSize: 16, marginBottom: 5 }}>📤 Upload Document</h3>
            <p style={{ color: "#475569", fontSize: 13 }}>
              PDF or TXT · max 50 MB · auto-indexed for RAG
            </p>
          </div>
          <DocumentUploader tenantId={tenantId!} onUploaded={load} />
        </div>

        {/* Document list */}
        {loading ? (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {[1, 2, 3, 4].map(i => (
              <div key={i} style={{
                height: 80, borderRadius: 14,
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.05)",
                backgroundImage: "linear-gradient(90deg, transparent, rgba(255,255,255,0.03), transparent)",
                backgroundSize: "200% 100%", animation: "shimmer 1.5s infinite",
              }} />
            ))}
          </div>
        ) : docs.length === 0 ? (
          <div style={{
            textAlign: "center", padding: "80px 40px",
            background: "rgba(255,255,255,0.02)", borderRadius: 20,
            border: "1px dashed rgba(255,255,255,0.08)",
          }}>
            <div style={{ fontSize: 52, marginBottom: 16 }}>📁</div>
            <h3 style={{ fontSize: 22, fontWeight: 700, marginBottom: 10 }}>No documents yet</h3>
            <p style={{ color: "#475569", fontSize: 15 }}>
              Upload a PDF or TXT file above to train your bot.
            </p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {docs.map((d, i) => {
              const s = STATUS_CONFIG[d.status] || STATUS_CONFIG.pending;
              const isConfirming = confirmDeleteId === d.id;
              return (
                <div key={d.id} style={{
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: 14, padding: "18px 22px",
                  display: "flex", alignItems: "center", gap: 16,
                  animation: `fadeInUp 0.4s ease ${i * 0.05}s both`,
                  transition: "all 0.25s",
                }}
                  onMouseEnter={e => {
                    (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.05)";
                    (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.1)";
                  }}
                  onMouseLeave={e => {
                    (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.03)";
                    (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.07)";
                  }}
                >
                  {/* File icon */}
                  <div style={{
                    width: 44, height: 44, borderRadius: 12, flexShrink: 0,
                    background: "rgba(255,255,255,0.05)",
                    border: "1px solid rgba(255,255,255,0.08)",
                    display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22,
                  }}>
                    {d.name.endsWith(".pdf") ? "📄" : "📝"}
                  </div>

                  {/* File info */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{
                      fontWeight: 600, fontSize: 14, color: "#f1f5f9",
                      marginBottom: 4, whiteSpace: "nowrap",
                      overflow: "hidden", textOverflow: "ellipsis",
                    }}>
                      {d.name}
                    </div>
                    <div style={{
                      display: "flex", alignItems: "center", gap: 12,
                      fontSize: 12, color: "#475569",
                    }}>
                      <span>{formatBytes(d.file_size_bytes)}</span>
                      {d.chunk_count != null && <span>· {d.chunk_count} chunks</span>}
                      <span>· {new Date(d.uploaded_at).toLocaleDateString()}</span>
                    </div>
                  </div>

                  {/* Status badge with dot */}
                  <div style={{
                    display: "flex", alignItems: "center", gap: 7,
                    padding: "6px 14px", borderRadius: 100, fontSize: 12, fontWeight: 600,
                    background: s.bg, color: s.color, border: `1px solid ${s.border}`,
                    flexShrink: 0,
                  }}>
                    <span style={{
                      width: 7, height: 7, borderRadius: "50%",
                      background: s.dot, display: "inline-block",
                      boxShadow: d.status === "processing" || d.status === "pending"
                        ? `0 0 6px ${s.dot}`
                        : "none",
                    }} />
                    {s.label}
                  </div>

                  {/* Delete */}
                  {isConfirming ? (
                    <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
                      <button
                        onClick={() => handleDelete(d.id)}
                        disabled={deletingId === d.id}
                        style={{
                          padding: "6px 14px", borderRadius: 8, border: "none",
                          background: "#ef4444", color: "#fff",
                          fontWeight: 600, fontSize: 12, cursor: "pointer",
                        }}
                      >
                        {deletingId === d.id ? "…" : "Delete"}
                      </button>
                      <button
                        onClick={() => setConfirmDeleteId(null)}
                        style={{
                          padding: "6px 10px", borderRadius: 8,
                          border: "1px solid rgba(255,255,255,0.1)",
                          background: "transparent", color: "#94a3b8",
                          fontSize: 12, cursor: "pointer",
                        }}
                      >Cancel</button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmDeleteId(d.id)}
                      title="Delete document"
                      style={{
                        padding: "8px 12px", borderRadius: 9, flexShrink: 0,
                        border: "1px solid rgba(239,68,68,0.2)",
                        background: "rgba(239,68,68,0.07)",
                        color: "#ef4444", fontSize: 14, cursor: "pointer",
                        transition: "all 0.2s",
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = "rgba(239,68,68,0.15)")}
                      onMouseLeave={e => (e.currentTarget.style.background = "rgba(239,68,68,0.07)")}
                    >🗑</button>
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
