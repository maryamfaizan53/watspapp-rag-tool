import { useState } from "react";
import { Link } from "react-router-dom";

interface Props {
  currentPath: string;
  onLogout: () => void;
}

const NAV_ITEMS = [
  { icon: "📊", label: "Dashboard", path: "/dashboard" },
  { icon: "🏢", label: "Tenants", path: "/tenants" },
];

export default function Sidebar({ currentPath, onLogout }: Props) {
  const [hoveredPath, setHoveredPath] = useState<string | null>(null);
  const [logoutHover, setLogoutHover] = useState(false);

  return (
    <div style={{
      width: 240,
      minHeight: "100vh",
      flexShrink: 0,
      background: "#0e1628",
      borderRight: "1px solid rgba(255,255,255,0.06)",
      display: "flex",
      flexDirection: "column",
      position: "sticky",
      top: 0,
      height: "100vh",
    }}>
      {/* Logo */}
      <div style={{
        padding: "24px 20px 20px",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        display: "flex", alignItems: "center", gap: 12,
      }}>
        <div style={{
          width: 38, height: 38, borderRadius: 10,
          background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 19, boxShadow: "0 4px 16px rgba(6,182,212,0.3)",
          flexShrink: 0,
        }}>🤖</div>
        <div>
          <div style={{ fontWeight: 800, fontSize: 17, letterSpacing: "-0.4px" }}>
            Bot<span style={{
              background: "linear-gradient(135deg, #06b6d4, #8b5cf6)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}>IQ</span>
          </div>
          <div style={{ fontSize: 11, color: "#475569", fontWeight: 500 }}>Admin Console</div>
        </div>
      </div>

      {/* Nav items */}
      <nav style={{ padding: "16px 12px", flex: 1 }}>
        <div style={{
          fontSize: 10, color: "#475569", fontWeight: 700,
          letterSpacing: "1.5px", textTransform: "uppercase",
          padding: "0 10px", marginBottom: 10,
        }}>
          Navigation
        </div>

        {NAV_ITEMS.map((item) => {
          const isActive =
            currentPath === item.path ||
            (item.path !== "/dashboard" && currentPath.startsWith(item.path));
          const isHovered = hoveredPath === item.path;

          return (
            <Link
              key={item.path}
              to={item.path}
              style={{ textDecoration: "none" }}
              onMouseEnter={() => setHoveredPath(item.path)}
              onMouseLeave={() => setHoveredPath(null)}
            >
              <div style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "11px 12px", borderRadius: 10, marginBottom: 4,
                background: isActive
                  ? "linear-gradient(135deg, rgba(6,182,212,0.15), rgba(139,92,246,0.1))"
                  : isHovered
                  ? "rgba(255,255,255,0.05)"
                  : "transparent",
                border: isActive
                  ? "1px solid rgba(6,182,212,0.2)"
                  : "1px solid transparent",
                transition: "all 0.2s ease",
                cursor: "pointer",
              }}>
                <span style={{
                  fontSize: 18, width: 24, textAlign: "center",
                  filter: isActive ? "none" : "opacity(0.7)",
                }}>{item.icon}</span>
                <span style={{
                  fontSize: 14,
                  fontWeight: isActive ? 600 : 500,
                  color: isActive ? "#06b6d4" : isHovered ? "#f1f5f9" : "#94a3b8",
                  transition: "color 0.2s",
                }}>{item.label}</span>
                {isActive && (
                  <div style={{
                    marginLeft: "auto", width: 6, height: 6,
                    borderRadius: "50%", background: "#06b6d4",
                  }} />
                )}
              </div>
            </Link>
          );
        })}
      </nav>

      {/* User + logout */}
      <div style={{
        padding: "16px 12px 20px",
        borderTop: "1px solid rgba(255,255,255,0.06)",
      }}>
        {/* User pill */}
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "10px 12px", borderRadius: 10, marginBottom: 10,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}>
          <div style={{
            width: 32, height: 32, borderRadius: "50%",
            background: "linear-gradient(135deg, #8b5cf6, #06b6d4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 14, fontWeight: 700, color: "#fff", flexShrink: 0,
          }}>A</div>
          <div style={{ overflow: "hidden" }}>
            <div style={{
              fontSize: 13, fontWeight: 600, color: "#f1f5f9",
              whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
            }}>Admin</div>
            <div style={{ fontSize: 11, color: "#475569" }}>Super Admin</div>
          </div>
        </div>

        {/* Logout button */}
        <button
          onClick={onLogout}
          onMouseEnter={() => setLogoutHover(true)}
          onMouseLeave={() => setLogoutHover(false)}
          style={{
            width: "100%", padding: "10px 12px",
            background: logoutHover ? "rgba(239,68,68,0.1)" : "rgba(255,255,255,0.03)",
            border: logoutHover ? "1px solid rgba(239,68,68,0.3)" : "1px solid rgba(255,255,255,0.06)",
            borderRadius: 10,
            color: logoutHover ? "#ef4444" : "#94a3b8",
            fontSize: 14, fontWeight: 500, cursor: "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            transition: "all 0.2s ease",
          }}
        >
          <span>🚪</span> Sign Out
        </button>
      </div>
    </div>
  );
}
