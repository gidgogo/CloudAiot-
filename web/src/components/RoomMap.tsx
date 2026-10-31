import type { Device } from "../types";
export function RoomMap({devices}:{devices:Device[]}) { return <section aria-label="room map">{devices.map(device=><span key={device.device_id} style={{left:`${device.map_position.x*100}%`,top:`${device.map_position.y*100}%`}}>{device.name}</span>)}</section>; }
