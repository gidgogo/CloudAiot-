import type { HelpRequest, HelpStatus } from "../types";
import { formatRelative, formatTime, HELP_SOURCE_LABEL, HELP_STATUS_LABEL } from "../utils/format";

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
