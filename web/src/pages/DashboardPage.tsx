import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, useAuth, useDirectory, useResource, useSession } from "../api/client";
import { DeviceStatusList, Icon } from "../components/DeviceCard";
import {
  applyCommandEvent,
  ControlEventTable,
  GestureBindingList,
  LiveControlPanel,
  useLiveControl,
} from "../components/DeviceStatus";
import { HelpRequestList, upsertHelpRequest, useHelpActions, useToast } from "../components/HelpRequestList";
import { RoomMap } from "../components/RoomMap";
import {
  canWatchHelp,
  EDGE_STATUS_LABEL,
  EVENT_LABEL,
  formatLatency,
  formatTime,
  HELP_STATUS_LABEL,
  type HelpRequest,
  LATENCY_TARGET_MS,
} from "../types";
import { useRealtimeEvent, useRealtimeStatus, useRecentEvents } from "../websocket/eventClient";

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
      <Icon name="help" size={40} />
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
    <section className="panel" aria-labelledby="activity-title">
      <header className="panel-head">
        <h2 id="activity-title">실시간 활동</h2>
        <span className="muted small">{status === "open" ? "수신 중" : "연결 대기"}</span>
      </header>
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
  const { push } = useToast();
  const { edgeStatus } = useRealtimeStatus();
  const [roomId, setRoomId] = useState<string | null>(null);
  // 실시간 제어 패널과 배치도가 같은 "지금 가리킨 기기"를 본다.
  const live = useLiveControl();
  const highlighted = live.step === "camera" ? null : live.target;

  useEffect(() => {
    if (!roomId && rooms.length > 0) {
      const mine = rooms.find((room) => room.resident_user_id === session.user.user_id);
      setRoomId((mine ?? rooms[0]).room_id);
    }
  }, [rooms, roomId, session.user.user_id]);

  const mappings = useResource(() => api.gestureMappings.list(), []);
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
  // 다른 방의 기기를 가리키면 그 방 배치도로 바꿔서 선택된 핀이 보이게 한다.
  useRealtimeEvent(["device.selected"], ({ data }) => {
    const device = devices.find((item) => item.device_id === data.device_id);
    if (device) setRoomId(device.room_id);
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
          <h1>대시보드</h1>
          {/* Carbon 관제 화면처럼 전체 상태를 제목 아래 한 줄로 */}
          <ul className="summary" aria-label="요약">
            <li>
              켜진 기기 <strong>{onCount}</strong>/{devices.length}
            </li>
            <li className={onlineCount < devices.length ? "summary-warn" : undefined}>
              연결된 기기 <strong>{onlineCount}</strong>/{devices.length}
            </li>
            {watching && (
              <li className={waitingCount > 0 ? "summary-alert" : undefined}>
                도움 요청 대기 <strong>{waitingCount}</strong>
              </li>
            )}
            <li className={edgeStatus === "disconnected" ? "summary-alert" : undefined}>카메라 {EDGE_STATUS_LABEL[edgeStatus]}</li>
          </ul>
        </div>
        <button
          type="button"
          className="button ghost small"
          onClick={() => void Promise.all([reload(), helpRequests.reload(), controlEvents.reload(), mappings.reload()])}
        >
          <Icon name="refresh" size={16} />
          새로고침
        </button>
      </div>

      {isUser && (
        <section className="panel help-panel" aria-label="도움 요청">
          <HelpButton onCreate={() => help.create()} sending={help.busyId === "create"} />
          {latestMine && (
            <p className="help-latest">
              최근 요청: {formatTime(latestMine.created_at_ms)} · <strong>{HELP_STATUS_LABEL[latestMine.status]}</strong>
            </p>
          )}
        </section>
      )}

      <div className="dash-top">
        <LiveControlPanel
          live={live}
          devices={devices}
          mappings={mappings.data ?? []}
          roomName={roomName}
          action={hasRole("ADMIN") ? <Link to="/admin" className="link">손동작 설정</Link> : undefined}
        />

        <section className="panel" aria-labelledby="attention-title">
          <header className="panel-head">
            <h2 id="attention-title">{watching ? "진행 중인 도움 요청" : "내 도움 요청"}</h2>
            <Link to="/help" className="link">전체 보기</Link>
          </header>
          {helpRequests.error && <p className="error-text">{helpRequests.error}</p>}
          {watching ? (
            <HelpRequestList
              requests={openHelp}
              userName={userName}
              canChange={help.canChange}
              onChange={help.changeStatus}
              busyId={help.busyId}
              emptyText="진행 중인 도움 요청 없음"
            />
          ) : (
            <HelpRequestList requests={helpItems} userName={userName} showUser={false} emptyText="보낸 도움 요청 없음" />
          )}
        </section>
      </div>

      <section className="panel" aria-labelledby="devices-title">
        <header className="panel-head">
          <h2 id="devices-title">기기 상태</h2>
          <div className="row">
            {loading && <span className="muted small">불러오는 중…</span>}
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
        </header>
        {rooms.length === 0 ? (
          <p className="empty">
            등록된 방이 없습니다.{hasRole("ADMIN") && <> <Link to="/mapping">방·기기 설정</Link>에서 추가하세요.</>}
          </p>
        ) : (
          <div className="devices-layout">
            <RoomMap devices={roomDevices} title={roomId ? roomName(roomId) : undefined} highlightedId={highlighted} />
            <DeviceStatusList devices={roomDevices} highlightedId={highlighted} />
          </div>
        )}
      </section>

      <section className="panel" aria-labelledby="bindings-title">
        <header className="panel-head">
          <h2 id="bindings-title">사용 가능한 손동작</h2>
        </header>
        {mappings.error && <p className="error-text">{mappings.error}</p>}
        <GestureBindingList mappings={mappings.data ?? []} />
      </section>

      {watching && (
        <div className="grid-2">
          <section className="panel" aria-labelledby="control-title">
            <header className="panel-head">
              <h2 id="control-title">최근 기기 제어</h2>
              <Link to="/history" className="link">제어 이력</Link>
            </header>
            {controlEvents.error && <p className="error-text">{controlEvents.error}</p>}
            <ControlEventTable events={controlEvents.data?.items ?? []} deviceName={deviceName} />
          </section>
          <RecentActivity />
        </div>
      )}
    </div>
  );
}

