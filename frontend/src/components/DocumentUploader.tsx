import { ChangeEvent, DragEvent, useState } from "react";
import { uploadDocument } from "../services/api";

const MAX_SIZE_MB = 50;
const ACCEPTED = ".pdf,.txt,application/pdf,text/plain";

interface Props { tenantId: string; onUploaded: () => void; }

export default function DocumentUploader({ tenantId, onUploaded }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(0);

  async function processFile(file: File) {
    setError(""); setSuccess("");

    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File exceeds ${MAX_SIZE_MB} MB limit.`);
      return;
    }

    setUploading(true);
    setProgress(0);

    // Simulate upload progress
    const progressInterval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 85) { clearInterval(progressInterval); return prev; }
        return prev + Math.random() * 15;
      });
    }, 200);

    try {
      const doc = await uploadDocument(tenantId, file);
      clearInterval(progressInterval);
      setProgress(100);
      setSuccess(`"${doc.name}" uploaded — processing started…`);
      onUploaded();
    } catch (err: any) {
      clearInterval(progressInterval);
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409) setError("This document is already in the knowledge base.");
      else if (err.response?.status === 415) setError("Unsupported file type. Only PDF and TXT accepted.");
      else if (err.response?.status === 413) setError("File exceeds 50 MB limit.");
      else setError(detail || "Upload failed.");
    } finally {
      setUploading(false);
      setProgress(0);
    }
  }

  async function handleFileInput(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    await processFile(file);
    e.target.value = "";
  }

  async function handleDrop(e: DragEvent<HTMLLabelElement>) {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    await processFile(file);
  }

  return (
    <div style={{ width: "100%" }}>
      {/* Drop zone */}
      <label
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 10,
          padding: "32px 24px",
          borderRadius: 14,
          border: `1.5px dashed ${dragging ? "#06b6d4" : uploading ? "rgba(139,92,246,0.4)" : "rgba(255,255,255,0.12)"}`,
          background: dragging
            ? "rgba(6,182,212,0.06)"
            : uploading
            ? "rgba(139,92,246,0.05)"
            : "rgba(255,255,255,0.02)",
          cursor: uploading ? "not-allowed" : "pointer",
          transition: "all 0.25s",
          textAlign: "center",
        }}
        onMouseEnter={e => {
          if (!uploading && !dragging) {
            (e.currentTarget as HTMLLabelElement).style.borderColor = "rgba(6,182,212,0.4)";
            (e.currentTarget as HTMLLabelElement).style.background = "rgba(6,182,212,0.04)";
          }
        }}
        onMouseLeave={e => {
          if (!uploading && !dragging) {
            (e.currentTarget as HTMLLabelElement).style.borderColor = "rgba(255,255,255,0.12)";
            (e.currentTarget as HTMLLabelElement).style.background = "rgba(255,255,255,0.02)";
          }
        }}
      >
        {/* Upload icon */}
        <div style={{
          width: 52, height: 52, borderRadius: 14,
          background: uploading ? "rgba(139,92,246,0.12)" : "rgba(6,182,212,0.1)",
          border: `1px solid ${uploading ? "rgba(139,92,246,0.25)" : "rgba(6,182,212,0.2)"}`,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 24, transition: "all 0.25s",
          animation: uploading ? "pulse-glow 1.5s ease-in-out infinite" : "none",
        }}>
          {uploading ? "⏳" : dragging ? "📂" : "📤"}
        </div>

        {uploading ? (
          <div style={{ width: "100%", maxWidth: 260 }}>
            <p style={{ fontSize: 14, fontWeight: 600, color: "#94a3b8", marginBottom: 8 }}>
              Uploading…
            </p>
            {/* Progress bar */}
            <div style={{
              height: 4, borderRadius: 2,
              background: "rgba(255,255,255,0.08)", overflow: "hidden",
            }}>
              <div style={{
                height: "100%", borderRadius: 2,
                background: "linear-gradient(90deg, #06b6d4, #8b5cf6)",
                width: `${progress}%`, transition: "width 0.3s ease",
              }} />
            </div>
            <p style={{ fontSize: 12, color: "#475569", marginTop: 6 }}>
              {Math.round(progress)}% complete
            </p>
          </div>
        ) : (
          <>
            <p style={{ fontSize: 14, fontWeight: 600, color: "#f1f5f9" }}>
              Drop PDF or TXT here, or click to browse
            </p>
            <p style={{ fontSize: 12, color: "#475569" }}>
              Max {MAX_SIZE_MB} MB · PDF and TXT supported
            </p>
          </>
        )}

        <input
          type="file"
          accept={ACCEPTED}
          onChange={handleFileInput}
          disabled={uploading}
          style={{ display: "none" }}
        />
      </label>

      {/* Error message */}
      {error && (
        <div style={{
          marginTop: 12, padding: "11px 16px", borderRadius: 10, fontSize: 13,
          background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.25)",
          color: "#fca5a5", animation: "fadeIn 0.3s ease",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Success message */}
      {success && (
        <div style={{
          marginTop: 12, padding: "11px 16px", borderRadius: 10, fontSize: 13,
          background: "rgba(16,185,129,0.08)", border: "1px solid rgba(16,185,129,0.25)",
          color: "#6ee7b7", animation: "fadeIn 0.3s ease",
          display: "flex", alignItems: "center", gap: 8,
        }}>
          ✅ {success}
        </div>
      )}
    </div>
  );
}
