import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { api, ApiError, UNAUTHORIZED_EVENT } from "../api/client";
import type { Role, Session } from "../types";

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

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
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
