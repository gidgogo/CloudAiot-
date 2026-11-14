import { useState } from "react";
import { api } from "../api/client";
import { ControlEventTable } from "../components/ControlEventTable";
import { useDirectory } from "../hooks/useDirectory";
import { useResource } from "../hooks/useResource";
import { useRealtimeEvent } from "../realtime/RealtimeContext";
import { applyCommandEvent } from "../utils/commands";
import { formatLatency, LATENCY_TARGET_MS } from "../utils/format";

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
