import {
  createContext,
  createElement,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type {
  ControlEvent,
  Device,
  DeviceInput,
  GestureAction,
  GestureMapping,
  GuardianLink,
  HelpRequest,
  HelpStatus,
  Paged,
  PageMeta,
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

// ---- AuthContext ----

interface AuthValue {
  session: Session | null;
  /** 첫 로그인 상태 확인이 끝나기 전에는 true */
  checking: boolean;
  /** 로그인이 만료되어 로그인 화면으로 돌아왔을 때 보여줄 안내 */
  notice: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  expire: (message?: string) => void;
  hasRole: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [checking, setChecking] = useState(true);
  const [notice, setNotice] = useState<string | null>(null);
  const sessionRef = useRef<Session | null>(null);
  sessionRef.current = session;

  const refresh = useCallback(async () => {
    try {
      setSession(await api.auth.me());
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setSession(null);
      else throw error;
    }
  }, []);

  useEffect(() => {
    refresh()
      .catch(() => setSession(null))
      .finally(() => setChecking(false));
  }, [refresh]);

  const expire = useCallback((message = "로그인이 만료되었습니다. 다시 로그인하세요.") => {
    if (sessionRef.current) setNotice(message);
    setSession(null);
  }, []);

  // 어떤 API든 401을 받으면 로그인 화면으로 보낸다.
  useEffect(() => {
    const onUnauthorized = () => expire();
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [expire]);

  // 서버가 알려준 만료 시각에 맞춰 로그아웃 처리한다.
  useEffect(() => {
    if (!session) return;
    const remaining = session.expires_at_ms - Date.now();
    const timer = window.setTimeout(() => expire(), Math.max(0, Math.min(remaining, 2 ** 31 - 1)));
    return () => window.clearTimeout(timer);
  }, [session, expire]);

  const login = useCallback(async (email: string, password: string) => {
    const next = await api.auth.login(email, password);
    setNotice(null);
    setSession(next);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } finally {
      setNotice(null);
      setSession(null);
    }
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      session,
      checking,
      notice,
      login,
      logout,
      expire,
      hasRole: (...roles) => !!session && roles.includes(session.user.role),
    }),
    [session, checking, notice, login, logout, expire],
  );

  return createElement(AuthContext.Provider, { value }, children);
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}

/** 로그인한 화면에서만 쓴다. */
export function useSession(): Session {
  const { session } = useAuth();
  if (!session) throw new Error("login required");
  return session;
}

// ---- useResource ----

export interface Resource<T> {
  data: T | undefined;
  error: string | null;
  loading: boolean;
  reload: () => Promise<void>;
  setData: Dispatch<SetStateAction<T | undefined>>;
}

/** 비동기 조회 결과와 다시 불러오기를 관리한다. 늦게 도착한 이전 응답은 버린다. */
export function useResource<T>(loader: () => Promise<T>, deps: unknown[] = []): Resource<T> {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const requestId = useRef(0);
  // 호출하는 쪽이 넘긴 deps가 바뀔 때만 loader를 새로 만든다.
  const load = useCallback(loader, deps);

  const reload = useCallback(async () => {
    const current = ++requestId.current;
    setLoading(true);
    try {
      const result = await load();
      if (current === requestId.current) {
        setData(result);
        setError(null);
      }
    } catch (caught) {
      if (current === requestId.current) setError(errorMessage(caught));
    } finally {
      if (current === requestId.current) setLoading(false);
    }
  }, [load]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { data, error, loading, reload, setData };
}

// ---- useDirectory ----

interface DirectoryValue {
  users: User[];
  rooms: Room[];
  devices: Device[];
  loading: boolean;
  userName: (userId: string | null | undefined) => string;
  roomName: (roomId: string | null | undefined) => string;
  deviceName: (deviceId: string | null | undefined) => string;
  usersByRole: (role: Role) => User[];
  reload: () => Promise<void>;
  /** 저장·삭제 API가 돌려준 결과를 목록에 바로 반영한다(다시 불러오지 않음). */
  upsertUser: (user: User) => void;
  removeUser: (userId: string) => void;
  upsertRoom: (room: Room) => void;
  removeRoom: (roomId: string) => void;
  upsertDevice: (device: Device) => void;
  removeDevice: (deviceId: string) => void;
  patchDevice: (deviceId: string, changes: Partial<Device>) => void;
}

const DirectoryContext = createContext<DirectoryValue | null>(null);

function upsert<T>(items: T[], item: T, key: (value: T) => string): T[] {
  const id = key(item);
  return items.some((value) => key(value) === id) ? items.map((value) => (key(value) === id ? item : value)) : [...items, item];
}

/** 로그인 사용자가 볼 수 있는 사용자·방·기기 목록을 한 번 불러와 화면 곳곳에서 쓴다. */
export function DirectoryProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [rooms, setRooms] = useState<Room[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const userId = session?.user.user_id;

  const reload = useCallback(async () => {
    if (!userId) return;
    setLoading(true);
    try {
      const [nextUsers, nextRooms, nextDevices] = await Promise.all([api.users.list(), api.rooms.list(), api.devices.list()]);
      setUsers(nextUsers);
      setRooms(nextRooms);
      setDevices(nextDevices);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    if (!userId) {
      setUsers([]);
      setRooms([]);
      setDevices([]);
      return;
    }
    reload().catch(() => undefined);
  }, [userId, reload]);

  const value = useMemo<DirectoryValue>(() => {
    const userMap = new Map(users.map((user) => [user.user_id, user]));
    const roomMap = new Map(rooms.map((room) => [room.room_id, room]));
    const deviceMap = new Map(devices.map((device) => [device.device_id, device]));
    return {
      users,
      rooms,
      devices,
      loading,
      reload,
      userName: (id) => (id ? (userMap.get(id)?.name ?? id) : "-"),
      roomName: (id) => (id ? (roomMap.get(id)?.name ?? id) : "-"),
      deviceName: (id) => (id ? (deviceMap.get(id)?.name ?? id) : "-"),
      usersByRole: (role) => users.filter((user) => user.role === role),
      upsertUser: (user) => setUsers((current) => upsert(current, user, (item) => item.user_id)),
      removeUser: (id) => setUsers((current) => current.filter((item) => item.user_id !== id)),
      upsertRoom: (room) => setRooms((current) => upsert(current, room, (item) => item.room_id)),
      removeRoom: (id) => setRooms((current) => current.filter((item) => item.room_id !== id)),
      upsertDevice: (device) => setDevices((current) => upsert(current, device, (item) => item.device_id)),
      removeDevice: (id) => setDevices((current) => current.filter((item) => item.device_id !== id)),
      patchDevice: (id, changes) =>
        setDevices((current) => current.map((item) => (item.device_id === id ? { ...item, ...changes } : item))),
    };
  }, [users, rooms, devices, loading, reload]);

  return createElement(DirectoryContext.Provider, { value }, children);
}

export function useDirectory(): DirectoryValue {
  const value = useContext(DirectoryContext);
  if (!value) throw new Error("useDirectory must be used inside DirectoryProvider");
  return value;
}
