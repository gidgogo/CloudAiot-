import type { ReactNode } from "react";
import { AccountPage } from "./pages/AccountPage";
import { DashboardPage } from "./pages/DashboardPage";
import { HelpRequestPage } from "./pages/HelpRequestPage";
import { HistoryPage } from "./pages/HistoryPage";
import type { Role } from "./types";

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
  { path: "/account", element: <AccountPage /> },
];
