import {
  createContext,
  createElement,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useAuth } from "../api/client";
import type { EventType, RealtimeEvent } from "../types";

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

// ---- RealtimeContext ----

type Listener = (event: RealtimeEvent) => void;
type Subscribe = (listener: Listener, types?: readonly EventType[]) => () => void;
export type EdgeStatus = "unknown" | "connected" | "disconnected";

interface StatusValue {
  status: SocketStatus;
  edgeStatus: EdgeStatus;
}

// 이벤트가 올 때마다 바뀌는 값(최근 이벤트)과 거의 바뀌지 않는 값(구독·연결 상태)을 나눠,
// 특정 이벤트만 듣는 화면이 다른 이벤트 때문에 다시 그려지지 않게 한다.
const SubscribeContext = createContext<Subscribe | null>(null);
const StatusContext = createContext<StatusValue | null>(null);
const RecentContext = createContext<RealtimeEvent[]>([]);
const MAX_RECENT = 40;

/** 로그인한 동안 /ws/v1/events에 연결해 이벤트를 화면 곳곳에 나눠준다. */
export function RealtimeProvider({ children }: { children: ReactNode }) {
  const { session, expire } = useAuth();
  const [status, setStatus] = useState<SocketStatus>("closed");
  const [edgeStatus, setEdgeStatus] = useState<EdgeStatus>("unknown");
  const [recent, setRecent] = useState<RealtimeEvent[]>([]);
  const listeners = useRef(new Set<{ listener: Listener; types?: ReadonlySet<EventType> }>());
  const userId = session?.user.user_id;

  useEffect(() => {
    if (!userId) return;
    const client = new EventClient({
      onEvent: (event) => {
        setRecent((current) => [event, ...current].slice(0, MAX_RECENT));
        if (event.event_type === "edge.connected") setEdgeStatus("connected");
        if (event.event_type === "edge.disconnected") setEdgeStatus("disconnected");
        for (const entry of listeners.current) {
          if (!entry.types || entry.types.has(event.event_type)) entry.listener(event);
        }
      },
      onStatus: setStatus,
      onUnauthorized: () => expire(),
    });
    client.start();
    return () => {
      client.stop();
      setRecent([]);
      setEdgeStatus("unknown");
    };
  }, [userId, expire]);

  const subscribe = useCallback<Subscribe>((listener, types) => {
    const entry = { listener, types: types ? new Set(types) : undefined };
    listeners.current.add(entry);
    return () => {
      listeners.current.delete(entry);
    };
  }, []);

  const statusValue = useMemo(() => ({ status, edgeStatus }), [status, edgeStatus]);

  return createElement(
    SubscribeContext.Provider,
    { value: subscribe },
    createElement(StatusContext.Provider, { value: statusValue }, createElement(RecentContext.Provider, { value: recent }, children)),
  );
}

export function useRealtimeStatus(): StatusValue {
  const value = useContext(StatusContext);
  if (!value) throw new Error("useRealtimeStatus must be used inside RealtimeProvider");
  return value;
}

export function useRecentEvents(): RealtimeEvent[] {
  return useContext(RecentContext);
}

/** 고른 종류의 이벤트만 받는다. handler의 event.data는 그 종류의 형식으로 좁혀진다. */
export function useRealtimeEvent<K extends EventType>(types: readonly K[], handler: (event: RealtimeEvent<K>) => void): void {
  const subscribe = useContext(SubscribeContext);
  if (!subscribe) throw new Error("useRealtimeEvent must be used inside RealtimeProvider");
  const handlerRef = useRef(handler);
  handlerRef.current = handler;
  const key = types.join(",");
  useEffect(
    () => subscribe((event) => handlerRef.current(event as RealtimeEvent<K>), key.split(",") as EventType[]),
    [subscribe, key],
  );
}
