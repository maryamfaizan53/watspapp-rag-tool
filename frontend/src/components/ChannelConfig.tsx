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
  const [msg, setMsg] = useState<{ text: string; ok: boolean } | null>(null);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  const wa = channels?.whatsapp || {};
  const tg = channels?.telegram || {};

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setMsg(null);
    try {
      await configureChannels(tenantId, {
        telegram_bot_token: tgToken || undefined,
        whatsapp_access_token: waAccessToken || undefined,
        whatsapp_phone_number_id: waPhoneNumberId || undefined,
        whatsapp_app_secret: waAppSecret || undefined,
        whatsapp_verify_token: waVerifyToken || undefined,
      });
      setMsg({ text: "Channels saved successfully.", ok: true });
      setTgToken("");
      setWaAccessToken(""); setWaPhoneNumberId("");
      setWaAppSecret(""); setWaVerifyToken("");
      onSaved();
    } catch (err: any) {
      setMsg({ text: err.response?.data?.detail || "Failed to save channels.", ok: false });
    } finally {
      setSaving(false);
    }
  }

  const inputStyle = (field: string) => ({
    width: "100%",
    background: "#080d1a",
    border: `1px solid ${focusedField === field ? "#06b6d4" : "rgba(255,255,255,0.08)"}`,
    borderRadius: 10, color: "#f1f5f9",
    padding: "12px 16px", fontSize: 14, outline: "none",
    transition: "border-color 0.2s, box-shadow 0.2s",
    boxShadow: focusedField === field ? "0 0 0 3px rgba(6,182,212,0.1)" : "none",
  });

  return (
    <form onSubmit={handleSave}>
      {/* Status banner */}
      {msg && (
        <div style={{
          background: msg.ok ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
          border: `1px solid ${msg.ok ? "rgba(16,185,129,0.25)" : "rgba(239,68,68,0.25)"}`,
          borderRadius: 12, padding: "14px 18px", marginBottom: 24,
          display: "flex", alignItems: "center", gap: 10,
          fontSize: 14, color: msg.ok ? "#6ee7b7" : "#fca5a5",
          animation: "fadeIn 0.3s ease",
        }}>
          {msg.ok ? "✅" : "⚠️"} {msg.text}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>

        {/* ── Telegram card ── */}
        <div style={{
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderRadius: 20, padding: 28,
          boxShadow: "0 4px 24px rgba(0,0,0,0.15)",
          transition: "border-color 0.2s",
        }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = "rgba(0,136,204,0.25)")}
          onMouseLeave={e => (e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)")}
        >
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24 }}>
            <div style={{
              width: 50, height: 50, borderRadius: 14, fontSize: 24,
              background: "rgba(0,136,204,0.12)", border: "1px solid rgba(0,136,204,0.25)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>✈️</div>
            <div>
              <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>Telegram</h3>
              {tg.configured ? (
                <span style={{
                  padding: "3px 10px", borderRadius: 100, fontSize: 11, fontWeight: 600,
                  background: "rgba(16,185,129,0.1)", color: "#10b981",
                  border: "1px solid rgba(16,185,129,0.25)",
                }}>✓ Configured</span>
              ) : (
                <span style={{
                  padding: "3px 10px", borderRadius: 100, fontSize: 11, fontWeight: 600,
                  background: "rgba(245,158,11,0.1)", color: "#f59e0b",
                  border: "1px solid rgba(245,158,11,0.25)",
                }}>Not Configured</span>
              )}
            </div>
          </div>

          {/* Bot Token field */}
          <div>
            <label style={{
              display: "block", fontSize: 11, fontWeight: 700,
              color: "#94a3b8", marginBottom: 8,
              textTransform: "uppercase", letterSpacing: "1.2px",
            }}>
              Bot Token
            </label>
            <input
              style={inputStyle("tg_token")}
              placeholder="123456:ABCdef… (leave blank to keep)"
              value={tgToken}
              onChange={e => setTgToken(e.target.value)}
              onFocus={() => setFocusedField("tg_token")}
              onBlur={() => setFocusedField(null)}
            />
            <p style={{ marginTop: 8, fontSize: 12, color: "#475569" }}>
              Get this from @BotFather on Telegram.
            </p>
          </div>
        </div>

        {/* ── WhatsApp card ── */}
        <div style={{
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.07)",
          borderRadius: 20, padding: 28,
          boxShadow: "0 4px 24px rgba(0,0,0,0.15)",
          transition: "border-color 0.2s",
        }}
          onMouseEnter={e => (e.currentTarget.style.borderColor = "rgba(37,211,102,0.2)")}
          onMouseLeave={e => (e.currentTarget.style.borderColor = "rgba(255,255,255,0.07)")}
        >
          {/* Header */}
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 24 }}>
            <div style={{
              width: 50, height: 50, borderRadius: 14, fontSize: 24,
              background: "rgba(37,211,102,0.1)", border: "1px solid rgba(37,211,102,0.25)",
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>💬</div>
            <div>
              <h3 style={{ fontSize: 17, fontWeight: 700, marginBottom: 6 }}>WhatsApp</h3>
              {wa.configured ? (
                <span style={{
                  padding: "3px 10px", borderRadius: 100, fontSize: 11, fontWeight: 600,
                  background: "rgba(16,185,129,0.1)", color: "#10b981",
                  border: "1px solid rgba(16,185,129,0.25)",
                }}>✓ Configured{wa.phone_number_id ? ` · ${wa.phone_number_id}` : ""}</span>
              ) : (
                <span style={{
                  padding: "3px 10px", borderRadius: 100, fontSize: 11, fontWeight: 600,
                  background: "rgba(245,158,11,0.1)", color: "#f59e0b",
                  border: "1px solid rgba(245,158,11,0.25)",
                }}>Not Configured</span>
              )}
            </div>
          </div>

          {/* WA fields */}
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {[
              { label: "Access Token", field: "wa_token", value: waAccessToken, setter: setWaAccessToken, placeholder: "From Meta App Dashboard" },
              { label: "Phone Number ID", field: "wa_phone", value: waPhoneNumberId, setter: setWaPhoneNumberId, placeholder: "From Meta App Dashboard" },
              { label: "App Secret", field: "wa_secret", value: waAppSecret, setter: setWaAppSecret, placeholder: "For webhook signature verification" },
              { label: "Verify Token", field: "wa_verify", value: waVerifyToken, setter: setWaVerifyToken, placeholder: "Any string, e.g. my-verify-token" },
            ].map(({ label, field, value, setter, placeholder }) => (
              <div key={field}>
                <label style={{
                  display: "block", fontSize: 11, fontWeight: 700,
                  color: "#94a3b8", marginBottom: 6,
                  textTransform: "uppercase", letterSpacing: "1.2px",
                }}>{label}</label>
                <input
                  style={inputStyle(field)}
                  placeholder={placeholder}
                  value={value}
                  onChange={e => setter(e.target.value)}
                  onFocus={() => setFocusedField(field)}
                  onBlur={() => setFocusedField(null)}
                />
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Save button */}
      <div style={{ marginTop: 24, display: "flex", justifyContent: "flex-end" }}>
        <button
          type="submit"
          disabled={saving}
          style={{
            padding: "13px 36px", borderRadius: 12, border: "none",
            background: saving ? "rgba(255,255,255,0.07)" : "linear-gradient(135deg, #06b6d4, #8b5cf6)",
            color: saving ? "#475569" : "#fff",
            fontSize: 15, fontWeight: 700, cursor: saving ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", gap: 10, transition: "all 0.3s",
            boxShadow: saving ? "none" : "0 4px 24px rgba(6,182,212,0.3)",
          }}
          onMouseEnter={e => { if (!saving) e.currentTarget.style.transform = "translateY(-2px)"; }}
          onMouseLeave={e => { e.currentTarget.style.transform = "translateY(0)"; }}
        >
          {saving ? (
            <>
              <span style={{
                width: 16, height: 16, border: "2px solid rgba(255,255,255,0.2)",
                borderTopColor: "#94a3b8", borderRadius: "50%",
                display: "inline-block", animation: "spin 1s linear infinite",
              }} />
              Saving…
            </>
          ) : "💾 Save Channels"}
        </button>
      </div>
    </form>
  );
}
