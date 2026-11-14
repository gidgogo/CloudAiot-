import type { ControlEvent } from "../types";
import {
  ACTION_LABEL,
  COMMAND_SOURCE_LABEL,
  COMMAND_STATUS_LABEL,
  formatLatency,
  formatTime,
  LATENCY_TARGET_MS,
} from "../utils/format";

interface Props {
  events: ControlEvent[];
  deviceName: (deviceId: string) => string;
  emptyText?: string;
}

export function ControlEventTable({ events, deviceName, emptyText = "제어 이력이 없습니다." }: Props) {
  if (events.length === 0) return <p className="empty">{emptyText}</p>;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">시각</th>
            <th scope="col">기기</th>
            <th scope="col">명령</th>
            <th scope="col">입력</th>
            <th scope="col">결과</th>
            <th scope="col">지연</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.command_id}>
              <td>{formatTime(event.command_published_at_ms)}</td>
              <td>{deviceName(event.device_id)}</td>
              <td>{ACTION_LABEL[event.action]}</td>
              <td>{COMMAND_SOURCE_LABEL[event.source] ?? event.source}</td>
              <td>
                <span className={`badge command-${event.status.toLowerCase()}`}>{COMMAND_STATUS_LABEL[event.status]}</span>
                {event.error_code && <small className="muted"> {event.error_code}</small>}
              </td>
              {/* NFR-01 목표(2초)를 넘은 지연은 강조한다. */}
              <td className={event.latency_ms !== null && event.latency_ms > LATENCY_TARGET_MS ? "danger-text" : undefined}>
                {formatLatency(event.latency_ms)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
