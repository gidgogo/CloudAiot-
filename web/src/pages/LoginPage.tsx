import { type FormEvent, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, errorMessage, useAuth, useDirectory, useSession } from "../api/client";
import { useAction, useToast } from "../components/HelpRequestList";
import { formatTime, ROLE_LABEL } from "../types";

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

// ---- AccountPage ----

export function AccountPage() {
  const session = useSession();
  const { userName } = useDirectory();
  const { push } = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");
  const { run, busy } = useAction();

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (next !== confirm) {
      push({ tone: "warning", title: "새 비밀번호가 서로 다릅니다" });
      return;
    }
    const ok = await run(() => api.auth.changePassword(current, next), {
      success: "비밀번호를 바꿨어요",
      failure: "비밀번호를 바꾸지 못했어요",
    });
    if (ok) {
      setCurrent("");
      setNext("");
      setConfirm("");
    }
  };

  return (
    <div>
      <div className="page-head">
        <h1>내 계정</h1>
      </div>
      <div className="grid-2">
        <section className="card">
          <h2>계정 정보</h2>
          <dl className="details">
            <dt>이름</dt>
            <dd>{session.user.name}</dd>
            <dt>이메일</dt>
            <dd>{session.user.email}</dd>
            <dt>역할</dt>
            <dd>{ROLE_LABEL[session.user.role]}</dd>
            {session.user.role === "GUARDIAN" && (
              <>
                <dt>연결된 사용자</dt>
                <dd>{session.linked_user_ids.length ? session.linked_user_ids.map(userName).join(", ") : "없음"}</dd>
              </>
            )}
            <dt>로그인 만료</dt>
            <dd>{formatTime(session.expires_at_ms)}</dd>
          </dl>
        </section>
        <section className="card">
          <h2>비밀번호 변경</h2>
          <form className="form" onSubmit={submit}>
            <label>
              현재 비밀번호
              <input type="password" required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
            </label>
            <label>
              새 비밀번호 <small className="muted">(8자 이상)</small>
              <input
                type="password"
                required
                minLength={8}
                maxLength={72}
                autoComplete="new-password"
                value={next}
                onChange={(e) => setNext(e.target.value)}
              />
            </label>
            <label>
              새 비밀번호 확인
              <input type="password" required autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </label>
            <button type="submit" className="button primary" disabled={busy}>
              {busy ? "바꾸는 중…" : "비밀번호 바꾸기"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
