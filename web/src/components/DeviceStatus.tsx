import { type ReactNode, useEffect, useState } from "react";
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
  type GestureAction,
  type GestureMapping,
  LATENCY_TARGET_MS,
  type Paged,
  type RealtimeEvent,
} from "../types";
import { useRealtimeEvent, useRealtimeStatus } from "../websocket/eventClient";
import { DeviceGlyph, Icon } from "./DeviceCard";

// 손동작 인식부터 기기 제어 결과까지 보여 주는 화면 조각들.
//  - HandSkeleton: 제스처 판정 규칙대로 손 관절을 그린 그림 (HouSign 편집기 참고)
//  - useLiveControl / LiveControlPanel: 실시간 이벤트로 인식 → 기기 → 명령 → 결과를 따라가 한 패널에 모은다
//  - GestureBindingList: 손동작 → 명령 → 대상 목록
//  - SoundToggle / playTone: 인식·성공·실패·도움 요청 효과음

// ---- HandSkeleton ----

/** 화면에 그릴 손 모양. 서버 제스처(POINTING, THUMB_UP, THUMB_DOWN, HELP)에 "아무것도 아님"을 더했다. */
export type HandPose = "IDLE" | "POINTING" | "THUMB_UP" | "THUMB_DOWN" | "HELP";
type Finger = "thumb" | "index" | "middle" | "ring" | "pinky";

const FINGERS: { key: Finger; label: string }[] = [
  { key: "thumb", label: "엄지" },
  { key: "index", label: "검지" },
  { key: "middle", label: "중지" },
  { key: "ring", label: "약지" },
  { key: "pinky", label: "소지" },
];

/** server/vision/gesture_rules.py 의 판정 규칙을 손가락별 펴짐/접힘으로 옮긴 것 */
export const POSE_FINGERS: Record<HandPose, Record<Finger, boolean>> = {
  IDLE: { thumb: false, index: false, middle: false, ring: false, pinky: false },
  POINTING: { thumb: false, index: true, middle: false, ring: false, pinky: false },
  THUMB_UP: { thumb: true, index: false, middle: false, ring: false, pinky: false },
  THUMB_DOWN: { thumb: true, index: false, middle: false, ring: false, pinky: false },
  HELP: { thumb: true, index: true, middle: true, ring: true, pinky: true },
};

export const POSE_LABEL: Record<HandPose, string> = {
  IDLE: "인식 대기",
  POINTING: "가리키기",
  THUMB_UP: "엄지 올림",
  THUMB_DOWN: "엄지 내림",
  HELP: "손바닥 펴기",
};

// 손가락 뿌리(MCP) 위치, 펴졌을 때 방향(도, -90이 위쪽), 마디 길이
const BONES: Record<Finger, { base: [number, number]; angle: number; lengths: number[] }> = {
  thumb: { base: [70, 166], angle: -112, lengths: [26, 22, 18] },
  index: { base: [80, 118], angle: -96, lengths: [30, 22, 18] },
  middle: { base: [100, 112], angle: -90, lengths: [34, 24, 20] },
  ring: { base: [119, 116], angle: -84, lengths: [30, 22, 18] },
  pinky: { base: [136, 126], angle: -76, lengths: [24, 18, 15] },
};
const PALM: [number, number][] = [
  [84, 200], [120, 200], [142, 150], [136, 126], [119, 116], [100, 112], [80, 118], [66, 160],
];

/** 손가락 하나의 관절 좌표 4개(뿌리 → 끝)를 만든다. */
export function fingerPoints(finger: Finger, extended: boolean): [number, number][] {
  const { base, angle, lengths } = BONES[finger];
  const [x, y] = base;
  if (finger === "thumb" && !extended) {
    // 접힌 엄지는 손바닥을 가로질러 눕는다.
    return [base, [x + 12, y - 12], [x + 25, y - 16], [x + 37, y - 14]];
  }
  if (!extended) {
    // 접힌 손가락은 뿌리에서 손바닥 안쪽(아래)으로 말려 들어간다.
    return [base, [x + 1, y + 15], [x + 2, y + 28], [x + 1, y + 38]];
  }
  const rad = (angle * Math.PI) / 180;
  const points: [number, number][] = [base];
  let distance = 0;
  for (const length of lengths) {
    distance += length;
    points.push([x + Math.cos(rad) * distance, y + Math.sin(rad) * distance]);
  }
  return points;
}

