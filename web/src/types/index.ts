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
