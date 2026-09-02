const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export class ApiClient {
  private static getToken() {
    if (typeof window !== "undefined") {
      return localStorage.getItem("sentinel_token");
    }
    return null;
  }

  private static async request(endpoint: string, options: RequestInit = {}) {
    const token = this.getToken();
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...((options.headers as Record<string, string>) || {}),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP Error ${response.status}`);
    }

    if (response.status === 204) return null;
    return response.json();
  }

  private static async requestRaw(endpoint: string, options: RequestInit = {}) {
    const token = this.getToken();
    const headers: Record<string, string> = {
      ...((options.headers as Record<string, string>) || {}),
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || `HTTP Error ${response.status}`);
    }
    if (response.status === 204) return null;
    return response.json();
  }

  // ── Auth ──────────────────────────────────────────────────────
  static async login(credentials: { username: string; password: string }) {
    const data = await this.request("/auth/login", {
      method: "POST",
      body: JSON.stringify(credentials),
    });
    if (data.access_token && typeof window !== "undefined") {
      localStorage.setItem("sentinel_token", data.access_token);
      localStorage.setItem("sentinel_user", JSON.stringify(data));
    }
    return data;
  }

  static logout() {
    if (typeof window !== "undefined") {
      localStorage.removeItem("sentinel_token");
      localStorage.removeItem("sentinel_user");
      window.location.href = "/login";
    }
  }

  static async getMe() {
    return this.request("/auth/me");
  }

  static getStoredUser(): { user_id: string; username: string; role: string } | null {
    if (typeof window === "undefined") return null;
    const raw = localStorage.getItem("sentinel_user");
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
  }

  // ── Dashboard & Security ──────────────────────────────────────
  static async getDashboard() {
    return this.request("/dashboard");
  }

  static async getSecurityMode() {
    return this.request("/security/mode");
  }

  static async getAuditLog() {
    return this.request("/audit/log");
  }

  static async verifyAuditChain() {
    return this.request("/audit/verify");
  }

  static async getNetworkMonitor() {
    return this.request("/security/network-monitor");
  }

  // ── Sessions (FR9.3 — persistent chat history) ────────────────
  static async listSessions() {
    return this.request("/sessions");
  }

  static async createSession(title: string = "New Chat") {
    return this.request("/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    });
  }

  static async getSession(sessionId: string) {
    return this.request(`/sessions/${sessionId}`);
  }

  static async deleteSession(sessionId: string) {
    return this.request(`/sessions/${sessionId}`, { method: "DELETE" });
  }

  static async getMessages(sessionId: string) {
    return this.request(`/sessions/${sessionId}/messages`);
  }

  static async sendMessage(sessionId: string, content: string) {
    return this.request(`/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  }

  // ── Tasks (FR3.5, FR9.5) ──────────────────────────────────────
  static async listTasks() {
    return this.request("/tasks");
  }

  static async getTask(id: string) {
    return this.request(`/tasks/${id}`);
  }

  static async createTask(goal: string, sessionId?: string) {
    return this.request("/tasks", {
      method: "POST",
      body: JSON.stringify({ goal, session_id: sessionId }),
    });
  }

  // ── Artifacts (FR6) ───────────────────────────────────────────
  static async listArtifacts() {
    return this.request("/artifacts");
  }

  static async getArtifact(id: string) {
    return this.request(`/artifacts/${id}`);
  }

  static async approveArtifact(id: string) {
    return this.request(`/artifacts/${id}/approve`, { method: "POST" });
  }

  static async rejectArtifact(id: string) {
    return this.request(`/artifacts/${id}/reject`, { method: "POST" });
  }

  // ── Knowledge Base (FR5) ──────────────────────────────────────
  static async listFiles() {
    return this.request("/files");
  }

  static async uploadFile(formData: FormData) {
    // Do NOT set Content-Type — browser auto-sets multipart boundary
    return this.requestRaw("/files/upload", {
      method: "POST",
      body: formData,
    });
  }

  static async searchKB(query: string) {
    return this.request("/rag/query", {
      method: "POST",
      body: JSON.stringify({ query, top_k: 5 }),
    });
  }

  // ── Models (FR1, FR1.4 — Model Resource Dashboard) ────────────
  static async listModels() {
    return this.request("/models");
  }
}