/** HouSign 편집기처럼 손 뼈대를 그린다. 펴진 손가락은 파랑, 접힌 손가락은 회색. */
export function HandSkeleton({ pose, active = true, size = 240 }: { pose: HandPose; active?: boolean; size?: number }) {
  const fingers = POSE_FINGERS[pose];
  // 엄지 내림은 엄지 올림을 뒤집어 그린다. 가리키기는 오른쪽을 향하게 살짝 기울인다.
  const transform = pose === "THUMB_DOWN" ? "rotate(180 100 150)" : pose === "POINTING" ? "rotate(22 100 160)" : undefined;
  return (
    <svg
      className={`hand-skeleton${active ? "" : " inactive"}`}
      viewBox="25 15 150 200"
      width={size}
      height={size}
      role="img"
      aria-label={`손 모양: ${POSE_LABEL[pose]}`}
    >
      <g transform={transform}>
        <polygon className="hand-palm" points={PALM.map((p) => p.join(",")).join(" ")} />
        <line className="hand-wrist" x1="82" y1="204" x2="122" y2="204" />
        {FINGERS.map(({ key }) => {
          const points = fingerPoints(key, fingers[key]);
          const kind = fingers[key] ? "extended" : "folded";
          return (
            <g key={key} className={`hand-finger ${kind}`}>
              <polyline points={points.map((p) => p.join(",")).join(" ")} />
              {points.map(([cx, cy], i) => (
                <circle key={i} cx={cx} cy={cy} r={i === points.length - 1 ? 4.5 : 3.8} />
              ))}
            </g>
          );
        })}
      </g>
    </svg>
  );
}

// ---- LiveControlPanel ----

type StepKey = "camera" | "selected" | "gesture" | "command" | "done";
type StepState = "off" | "active" | "done" | "fail";

