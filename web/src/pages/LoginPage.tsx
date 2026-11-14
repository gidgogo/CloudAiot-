import { useState, type FormEvent } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useAuth } from "../auth/AuthContext";

export function LoginPage() {
  const { session, login, notice } = useAuth();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const from = (location.state as { from?: string } | null)?.from ?? "/";
  if (session) return <Navigate to={from} replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login(email, password);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={submit} aria-labelledby="login-title">
        <div className="login-brand" aria-hidden="true">✋</div>
        <h1 id="login-title">CloudAIoT</h1>
        <p className="muted">손동작으로 기기를 제어하고 도움을 요청하는 AIoT 시스템</p>
        {notice && !error && <p className="notice" role="status">{notice}</p>}
        {error && <p className="error-text" role="alert">{error}</p>}
        <label>
          이메일
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoFocus
          />
        </label>
        <label>
          비밀번호
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <button type="submit" className="button primary block" disabled={submitting}>
          {submitting ? "로그인 중…" : "로그인"}
        </button>
        <p className="muted small">계정은 관리자에게 요청하세요.</p>
      </form>
    </main>
  );
}
