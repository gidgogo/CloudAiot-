import { useCallback, useEffect, useRef, useState } from "react";
import { api, errorMessage, useDirectory, useSession } from "../api/client";
import { HelpRequestList, upsertHelpRequest, useHelpActions } from "../components/HelpRequestList";
import { HELP_STATUS_LABEL, type HelpRequest, type HelpStatus, type PageMeta } from "../types";
import { useRealtimeEvent } from "../websocket/eventClient";

const PAGE_SIZE = 20;
type Tab = HelpStatus | "ALL";
const TABS: { value: Tab; label: string }[] = [
  ...(Object.keys(HELP_STATUS_LABEL) as HelpStatus[]).map((status) => ({ value: status, label: HELP_STATUS_LABEL[status] })),
  { value: "ALL", label: "전체" },
];

const DESCRIPTION = {
  USER: "내가 보낸 도움 요청과 처리 상태입니다.",
  GUARDIAN: "연결된 사용자의 도움 요청을 확인하고 처리합니다.",
  ADMIN: "모든 사용자의 도움 요청입니다.",
} as const;

export function HelpRequestPage() {
  const session = useSession();
  const role = session.user.role;
  const { usersByRole, userName } = useDirectory();
  const [tab, setTab] = useState<Tab>(role === "USER" ? "ALL" : "CREATED");
  const [items, setItems] = useState<HelpRequest[]>([]);
  const [meta, setMeta] = useState<PageMeta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [onBehalf, setOnBehalf] = useState("");
  const requestId = useRef(0);

  const load = useCallback(
    async (offset = 0) => {
      // 탭을 빨리 바꿀 때 늦게 도착한 이전 탭 응답은 버린다.
      const current = ++requestId.current;
      setLoading(true);
      try {
        const page = await api.helpRequests.list({ status: tab === "ALL" ? undefined : tab, limit: PAGE_SIZE, offset });
        if (current !== requestId.current) return;
        setItems((previous) => (offset === 0 ? page.items : [...previous, ...page.items]));
        setMeta(page.meta);
        setError(null);
      } catch (caught) {
        if (current === requestId.current) setError(errorMessage(caught));
      } finally {
        if (current === requestId.current) setLoading(false);
      }
    },
    [tab],
  );

  useEffect(() => {
    void load(0);
  }, [load]);

  useRealtimeEvent(["help.created", "help.updated"], () => void load(0));

  const help = useHelpActions((request) => {
    if (tab === "ALL" || request.status === tab) setItems((current) => upsertHelpRequest(current, request));
    else setItems((current) => current.filter((item) => item.request_id !== request.request_id));
  });

  const residents = usersByRole("USER");

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>도움 요청</h1>
          <p className="muted">{DESCRIPTION[role]}</p>
        </div>
        {role === "USER" && (
          <button type="button" className="button danger" disabled={help.busyId === "create"} onClick={() => void help.create()}>
            🆘 도움 요청 보내기
          </button>
        )}
        {role === "ADMIN" && residents.length > 0 && (
          <form
            className="row"
            onSubmit={(event) => {
              event.preventDefault();
              if (onBehalf) void help.create(onBehalf);
            }}
          >
            <select aria-label="대신 요청할 사용자" value={onBehalf} onChange={(event) => setOnBehalf(event.target.value)}>
              <option value="">사용자 선택</option>
              {residents.map((user) => (
                <option key={user.user_id} value={user.user_id}>
                  {user.name}
                </option>
              ))}
            </select>
            <button type="submit" className="button" disabled={!onBehalf || help.busyId === "create"}>
              대신 요청
            </button>
          </form>
        )}
      </div>

      {role === "GUARDIAN" && session.linked_user_ids.length === 0 && (
        <p className="notice">연결된 사용자가 없습니다. 관리자에게 연결을 요청하세요.</p>
      )}

      <div className="tabs" role="tablist" aria-label="상태">
        {TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            role="tab"
            aria-selected={tab === item.value}
            className={`tab${tab === item.value ? " active" : ""}`}
            onClick={() => setTab(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <section className="card">
        {error && <p className="error-text">{error}</p>}
        <HelpRequestList
          requests={items}
          userName={userName}
          canChange={help.canChange}
          onChange={help.changeStatus}
          busyId={help.busyId}
          showUser={role !== "USER"}
          emptyText={loading ? "불러오는 중…" : "해당하는 도움 요청이 없습니다."}
        />
        {meta && items.length < meta.total && (
          <button type="button" className="button ghost block" disabled={loading} onClick={() => void load(items.length)}>
            더 보기 ({items.length} / {meta.total})
          </button>
        )}
      </section>
    </div>
  );
}
