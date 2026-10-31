export type DeviceState = "ON" | "OFF" | "UNKNOWN";
export type HelpStatus = "CREATED" | "CONFIRMED" | "COMPLETED";
export interface Device { device_id:string; room_id:string; name:string; device_type:string; map_position:{x:number;y:number}; pointing_region:{min_angle_deg:number;max_angle_deg:number}; state?:DeviceState; enabled:boolean; }
export interface HelpRequest { request_id:string; correlation_id:string; user_id:string; source:"GESTURE"|"WEB"; status:HelpStatus; created_at_ms:number; }
export interface RealtimeEvent { schema_version:"1.0"; event_id:string; event_type:string; correlation_id:string; timestamp_ms:number; data:Record<string, unknown>; }
export interface ApiEnvelope<T> { success:boolean; data:T; }
