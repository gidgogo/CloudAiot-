import {
  CONNECTION_LABEL,
  type Device,
  DEVICE_STATE_LABEL,
  deviceIcon,
  deviceTypeLabel,
  formatRelative,
} from "../types";

export function StateBadge({ state }: { state: Device["state"] }) {
  return <span className={`badge state-${state.toLowerCase()}`}>{DEVICE_STATE_LABEL[state]}</span>;
}

export function ConnectionBadge({ status }: { status: Device["connection_status"] }) {
  return (
    <span className={`badge conn-${status.toLowerCase()}`}>
      <span className="dot" aria-hidden="true" />
      {CONNECTION_LABEL[status]}
    </span>
  );
}

interface DeviceCardProps {
  device: Device;
  roomName?: string;
  highlighted?: boolean;
}

export function DeviceCard({ device, roomName, highlighted = false }: DeviceCardProps) {
  return (
    <article
      className={`device-card${highlighted ? " highlighted" : ""}${device.enabled ? "" : " disabled"}`}
      aria-label={`${device.name} ${DEVICE_STATE_LABEL[device.state]}`}
    >
      <div className="device-card-head">
        <span className={`device-icon state-${device.state.toLowerCase()}`} aria-hidden="true">
          {deviceIcon(device.device_type)}
        </span>
        <div>
          <strong>{device.name}</strong>
          <small>
            {[deviceTypeLabel(device.device_type) === device.name ? null : deviceTypeLabel(device.device_type), roomName]
              .filter(Boolean)
              .join(" · ") || "\u00a0"}
          </small>
        </div>
      </div>
      <div className="device-card-status">
        <StateBadge state={device.state} />
        <ConnectionBadge status={device.connection_status} />
        {!device.enabled && <span className="badge muted">사용 안 함</span>}
        {highlighted && <span className="badge selected">선택됨</span>}
      </div>
      <small className="muted">
        상태 갱신 {formatRelative(device.state_updated_at_ms)}
      </small>
    </article>
  );
}
