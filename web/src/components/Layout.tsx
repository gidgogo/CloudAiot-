import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useAuth, useSession } from "../auth/AuthContext";
import { useRealtimeStatus } from "../realtime/RealtimeContext";
import { PAGES } from "../routes";
import { ROLE_LABEL } from "../utils/format";
import { canWatchHelp, hasAnyRole } from "../utils/permissions";
import type { SocketStatus } from "../websocket/eventClient";
import { HelpAlerts } from "./HelpAlerts";

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