const STEPS: { key: StepKey; label: string }[] = [
  { key: "camera", label: "카메라" },
  { key: "selected", label: "기기 선택" },
  { key: "gesture", label: "제스처 확정" },
  { key: "command", label: "명령 전송" },
  { key: "done", label: "완료" },
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

/** 확정된 명령(ON/OFF/HELP)을 지금 매핑에서 그 명령을 내는 제스처로 되돌린다. */
export function poseForAction(action: GestureAction | null, mappings: GestureMapping[]): HandPose {
  if (!action) return "IDLE";
  return mappings.find((mapping) => mapping.enabled && mapping.action === action)?.gesture ?? "IDLE";
}

const ACTION_TARGET: Record<GestureAction, string> = {
  ON: "가리킨 기기",
  OFF: "가리킨 기기",
  HELP: "보호자에게 알림",
};

/** 지금 진행 중인 인식 한 번의 상태. 대시보드의 패널과 배치도가 같은 값을 본다. */
export interface LiveState {
  step: StepKey;
  failed: boolean;
  /** 가리킨(또는 명령 대상) 기기 */
  target: string | null;
  action: GestureAction | null;
  error: string | null;
  latency: number | null;
}

export const IDLE_LIVE: LiveState = { step: "camera", failed: false, target: null, action: null, error: null, latency: null };

const LIVE_EVENTS = ["device.selected", "gesture.confirmed", "command.created", "command.completed", "command.failed"] as const;

/** 이벤트 하나를 받아 다음 상태를 만든다. 화면과 떼어 놓아 테스트할 수 있게 했다. */
export function nextLiveState(state: LiveState, event: RealtimeEvent): LiveState {
  switch (event.event_type) {
    case "device.selected":
      // 새로 가리키면 이전 명령 결과는 지운다.
      return { ...IDLE_LIVE, step: "selected", target: event.data.device_id };
    case "gesture.confirmed":
      return {
        ...state,
        step: "gesture",
        failed: false,
        action: event.data.action ?? null,
        target: event.data.target_device_id ?? state.target,
      };
    case "command.created":
      return { ...state, step: "command", failed: false, target: event.data.device_id, action: event.data.action };
    case "command.completed":
      return { ...state, step: "done", failed: false, target: event.data.device_id, latency: event.data.latency_ms };
    case "command.failed":
      return {
        ...state,
        step: "done",
        failed: true,
        target: event.data.device_id,
        error: event.data.error_code ?? "알 수 없는 오류",
        latency: event.data.latency_ms,
      };
    default:
      return state;
  }
}

/**
 * 실시간 이벤트로 인식 진행 상태를 따라간다. 마지막 이벤트 후 RECOGNITION_RESET_MS가 지나면 대기로 돌아간다.
 * 같은 단계의 이벤트가 다시 와도(예: 같은 기기를 다시 가리킴) 타이머를 새로 시작한다.
 */
export function useLiveControl(): LiveState {
  const [state, setState] = useState<LiveState>(IDLE_LIVE);
  const [received, setReceived] = useState(0);

  useRealtimeEvent(LIVE_EVENTS, (event) => {
    setState((current) => nextLiveState(current, event));
    setReceived((count) => count + 1);
  });

  useEffect(() => {
    if (received === 0) return;
    const timer = window.setTimeout(() => setState(IDLE_LIVE), RECOGNITION_RESET_MS);
    return () => window.clearTimeout(timer);
  }, [received]);

  return state;
}

type Tone = "idle" | "active" | "ok" | "bad";

/** '결과' 줄에 보여 줄 글자와 색. */
export function liveResult(state: LiveState): { text: string; tone: Tone } {
  const { step, failed, action, error, latency } = state;
  if (step === "gesture" && action === "HELP") return { text: "보호자에게 알림 보냄", tone: "ok" };
  if (step === "done" && failed) return { text: `실패 · ${error ?? "알 수 없는 오류"}`, tone: "bad" };
  if (step === "done") return { text: `완료${latency !== null ? ` · ${formatLatency(latency)}` : ""}`, tone: "ok" };
  if (step === "camera") return { text: "대기 중", tone: "idle" };
  return { text: "진행 중", tone: "active" };
}

interface PanelProps {
  live: LiveState;
  devices: Device[];
  mappings: GestureMapping[];
  roomName: (roomId: string) => string;
  /** ADMIN이면 손동작 매핑 화면으로 가는 링크 */
  action?: ReactNode;
}

/**
 * 대시보드의 '실시간 제어' 패널.
 * 왼쪽에 손 관절 그림, 오른쪽에 인식된 동작 · 선택된 기기 · 연결된 명령 · 결과를 한 줄씩 두고,
 * 아래에 카메라 → 기기 선택 → 제스처 확정 → 명령 전송 → 완료 5단계를 연결선으로 잇는다.
 * 시연에서 "엄지 올림 → 조명 선택 → 켜기 명령 → 완료" 흐름을 한 영역에서 따라갈 수 있게 한다.
 */
export function LiveControlPanel({ live, devices, mappings, roomName, action: headerAction }: PanelProps) {
  const { edgeStatus } = useRealtimeStatus();
  const { step, failed, target, action } = live;
  const cameraOn = edgeStatus === "connected";
  const states = stepStates(step, failed, cameraOn);
  const pose: HandPose = step === "selected" ? "POINTING" : step === "camera" ? "IDLE" : poseForAction(action, mappings);
  const handActive = cameraOn && step !== "camera";
  const device = devices.find((item) => item.device_id === target);
  const extended = FINGERS.filter(({ key }) => POSE_FINGERS[pose][key]).map(({ label }) => label);
  const result = liveResult(live);

  return (
    <section className="panel live-panel" aria-labelledby="live-title">
      <header className="panel-head">
        <div>
          <h2 id="live-title">실시간 제어</h2>
          <p className="panel-sub">기기를 손가락으로 가리킨 뒤 손동작을 잠시 유지하면 명령이 실행됩니다.</p>
        </div>
        {headerAction}
      </header>

      <div className="live-body">
        <figure className="live-hand">
          <HandSkeleton pose={pose} active={handActive} size={200} />
          <figcaption>
            {cameraOn ? `카메라 ${EDGE_STATUS_LABEL[edgeStatus]}` : `카메라 ${EDGE_STATUS_LABEL[edgeStatus]} · 손을 볼 수 없음`}
            <br />
            펴진 손가락: {extended.length > 0 ? extended.join(", ") : "없음"}
          </figcaption>
        </figure>

        <dl className="live-rows" aria-live="polite">
          <div className="live-row">
            <dt>인식된 동작</dt>
            <dd>
              <strong>{POSE_LABEL[pose]}</strong>
              <code>{pose.toLowerCase()}</code>
            </dd>
          </div>
          <div className="live-row">
            <dt>선택된 기기</dt>
            <dd>
              {device ? (
                <>
                  <span className={`device-row-icon state-${device.state.toLowerCase()}`}>
                    <DeviceGlyph type={device.device_type} size={18} />
                  </span>
                  <strong>{device.name}</strong>
                  <small className="muted">
                    {device.device_id} · {roomName(device.room_id)}
                  </small>
                </>
              ) : (
                <span className="muted">가리킨 기기 없음</span>
              )}
            </dd>
          </div>
          <div className="live-row">
            <dt>연결된 명령</dt>
            <dd>
              {action ? (
                <>
                  <strong>{ACTION_LABEL[action]}</strong>
                  <span className="muted">→ {action === "HELP" ? ACTION_TARGET.HELP : device?.name ?? ACTION_TARGET[action]}</span>
                </>
              ) : (
                <span className="muted">{step === "selected" ? "엄지를 올리거나 내려 켜고 끄세요" : "없음"}</span>
              )}
            </dd>
          </div>
          <div className="live-row">
            <dt>결과</dt>
            <dd>
              <span className={`status status-${result.tone}`}>
                <span className="dot" aria-hidden="true" />
                {result.text}
              </span>
            </dd>
          </div>
        </dl>
      </div>

      <ol className="stepper" aria-label="진행 단계">
        {STEPS.map((item, i) => (
          <li key={item.key} className={`stepper-step is-${states[i]}`} aria-current={states[i] === "active" ? "step" : undefined}>
            <span className="stepper-mark" aria-hidden="true">
              {states[i] === "done" ? "✓" : states[i] === "fail" ? "!" : i + 1}
            </span>
            <span className="stepper-label">
              {item.label}
              <span className="sr-only">
                {states[i] === "done" ? " 완료" : states[i] === "active" ? " 진행 중" : states[i] === "fail" ? " 실패" : ""}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

// ---- GestureBindingList ----

const GESTURE_ORDER = ["THUMB_UP", "THUMB_DOWN", "HELP"];

interface BindingProps {
  mappings: GestureMapping[];
  /** 관리자 화면에서만 넘긴다. 없으면 읽기 전용. */
  onChange?: (mapping: GestureMapping, changes: { action?: GestureAction; enabled?: boolean }) => void;
}

/** 손동작 → 명령 → 대상을 한 줄씩 보여 주는 목록. 켜기·끄기·도움 순. */
export function GestureBindingList({ mappings, onChange }: BindingProps) {
  if (mappings.length === 0) return <p className="empty">등록된 손동작이 없습니다.</p>;
  const sorted = [...mappings].sort((a, b) => GESTURE_ORDER.indexOf(a.gesture) - GESTURE_ORDER.indexOf(b.gesture));
  return (
    <ul className="bindings">
      {sorted.map((mapping) => (
        <li key={mapping.gesture} className={`binding${mapping.enabled ? "" : " disabled"}`}>
          <HandSkeleton pose={mapping.gesture} active={mapping.enabled} size={56} />
          <span className="binding-gesture">
            <strong>{POSE_LABEL[mapping.gesture]}</strong>
            <code>{mapping.gesture.toLowerCase()}</code>
          </span>
          <span className="binding-flow">
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
              <strong>{ACTION_LABEL[mapping.action]}</strong>
            )}
            <span className="muted">→ {ACTION_TARGET[mapping.action]}</span>
          </span>
          {onChange ? (
            <label className="switch">
              <input
                type="checkbox"
                checked={mapping.enabled}
                onChange={(event) => onChange(mapping, { enabled: event.target.checked })}
              />
              <span>{mapping.enabled ? "사용" : "사용 안 함"}</span>
            </label>
          ) : (
            <span className={`status ${mapping.enabled ? "status-ok" : "status-idle"}`}>
              <span className="dot" aria-hidden="true" />
              {mapping.enabled ? "사용" : "사용 안 함"}
            </span>
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

// 효과음은 파일 없이 Web Audio로 만든다. AudioContext는 화면 전체에서 하나만 쓴다.
let audio: AudioContext | null = null;

function audioContext(): AudioContext | null {
  try {
    const Context =
      window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Context) return null;
    audio ??= new Context();
    // 브라우저는 사용자가 한 번 누르기 전에는 소리를 막아 두므로 그때마다 깨운다.
    if (audio.state === "suspended") void audio.resume();
    return audio;
  } catch {
    return null;
  }
}

/** 짧은 "삑" 소리. 소리를 낼 수 없는 브라우저에서는 아무것도 하지 않는다. */
export function playTone(frequency: number, durationMs = 120): void {
  const context = audioContext();
  if (!context) return;
  try {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    const end = context.currentTime + durationMs / 1000;
    oscillator.frequency.value = frequency;
    gain.gain.setValueAtTime(0.15, context.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, end);
    oscillator.connect(gain).connect(context.destination);
    oscillator.start();
    oscillator.stop(end);
  } catch {
    // 재생이 막혀도 화면 동작에는 영향이 없다.
  }
}

/**
 * 상단 바의 소리 켜기/끄기 버튼. 켜져 있으면 제스처 확정·제어 성공·실패 때 서로 다른 소리가 난다.
 * (보호자용 도움 요청 알림음은 놓치면 안 되므로 이 설정과 상관없이 울린다.)
 */
export function SoundToggle() {
  const [on, setOn] = useState(readSoundSetting);

  const play = (frequency: number) => {
    if (on) playTone(frequency);
  };

  useRealtimeEvent(["gesture.confirmed"], () => play(880));
  useRealtimeEvent(["command.completed"], () => play(1320));
  useRealtimeEvent(["command.failed"], () => play(220));

  const toggle = () => {
    const next = !on;
    setOn(next);
    writeSoundSetting(next);
    // 켤 때 누른 순간을 이용해 소리 재생을 허용받는다.
    if (next) audioContext();
  };

  return (
    <button
      type="button"
      className="icon-button"
      aria-pressed={on}
      title={on ? "인식 소리 끄기" : "인식 소리 켜기"}
      onClick={toggle}
    >
      <Icon name={on ? "soundOn" : "soundOff"} />
      <span className="sr-only">{on ? "인식 소리 끄기" : "인식 소리 켜기"}</span>
    </button>
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
