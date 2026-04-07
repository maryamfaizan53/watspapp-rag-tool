import { ChangeEvent, useState } from "react";
import { uploadDocument } from "../services/api";

const MAX_SIZE_MB = 50;
const ACCEPTED = ".pdf,.txt,application/pdf,text/plain";

interface Props { tenantId: string; onUploaded: () => void; }

export default function DocumentUploader({ tenantId, onUploaded }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  async function handleFile(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(""); setSuccess("");

    if (file.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File exceeds ${MAX_SIZE_MB} MB limit.`);
      return;
    }

    setUploading(true);
    try {
      const doc = await uploadDocument(tenantId, file);
      setSuccess(`"${doc.name}" uploaded — processing…`);
      onUploaded();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (err.response?.status === 409) setError("This document is already in the knowledge base.");
      else if (err.response?.status === 415) setError("Unsupported file type. Only PDF and TXT accepted.");
      else if (err.response?.status === 413) setError("File exceeds 50 MB limit.");
      else setError(detail || "Upload failed.");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <label style={{ display: "inline-block", padding: "8px 20px", background: uploading ? "#aaa" : "#0070f3",
        color: "#fff", borderRadius: 4, cursor: uploading ? "not-allowed" : "pointer" }}>
        {uploading ? "Uploading…" : "+ Upload Document"}
        <input type="file" accept={ACCEPTED} onChange={handleFile} disabled={uploading} style={{ display: "none" }} />
      </label>
      <span style={{ marginLeft: 12, fontSize: 12, color: "#888" }}>PDF or TXT · max 50 MB</span>
      {error && <p style={{ color: "#c00", marginTop: 8, fontSize: 13 }}>{error}</p>}
      {success && <p style={{ color: "#0a0", marginTop: 8, fontSize: 13 }}>{success}</p>}
    </div>
  );
}
