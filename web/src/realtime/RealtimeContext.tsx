import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import type { EventType, RealtimeEvent } from "../types";
import { EventClient, type SocketStatus } from "../websocket/eventClient";

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

  return (
    <SubscribeContext.Provider value={subscribe}>
      <StatusContext.Provider value={statusValue}>
        <RecentContext.Provider value={recent}>{children}</RecentContext.Provider>
      </StatusContext.Provider>
    </SubscribeContext.Provider>
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
