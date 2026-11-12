import type {
  CommandStatus,
  ConnectionStatus,
  DeviceState,
  EventType,
  GestureAction,
  HelpSource,
  HelpStatus,
  MappableGesture,
  Role,
} from "../types";

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
