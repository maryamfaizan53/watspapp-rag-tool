import { Navigate, Outlet } from "react-router-dom";

function isAuthenticated(): boolean {
  const token = localStorage.getItem("access_token");
  if (!token) return false;
  try {
    // Decode JWT payload to check expiry (no library needed)
    const payload = JSON.parse(atob(token.split(".")[1]));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

export default function ProtectedRoute() {
  return isAuthenticated() ? <Outlet /> : <Navigate to="/login" replace />;
}
