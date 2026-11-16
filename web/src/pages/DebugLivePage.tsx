// [임시·개발용] 실시간 동작 확인 화면. 제거: 이 파일을 지우고 `grep -rn "DEBUG-LIVE" server web/src`로 나온 줄을 지운다.
// 서버를 DEBUG_LIVE=1로 실행해야 영상이 나온다(server/api/debug_live.py).
import { useEffect, useState } from "react";
import { EVENT_LABEL, formatTime } from "../types";
import { useRecentEvents } from "../websocket/eventClient";

const BASE = "/api/v1/debug/live";
const POLL_MS = 300;

interface LiveIntent {
  status: string;
  action: string;
  target_device_id: string | null;
  cancel_reason: string | null;
}

interface LiveState {
  connected_edges: string[];
  edge_id?: string;
  gesture?: string;
  handedness?: string;
  stable_frames?: number;
  hold_time_ms?: number;
  fps?: number;
  ai_ms?: number;
  edge_to_server_ms?: number;
  width?: number;
  height?: number;
  last_intent?: LiveIntent | null;
}

function useLiveState(): { state: LiveState | null; error: string | null } {
  const [state, setState] = useState<LiveState | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const response = await fetch(`${BASE}/state`, { credentials: "same-origin" });
        const body = await response.json();
        if (!alive) return;
        if (response.ok && body.success) {
          setState(body.data);
          setError(null);
        } else {
          setError(body.error?.message ?? `HTTP ${response.status}`);
        }
      } catch (caught) {
        if (alive) setError(String(caught));
      }
    };
    void load();
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);
  return { state, error };
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "4px 0" }}>
      <span className="muted">{label}</span>
      <strong style={{ fontVariantNumeric: "tabular-nums" }}>{value}</strong>
    </div>
  );
}

export function DebugLivePage() {
  const { state, error } = useLiveState();
  const recent = useRecentEvents();
  const [streamKey, setStreamKey] = useState(0);
  const connected = (state?.connected_edges.length ?? 0) > 0;
  const intent = state?.last_intent;

  return (
    <div className="dashboard">
      <div className="page-head">
        <div>
          <h1>실시간 동작 확인 (임시)</h1>
          <p className="muted">Edge 영상에 손동작 판정 결과를 겹쳐 보여 줍니다. 개발용 화면이며 영상은 저장하지 않습니다.</p>
        </div>
        <button type="button" className="button ghost small" onClick={() => setStreamKey((key) => key + 1)}>
          영상 다시 연결
        </button>
      </div>

      {error && <p className="empty">상태를 불러오지 못했습니다: {error}</p>}

      <div className="grid-2">
        <section className="card" aria-label="카메라 영상">
          <div className="card-head">
            <h2>카메라</h2>
            <span className="muted small">{connected ? `연결됨 (${state?.connected_edges.join(", ")})` : "연결 대기"}</span>
          </div>
          {connected ? (
            <img
              key={streamKey}
              src={`${BASE}/stream?k=${streamKey}`}
              alt="Edge 실시간 영상과 손동작 판정"
              style={{ width: "100%", borderRadius: 8, background: "#000" }}
            />
          ) : (
            <p className="empty">Edge가 연결되면 영상이 나옵니다.</p>
          )}
        </section>

        <section className="card" aria-label="판정 결과">
          <div className="card-head">
            <h2>판정 결과</h2>
          </div>
          <Row label="제스처" value={state?.gesture ?? "-"} />
          <Row label="손" value={state?.handedness ?? "-"} />
          <Row label="안정화" value={`${state?.stable_frames ?? 0}프레임 / ${state?.hold_time_ms ?? 0}ms`} />
          <Row
            label="마지막 의도"
            value={intent ? `${intent.status} ${intent.action} ${intent.target_device_id ?? ""} ${intent.cancel_reason ?? ""}`.trim() : "-"}
          />
          <Row label="수신 FPS" value={state?.fps != null ? `${state.fps}` : "-"} />
          <Row label="AI 처리" value={state?.ai_ms != null ? `${state.ai_ms}ms` : "-"} />
          <Row label="Edge→서버" value={state?.edge_to_server_ms != null ? `${state.edge_to_server_ms}ms` : "-"} />
          <Row label="해상도" value={state?.width ? `${state.width}×${state.height}` : "-"} />

          <div className="card-head" style={{ marginTop: 16 }}>
            <h2>웹 이벤트</h2>
          </div>
          {recent.length === 0 ? (
            <p className="empty">아직 받은 이벤트가 없습니다.</p>
          ) : (
            <ol className="activity">
              {recent.slice(0, 10).map((event) => (
                <li key={event.event_id}>
                  <time>{formatTime(event.timestamp_ms)}</time>
                  <span>{EVENT_LABEL[event.event_type] ?? event.event_type}</span>
                  <span className="muted small">{JSON.stringify(event.data)}</span>
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
