
// 서버 응답 형식. docs/api-spec.md, docs/websocket-spec.md와 맞춘다.

export type Role = "USER" | "GUARDIAN" | "ADMIN";
export type DeviceState = "ON" | "OFF" | "UNKNOWN";
export type ConnectionStatus = "ONLINE" | "OFFLINE";
export type HelpStatus = "CREATED" | "CONFIRMED" | "COMPLETED";
export type HelpSource = "GESTURE" | "WEB";
export type CommandStatus = "PENDING" | "COMPLETED" | "FAILED";
export type MappableGesture = "THUMB_UP" | "THUMB_DOWN" | "HELP";
export type GestureAction = "ON" | "OFF" | "HELP";

export interface User {
  user_id: string;
  email: string;
  name: string;
  role: Role;
  created_at_ms: number;
}

export interface Session {
  user: User;
  linked_user_ids: string[];
  expires_at_ms: number;
}

export interface Room {
  room_id: string;
  name: string;
  description: string | null;
  resident_user_id: string | null;
  created_at_ms: number;
  updated_at_ms: number;
}

export interface MapPosition {
  x: number;
  y: number;
}

export interface PointingRegion {
  min_angle_deg: number;
  max_angle_deg: number;
}

export interface Device {
  device_id: string;
  room_id: string;
  name: string;
  device_type: string;
  map_position: MapPosition;
  pointing_region: PointingRegion;
  enabled: boolean;
  state: DeviceState;
  connection_status: ConnectionStatus;
  state_updated_at_ms: number | null;
  created_at_ms: number;
  updated_at_ms: number;
}

export interface DeviceInput {
  device_id?: string;
  room_id: string;
  name: string;
  device_type: string;
  map_position: MapPosition;
  pointing_region: PointingRegion;
  enabled: boolean;
}

export interface ControlEvent {
  command_id: string;
  correlation_id: string;
  device_id: string;
  action: "ON" | "OFF";
  source: "GESTURE" | "WEB" | "SYSTEM";
  status: CommandStatus;
  result: "OK" | "ERROR" | "EXPIRED" | "DUPLICATE" | null;
  error_code: string | null;
  gesture_confirmed_at_ms: number | null;
  command_published_at_ms: number;
  ack_received_at_ms: number | null;
  latency_ms: number | null;
}

export interface HelpRequest {
  schema_version: "1.0";
  request_id: string;
  correlation_id: string;
  user_id: string;
  source: HelpSource;
  status: HelpStatus;
  created_at_ms: number;
  confirmed_at_ms: number | null;
  confirmed_by: string | null;
  completed_at_ms: number | null;
  completed_by: string | null;
}

export interface GuardianLink {
  guardian_id: string;
  user_id: string;
  created_at_ms: number;
}

export interface GestureMapping {
  gesture: MappableGesture;
  action: GestureAction;
  enabled: boolean;
  updated_at_ms: number;
}

export interface PageMeta {
  total: number;
  limit: number;
  offset: number;
}

export interface Paged<T> {
  items: T[];
  meta: PageMeta;
}

export type EventType =
  | "edge.connected"
  | "edge.disconnected"
  | "device.selected"
  | "gesture.confirmed"
  | "command.created"
  | "command.completed"
  | "command.failed"
  | "device.state_changed"
  | "help.created"
  | "help.updated";

export interface DeviceStateEventData {
  device_id: string;
  state: DeviceState;
  connection_status: ConnectionStatus;
  updated_at_ms: number | null;
}

export interface HelpEventData {
  request_id: string;
  user_id: string;
  status: HelpStatus;
}

export type CommandEventData = Pick<
  ControlEvent,
  "command_id" | "device_id" | "action" | "status" | "result" | "error_code" | "latency_ms"
>;

/** 이벤트 종류별 data 형식(docs/websocket-spec.md). */
export interface EventDataMap {
  "edge.connected": Record<string, unknown>;
  "edge.disconnected": Record<string, unknown>;
  "device.selected": { device_id: string; device_name?: string };
  "gesture.confirmed": Record<string, unknown>;
  "command.created": CommandEventData;
  "command.completed": CommandEventData;
  "command.failed": CommandEventData;
  "device.state_changed": DeviceStateEventData;
  "help.created": HelpEventData;
  "help.updated": HelpEventData;
}

interface EventEnvelope<K extends EventType> {
  schema_version: "1.0";
  event_id: string;
  event_type: K;
  correlation_id: string;
  timestamp_ms: number;
  data: EventDataMap[K];
}

/** 종류를 고르면 data 형식이 그 종류로 좁혀진다. */
export type RealtimeEvent<K extends EventType = EventType> = { [T in K]: EventEnvelope<T> }[K];

// ---- format ----

