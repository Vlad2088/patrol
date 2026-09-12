// API-клиент: fetch с JWT, refresh-логика, типизированные методы
const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8100/api/v1";

export interface TokenPair {
  access: string;
  refresh: string;
  role: "dispatcher" | "guard";
  full_name: string;
}

const store = {
  get access() {
    return localStorage.getItem("patrol_access") ?? "";
  },
  get refresh() {
    return localStorage.getItem("patrol_refresh") ?? "";
  },
  set(t: TokenPair) {
    localStorage.setItem("patrol_access", t.access);
    localStorage.setItem("patrol_refresh", t.refresh);
    localStorage.setItem("patrol_user", JSON.stringify({ role: t.role, full_name: t.full_name }));
  },
  clear() {
    localStorage.removeItem("patrol_access");
    localStorage.removeItem("patrol_refresh");
    localStorage.removeItem("patrol_user");
  },
};

export const authStore = store;

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function doRefresh(): Promise<boolean> {
  const r = store.refresh;
  if (!r) return false;
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: r }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  localStorage.setItem("patrol_access", data.access);
  localStorage.setItem("patrol_refresh", data.refresh);
  return true;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (store.access) headers.Authorization = `Bearer ${store.access}`;
  if (options.body) headers["Content-Type"] = "application/json";

  const res = await fetch(`${BASE}${path}`, { ...options, headers });
  if (res.status === 401 && retry && store.refresh) {
    if (await doRefresh()) return request<T>(path, options, false);
    store.clear();
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* пустое тело */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") ?? "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.blob()) as unknown as T;
}

// --- типы ---

export interface Obj { id: number; name: string; address: string | null; is_active: boolean }
export interface RouteT { id: number; object_id: number; name: string; is_active: boolean; checkpoints_count: number }
export interface CheckpointT { id: number; route_id: number; order_num: number; code: string; name: string | null }
export interface ScheduleT {
  id: number; route_id: number; kind: "once" | "daily" | "weekly" | "shift";
  once_date: string | null; weekdays: number[] | null; shift_kind: "day" | "night" | null;
  window_start: string; window_end: string; is_active: boolean;
}
export interface ShiftT { id: number; object_id: number; guard_id: number; starts_at: string; ends_at: string; guard_full_name: string; object_name: string }
export interface GuardT { id: number; login: string; full_name: string; role: string; is_active: boolean; created_at: string }
export interface PatrolT {
  id: number; object_id: number; object_name: string; route_id: number; route_name: string;
  patrol_date: string; window_start: string; window_end: string; status: string;
  started_by_id: number | null; started_at: string | null; finished_at: string | null;
  checkpoints_total: number; checkpoints_scanned: number;
}
export interface DashboardRowT {
  object_id: number; object_name: string; patrols_total: number; in_progress: number;
  completed: number; missed: number; partial: number; planned: number; violations: number;
}
export interface ViolationT { id: number; patrol_id: number; kind: string; details: Record<string, unknown>; detected_at: string }
export interface AuditT { id: number; user_id: number; action: string; entity: string; entity_id: number | null; payload: Record<string, unknown>; created_at: string }

// --- API ---

export const api = {
  login: (login: string, password: string) =>
    request<TokenPair>("/auth/login", { method: "POST", body: JSON.stringify({ login, password }) }),

  objects: () => request<Obj[]>("/objects"),
  createObject: (b: { name: string; address?: string }) =>
    request<Obj>("/objects", { method: "POST", body: JSON.stringify(b) }),
  updateObject: (id: number, b: Partial<Obj>) =>
    request<Obj>(`/objects/${id}`, { method: "PATCH", body: JSON.stringify(b) }),

  routes: (objectId?: number) =>
    request<RouteT[]>(`/routes${objectId ? `?object_id=${objectId}` : ""}`),
  createRoute: (b: { object_id: number; name: string }) =>
    request<RouteT>("/routes", { method: "POST", body: JSON.stringify(b) }),
  checkpoints: (routeId: number) => request<CheckpointT[]>(`/routes/${routeId}/checkpoints`),
  addCheckpoints: (routeId: number, items: { name: string | null }[]) =>
    request<CheckpointT[]>(`/routes/${routeId}/checkpoints`, { method: "POST", body: JSON.stringify({ items }) }),
  deleteCheckpoint: (id: number) => request<void>(`/checkpoints/${id}`, { method: "DELETE" }),
  qrPdfUrl: (routeId: number) => `${BASE}/routes/${routeId}/qr.pdf`,

  schedules: (routeId?: number) =>
    request<ScheduleT[]>(`/schedules${routeId ? `?route_id=${routeId}` : ""}`),
  createSchedule: (b: Record<string, unknown>) =>
    request<ScheduleT>("/schedules", { method: "POST", body: JSON.stringify(b) }),
  deleteSchedule: (id: number) => request<void>(`/schedules/${id}`, { method: "DELETE" }),

  shifts: (params?: { object_id?: number; date?: string }) => {
    const q = new URLSearchParams();
    if (params?.object_id) q.set("object_id", String(params.object_id));
    if (params?.date) q.set("date", params.date);
    return request<ShiftT[]>(`/shifts${q.size ? `?${q}` : ""}`);
  },
  createShift: (b: { object_id: number; guard_id: number; starts_at: string; ends_at: string }) =>
    request<ShiftT>("/shifts", { method: "POST", body: JSON.stringify(b) }),
  deleteShift: (id: number) => request<void>(`/shifts/${id}`, { method: "DELETE" }),

  guards: () => request<GuardT[]>("/guards"),
  createGuard: (b: { login: string; password: string; full_name: string }) =>
    request<GuardT>("/guards", { method: "POST", body: JSON.stringify(b) }),
  updateGuard: (id: number, b: Record<string, unknown>) =>
    request<GuardT>(`/guards/${id}`, { method: "PATCH", body: JSON.stringify(b) }),

  patrols: (params?: { date?: string; object_id?: number; status_filter?: string }) => {
    const q = new URLSearchParams();
    if (params?.date) q.set("date", params.date);
    if (params?.object_id) q.set("object_id", String(params.object_id));
    if (params?.status_filter) q.set("status_filter", params.status_filter);
    return request<PatrolT[]>(`/patrols${q.size ? `?${q}` : ""}`);
  },

  dashboard: (date?: string) =>
    request<{ date: string; rows: DashboardRowT[] }>(`/dashboard${date ? `?date=${date}` : ""}`),
  notifications: () => request<ViolationT[]>("/notifications"),

  reportUrl: (kind: "patrols" | "violations", fmt: "csv" | "xlsx") => `${BASE}/reports/${kind}.${fmt}`,

  audit: () => request<AuditT[]>("/audit"),
};
