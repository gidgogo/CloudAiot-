import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage, useDirectory, useSession } from "../api/client";
import {
  canChangeHelpStatus,
  canWatchHelp,
  formatRelative,
  formatTime,
  HELP_SOURCE_LABEL,
  HELP_STATUS_LABEL,
  type HelpRequest,
  type HelpStatus,
} from "../types";
import { useRealtimeEvent, useRealtimeStatus } from "../websocket/eventClient";

interface Props {
  requests: HelpRequest[];
  userName: (userId: string | null) => string;
  canChange?: (request: HelpRequest) => boolean;
  onChange?: (request: HelpRequest, status: Exclude<HelpStatus, "CREATED">) => void;
  busyId?: string | null;
  showUser?: boolean;
  emptyText?: string;
}

const NEXT: Partial<Record<HelpStatus, { status: Exclude<HelpStatus, "CREATED">; label: string }>> = {
  CREATED: { status: "CONFIRMED", label: "확인했어요" },
  CONFIRMED: { status: "COMPLETED", label: "처리 완료" },
};

export function HelpStatusBadge({ status }: { status: HelpStatus }) {
  return <span className={`badge help-${status.toLowerCase()}`}>{HELP_STATUS_LABEL[status]}</span>;
}

export function HelpRequestList({ requests, userName, canChange, onChange, busyId, showUser = true, emptyText }: Props) {
  if (requests.length === 0) return <p className="empty">{emptyText ?? "도움 요청이 없습니다."}</p>;
  // 볼 권한이 없는 계정(예: 사용자가 보는 보호자)은 ID 대신 아무것도 표시하지 않는다.
  const actor = (id: string | null) => {
    if (!id) return "";
    const name = userName(id);
    return name && name !== id ? ` (${name})` : "";
  };
  return (
    <ul className="help-list">
      {requests.map((request) => {
        const next = NEXT[request.status];
        const actionable = !!next && !!onChange && (canChange?.(request) ?? false);
        return (
          <li key={request.request_id} className={`help-item help-item-${request.status.toLowerCase()}`}>
            <div className="help-item-main">
              <div className="help-item-title">
                <HelpStatusBadge status={request.status} />
                {showUser && <strong>{userName(request.user_id)}</strong>}
                <span className="muted">{HELP_SOURCE_LABEL[request.source]}으로 요청</span>
              </div>
              <div className="help-item-times muted small">
                <span title={formatTime(request.created_at_ms)}>요청 {formatRelative(request.created_at_ms)}</span>
                {request.confirmed_at_ms && (
                  <span>
                    · 확인 {formatTime(request.confirmed_at_ms)}
                    {actor(request.confirmed_by)}
                  </span>
                )}
                {request.completed_at_ms && (
                  <span>
                    · 완료 {formatTime(request.completed_at_ms)}
                    {actor(request.completed_by)}
                  </span>
                )}
              </div>
            </div>
            {actionable && next && (
              <button
                type="button"
                className={`button ${request.status === "CREATED" ? "danger" : "primary"}`}
                disabled={busyId === request.request_id}
                onClick={() => onChange?.(request, next.status)}
              >
                {busyId === request.request_id ? "처리 중…" : next.label}
              </button>
            )}
          </li>
        );
      })}
    </ul>
  );
}

// ---- Toasts ----

export type ToastTone = "info" | "success" | "warning" | "danger";

export interface ToastInput {
  tone?: ToastTone;
  title: string;
  message?: string;
  /** true면 사용자가 닫을 때까지 남는다(도움 요청 등). */
  sticky?: boolean;
  action?: { label: string; onClick: () => void };
}

interface Toast extends ToastInput {
  id: number;
}

interface ToastValue {
  push: (toast: ToastInput) => void;
}

