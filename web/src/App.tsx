import { type ReactNode, useState } from "react";
import { BrowserRouter, Link, Navigate, NavLink, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, DirectoryProvider, useAuth, useSession } from "./api/client";
import { HelpAlerts, ToastProvider } from "./components/HelpRequestList";
import { DashboardPage, HistoryPage } from "./pages/DashboardPage";
import { HelpRequestPage } from "./pages/HelpRequestPage";
import { AccountPage, LoginPage } from "./pages/LoginPage";
import { AdminPage, RoomMappingPage } from "./pages/RoomMappingPage";
import { canWatchHelp, hasAnyRole, type Role, ROLE_LABEL } from "./types";
import { RealtimeProvider, type SocketStatus, useRealtimeStatus } from "./websocket/eventClient";

function RequireLogin({ children }: { children: ReactNode }) {
  const { session, checking } = useAuth();
  const location = useLocation();
  if (checking) return <div className="splash" role="status">불러오는 중…</div>;
  if (!session) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

function Guarded({ page }: { page: PageRoute }) {
  const { hasRole } = useAuth();
  if (!page.roles || hasRole(...page.roles)) return <>{page.element}</>;
  return (
    <section className="card">
      <h1>접근 권한이 없습니다</h1>
      <p className="muted">이 화면은 {page.roles.map((role) => ROLE_LABEL[role]).join(", ")}만 사용할 수 있습니다.</p>
      <Link to="/" className="link">대시보드로 돌아가기</Link>
    </section>
  );
}

function NotFound() {
  return (
    <section className="card">
      <h1>페이지를 찾을 수 없습니다</h1>
      <Link to="/" className="link">대시보드로 돌아가기</Link>
    </section>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <RealtimeProvider>
            <DirectoryProvider>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route
                  element={
                    <RequireLogin>
                      <Layout />
                    </RequireLogin>
                  }
                >
                  {PAGES.map((page) =>
                    page.path === "/" ? (
                      <Route key={page.path} index element={<Guarded page={page} />} />
                    ) : (
                      <Route key={page.path} path={page.path.slice(1)} element={<Guarded page={page} />} />
                    ),
                  )}
                  <Route path="*" element={<NotFound />} />
                </Route>
              </Routes>
            </DirectoryProvider>
          </RealtimeProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}

// ---- routes ----

export interface PageRoute {
  path: string;
  element: ReactNode;
  /** 메뉴에 보일 이름. 없으면 메뉴에 넣지 않는다. */
  label?: string;
  /** 볼 수 있는 역할. 없으면 로그인한 모두. */
  roles?: Role[];
}

/** 로그인 후 화면 목록. 경로·메뉴·접근 권한을 이 한 곳에서 정한다. */
export const PAGES: PageRoute[] = [
  { path: "/", label: "대시보드", element: <DashboardPage /> },
  { path: "/help", label: "도움 요청", element: <HelpRequestPage /> },
  { path: "/history", label: "제어 이력", roles: ["GUARDIAN", "ADMIN"], element: <HistoryPage /> },
  { path: "/mapping", label: "방·기기 설정", roles: ["ADMIN"], element: <RoomMappingPage /> },
  { path: "/admin", label: "사용자·매핑 관리", roles: ["ADMIN"], element: <AdminPage /> },
  { path: "/account", element: <AccountPage /> },
];

// ---- Layout ----

const SOCKET_LABEL: Record<SocketStatus, string> = {
  connecting: "연결 중",
  open: "실시간 연결됨",
  reconnecting: "다시 연결 중",
  unauthorized: "인증 필요",
  closed: "연결 안 됨",
};

function NotificationButton() {
  const supported = typeof window !== "undefined" && "Notification" in window;
  const [permission, setPermission] = useState(supported ? Notification.permission : "denied");
  if (!supported || permission !== "default") return null;
  return (
    <button
      type="button"
      className="button ghost small"
      onClick={async () => setPermission(await Notification.requestPermission())}
    >
      🔔 브라우저 알림 켜기
    </button>
  );
}

export function Layout() {
  const session = useSession();
  const { logout } = useAuth();
  const { status } = useRealtimeStatus();
  const [menuOpen, setMenuOpen] = useState(false);
  const role = session.user.role;
  const links = PAGES.filter((page) => page.label && hasAnyRole(role, page.roles));

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">본문으로 건너뛰기</a>
      <header className="topbar">
        <div className="topbar-inner">
          <NavLink to="/" className="brand" onClick={() => setMenuOpen(false)}>
            <span className="brand-mark" aria-hidden="true">✋</span>
            CloudAIoT
          </NavLink>
          <button
            type="button"
            className="icon-button menu-toggle"
            aria-expanded={menuOpen}
            aria-controls="main-nav"
            onClick={() => setMenuOpen((open) => !open)}
          >
            ☰<span className="sr-only">메뉴</span>
          </button>
          <nav id="main-nav" className={`nav${menuOpen ? " open" : ""}`} aria-label="주 메뉴">
            {links.map((page) => (
              <NavLink key={page.path} to={page.path} end={page.path === "/"} onClick={() => setMenuOpen(false)}>
                {page.label}
              </NavLink>
            ))}
          </nav>
          <div className="topbar-right">
            <span className={`live live-${status}`} title={SOCKET_LABEL[status]}>
              <span className="dot" aria-hidden="true" />
              <span className="live-label">{SOCKET_LABEL[status]}</span>
            </span>
            {canWatchHelp(role) && <NotificationButton />}
            <NavLink to="/account" className="user-chip" title="내 계정">
              {session.user.name}
              <small>{ROLE_LABEL[session.user.role]}</small>
            </NavLink>
            <button type="button" className="button ghost small" onClick={() => void logout()}>
              로그아웃
            </button>
          </div>
        </div>
      </header>
      <main id="main" className="page">
        <Outlet />
      </main>
      <HelpAlerts />
    </div>
  );
}
