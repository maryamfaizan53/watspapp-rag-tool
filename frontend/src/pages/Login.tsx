import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../services/api";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [focusedField, setFocusedField] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const token = await login(email, password);
      localStorage.setItem("access_token", token);
      navigate("/dashboard");
    } catch (err: any) {
      setError(err.response?.data?.detail || "Login failed. Check your credentials.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      display: "flex",
      background: "#080d1a",
      overflow: "hidden",
    }}>
      {/* ── LEFT PANEL ── */}
      <div style={{
        flex: "0 0 45%",
        position: "relative",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "60px 48px",
        background: "linear-gradient(145deg, #0e1a2e 0%, #080d1a 100%)",
        borderRight: "1px solid rgba(255,255,255,0.05)",
        overflow: "hidden",
      }}>
        {/* Decorative glow orbs */}
        <div style={{
          position: "absolute", top: "15%", left: "10%",
          width: 340, height: 340,
          background: "radial-gradient(circle, rgba(6,182,212,0.12) 0%, transparent 65%)",
          borderRadius: "50%", pointerEvents: "none",
          animation: "float 7s ease-in-out infinite",
        }} />
        <div style={{
          position: "absolute", bottom: "10%", right: "5%",
          width: 280, height: 280,
          background: "radial-gradient(circle, rgba(139,92,246,0.14) 0%, transparent 65%)",
          borderRadius: "50%", pointerEvents: "none",
          animation: "float 9s ease-in-out infinite reverse",
        }} />
        <div style={{
          position: "absolute", top: "55%", left: "55%",
          width: 180, height: 180,
          background: "radial-gradient(circle, rgba(16,185,129,0.08) 0%, transparent 65%)",
          borderRadius: "50%", pointerEvents: "none",
        }} />

        {/* Content */}
        <div style={{ position: "relative", zIndex: 1, textAlign: "center", maxWidth: 380 }}>
          {/* Logo */}
          <div style={{
            width: 72, height: 72, borderRadius: 20,
            background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 34, margin: "0 auto 24px",
            boxShadow: "0 8px 40px rgba(6,182,212,0.35)",
            animation: "pulse-glow 3s ease-in-out infinite",
          }}>🤖</div>

          <h1 style={{ fontSize: 38, fontWeight: 800, letterSpacing: "-1.5px", marginBottom: 12 }}>
            Bot<span style={{
              background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
              WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent", backgroundClip: "text",
            }}>IQ</span>
          </h1>
          <p style={{ fontSize: 17, color: "#94a3b8", lineHeight: 1.65, marginBottom: 48 }}>
            AI-powered WhatsApp &amp; Telegram bots for Pakistan's financial sector.
          </p>

          {/* Feature points */}
          <div style={{ display: "flex", flexDirection: "column", gap: 18, textAlign: "left" }}>
            {[
              { icon: "⚡", text: "Instant answers, 24/7" },
              { icon: "🇵🇰", text: "Urdu & English support" },
              { icon: "🔒", text: "Secure, isolated knowledge base" },
              { icon: "📊", text: "Real-time analytics dashboard" },
            ].map((item, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <div style={{
                  width: 38, height: 38, borderRadius: 10, flexShrink: 0,
                  background: "rgba(255,255,255,0.05)",
                  border: "1px solid rgba(255,255,255,0.08)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 18,
                }}>{item.icon}</div>
                <span style={{ color: "#94a3b8", fontSize: 15 }}>{item.text}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── RIGHT PANEL ── */}
      <div style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "60px 48px",
        position: "relative",
      }}>
        {/* Subtle background glow */}
        <div style={{
          position: "absolute", top: "30%", right: "20%",
          width: 300, height: 300,
          background: "radial-gradient(circle, rgba(139,92,246,0.07) 0%, transparent 65%)",
          borderRadius: "50%", pointerEvents: "none",
        }} />

        <div style={{
          position: "relative", zIndex: 1,
          width: "100%", maxWidth: 420,
          animation: "fadeInUp 0.7s ease both",
        }}>
          <div style={{ marginBottom: 40 }}>
            <h2 style={{ fontSize: 30, fontWeight: 800, letterSpacing: "-0.8px", marginBottom: 8 }}>
              Welcome back
            </h2>
            <p style={{ color: "#475569", fontSize: 15 }}>
              Sign in to your admin portal
            </p>
          </div>

          {/* Error banner */}
          {error && (
            <div style={{
              background: "rgba(239,68,68,0.08)",
              border: "1px solid rgba(239,68,68,0.25)",
              borderRadius: 12, padding: "14px 18px",
              marginBottom: 24, fontSize: 14,
              color: "#fca5a5", animation: "fadeIn 0.3s ease",
              display: "flex", alignItems: "center", gap: 8,
            }}>
              ⚠️ {error}
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 20 }}>
            {/* Email */}
            <div>
              <label style={{
                display: "block", fontSize: 13, fontWeight: 600,
                color: "#94a3b8", marginBottom: 8,
              }}>
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onFocus={() => setFocusedField("email")}
                onBlur={() => setFocusedField(null)}
                placeholder="admin@company.com"
                required
                style={{
                  width: "100%", background: "#0e1628",
                  border: `1px solid ${focusedField === "email" ? "#06b6d4" : "rgba(255,255,255,0.09)"}`,
                  borderRadius: 12, color: "#f1f5f9",
                  padding: "14px 18px", fontSize: 15, outline: "none",
                  transition: "border-color 0.2s, box-shadow 0.2s",
                  boxShadow: focusedField === "email" ? "0 0 0 3px rgba(6,182,212,0.12)" : "none",
                }}
              />
            </div>

            {/* Password */}
            <div>
              <label style={{
                display: "block", fontSize: 13, fontWeight: 600,
                color: "#94a3b8", marginBottom: 8,
              }}>
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={() => setFocusedField("password")}
                onBlur={() => setFocusedField(null)}
                placeholder="••••••••"
                required
                style={{
                  width: "100%", background: "#0e1628",
                  border: `1px solid ${focusedField === "password" ? "#06b6d4" : "rgba(255,255,255,0.09)"}`,
                  borderRadius: 12, color: "#f1f5f9",
                  padding: "14px 18px", fontSize: 15, outline: "none",
                  transition: "border-color 0.2s, box-shadow 0.2s",
                  boxShadow: focusedField === "password" ? "0 0 0 3px rgba(6,182,212,0.12)" : "none",
                }}
              />
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%", padding: "15px 0", borderRadius: 12, border: "none",
                background: loading ? "rgba(255,255,255,0.08)" : "linear-gradient(135deg, #06b6d4, #8b5cf6)",
                color: loading ? "#475569" : "#fff",
                fontSize: 16, fontWeight: 700, cursor: loading ? "not-allowed" : "pointer",
                display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
                boxShadow: loading ? "none" : "0 4px 24px rgba(6,182,212,0.3)",
                transition: "all 0.3s", marginTop: 8,
              }}
              onMouseEnter={e => { if (!loading) e.currentTarget.style.transform = "translateY(-2px)"; }}
              onMouseLeave={e => { e.currentTarget.style.transform = "translateY(0)"; }}
            >
              {loading ? (
                <>
                  <span style={{
                    display: "inline-block", width: 18, height: 18,
                    border: "2px solid rgba(255,255,255,0.2)", borderTopColor: "#94a3b8",
                    borderRadius: "50%", animation: "spin 1s linear infinite",
                  }} />
                  Signing in…
                </>
              ) : (
                "Sign In →"
              )}
            </button>
          </form>

          {/* Back to home */}
          <div style={{ textAlign: "center", marginTop: 32 }}>
            <Link
              to="/"
              style={{ fontSize: 14, color: "#475569", transition: "color 0.2s" }}
              onMouseEnter={e => (e.currentTarget.style.color = "#94a3b8")}
              onMouseLeave={e => (e.currentTarget.style.color = "#475569")}
            >
              ← Back to home
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
