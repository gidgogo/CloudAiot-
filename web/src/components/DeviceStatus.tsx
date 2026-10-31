import type { DeviceState } from "../types";
export function DeviceStatus({state}:{state:DeviceState}) { return <output>{state}</output>; }
