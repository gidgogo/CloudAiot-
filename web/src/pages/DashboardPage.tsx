import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth, useSession } from "../auth/AuthContext";
import { ControlEventTable } from "../components/ControlEventTable";
import { DeviceCard } from "../components/DeviceCard";
import { HelpRequestList } from "../components/HelpRequestList";
import { RoomMap } from "../components/RoomMap";
import { useToast } from "../components/Toasts";
import { useDirectory } from "../hooks/useDirectory";
import { upsertHelpRequest, useHelpActions } from "../hooks/useHelpActions";
import { useResource } from "../hooks/useResource";
import { useRealtimeEvent, useRealtimeStatus, useRecentEvents } from "../realtime/RealtimeContext";
import type { HelpRequest } from "../types";
import { applyCommandEvent } from "../utils/commands";
import { EDGE_STATUS_LABEL, EVENT_LABEL, formatTime, HELP_STATUS_LABEL } from "../utils/format";
import { canWatchHelp } from "../utils/permissions";

const HIGHLIGHT_MS = 6000;

function HelpButton({ onCreate, sending }: { onCreate: () => Promise<boolean>; sending: boolean }) {
  const [confirming, setConfirming] = useState(false);

  if (confirming || sending) {
    return (
      <div className="help-button-confirm" role="group" aria-label="도움 요청 확인">
        <p>보호자에게 도움을 요청할까요?</p>
        <div className="row">
          <button
            type="button"
            className="button danger large"
            disabled={sending}
            onClick={() => void onCreate().then(() => setConfirming(false))}
          >
            {sending ? "보내는 중…" : "네, 요청할게요"}
          </button>
          <button type="button" className="button ghost large" disabled={sending} onClick={() => setConfirming(false)}>
            취소
          </button>
        </div>
      </div>
    );
  }
  return (
    <button type="button" className="help-button" onClick={() => setConfirming(true)}>
      <span aria-hidden="true">🆘</span>
      도움 요청
      <small>누르면 보호자에게 알림이 갑니다</small>
    </button>
  );
}

