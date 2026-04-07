import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../services/api";

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

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
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", minHeight: "100vh" }}>
      <form onSubmit={handleSubmit} style={{ background: "#fff", padding: 32, borderRadius: 8, width: 360, boxShadow: "0 2px 8px rgba(0,0,0,.1)" }}>
        <h1 style={{ marginBottom: 24, fontSize: 22 }}>PSX Chatbot Admin</h1>
        {error && <p style={{ color: "#c00", marginBottom: 12 }}>{error}</p>}
        <label style={{ display: "block", marginBottom: 4 }}>Email</label>
        <input
          type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
          style={{ width: "100%", padding: 8, marginBottom: 16, border: "1px solid #ccc", borderRadius: 4 }}
        />
        <label style={{ display: "block", marginBottom: 4 }}>Password</label>
        <input
          type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
          style={{ width: "100%", padding: 8, marginBottom: 24, border: "1px solid #ccc", borderRadius: 4 }}
        />
        <button type="submit" disabled={loading}
          style={{ width: "100%", padding: 10, background: "#0070f3", color: "#fff", border: "none", borderRadius: 4, fontWeight: 600 }}>
          {loading ? "Signing in…" : "Sign In"}
        </button>
      </form>
    </div>
  );
}
