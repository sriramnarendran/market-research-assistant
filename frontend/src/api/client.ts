import type {
  AdminOverview,
  AppErrorRow,
  LoginRequest,
  RunCreateRequest,
  RunCreateResponse,
  RunDetail,
  RunMetrics,
  RunSummary,
  SignupRequest,
  SourceDetail,
  SourceSummary,
  UsageDayRow,
  UserResponse,
  UserUsageSummary,
} from "@/api/types";

const BASE = "/api";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      if (typeof parsed?.detail === "string") {
        detail = parsed.detail;
      } else if (Array.isArray(parsed?.detail)) {
        detail = parsed.detail
          .map((item: { msg?: string }) => item.msg)
          .filter(Boolean)
          .join(" ");
      }
    } catch {
      /* ignore */
    }
    throw new ApiError(resp.status, detail || resp.statusText);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export const api = {
  auth: {
    signup: (body: SignupRequest) =>
      request<UserResponse>("/auth/signup", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    login: (body: LoginRequest) =>
      request<UserResponse>("/auth/login", {
        method: "POST",
        body: JSON.stringify(body),
      }),
    logout: () =>
      request<void>("/auth/logout", {
        method: "POST",
      }),
    me: () => request<UserResponse>("/auth/me"),
  },
  createRun: (body: RunCreateRequest) =>
    request<RunCreateResponse>("/runs", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listRuns: () => request<RunSummary[]>("/runs"),
  getRun: (id: string) => request<RunDetail>(`/runs/${id}`),
  listRunSources: (id: string) => request<SourceSummary[]>(`/runs/${id}/sources`),
  getSource: (id: string) => request<SourceDetail>(`/sources/${id}`),
  exportRunPdf: async (id: string): Promise<void> => {
    const resp = await fetch(`${BASE}/runs/${id}/export.pdf`, {
      credentials: "include",
    });
    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      let detail = text;
      try {
        const parsed = JSON.parse(text);
        detail = typeof parsed?.detail === "string" ? parsed.detail : text;
      } catch {
        /* ignore */
      }
      throw new ApiError(resp.status, detail || resp.statusText);
    }
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report-${id}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
  admin: {
    overview: () => request<AdminOverview>("/admin/metrics/overview"),
    usage: () => request<UsageDayRow[]>("/admin/metrics/usage"),
    runs: () => request<RunMetrics>("/admin/metrics/runs"),
    userUsage: (userId: string) =>
      request<UserUsageSummary>(`/admin/users/${userId}/usage`),
    errors: () => request<AppErrorRow[]>("/admin/errors"),
  },
};

export { ApiError };
