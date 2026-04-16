import { FormEvent, useState } from "react";
import { configureChannels } from "../services/api";

interface Props { tenantId: string; channels: any; onSaved: () => void; }

export default function ChannelConfig({ tenantId, channels, onSaved }: Props) {
  const [tgToken, setTgToken] = useState("");
  const [waAccessToken, setWaAccessToken] = useState("");
  const [waPhoneNumberId, setWaPhoneNumberId] = useState("");
  const [waAppSecret, setWaAppSecret] = useState("");
  const [waVerifyToken, setWaVerifyToken] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await configureChannels(tenantId, {
        telegram_bot_token: tgToken || undefined,
        whatsapp_access_token: waAccessToken || undefined,
        whatsapp_phone_number_id: waPhoneNumberId || undefined,
        whatsapp_app_secret: waAppSecret || undefined,
        whatsapp_verify_token: waVerifyToken || undefined,
      });
      setMsg("Channels saved successfully.");
      setTgToken("");
      setWaAccessToken(""); setWaPhoneNumberId("");
      setWaAppSecret(""); setWaVerifyToken("");
      onSaved();
    } catch (err: any) {
      setMsg(err.response?.data?.detail || "Failed to save channels.");
    } finally {
      setSaving(false);
    }
  }

  const inputStyle = { width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 4, marginBottom: 12, boxSizing: "border-box" as const };
  const wa = channels?.whatsapp || {};

  return (
    <form onSubmit={handleSave} style={{ maxWidth: 480 }}>
      <h3 style={{ marginBottom: 16 }}>Channel Configuration</h3>

      <h4 style={{ marginBottom: 8 }}>Telegram</h4>
      {channels?.telegram?.configured && (
        <p style={{ color: "#0a0", marginBottom: 8, fontSize: 13 }}>✓ Telegram configured</p>
      )}
      <input
        placeholder="Bot token (leave blank to keep existing)"
        value={tgToken}
        onChange={(e) => setTgToken(e.target.value)}
        style={inputStyle}
      />

      <h4 style={{ marginBottom: 8, marginTop: 8 }}>WhatsApp (Meta Cloud API)</h4>
      {wa.configured && (
        <p style={{ color: "#0a0", marginBottom: 8, fontSize: 13 }}>
          ✓ WhatsApp configured — Phone Number ID: {wa.phone_number_id || "set"}
        </p>
      )}
      <input
        placeholder="Access Token (from Meta App Dashboard)"
        value={waAccessToken}
        onChange={(e) => setWaAccessToken(e.target.value)}
        style={inputStyle}
      />
      <input
        placeholder="Phone Number ID (from Meta App Dashboard)"
        value={waPhoneNumberId}
        onChange={(e) => setWaPhoneNumberId(e.target.value)}
        style={inputStyle}
      />
      <input
        placeholder="App Secret (for webhook signature verification)"
        value={waAppSecret}
        onChange={(e) => setWaAppSecret(e.target.value)}
        style={inputStyle}
      />
      <input
        placeholder="Verify Token (any string you choose, e.g. my-verify-token)"
        value={waVerifyToken}
        onChange={(e) => setWaVerifyToken(e.target.value)}
        style={inputStyle}
      />

      {msg && (
        <p style={{ marginBottom: 12, color: msg.includes("success") ? "#0a0" : "#c00" }}>{msg}</p>
      )}
      <button
        type="submit"
        disabled={saving}
        style={{ padding: "8px 20px", background: "#0070f3", color: "#fff", border: "none", borderRadius: 4, cursor: "pointer" }}
      >
        {saving ? "Saving…" : "Save Channels"}
      </button>
    </form>
  );
}
