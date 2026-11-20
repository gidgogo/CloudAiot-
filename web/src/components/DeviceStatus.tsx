import { useEffect, useRef, useState } from "react";
import {
  ACTION_LABEL,
  COMMAND_SOURCE_LABEL,
  COMMAND_STATUS_LABEL,
  type CommandEventData,
  type ControlEvent,
  formatLatency,
  type Device,
  EDGE_STATUS_LABEL,
  formatTime,
  GESTURE_LABEL,
  type GestureAction,
  type GestureMapping,
  LATENCY_TARGET_MS,
  type Paged,
} from "../types";
import { type SocketStatus, useRealtimeEvent, useRealtimeStatus } from "../websocket/eventClient";

// HouSign(웹캠 손동작으로 Home Assistant를 제어하는 오픈소스)의 UI에서 가져온 아이디어:
//  - 트레이 아이콘이 "지금 상태"를 보여 준다 → RecognitionStrip
//  - 제스처 → 동작 → 대상을 한 줄로 묶은 바인딩 표 → GestureBindingList
//  - 제스처가 인식되면 소리로 알려 준다 → SoundToggle
//  - 연결 설정·상태를 한 화면에 모은다 → SystemStatusCard

// ---- RecognitionStrip ----

type StepKey = "camera" | "selected" | "gesture" | "command" | "done";
type StepState = "off" | "active" | "done" | "fail";

const STEPS: { key: StepKey; label: string; icon: string }[] = [
  { key: "camera", label: "카메라", icon: "📷" },
  { key: "selected", label: "기기 선택", icon: "👉" },
  { key: "gesture", label: "제스처 확정", icon: "✋" },
  { key: "command", label: "명령 전송", icon: "📡" },
  { key: "done", label: "완료", icon: "✅" },
];

/** 마지막 이벤트 후 이 시간이 지나면 "대기" 상태로 돌아간다. */
export const RECOGNITION_RESET_MS = 5000;

/** 지금 어느 단계까지 왔는지로 각 칸의 상태를 정한다. 카메라 칸은 엣지 연결 여부만 본다. */
export function stepStates(current: StepKey, failed: boolean, cameraOn: boolean): StepState[] {
  const index = STEPS.findIndex((step) => step.key === current);
  return STEPS.map((step, i) => {
    if (step.key === "camera") return cameraOn ? "done" : "off";
    if (i < index) return "done";
    if (i === index) return failed ? "fail" : "active";
    return "off";
  });
}

/**
 * 대시보드 맨 위의 인식 진행 막대.
 * 카메라 → 기기 선택 → 제스처 확정 → 명령 전송 → 완료 순서로, 실시간 이벤트가 올 때마다 칸이 켜진다.
 */
export function RecognitionStrip({ deviceName }: { deviceName: (deviceId: string) => string }) {
  const { edgeStatus } = useRealtimeStatus();
  const [step, setStep] = useState<StepKey>("camera");
  const [failed, setFailed] = useState(false);
  const [target, setTarget] = useState<string | null>(null);

  const go = (next: StepKey, isFail = false) => {
    setStep(next);
    setFailed(isFail);
  };

  useRealtimeEvent(["device.selected"], ({ data }) => {
    setTarget(data.device_id);
    go("selected");
  });
  useRealtimeEvent(["gesture.confirmed"], () => go("gesture"));
  useRealtimeEvent(["command.created"], ({ data }) => {
    setTarget(data.device_id);
    go("command");
  });
  useRealtimeEvent(["command.completed"], () => go("done"));
  useRealtimeEvent(["command.failed"], () => go("done", true));

  useEffect(() => {
    if (step === "camera") return;
    const timer = window.setTimeout(() => {
      go("camera");
      setTarget(null);
    }, RECOGNITION_RESET_MS);
    return () => window.clearTimeout(timer);
  }, [step, failed]);

  const states = stepStates(step, failed, edgeStatus === "connected");
  let message = "기기를 가리키고 손동작을 해 보세요.";
  if (edgeStatus !== "connected") message = `카메라 ${EDGE_STATUS_LABEL[edgeStatus]}`;
  if (target) message = `대상: ${deviceName(target)}`;
  if (step === "done") message = failed ? `${target ? deviceName(target) : "기기"} 제어 실패` : `${target ? deviceName(target) : "기기"} 제어 완료`;

  return (
    <section className="card recognition" aria-label="인식 진행 상태">
      <ol className="recognition-steps">
        {STEPS.map((item, i) => (
          <li key={item.key} className={`recognition-step is-${states[i]}`}>
            <span className="recognition-icon" aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </li>
        ))}
      </ol>
      <p className="recognition-message" role="status">{message}</p>
    </section>
  );
}