const ToastContext = createContext<ToastValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)), []);

  const push = useCallback(
    (toast: ToastInput) => {
      const id = nextId.current++;
      setToasts((current) => [...current.slice(-4), { ...toast, id }]);
      if (!toast.sticky) window.setTimeout(() => dismiss(id), toast.tone === "danger" ? 8000 : 4000);
    },
    [dismiss],
  );

  const value = useMemo(() => ({ push }), [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast toast-${toast.tone ?? "info"}`} role={toast.tone === "danger" ? "alert" : "status"}>
            <div className="toast-body">
              <strong>{toast.title}</strong>
              {toast.message && <p>{toast.message}</p>}
            </div>
            <div className="toast-actions">
              {toast.action && (
                <button
                  type="button"
                  className="button small"
                  onClick={() => {
                    toast.action?.onClick();
                    dismiss(toast.id);
                  }}
                >
                  {toast.action.label}
                </button>
              )}
              <button type="button" className="icon-button" aria-label="알림 닫기" onClick={() => dismiss(toast.id)}>
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastValue {
  const value = useContext(ToastContext);
  if (!value) throw new Error("useToast must be used inside ToastProvider");
  return value;
}

// ---- useAction ----

export interface ActionOptions {
  /** 실패 알림 제목 */
  failure: string;
  /** 성공 알림 제목(없으면 알리지 않음) */
  success?: string;
  /** 진행 중 표시를 구분할 키(예: 처리 중인 요청 ID) */
  key?: string;
}

/**
 * 저장·삭제 같은 사용자 동작의 공통 처리: 진행 중 표시, 성공·실패 알림.
 * run()은 성공하면 true, 실패하면(알림을 띄운 뒤) false를 돌려준다.
 */
export function useAction() {
  const { push } = useToast();
  const [pending, setPending] = useState<string | null>(null);

  const run = useCallback(
    async (action: () => Promise<unknown>, { failure, success, key = "action" }: ActionOptions): Promise<boolean> => {
      setPending(key);
      try {
        await action();
        if (success) push({ tone: "success", title: success });
        return true;
      } catch (error) {
        push({ tone: "danger", title: failure, message: errorMessage(error) });
        return false;
      } finally {
        setPending(null);
      }
    },
    [push],
  );

  return { run, pending, busy: pending !== null };
}

// ---- useHelpActions ----

/**
 * 도움 요청 생성·상태 변경. 서버가 돌려준 요청을 onSaved로 넘겨 화면 목록에 바로 반영한다.
 * (다른 화면에는 실시간 이벤트로 전달된다.)
 */
export function useHelpActions(onSaved: (request: HelpRequest) => void) {
  const session = useSession();
  const { run, pending } = useAction();

  const changeStatus = (request: HelpRequest, status: Exclude<HelpStatus, "CREATED">) =>
    run(async () => onSaved(await api.helpRequests.updateStatus(request.request_id, status)), {
      key: request.request_id,
      failure: "상태를 바꾸지 못했어요",
    });

  const create = (userId?: string) =>
    run(async () => onSaved(await api.helpRequests.create(userId)), {
      key: "create",
      success: userId ? "도움 요청을 대신 보냈어요" : "보호자에게 도움 요청을 보냈어요",
      failure: "도움 요청을 보내지 못했어요",
    });

  return {
    create,
    changeStatus,
    canChange: (request: HelpRequest) => canChangeHelpStatus(session, request),
    busyId: pending,
  };
}

/** 목록에 같은 요청이 있으면 바꾸고, 없으면 맨 앞에 넣는다. */
export function upsertHelpRequest(items: HelpRequest[], request: HelpRequest): HelpRequest[] {
  return items.some((item) => item.request_id === request.request_id)
    ? items.map((item) => (item.request_id === request.request_id ? request : item))
    : [request, ...items];
}

// ---- HelpAlerts ----

const BASE_TITLE = "CloudAIoT 대시보드";

function beep(): void {
  try {
    const AudioCtx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return;
    const context = new AudioCtx();
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    oscillator.frequency.value = 880;
    gain.gain.setValueAtTime(0.15, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + 0.6);
    oscillator.connect(gain).connect(context.destination);
    oscillator.start();
    oscillator.stop(context.currentTime + 0.6);
    oscillator.onended = () => void context.close();
  } catch {
    // 브라우저가 소리 재생을 막으면 무시한다.
  }
}

/**
 * 보호자·관리자에게 새 도움 요청을 즉시 알린다.
 * 화면 알림(닫을 때까지 유지), 소리, 브라우저 알림(허용한 경우), 탭 제목의 대기 건수.
 * 대기 건수는 접속·재접속할 때만 서버에서 받고, 그 사이에는 이벤트로 더하고 뺀다.
 */
export function HelpAlerts() {
  const session = useSession();
  const { userName } = useDirectory();
  const { status } = useRealtimeStatus();
  const { push } = useToast();
  const navigate = useNavigate();
  const [openCount, setOpenCount] = useState(0);
  const watching = canWatchHelp(session.user.role);
  const connected = status === "open";

  useEffect(() => {
    if (!watching || !connected) return;
    api.helpRequests
      .list({ status: "CREATED", limit: 1 })
      .then((page) => setOpenCount(page.meta.total))
      .catch(() => undefined);
  }, [watching, connected, session.user.user_id]);

  useEffect(() => {
    document.title = openCount > 0 ? `(${openCount}) 도움 요청 · ${BASE_TITLE}` : BASE_TITLE;
    return () => {
      document.title = BASE_TITLE;
    };
  }, [openCount]);

  useRealtimeEvent(["help.created", "help.updated"], (event) => {
    if (!watching) return;
    if (event.event_type === "help.updated") {
      // 확인 대기에서 벗어나는 변화는 CREATED → CONFIRMED 뿐이다.
      if (event.data.status === "CONFIRMED") setOpenCount((count) => Math.max(0, count - 1));
      return;
    }
    setOpenCount((count) => count + 1);
    const name = userName(event.data.user_id);
    push({
      tone: "danger",
      title: `🚨 ${name}님이 도움을 요청했습니다`,
      message: "도움 요청 화면에서 확인해 주세요.",
      sticky: true,
      action: { label: "확인하러 가기", onClick: () => navigate("/help") },
    });
    beep();
    if ("Notification" in window && Notification.permission === "granted") {
      try {
        new Notification("도움 요청", { body: `${name}님이 도움을 요청했습니다.`, tag: event.data.request_id });
      } catch {
        // 일부 브라우저는 페이지에서 직접 알림을 만들 수 없다.
      }
    }
  });

  return null;
}