export const ROLE_LABEL: Record<Role, string> = { USER: "사용자", GUARDIAN: "보호자", ADMIN: "관리자" };
export const DEVICE_STATE_LABEL: Record<DeviceState, string> = { ON: "켜짐", OFF: "꺼짐", UNKNOWN: "알 수 없음" };
export const CONNECTION_LABEL: Record<ConnectionStatus, string> = { ONLINE: "연결됨", OFFLINE: "연결 끊김" };
export const HELP_STATUS_LABEL: Record<HelpStatus, string> = { CREATED: "확인 대기", CONFIRMED: "확인함", COMPLETED: "처리 완료" };
export const HELP_SOURCE_LABEL: Record<HelpSource, string> = { GESTURE: "손동작", WEB: "웹" };
export const COMMAND_STATUS_LABEL: Record<CommandStatus, string> = { PENDING: "응답 대기", COMPLETED: "성공", FAILED: "실패" };
export const COMMAND_SOURCE_LABEL: Record<string, string> = { GESTURE: "손동작", WEB: "웹", SYSTEM: "시스템" };
export const GESTURE_LABEL: Record<MappableGesture, string> = { THUMB_UP: "엄지 올림 👍", THUMB_DOWN: "엄지 내림 👎", HELP: "도움 요청 손동작 ✋" };
export const ACTION_LABEL: Record<GestureAction, string> = { ON: "켜기", OFF: "끄기", HELP: "도움 요청" };
export const EDGE_STATUS_LABEL = { unknown: "신호 대기", connected: "연결됨", disconnected: "연결 끊김" } as const;
export const ROLES = Object.keys(ROLE_LABEL) as Role[];
/** NFR-01: 유효 제스처 확정부터 기기 동작까지 2초 이내 */
export const LATENCY_TARGET_MS = 2000;

export const DEVICE_TYPES: { value: string; label: string; icon: string }[] = [
  { value: "LIGHT", label: "조명", icon: "💡" },
  { value: "FAN", label: "선풍기", icon: "🌀" },
  { value: "TV", label: "TV", icon: "📺" },
  { value: "AIR_CONDITIONER", label: "에어컨", icon: "❄️" },
  { value: "HEATER", label: "난방기", icon: "🔥" },
  { value: "OUTLET", label: "콘센트", icon: "🔌" },
  { value: "OTHER", label: "기타", icon: "⚙️" },
];

export function deviceTypeLabel(type: string): string {
  return DEVICE_TYPES.find((item) => item.value === type)?.label ?? type;
}

export function deviceIcon(type: string): string {
  return DEVICE_TYPES.find((item) => item.value === type)?.icon ?? "⚙️";
}

export const EVENT_LABEL: Record<EventType, string> = {
  "edge.connected": "카메라 연결",
  "edge.disconnected": "카메라 연결 끊김",
  "device.selected": "기기 선택",
  "gesture.confirmed": "제스처 확정",
  "command.created": "제어 명령 전송",
  "command.completed": "기기 제어 성공",
  "command.failed": "기기 제어 실패",
  "device.state_changed": "기기 상태 변경",
  "help.created": "도움 요청",
  "help.updated": "도움 요청 상태 변경",
};

const timeFormat = new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const dateTimeFormat = new Intl.DateTimeFormat("ko-KR", {
  month: "numeric",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});

export function formatTime(ms: number | null | undefined, now: number = Date.now()): string {
  if (!ms) return "-";
  const date = new Date(ms);
  const today = new Date(now);
  const sameDay = date.toDateString() === today.toDateString();
  return sameDay ? `오늘 ${timeFormat.format(date)}` : dateTimeFormat.format(date);
}

export function formatRelative(ms: number | null | undefined, now: number = Date.now()): string {
  if (!ms) return "-";
  const seconds = Math.round((now - ms) / 1000);
  if (seconds < 10) return "방금";
  if (seconds < 60) return `${seconds}초 전`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}분 전`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

export function formatLatency(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "-";
  return ms < 1000 ? `${ms}ms` : `${(ms / 1000).toFixed(2)}초`;
}

// ---- permissions ----

/**
 * 화면에서 쓰는 권한 판단. 서버(server/security/permissions.py)와 같은 규칙이며,
 * 최종 판단은 서버가 한다. 화면은 버튼·메뉴를 보일지만 정한다.
 */

/** 도움 요청을 받아 처리하는 역할(실시간 알림 대상) */
export function canWatchHelp(role: Role): boolean {
  return role === "GUARDIAN" || role === "ADMIN";
}

export function canChangeHelpStatus(session: Session, request: HelpRequest): boolean {
  if (session.user.role === "ADMIN") return true;
  return session.user.role === "GUARDIAN" && session.linked_user_ids.includes(request.user_id);
}

export function hasAnyRole(role: Role, roles?: readonly Role[]): boolean {
  return !roles || roles.includes(role);
}
