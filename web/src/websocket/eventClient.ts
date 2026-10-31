import type { RealtimeEvent } from "../types";
export function createEventSocket(onEvent:(event:RealtimeEvent)=>void): WebSocket {
 const protocol=location.protocol==="https:"?"wss":"ws";
 const socket=new WebSocket(`${protocol}://${location.host}/ws/v1/events`);
 socket.onmessage=(message)=>onEvent(JSON.parse(message.data) as RealtimeEvent);
 return socket;
}
