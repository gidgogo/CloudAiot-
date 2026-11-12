import type {
  ControlEvent,
  Device,
  DeviceInput,
  GestureAction,
  GestureMapping,
  GuardianLink,
  HelpRequest,
  HelpStatus,
  PageMeta,
  Paged,
  Role,
  Room,
  Session,
  User,
} from "../types";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "/api/v1";
export const CSRF_COOKIE = "aiot_csrf_token";
export const CSRF_HEADER = "X-CSRF-Token";
/** 로그인이 만료되거나 풀렸을 때 window에 보내는 이벤트 이름. */
export const UNAUTHORIZED_EVENT = "aiot:unauthorized";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function readCookie(name: string, cookie: string = document.cookie): string | undefined {
  for (const part of cookie.split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key === name) return decodeURIComponent(rest.join("="));
  }
  return undefined;
}

type Query = Record<string, string | number | boolean | null | undefined>;

function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const search = params.toString();
  return `${API_BASE_URL}${path}${search ? `?${search}` : ""}`;
}

interface Envelope<T> {
  data: T;
  meta?: PageMeta;
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<Envelope<T>> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") {
    const csrf = readCookie(CSRF_COOKIE);
    if (csrf) headers[CSRF_HEADER] = csrf;
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      credentials: "include",
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "서버에 연결할 수 없습니다. 네트워크를 확인하세요.");
  }

  if (response.status === 204) return { data: undefined as T };

  let payload: { success?: boolean; data?: T; meta?: PageMeta; error?: { code: string; message: string } };
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(response.status, "INTERNAL_ERROR", "서버 응답을 해석할 수 없습니다.");
  }

  if (!response.ok || payload.success !== true) {
    const error = payload.error ?? { code: "INTERNAL_ERROR", message: "요청을 처리하지 못했습니다." };
    // 로그인 자체가 없거나 만료된 경우(UNAUTHORIZED)만 로그아웃 처리한다.
    // 비밀번호 틀림(INVALID_CREDENTIALS) 같은 다른 401은 화면에서 안내만 한다.
    if (error.code === "UNAUTHORIZED") window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    throw new ApiError(response.status, error.code, error.message);
  }
  return { data: payload.data as T, meta: payload.meta };
}

async function data<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  return (await request<T>(method, path, body, query)).data;
}

async function paged<T>(path: string, query?: Query): Promise<Paged<T>> {
  const result = await request<T[]>("GET", path, undefined, query);
  return { items: result.data, meta: result.meta ?? { total: result.data.length, limit: result.data.length, offset: 0 } };
}

export const api = {
  auth: {
    login: (email: string, password: string) => data<Session>("POST", "/auth/login", { email, password }),
    logout: () => data<null>("POST", "/auth/logout"),
    me: () => data<Session>("GET", "/auth/me"),
    changePassword: (current_password: string, new_password: string) =>
      data<null>("POST", "/auth/password", { current_password, new_password }),
  },
  rooms: {
    list: () => data<Room[]>("GET", "/rooms"),
    create: (room: { room_id?: string; name: string; description?: string | null; resident_user_id?: string | null }) =>
      data<Room>("POST", "/rooms", room),
    update: (roomId: string, changes: Partial<Pick<Room, "name" | "description" | "resident_user_id">>) =>
      data<Room>("PATCH", `/rooms/${encodeURIComponent(roomId)}`, changes),
    remove: (roomId: string) => data<void>("DELETE", `/rooms/${encodeURIComponent(roomId)}`),
  },
  devices: {
    list: (query?: { room_id?: string; enabled?: boolean }) => data<Device[]>("GET", "/devices", undefined, query),
    create: (device: DeviceInput) => data<Device>("POST", "/devices", device),
    update: (deviceId: string, changes: Partial<Omit<DeviceInput, "device_id">>) =>
      data<Device>("PATCH", `/devices/${encodeURIComponent(deviceId)}`, changes),
    remove: (deviceId: string) => data<void>("DELETE", `/devices/${encodeURIComponent(deviceId)}`),
  },
  controlEvents: {
    list: (query?: { device_id?: string; limit?: number; offset?: number }) => paged<ControlEvent>("/control-events", query),
  },
  helpRequests: {
    list: (query?: { status?: HelpStatus; limit?: number; offset?: number }) => paged<HelpRequest>("/help-requests", query),
    create: (userId?: string) => data<HelpRequest>("POST", "/help-requests", userId ? { user_id: userId } : {}),
    updateStatus: (requestId: string, status: Exclude<HelpStatus, "CREATED">) =>
      data<HelpRequest>("PATCH", `/help-requests/${encodeURIComponent(requestId)}`, { status }),
  },
  users: {
    list: (role?: Role) => data<User[]>("GET", "/users", undefined, { role }),
    create: (user: { user_id?: string; email: string; password: string; name: string; role: Role }) =>
      data<User>("POST", "/users", user),
    update: (userId: string, changes: { name?: string; role?: Role; password?: string }) =>
      data<User>("PATCH", `/users/${encodeURIComponent(userId)}`, changes),
    remove: (userId: string) => data<void>("DELETE", `/users/${encodeURIComponent(userId)}`),
  },
  guardianLinks: {
    list: () => data<GuardianLink[]>("GET", "/guardian-links"),
    create: (guardian_id: string, user_id: string) => data<GuardianLink>("POST", "/guardian-links", { guardian_id, user_id }),
    remove: (guardianId: string, userId: string) =>
      data<void>("DELETE", `/guardian-links/${encodeURIComponent(guardianId)}/${encodeURIComponent(userId)}`),
  },
  gestureMappings: {
    list: () => data<GestureMapping[]>("GET", "/gesture-mappings"),
    update: (gesture: string, changes: { action?: GestureAction; enabled?: boolean }) =>
      data<GestureMapping>("PATCH", `/gesture-mappings/${encodeURIComponent(gesture)}`, changes),
  },
};

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "알 수 없는 오류가 발생했습니다.";
}
