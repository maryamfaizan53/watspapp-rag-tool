import { FormEvent, useState } from "react";
import { configureChannels } from "../services/api";

interface Props { tenantId: string; channels: any; onSaved: () => void; }

export default function ChannelConfig({ tenantId, channels, onSaved }: Props) {
  const [tgToken, setTgToken] = useState("");
  const [waAccountSid, setWaAccountSid] = useState("");
  const [waAuthToken, setWaAuthToken] = useState("");
  const [waFromNumber, setWaFromNumber] = useState("");
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      await configureChannels(tenantId, {
        telegram_bot_token: tgToken || undefined,
        whatsapp_account_sid: waAccountSid || undefined,
        whatsapp_auth_token: waAuthToken || undefined,
        whatsapp_from_number: waFromNumber || undefined,
      });
      setMsg("Channels saved successfully.");
      setTgToken(""); setWaAccountSid(""); setWaAuthToken(""); setWaFromNumber("");
      onSaved();
    } catch (err: any) {
      setMsg(err.response?.data?.detail || "Failed to save channels.");
    } finally {
      setSaving(false);
    }
  }

  const inputStyle = { width: "100%", padding: 8, border: "1px solid #ccc", borderRadius: 4, marginBottom: 12 };

  return (
    <form onSubmit={handleSave} style={{ maxWidth: 480 }}>
      <h3 style={{ marginBottom: 16 }}>Channel Configuration</h3>

      <h4 style={{ marginBottom: 8 }}>Telegram</h4>
      {channels?.telegram?.configured && <p style={{ color: "#0a0", marginBottom: 8, fontSize: 13 }}>✓ Telegram configured</p>}
      <input placeholder="Bot token (leave blank to keep existing)" value={tgToken} onChange={(e) => setTgToken(e.target.value)} style={inputStyle} />

      <h4 style={{ marginBottom: 8, marginTop: 8 }}>WhatsApp (Twilio)</h4>
      {channels?.whatsapp?.configured && <p style={{ color: "#0a0", marginBottom: 8, fontSize: 13 }}>✓ WhatsApp configured — from: {channels.whatsapp.from_number}</p>}
      <input placeholder="Account SID" value={waAccountSid} onChange={(e) => setWaAccountSid(e.target.value)} style={inputStyle} />
      <input placeholder="Auth Token" value={waAuthToken} onChange={(e) => setWaAuthToken(e.target.value)} style={inputStyle} />
      <input placeholder="From Number (e.g. +15551234567)" value={waFromNumber} onChange={(e) => setWaFromNumber(e.target.value)} style={inputStyle} />

      {msg && <p style={{ marginBottom: 12, color: msg.includes("success") ? "#0a0" : "#c00" }}>{msg}</p>}
      <button type="submit" disabled={saving}
        style={{ padding: "8px 20px", background: "#0070f3", color: "#fff", border: "none", borderRadius: 4 }}>
        {saving ? "Saving…" : "Save Channels"}
      </button>
    </form>
  );
}
