import { type ReactNode, useEffect, useRef, useState } from "react";
import {
  ACTION_LABEL,
  COMMAND_SOURCE_LABEL,
  COMMAND_STATUS_LABEL,
  type CommandEventData,
  CONNECTION_LABEL,
  type ControlEvent,
  DEVICE_STATE_LABEL,
  deviceIcon,
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
//  - 편집기의 LEFT hand · Binding Preview · RIGHT hand 3단 구성과 손 뼈대 그림 → RecognitionPanel, HandSkeleton
//  - 제스처 → 동작 → 대상을 묶은 바인딩 → GestureBindingList
//  - 제스처가 인식되면 소리로 알려 준다 → SoundToggle
//  - 연결 설정·상태를 한 화면에 모은다 → SystemStatusCard

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

/** HouSign 편집기처럼 손 뼈대를 그린다. 펴진 손가락은 주황, 접힌 손가락은 푸른 회색. */
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

/** 손가락별 "엄지: 펴짐" 칩. 펴진 손가락은 초록. */
export function FingerChips({ pose, active = true }: { pose: HandPose; active?: boolean }) {
  return (
    <ul className={`finger-chips${active ? "" : " inactive"}`} aria-label="손가락 상태">
      {FINGERS.map(({ key, label }) => (
        <li key={key} className={`chip${POSE_FINGERS[pose][key] ? " chip-on" : ""}`}>
          {label}: {POSE_FINGERS[pose][key] ? "펴짐" : "접힘"}
        </li>
      ))}
    </ul>
  );
}

// ---- RecognitionPanel ----

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

function Pill({ on, children }: { on: boolean; children: string }) {
  return <span className={`pill${on ? " pill-on" : ""}`}>{children}</span>;
}

interface PanelProps {
  devices: Device[];
  mappings: GestureMapping[];
  roomName: (roomId: string) => string;
  /** ADMIN이면 손동작 편집 화면으로 가는 버튼을 보여 준다. */
  editLink?: ReactNode;
}

/**
 * HouSign 편집기의 3단 구성(LEFT hand · Binding Preview · RIGHT hand)을 옮긴 대시보드 첫 화면.
 * 왼쪽: 카메라가 본 손 모양, 가운데: 지금 인식 단계와 확정된 손동작, 오른쪽: 손가락으로 고른 기기.
 */
export function RecognitionPanel({ devices, mappings, roomName, editLink }: PanelProps) {
  const { edgeStatus } = useRealtimeStatus();
  const [step, setStep] = useState<StepKey>("camera");
  const [failed, setFailed] = useState(false);
  const [target, setTarget] = useState<string | null>(null);
  const [action, setAction] = useState<GestureAction | null>(null);

  const go = (next: StepKey, isFail = false) => {
    setStep(next);
    setFailed(isFail);
  };

  useRealtimeEvent(["device.selected"], ({ data }) => {
    setTarget(data.device_id);
    setAction(null);
    go("selected");
  });
  useRealtimeEvent(["gesture.confirmed"], ({ data }) => {
    const confirmed = data.action as GestureAction | null | undefined;
    setAction(confirmed ?? null);
    if (typeof data.target_device_id === "string") setTarget(data.target_device_id);
    go("gesture");
  });
  useRealtimeEvent(["command.created"], ({ data }) => {
    setTarget(data.device_id);
    setAction(data.action);
    go("command");
  });
  useRealtimeEvent(["command.completed"], () => go("done"));
  useRealtimeEvent(["command.failed"], () => go("done", true));

  useEffect(() => {
    if (step === "camera") return;
    const timer = window.setTimeout(() => {
      go("camera");
      setTarget(null);
      setAction(null);
    }, RECOGNITION_RESET_MS);
    return () => window.clearTimeout(timer);
  }, [step, failed]);

  const cameraOn = edgeStatus === "connected";
  const states = stepStates(step, failed, cameraOn);
  const pose: HandPose = step === "selected" ? "POINTING" : step === "camera" ? "IDLE" : poseForAction(action, mappings);
  const handActive = cameraOn && step !== "camera";
  const device = devices.find((item) => item.device_id === target);
  const mapping = mappings.find((item) => item.gesture === pose);

  return (
    <div className="studio">
      <section className="card studio-side" aria-labelledby="hand-title">
        <div className="studio-head">
          <div>
            <h2 id="hand-title">손 인식</h2>
            <p className="studio-sub">카메라 · {EDGE_STATUS_LABEL[edgeStatus]}</p>
          </div>
          <Pill on={handActive}>{handActive ? "active" : "inactive"}</Pill>
        </div>
        <div className="studio-canvas">
          <HandSkeleton pose={pose} active={handActive} />
        </div>
        <FingerChips pose={pose} active={handActive} />
      </section>

      <section className="card studio-center" aria-labelledby="preview-title">
        <div className="studio-head">
          <div>
            <h2 id="preview-title">인식 미리보기</h2>
            <p className="studio-sub">기기를 손가락으로 가리킨 뒤 손동작을 잠시 유지하면 명령이 실행됩니다.</p>
          </div>
          {editLink}
        </div>

        <div className="block">
          <span className="block-label">진행 단계</span>
          <ol className="steps">
            {STEPS.map((item, i) => (
              <li key={item.key} className={`step is-${states[i]}`}>
                {item.label}
              </li>
            ))}
          </ol>
        </div>

        <div className="block" role="status">
          <span className="block-label">현재 인식된 손동작</span>
          <strong className="block-title">{POSE_LABEL[pose]}</strong>
          <span className="block-code">{pose.toLowerCase()}</span>
          <small className="block-meta">
            단계: {STEPS.find((item) => item.key === step)?.label}
            {failed ? " (실패)" : ""} | 대상: {device ? device.name : "없음"} | 명령: {action ? ACTION_LABEL[action] : "없음"}
          </small>
        </div>

        <div className="block">
          <span className="block-label">연결된 동작</span>
          {mapping && pose !== "POINTING" ? (
            <>
              <strong className="block-title">{ACTION_LABEL[mapping.action]}</strong>
              <p className="muted small">
                {GESTURE_LABEL[mapping.gesture]} → {ACTION_LABEL[mapping.action]} → {ACTION_TARGET[mapping.action]}
                {mapping.enabled ? "" : " (사용 안 함)"}
              </p>
            </>
          ) : (
            <>
              <strong className="block-title muted">{pose === "POINTING" ? "기기 고르는 중" : "연결된 동작 없음"}</strong>
              <p className="muted small">
                {pose === "POINTING" ? "이제 엄지를 올리거나 내려서 켜고 끄세요." : "등록된 손동작을 하면 여기에 연결된 명령이 보입니다."}
              </p>
            </>
          )}
        </div>
      </section>

      <section className="card studio-side" aria-labelledby="target-title">
        <div className="studio-head">
          <div>
            <h2 id="target-title">선택된 기기</h2>
            <p className="studio-sub">{device ? `${device.device_id} · ${roomName(device.room_id)}` : "가리킨 기기가 없습니다"}</p>
          </div>
          <Pill on={Boolean(device)}>{device ? "active" : "inactive"}</Pill>
        </div>
        <div className={`studio-canvas device-stage${device?.state === "ON" ? " is-on" : ""}`}>
          <span className="device-stage-icon" aria-hidden="true">
            {device ? deviceIcon(device.device_type) : "👉"}
          </span>
          <strong>{device ? device.name : "기기를 가리켜 보세요"}</strong>
        </div>
        <ul className="finger-chips" aria-label="기기 상태">
          <li className={`chip${device?.state === "ON" ? " chip-on" : ""}`}>
            상태: {device ? DEVICE_STATE_LABEL[device.state] : "-"}
          </li>
          <li className={`chip${device?.connection_status === "ONLINE" ? " chip-on" : ""}`}>
            연결: {device ? CONNECTION_LABEL[device.connection_status] : "-"}
          </li>
          <li className={`chip${device?.enabled ? " chip-on" : ""}`}>사용: {device ? (device.enabled ? "예" : "아니요") : "-"}</li>
        </ul>
      </section>
    </div>
  );
}

// ---- GestureBindingList ----

const ACTION_TARGET: Record<GestureAction, string> = {
  ON: "가리킨 기기",
  OFF: "가리킨 기기",
  HELP: "보호자에게 알림",
};

const GESTURE_ORDER = ["THUMB_UP", "THUMB_DOWN", "HELP"];

interface BindingProps {
  mappings: GestureMapping[];
  /** 관리자 화면에서만 넘긴다. 없으면 읽기 전용. */
  onChange?: (mapping: GestureMapping, changes: { action?: GestureAction; enabled?: boolean }) => void;
}

/** 손동작 하나를 뼈대 그림 + 손가락 칩 + "→ 동작 → 대상" 으로 보여 주는 카드 목록. 켜기·끄기·도움 순. */
export function GestureBindingList({ mappings, onChange }: BindingProps) {
  if (mappings.length === 0) return <p className="empty">등록된 손동작이 없습니다.</p>;
  const sorted = [...mappings].sort((a, b) => GESTURE_ORDER.indexOf(a.gesture) - GESTURE_ORDER.indexOf(b.gesture));
  return (
    <ul className="bindings">
      {sorted.map((mapping) => (
        <li key={mapping.gesture} className={`binding${mapping.enabled ? "" : " disabled"}`}>
          <div className="binding-canvas">
            <HandSkeleton pose={mapping.gesture} active={mapping.enabled} size={120} />
          </div>
          <div className="binding-body">
            <div className="binding-top">
              <strong className="binding-gesture">{POSE_LABEL[mapping.gesture]}</strong>
              <Pill on={mapping.enabled}>{mapping.enabled ? "사용" : "사용 안 함"}</Pill>
            </div>
            <span className="block-code">{mapping.gesture.toLowerCase()}</span>
            <div className="binding-flow">
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
              <span className="muted">{ACTION_TARGET[mapping.action]}</span>
            </div>
            <FingerChips pose={mapping.gesture} active={mapping.enabled} />
            {onChange && (
              <label className="switch">
                <input
                  type="checkbox"
                  checked={mapping.enabled}
                  onChange={(event) => onChange(mapping, { enabled: event.target.checked })}
                />
                <span>이 손동작 사용</span>
              </label>
            )}
          </div>
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
