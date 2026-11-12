import type { RealtimeEvent } from "../types";

export type SocketStatus = "connecting" | "open" | "reconnecting" | "unauthorized" | "closed";

/** 서버 종료 코드(규격 8.5). 인증 문제면 다시 연결하지 않는다. */
export const CLOSE_UNAUTHORIZED = 4401;
export const CLOSE_FORBIDDEN = 4403;
export const RECONNECT_DELAYS_MS = [1000, 2000, 4000, 8000, 16000, 30000];

export interface EventClientOptions {
  url?: string;
  onEvent: (event: RealtimeEvent) => void;
  onStatus?: (status: SocketStatus) => void;
  onUnauthorized?: () => void;
  createSocket?: (url: string) => WebSocket;
  delays?: number[];
  setTimer?: (callback: () => void, ms: number) => unknown;
  clearTimer?: (handle: unknown) => void;
}

export function defaultEventUrl(location: Location = window.location): string {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${location.host}/ws/v1/events`;
}

/** /ws/v1/events 연결을 유지한다. 끊기면 1·2·4…30초 간격으로 다시 연결한다. */
export class EventClient {
  private socket: WebSocket | null = null;
  private attempt = 0;
  private timer: unknown = null;
  private stopped = true;
  private readonly options: Required<Omit<EventClientOptions, "onStatus" | "onUnauthorized">> &
    Pick<EventClientOptions, "onStatus" | "onUnauthorized">;

  constructor(options: EventClientOptions) {
    this.options = {
      url: options.url ?? defaultEventUrl(),
      createSocket: options.createSocket ?? ((url) => new WebSocket(url)),
      delays: options.delays ?? RECONNECT_DELAYS_MS,
      setTimer: options.setTimer ?? ((callback, ms) => window.setTimeout(callback, ms)),
      clearTimer: options.clearTimer ?? ((handle) => window.clearTimeout(handle as number)),
      onEvent: options.onEvent,
      onStatus: options.onStatus,
      onUnauthorized: options.onUnauthorized,
    };
  }

  start(): void {
    if (!this.stopped) return;
    this.stopped = false;
    this.attempt = 0;
    this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer !== null) this.options.clearTimer(this.timer);
    this.timer = null;
    const socket = this.socket;
    this.socket = null;
    if (socket && socket.readyState <= 1) socket.close(1000);
    this.options.onStatus?.("closed");
  }

  private connect(): void {
    this.options.onStatus?.(this.attempt === 0 ? "connecting" : "reconnecting");
    const socket = this.options.createSocket(this.options.url);
    this.socket = socket;

    socket.onopen = () => {
      this.attempt = 0;
      this.options.onStatus?.("open");
    };
    socket.onmessage = (message: MessageEvent) => {
      try {
        const event = JSON.parse(String(message.data)) as RealtimeEvent;
        if (event && typeof event.event_type === "string") this.options.onEvent(event);
      } catch {
        // 형식이 잘못된 메시지는 무시한다.
      }
    };
    socket.onclose = (event: CloseEvent) => {
      if (this.socket !== socket || this.stopped) return;
      this.socket = null;
      if (event.code === CLOSE_UNAUTHORIZED || event.code === CLOSE_FORBIDDEN) {
        this.stopped = true;
        this.options.onStatus?.("unauthorized");
        if (event.code === CLOSE_UNAUTHORIZED) this.options.onUnauthorized?.();
        return;
      }
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    const delays = this.options.delays;
    const delay = delays[Math.min(this.attempt, delays.length - 1)];
    this.attempt += 1;
    this.options.onStatus?.("reconnecting");
    this.timer = this.options.setTimer(() => {
      this.timer = null;
      if (!this.stopped) this.connect();
    }, delay);
  }
}