// ---- HistoryPage ----

const PAGE_SIZE = 25;

export function HistoryPage() {
  const { devices, deviceName } = useDirectory();
  const [deviceId, setDeviceId] = useState("");
  const [offset, setOffset] = useState(0);
  const page = useResource(
    () => api.controlEvents.list({ device_id: deviceId || undefined, limit: PAGE_SIZE, offset }),
    [deviceId, offset],
  );

  // 새 명령은 첫 페이지이고 선택한 기기일 때만 다시 불러오고, 결과는 해당 행만 바꾼다.
  useRealtimeEvent(["command.created"], ({ data }) => {
    if (offset === 0 && (!deviceId || data.device_id === deviceId)) void page.reload();
  });
  useRealtimeEvent(["command.completed", "command.failed"], ({ data }) => page.setData((current) => applyCommandEvent(current, data)));

  const items = page.data?.items ?? [];
  const total = page.data?.meta.total ?? 0;
  const measured = items.flatMap((item) => (item.latency_ms === null ? [] : [item.latency_ms]));
  const average = measured.length ? Math.round(measured.reduce((sum, value) => sum + value, 0) / measured.length) : null;
  const overTarget = measured.filter((value) => value > LATENCY_TARGET_MS).length;

  return (
    <div>
      <div className="page-head">
        <div>
          <h1>기기 제어 이력</h1>
          <p className="muted">제스처 확정부터 기기 응답(ACK)까지의 지연을 함께 기록합니다. 목표는 2초 이내(NFR-01)입니다.</p>
        </div>
        <select
          aria-label="기기 선택"
          value={deviceId}
          onChange={(event) => {
            setDeviceId(event.target.value);
            setOffset(0);
          }}
        >
          <option value="">모든 기기</option>
          {devices.map((device) => (
            <option key={device.device_id} value={device.device_id}>
              {device.name}
            </option>
          ))}
        </select>
      </div>

      <section className="stats" aria-label="이 페이지 요약">
        <div className="stat">
          <span className="stat-label">전체 기록</span>
          <strong className="stat-value">{total}</strong>
        </div>
        <div className="stat">
          <span className="stat-label">평균 지연(이 페이지)</span>
          <strong className="stat-value stat-text">{formatLatency(average)}</strong>
        </div>
        <div className={`stat${overTarget ? " stat-alert" : ""}`}>
          <span className="stat-label">2초 초과</span>
          <strong className="stat-value">{overTarget}</strong>
        </div>
      </section>

      <section className="card">
        {page.error && <p className="error-text">{page.error}</p>}
        <ControlEventTable events={items} deviceName={deviceName} emptyText={page.loading ? "불러오는 중…" : "제어 이력이 없습니다."} />
        <div className="pager">
          <button type="button" className="button ghost small" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
            이전
          </button>
          <span className="muted small">
            {total === 0 ? 0 : offset + 1}–{Math.min(offset + PAGE_SIZE, total)} / {total}
          </span>
          <button
            type="button"
            className="button ghost small"
            disabled={offset + PAGE_SIZE >= total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            다음
          </button>
        </div>
      </section>
    </div>
  );
}
