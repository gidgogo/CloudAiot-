import type { Device } from "../types";
export function DeviceCard({device}:{device:Device}) { return <article><strong>{device.name}</strong><span>{device.state ?? "UNKNOWN"}</span></article>; }
