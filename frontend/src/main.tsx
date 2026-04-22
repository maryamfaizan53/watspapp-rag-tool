import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import Dashboard from "./pages/Dashboard";
import Documents from "./pages/Documents";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import TenantDetail from "./pages/TenantDetail";
import Tenants from "./pages/Tenants";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/tenants" element={<Tenants />} />
          <Route path="/tenants/:id" element={<TenantDetail />} />
          <Route path="/tenants/:id/documents" element={<Documents />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>
);