// ---- GestureBindingList ----

const ACTION_TARGET: Record<GestureAction, string> = {
  ON: "가리킨 기기",
  OFF: "가리킨 기기",
  HELP: "보호자에게 알림",
};

interface BindingProps {
  mappings: GestureMapping[];
  /** 관리자 화면에서만 넘긴다. 없으면 읽기 전용. */
  onChange?: (mapping: GestureMapping, changes: { action?: GestureAction; enabled?: boolean }) => void;
}

const GESTURE_ORDER = ["THUMB_UP", "THUMB_DOWN", "HELP"];

/** 제스처 → 동작 → 대상을 한 줄씩 보여 주는 카드 목록. 켜기·끄기·도움 순으로 늘어놓는다. */
export function GestureBindingList({ mappings, onChange }: BindingProps) {
  if (mappings.length === 0) return <p className="empty">등록된 손동작이 없습니다.</p>;
  const sorted = [...mappings].sort((a, b) => GESTURE_ORDER.indexOf(a.gesture) - GESTURE_ORDER.indexOf(b.gesture));
  return (
    <ul className="bindings">
      {sorted.map((mapping) => (
        <li key={mapping.gesture} className={`binding${mapping.enabled ? "" : " disabled"}`}>
          <span className="binding-gesture">{GESTURE_LABEL[mapping.gesture] ?? mapping.gesture}</span>
          <span className="binding-arrow" aria-hidden="true">→</span>
          {onChange ? (
            <select
              aria-label={`${mapping.gesture} 명령`}
              value={mapping.action}
              onChange={(event) => onChange(mapping, { action: event.target.value as GestureAction })}
            >
              {(Object.keys(ACTION_LABEL) as GestureAction[]).map((action) => (
                <option key={action} value={action}>
                  {ACTION_LABEL[action]}
                </option>
              ))}
            </select>
          ) : (
            <strong className="binding-action">{ACTION_LABEL[mapping.action]}</strong>
          )}
          <span className="binding-arrow" aria-hidden="true">→</span>
          <span className="binding-target muted">{ACTION_TARGET[mapping.action]}</span>
          {onChange ? (
            <label className="switch binding-switch">
              <input
                type="checkbox"
                checked={mapping.enabled}
                onChange={(event) => onChange(mapping, { enabled: event.target.checked })}
              />
              <span>{mapping.enabled ? "사용" : "사용 안 함"}</span>
            </label>
          ) : (
            !mapping.enabled && <span className="badge muted binding-switch">사용 안 함</span>
          )}
        </li>
      ))}
    </ul>
  );
}

// ---- SoundToggle ----

const SOUND_KEY = "cloudaiot.sound";

function readSoundSetting(): boolean {
  try {
    return window.localStorage.getItem(SOUND_KEY) !== "off";
  } catch {
    return true;
  }
}

function writeSoundSetting(on: boolean) {
  try {
    window.localStorage.setItem(SOUND_KEY, on ? "on" : "off");
  } catch {
    // 저장이 막힌 브라우저에서는 이번 접속 동안만 기억한다.
  }
}

/** 짧은 "삑" 소리. 파일 없이 Web Audio로 만든다. */
function beep(context: AudioContext, frequency: number, durationMs = 120) {
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  oscillator.frequency.value = frequency;
  gain.gain.setValueAtTime(0.15, context.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.001, context.currentTime + durationMs / 1000);
  oscillator.connect(gain).connect(context.destination);
  oscillator.start();
  oscillator.stop(context.currentTime + durationMs / 1000);
}

/**
 * 상단 바의 소리 켜기/끄기 버튼. 켜져 있으면 제스처 확정·제어 성공·실패 때 서로 다른 소리가 난다.
 * 브라우저는 사용자가 한 번 누르기 전에는 소리를 막으므로, 버튼을 누를 때 AudioContext를 깨운다.
 */
export function SoundToggle() {
  const [on, setOn] = useState(readSoundSetting);
  const contextRef = useRef<AudioContext | null>(null);

  const play = (frequency: number) => {
    if (!on || typeof AudioContext === "undefined") return;
    contextRef.current ??= new AudioContext();
    if (contextRef.current.state === "suspended") void contextRef.current.resume();
    beep(contextRef.current, frequency);
  };

  useRealtimeEvent(["gesture.confirmed"], () => play(880));
  useRealtimeEvent(["command.completed"], () => play(1320));
  useRealtimeEvent(["command.failed"], () => play(220));

  const toggle = () => {
    const next = !on;
    setOn(next);
    writeSoundSetting(next);
    if (next && typeof AudioContext !== "undefined") {
      contextRef.current ??= new AudioContext();
      void contextRef.current.resume();
    }
  };

  return (
    <button
      type="button"
      className="icon-button"
      aria-pressed={on}
      title={on ? "인식 소리 끄기" : "인식 소리 켜기"}
      onClick={toggle}
    >
      {on ? "🔊" : "🔇"}
      <span className="sr-only">{on ? "인식 소리 끄기" : "인식 소리 켜기"}</span>
    </button>
  );
}

