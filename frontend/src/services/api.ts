import axios, { AxiosInstance } from "axios";

const BASE_URL = import.meta.env.VITE_API_URL || "";

const api: AxiosInstance = axios.create({ baseURL: BASE_URL });

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Redirect to /login on 401
api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("access_token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

// ── Auth ─────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<string> {
  const { data } = await api.post("/auth/login", { email, password });
  return data.access_token;
}

export async function logout(): Promise<void> {
  await api.post("/auth/logout");
  localStorage.removeItem("access_token");
}

// ── Tenants ───────────────────────────────────────────────────────────

export async function listTenants(params?: { status?: string; page?: number }): Promise<any> {
  const { data } = await api.get("/admin/tenants", { params });
  return data;
}

export async function createTenant(body: {
  name: string;
  plan: string;
  quota?: { messages_per_month: number; rate_limit_per_minute: number };
}): Promise<any> {
  const { data } = await api.post("/admin/tenants", body);
  return data;
}

export async function getTenant(tenantId: string): Promise<any> {
  const { data } = await api.get(`/admin/tenants/${tenantId}`);
  return data;
}

export async function updateTenant(tenantId: string, body: any): Promise<any> {
  const { data } = await api.put(`/admin/tenants/${tenantId}`, body);
  return data;
}

export async function deleteTenant(tenantId: string): Promise<void> {
  await api.delete(`/admin/tenants/${tenantId}`);
}

export async function configureChannels(tenantId: string, body: any): Promise<void> {
  await api.put(`/admin/tenants/${tenantId}/channels`, body);
}

// ── Documents ────────────────────────────────────────────────────────

export async function listDocuments(tenantId: string, status?: string): Promise<any> {
  const { data } = await api.get(`/admin/tenants/${tenantId}/documents`, {
    params: status ? { status } : undefined,
  });
  return data;
}

export async function uploadDocument(tenantId: string, file: File): Promise<any> {
  const form = new FormData();
  form.append("file", file);
  const { data } = await api.post(`/admin/tenants/${tenantId}/documents`, form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function deleteDocument(tenantId: string, documentId: string): Promise<void> {
  await api.delete(`/admin/tenants/${tenantId}/documents/${documentId}`);
}

// ── Metrics ───────────────────────────────────────────────────────────

export async function getTenantMetrics(
  tenantId: string,
  params?: { from_date?: string; to_date?: string }
): Promise<any> {
  const { data } = await api.get(`/admin/tenants/${tenantId}/metrics`, { params });
  return data;
}
