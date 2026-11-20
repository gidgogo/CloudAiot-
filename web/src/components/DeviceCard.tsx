import {
  CONNECTION_LABEL,
  type Device,
  DEVICE_STATE_LABEL,
  deviceTypeLabel,
  formatRelative,
} from "../types";

// ---- Icon ----

// 메뉴·상단·기기에 쓰는 선 아이콘. 24×24 칸에 1.75px 선으로 통일한다(IBM Carbon 아이콘 느낌).
const PATHS = {
  dashboard: "M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z",
  help: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 8v5M12 16.5v.5",
  history: "M12 21a9 9 0 1 0-8.5-6M3 20v-5h5M12 7v5l3 2",
  home: "M4 10.5 12 4l8 6.5V20h-5v-6H9v6H4z",
  settings:
    "M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 13.5l1.6 1.2-2 3.4-1.9-.7a7 7 0 0 1-2 1.2L14.8 21h-4l-.3-2.4a7 7 0 0 1-2-1.2l-1.9.7-2-3.4 1.6-1.2a7 7 0 0 1 0-2.4L4.6 9.9l2-3.4 1.9.7a7 7 0 0 1 2-1.2L10.8 3h4l.3 2.4a7 7 0 0 1 2 1.2l1.9-.7 2 3.4-1.6 1.2a7 7 0 0 1 0 2.4z",
  users: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21v-1a6 6 0 0 1 12 0v1M16 3.5a4 4 0 0 1 0 7M22 21v-1a6 6 0 0 0-4-5.6",
  soundOn: "M4 9h4l5-4v14l-5-4H4zM16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12",
  soundOff: "M4 9h4l5-4v14l-5-4H4zM17 9.5l5 5M22 9.5l-5 5",
  bell: "M6 16V11a6 6 0 1 1 12 0v5l2 2H4zM10 21h4",
  logout: "M15 4h4v16h-4M10 8l-4 4 4 4M6 12h10",
  refresh: "M20 11a8 8 0 0 0-14.5-4.5M4 4v4h4M4 13a8 8 0 0 0 14.5 4.5M20 20v-4h-4",
  menu: "M4 7h16M4 12h16M4 17h16",
  hand: "M8 13V5.5a1.5 1.5 0 0 1 3 0V11M11 10V4.5a1.5 1.5 0 0 1 3 0V11M14 10.5V6a1.5 1.5 0 0 1 3 0v8a7 7 0 0 1-7 7h-.5a6 6 0 0 1-4.9-2.6L3 15a1.5 1.5 0 0 1 2.4-1.8L8 15",
  light: "M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9V16h7v-2.1A6 6 0 0 0 12 3z",
  fan: "M12 13.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM12 10.5C11 6 12 3 15 3s3 4-1.5 7.5M13.5 12c4.5-1 7.5 0 7.5 3s-4 3-7.5-1.5M12 13.5c1 4.5 0 7.5-3 7.5s-3-4 1.5-7.5M10.5 12C6 13 3 12 3 9s4-3 7.5 1.5",
  tv: "M3 6h18v12H3zM8 21h8",
  snow: "M12 3v18M4.2 7.5l15.6 9M4.2 16.5l15.6-9",
  flame: "M12 21a6 6 0 0 0 6-6c0-4-3-6-4-10-2 2-3 4-3 6-1-1-2-2-2-3-2 2-3 4-3 7a6 6 0 0 0 6 6z",
  plug: "M9 3v5M15 3v5M6 8h12v3a6 6 0 0 1-12 0zM12 17v4",
  device: "M5 4h14v16H5zM9 17h6",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      className={`icon${className ? ` ${className}` : ""}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}

const DEVICE_GLYPH: Record<string, IconName> = {
  LIGHT: "light",
  FAN: "fan",
  TV: "tv",
  AIR_CONDITIONER: "snow",
  HEATER: "flame",
  OUTLET: "plug",
};

/** 기기 종류별 선 아이콘. 모르는 종류는 일반 기기 모양. */
export function DeviceGlyph({ type, size = 20 }: { type: string; size?: number }) {
  return <Icon name={DEVICE_GLYPH[type] ?? "device"} size={size} />;
}

// ---- 상태 배지 ----
// 색만으로 구분하지 않도록 항상 "전원: 켜짐", "연결: 끊김"처럼 글자를 붙인다.

export function StateBadge({ state, label = false }: { state: Device["state"]; label?: boolean }) {
  return (
    <span className={`badge state-${state.toLowerCase()}`}>
      {label && "전원 "}
      {DEVICE_STATE_LABEL[state]}
    </span>
  );
}

export function ConnectionBadge({ status }: { status: Device["connection_status"] }) {
  return (
    <span className={`badge conn-${status.toLowerCase()}`}>
      <span className="dot" aria-hidden="true" />
      {CONNECTION_LABEL[status]}
    </span>
  );
}

// ---- DeviceStatusList ----

interface ListProps {
  devices: Device[];
  roomName?: (roomId: string) => string;
  highlightedId?: string | null;
}

/**
 * 배치도 옆에 놓는 기기 목록. 한 기기 한 줄에 전원과 연결을 따로 보여 준다.
 * 연결이 끊긴 기기는 전원을 알 수 없으므로 "꺼짐"과 "알 수 없음"이 구분된다.
 */
export function DeviceStatusList({ devices, roomName, highlightedId }: ListProps) {
  if (devices.length === 0) return <p className="empty">등록된 기기가 없습니다.</p>;
  return (
    <ul className="device-list">
      {devices.map((device) => {
        const type = deviceTypeLabel(device.device_type);
        const sub = [type === device.name ? null : type, roomName?.(device.room_id)].filter(Boolean).join(" · ");
        const selected = device.device_id === highlightedId;
        return (
          <li
            key={device.device_id}
            className={`device-row${selected ? " selected" : ""}${device.enabled ? "" : " disabled"}`}
            aria-label={`${device.name} 전원 ${DEVICE_STATE_LABEL[device.state]}, ${CONNECTION_LABEL[device.connection_status]}`}
          >
            <span className={`device-row-icon state-${device.state.toLowerCase()}`}>
              <DeviceGlyph type={device.device_type} />
            </span>
            <span className="device-row-name">
              <strong>{device.name}</strong>
              <small>
                {sub || device.device_id}
                {device.state_updated_at_ms !== null && ` · 갱신 ${formatRelative(device.state_updated_at_ms)}`}
              </small>
            </span>
            <span className="device-row-field">
              <small>전원</small>
              <StateBadge state={device.state} />
            </span>
            <span className="device-row-field">
              <small>연결</small>
              <ConnectionBadge status={device.connection_status} />
            </span>
            {selected && <span className="badge selected">선택됨</span>}
            {!device.enabled && <span className="badge muted">사용 안 함</span>}
          </li>
        );
      })}
    </ul>
  );
}