function RecentActivity() {
  const recent = useRecentEvents();
  const { status } = useRealtimeStatus();
  const { userName, deviceName } = useDirectory();
  return (
    <section className="card" aria-labelledby="activity-title">
      <div className="card-head">
        <h2 id="activity-title">실시간 활동</h2>
        <span className="muted small">{status === "open" ? "수신 중" : "연결 대기"}</span>
      </div>
      {recent.length === 0 ? (
        <p className="empty">아직 받은 이벤트가 없습니다.</p>
      ) : (
        <ol className="activity">
          {recent.slice(0, 12).map((event) => (
            <li key={event.event_id}>
              <time>{formatTime(event.timestamp_ms)}</time>
              <span>{EVENT_LABEL[event.event_type] ?? event.event_type}</span>
              <span className="muted small">
                {"device_id" in event.data ? deviceName(String(event.data.device_id)) : ""}
                {"user_id" in event.data ? userName(String(event.data.user_id)) : ""}
              </span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

export function DashboardPage() {
  const session = useSession();
  const { hasRole } = useAuth();
  const isUser = session.user.role === "USER";
  const watching = canWatchHelp(session.user.role);
  const { rooms, devices, patchDevice, userName, roomName, deviceName, loading, reload } = useDirectory();
  const { edgeStatus } = useRealtimeStatus();
  const { push } = useToast();
  const [roomId, setRoomId] = useState<string | null>(null);
  const [highlighted, setHighlighted] = useState<string | null>(null);

  useEffect(() => {
    if (!roomId && rooms.length > 0) {
      const mine = rooms.find((room) => room.resident_user_id === session.user.user_id);
      setRoomId((mine ?? rooms[0]).room_id);
    }
  }, [rooms, roomId, session.user.user_id]);

  const helpRequests = useResource(() => api.helpRequests.list({ limit: isUser ? 5 : 20 }), [isUser]);
  const controlEvents = useResource(
    () => (watching ? api.controlEvents.list({ limit: 8 }) : Promise.resolve(undefined)),
    [watching],
  );
  const help = useHelpActions((request: HelpRequest) =>
    helpRequests.setData((page) => page && { ...page, items: upsertHelpRequest(page.items, request) }),
  );

  useRealtimeEvent(["device.state_changed"], ({ data }) =>
    patchDevice(data.device_id, {
      state: data.state,
      connection_status: data.connection_status,
      state_updated_at_ms: data.updated_at_ms,
    }),
  );
  useRealtimeEvent(["device.selected"], ({ data }) => {
    setHighlighted(data.device_id);
    window.setTimeout(() => setHighlighted((current) => (current === data.device_id ? null : current)), HIGHLIGHT_MS);
  });
  useRealtimeEvent(["help.created", "help.updated"], () => void helpRequests.reload());
  useRealtimeEvent(["command.created"], () => void controlEvents.reload());
  useRealtimeEvent(["command.completed", "command.failed"], (event) => {
    controlEvents.setData((page) => applyCommandEvent(page, event.data));
    if (event.event_type === "command.failed") {
      push({ tone: "warning", title: `${deviceName(event.data.device_id)} 제어 실패`, message: event.data.error_code ?? undefined });
    }
  });

  const roomDevices = useMemo(() => devices.filter((device) => device.room_id === roomId), [devices, roomId]);
  const helpItems = helpRequests.data?.items ?? [];
  const openHelp = helpItems.filter((request) => request.status !== "COMPLETED");
  const onCount = devices.filter((device) => device.state === "ON").length;
  const onlineCount = devices.filter((device) => device.connection_status === "ONLINE").length;
  const waitingCount = helpItems.filter((request) => request.status === "CREATED").length;
  const latestMine = isUser ? helpItems[0] : undefined;

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>안녕하세요, {session.user.name}님</h1>
          <p className="muted">
            {isUser ? "손동작이나 아래 버튼으로 도움을 요청할 수 있어요." : "기기 상태와 도움 요청을 실시간으로 확인합니다."}
          </p>
        </div>
        <button
          type="button"
          className="button ghost small"
          onClick={() => void Promise.all([reload(), helpRequests.reload(), controlEvents.reload()])}
        >
          새로고침
        </button>
      </div>

      {isUser && (
        <section className="card help-panel" aria-label="도움 요청">
          <HelpButton onCreate={() => help.create()} sending={help.busyId === "create"} />
          {latestMine && (
            <p className="help-latest">
              최근 요청: {formatTime(latestMine.created_at_ms)} · <strong>{HELP_STATUS_LABEL[latestMine.status]}</strong>
            </p>
          )}
        </section>
      )}

      <section className="stats" aria-label="요약">
        <div className="stat">
          <span className="stat-label">켜진 기기</span>
          <strong className="stat-value">
            {onCount}
            <small> / {devices.length}</small>
          </strong>
        </div>
        <div className="stat">
          <span className="stat-label">연결된 기기</span>
          <strong className="stat-value">
            {onlineCount}
            <small> / {devices.length}</small>
          </strong>
        </div>
        {watching && (
          <div className={`stat${waitingCount > 0 ? " stat-alert" : ""}`}>
            <span className="stat-label">확인 대기 도움 요청</span>
            <strong className="stat-value">{waitingCount}</strong>
          </div>
        )}
        <div className="stat">
          <span className="stat-label">카메라</span>
          <strong className="stat-value stat-text">{EDGE_STATUS_LABEL[edgeStatus]}</strong>
        </div>
      </section>

      {watching && (
        <section className="card" aria-labelledby="open-help-title">
          <div className="card-head">
            <h2 id="open-help-title">진행 중인 도움 요청</h2>
            <Link to="/help" className="link">전체 보기</Link>
          </div>
          {helpRequests.error && <p className="error-text">{helpRequests.error}</p>}
          <HelpRequestList
            requests={openHelp}
            userName={userName}
            canChange={help.canChange}
            onChange={help.changeStatus}
            busyId={help.busyId}
            emptyText="진행 중인 도움 요청이 없습니다."
          />
        </section>
      )}

      <div className="grid-2">
        <section className="card" aria-labelledby="map-title">
          <div className="card-head">
            <h2 id="map-title">방 배치도</h2>
            {rooms.length > 1 && (
              <select aria-label="방 선택" value={roomId ?? ""} onChange={(event) => setRoomId(event.target.value)}>
                {rooms.map((room) => (
                  <option key={room.room_id} value={room.room_id}>
                    {room.name}
                  </option>
                ))}
              </select>
            )}
          </div>
          {rooms.length === 0 ? (
            <p className="empty">
              등록된 방이 없습니다.{hasRole("ADMIN") && <> <Link to="/mapping">방·기기 설정</Link>에서 추가하세요.</>}
            </p>
          ) : (
            <RoomMap devices={roomDevices} title={roomId ? roomName(roomId) : undefined} highlightedId={highlighted} />
          )}
        </section>

        <section className="card" aria-labelledby="devices-title">
          <div className="card-head">
            <h2 id="devices-title">기기 상태</h2>
            {loading && <span className="muted small">불러오는 중…</span>}
          </div>
          {devices.length === 0 ? (
            <p className="empty">등록된 기기가 없습니다.</p>
          ) : (
            <div className="device-grid">
              {devices.map((device) => (
                <DeviceCard
                  key={device.device_id}
                  device={device}
                  roomName={rooms.length > 1 ? roomName(device.room_id) : undefined}
                  highlighted={device.device_id === highlighted}
                />
              ))}
            </div>
          )}
        </section>
      </div>

      {isUser && (
        <section className="card" aria-labelledby="my-help-title">
          <div className="card-head">
            <h2 id="my-help-title">내 도움 요청</h2>
            <Link to="/help" className="link">전체 보기</Link>
          </div>
          <HelpRequestList requests={helpItems} userName={userName} showUser={false} />
        </section>
      )}

      {watching && (
        <div className="grid-2">
          <section className="card" aria-labelledby="control-title">
            <div className="card-head">
              <h2 id="control-title">최근 기기 제어</h2>
              <Link to="/history" className="link">제어 이력</Link>
            </div>
            {controlEvents.error && <p className="error-text">{controlEvents.error}</p>}
            <ControlEventTable events={controlEvents.data?.items ?? []} deviceName={deviceName} />
          </section>
          <RecentActivity />
        </div>
      )}
    </div>
  );
}