// ---- SystemStatusCard ----

const SOCKET_TEXT: Record<SocketStatus, string> = {
  connecting: "연결 중",
  open: "연결됨",
  reconnecting: "다시 연결 중",
  unauthorized: "인증 필요",
  closed: "연결 안 됨",
};

type Tone = "ok" | "warn" | "bad" | "idle";

function StatusRow({ label, value, tone, detail }: { label: string; value: string; tone: Tone; detail?: string }) {
  return (
    <li className={`system-row tone-${tone}`}>
      <span className="dot" aria-hidden="true" />
      <span className="system-label">{label}</span>
      <strong className="system-value">{value}</strong>
      {detail && <small className="system-detail muted">{detail}</small>}
    </li>
  );
}

/** 실시간 서버·카메라·기기 연결을 한 카드에 모아 보여 준다. */
export function SystemStatusCard({ devices }: { devices: Device[] }) {
  const { status, edgeStatus } = useRealtimeStatus();
  const enabled = devices.filter((device) => device.enabled);
  const offline = enabled.filter((device) => device.connection_status === "OFFLINE");
  const socketTone: Tone = status === "open" ? "ok" : status === "unauthorized" ? "bad" : "warn";
  const edgeTone: Tone = edgeStatus === "connected" ? "ok" : edgeStatus === "disconnected" ? "bad" : "idle";
  const deviceTone: Tone = enabled.length === 0 ? "idle" : offline.length === 0 ? "ok" : "warn";

  return (
    <section className="card" aria-labelledby="system-title">
      <div className="card-head">
        <h2 id="system-title">시스템 상태</h2>
      </div>
      <ul className="system-status">
        <StatusRow label="실시간 서버" value={SOCKET_TEXT[status]} tone={socketTone} />
        <StatusRow label="카메라" value={EDGE_STATUS_LABEL[edgeStatus]} tone={edgeTone} />
        <StatusRow
          label="기기 연결"
          value={`${enabled.length - offline.length} / ${enabled.length}`}
          tone={deviceTone}
          detail={offline.length > 0 ? `끊김: ${offline.map((device) => device.name).join(", ")}` : undefined}
        />
      </ul>
    </section>
  );
}

// ---- ControlEventTable ----

interface Props {
  events: ControlEvent[];
  deviceName: (deviceId: string) => string;
  emptyText?: string;
}

export function ControlEventTable({ events, deviceName, emptyText = "제어 이력이 없습니다." }: Props) {
  if (events.length === 0) return <p className="empty">{emptyText}</p>;
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">시각</th>
            <th scope="col">기기</th>
            <th scope="col">명령</th>
            <th scope="col">입력</th>
            <th scope="col">결과</th>
            <th scope="col">지연</th>
          </tr>
        </thead>
        <tbody>
          {events.map((event) => (
            <tr key={event.command_id}>
              <td>{formatTime(event.command_published_at_ms)}</td>
              <td>{deviceName(event.device_id)}</td>
              <td>{ACTION_LABEL[event.action]}</td>
              <td>{COMMAND_SOURCE_LABEL[event.source] ?? event.source}</td>
              <td>
                <span className={`badge command-${event.status.toLowerCase()}`}>{COMMAND_STATUS_LABEL[event.status]}</span>
                {event.error_code && <small className="muted"> {event.error_code}</small>}
              </td>
              {/* NFR-01 목표(2초)를 넘은 지연은 강조한다. */}
              <td className={event.latency_ms !== null && event.latency_ms > LATENCY_TARGET_MS ? "danger-text" : undefined}>
                {formatLatency(event.latency_ms)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---- commands ----

/**
 * command.completed / command.failed 이벤트에는 표에 필요한 결과가 모두 들어 있으므로
 * 목록을 다시 불러오지 않고 해당 행만 바꾼다. 목록에 없으면 그대로 둔다.
 */
export function applyCommandEvent(page: Paged<ControlEvent> | undefined, data: CommandEventData): Paged<ControlEvent> | undefined {
  if (!page || !page.items.some((item) => item.command_id === data.command_id)) return page;
  return {
    ...page,
    items: page.items.map((item) =>
      item.command_id === data.command_id
        ? { ...item, status: data.status, result: data.result, error_code: data.error_code, latency_ms: data.latency_ms }
        : item,
    ),
  };
}
