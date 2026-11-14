import type { ReactNode } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { Layout } from "./components/Layout";
import { ToastProvider } from "./components/Toasts";
import { DirectoryProvider } from "./hooks/useDirectory";
import { LoginPage } from "./pages/LoginPage";
import { RealtimeProvider } from "./realtime/RealtimeContext";
import { PAGES, type PageRoute } from "./routes";
import { ROLE_LABEL } from "./utils/format";

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
