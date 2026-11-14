import { type MouseEvent, useRef } from "react";
import { type Device, DEVICE_STATE_LABEL, deviceIcon, type PointingRegion } from "../types";

interface RoomMapProps {
  devices: Device[];
  title?: string;
  /** 실시간 device.selected 이벤트로 선택된 기기 */
  highlightedId?: string | null;
  /** 편집 중인 기기 */
  selectedId?: string | null;
  onSelect?: (deviceId: string) => void;
  /** 편집 모드: 배치도를 누르면 그 위치(0~1)를 알려준다. */
  onPick?: (position: { x: number; y: number }) => void;
  /** 편집 중 아직 저장하지 않은 위치 */
  draftPosition?: { x: number; y: number } | null;
}

/** 웹 배치도. map_position(0~1)을 방 평면에 표시한다. 포인팅 판정과는 별개다. */
export function RoomMap({ devices, title, highlightedId, selectedId, onSelect, onPick, draftPosition }: RoomMapProps) {
  const area = useRef<HTMLDivElement>(null);

  const handleClick = (event: MouseEvent<HTMLDivElement>) => {
    if (!onPick || !area.current) return;
    // 아이콘이 가장자리에서 잘리지 않도록 안쪽 영역(area) 기준으로 0~1 좌표를 계산한다.
    const rect = area.current.getBoundingClientRect();
    onPick({
      x: round(clamp((event.clientX - rect.left) / rect.width, 0, 1)),
      y: round(clamp((event.clientY - rect.top) / rect.height, 0, 1)),
    });
  };

  return (
    <figure className="room-map-figure">
      <div
        className={`room-map${onPick ? " editable" : ""}`}
        onClick={handleClick}
        role={onPick ? "button" : undefined}
        aria-label={onPick ? "배치도를 눌러 기기 위치 지정" : `${title ?? "방"} 배치도`}
        tabIndex={onPick ? 0 : undefined}
      >
        {title && <span className="room-map-title">{title}</span>}
        {devices.length === 0 && !draftPosition && <span className="room-map-empty">등록된 기기가 없습니다</span>}
        <div className="room-map-area" ref={area}>
        {devices.map((device) => {
          const classes = [
            "map-device",
            `state-${device.state.toLowerCase()}`,
            device.device_id === highlightedId ? "highlighted" : "",
            device.device_id === selectedId ? "selected" : "",
            device.enabled ? "" : "disabled",
          ].join(" ");
          return (
            <button
              key={device.device_id}
              type="button"
              className={classes}
              style={{ left: `${device.map_position.x * 100}%`, top: `${device.map_position.y * 100}%` }}
              title={`${device.name} · ${DEVICE_STATE_LABEL[device.state]}`}
              onClick={(event) => {
                event.stopPropagation();
                onSelect?.(device.device_id);
              }}
            >
              <span className="map-device-icon" aria-hidden="true">{deviceIcon(device.device_type)}</span>
              <span className="map-device-name">{device.name}</span>
            </button>
          );
        })}
        {draftPosition && (
          <span
            className="map-draft"
            style={{ left: `${draftPosition.x * 100}%`, top: `${draftPosition.y * 100}%` }}
            aria-label="새 위치"
          />
        )}
        </div>
      </div>
      {onPick && <figcaption className="muted">배치도를 눌러 위치를 정합니다. 웹 표시용이며 포인팅 판정에는 쓰지 않습니다.</figcaption>}
    </figure>
  );
}

// ---- geometry ----

/**
 * 포인팅 각도 기준은 서버 의도 판단 모듈(server/intent/device_matcher.py)과 같다.
 * 화면 좌표에서 atan2(dy, dx): 오른쪽 0°, 아래 +90°, 위 -90°, 왼쪽 ±180°.
 */

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function round(value: number, digits = 2): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

export function polarPoint(cx: number, cy: number, radius: number, angleDeg: number): { x: number; y: number } {
  const radians = (angleDeg * Math.PI) / 180;
  return { x: cx + radius * Math.cos(radians), y: cy + radius * Math.sin(radians) };
}

/** 중심에서 min→max 각도로 펼쳐진 부채꼴 SVG 경로. 각도가 커지는 방향은 화면에서 시계 방향이다. */
export function wedgePath(cx: number, cy: number, radius: number, region: PointingRegion): string {
  const span = region.max_angle_deg - region.min_angle_deg;
  if (span >= 360) {
    return `M ${cx - radius} ${cy} a ${radius} ${radius} 0 1 1 ${radius * 2} 0 a ${radius} ${radius} 0 1 1 ${-radius * 2} 0 Z`;
  }
  const start = polarPoint(cx, cy, radius, region.min_angle_deg);
  const end = polarPoint(cx, cy, radius, region.max_angle_deg);
  const largeArc = span > 180 ? 1 : 0;
  const f = (n: number) => n.toFixed(2);
  return `M ${f(cx)} ${f(cy)} L ${f(start.x)} ${f(start.y)} A ${radius} ${radius} 0 ${largeArc} 1 ${f(end.x)} ${f(end.y)} Z`;
}

/** 두 영역이 한 각도라도 겹치면 true. 서버 매칭은 양 끝을 포함(<=)한다. */
export function regionsOverlap(a: PointingRegion, b: PointingRegion): boolean {
  return a.min_angle_deg <= b.max_angle_deg && b.min_angle_deg <= a.max_angle_deg;
}

/** 사용 중인 기기끼리 방향 영역이 겹치는 쌍. 겹치면 서버는 대상을 정하지 못하고 명령을 취소한다. */
export function findOverlaps(devices: Device[]): [Device, Device][] {
  const active = devices.filter((device) => device.enabled);
  const pairs: [Device, Device][] = [];
  for (let i = 0; i < active.length; i += 1) {
    for (let j = i + 1; j < active.length; j += 1) {
      if (regionsOverlap(active[i].pointing_region, active[j].pointing_region)) pairs.push([active[i], active[j]]);
    }
  }
  return pairs;
}

/** 중심 기준 화면 좌표의 각도(-180~180). */
export function angleFromCenter(cx: number, cy: number, x: number, y: number): number {
  return (Math.atan2(y - cy, x - cx) * 180) / Math.PI;
}

export function isValidRegion(region: PointingRegion): boolean {
  return (
    Number.isFinite(region.min_angle_deg) &&
    Number.isFinite(region.max_angle_deg) &&
    region.min_angle_deg >= -180 &&
    region.max_angle_deg <= 180 &&
    region.min_angle_deg < region.max_angle_deg
  );
}

// ---- PointingRegionEditor ----

const WIDTH = 320;
const HEIGHT = 240;
const CX = WIDTH / 2;
const CY = HEIGHT / 2;
const RADIUS = 88;

export function regionToCenter(region: PointingRegion): { center: number; tolerance: number } {
  return {
    center: round((region.min_angle_deg + region.max_angle_deg) / 2, 1),
    tolerance: round((region.max_angle_deg - region.min_angle_deg) / 2, 1),
  };
}

export function centerToRegion(center: number, tolerance: number): PointingRegion {
  return {
    min_angle_deg: round(clamp(center - tolerance, -180, 180), 1),
    max_angle_deg: round(clamp(center + tolerance, -180, 180), 1),
  };
}

interface Props {
  /** 같은 방의 다른 기기(겹침 확인용) */
  others: Device[];
  region: PointingRegion;
  onChange: (region: PointingRegion) => void;
  label?: string;
}

/**
 * 포인팅 방향 영역 편집기. 카메라 영상 기준으로 손목→검지 끝 방향 각도를 정한다.
 * 오른쪽 0°, 아래 +90°, 위 -90°, 왼쪽 ±180° (서버 device_matcher와 같은 기준).
 */
export function PointingRegionEditor({ others, region, onChange, label = "이 기기" }: Props) {
  const { center, tolerance } = regionToCenter(region);
  const overlapping = others.filter((device) => device.enabled && regionsOverlap(device.pointing_region, region));

  const handleClick = (event: MouseEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * WIDTH;
    const y = ((event.clientY - rect.top) / rect.height) * HEIGHT;
    onChange(centerToRegion(round(angleFromCenter(CX, CY, x, y), 0), tolerance));
  };

  const tip = polarPoint(CX, CY, RADIUS + 8, center);

  return (
    <div className="region-editor">
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="region-canvas"
        onClick={handleClick}
        role="img"
        aria-label={`포인팅 방향 ${center}도, 허용 범위 ±${tolerance}도`}
      >
        <rect x="1" y="1" width={WIDTH - 2} height={HEIGHT - 2} rx="10" className="region-frame" />
        <line x1={CX} y1="10" x2={CX} y2={HEIGHT - 10} className="region-axis" />
        <line x1="10" y1={CY} x2={WIDTH - 10} y2={CY} className="region-axis" />
        <text x={WIDTH - 12} y={CY - 6} textAnchor="end" className="region-label">0° 오른쪽</text>
        <text x={CX + 6} y={HEIGHT - 10} className="region-label">90° 아래</text>
        <text x={CX + 6} y="20" className="region-label">-90° 위</text>
        <text x="12" y={CY - 6} className="region-label">±180° 왼쪽</text>
        {others.map((device) => (
          <path
            key={device.device_id}
            d={wedgePath(CX, CY, RADIUS, device.pointing_region)}
            className={`region-other${device.enabled ? "" : " disabled"}${overlapping.includes(device) ? " overlap" : ""}`}
          >
            <title>{device.name}</title>
          </path>
        ))}
        {others.map((device) => {
          const mid = (device.pointing_region.min_angle_deg + device.pointing_region.max_angle_deg) / 2;
          const point = polarPoint(CX, CY, RADIUS * 0.7, mid);
          return (
            <text key={`${device.device_id}-label`} x={point.x} y={point.y} textAnchor="middle" className="region-other-label">
              {device.name}
            </text>
          );
        })}
        <path d={wedgePath(CX, CY, RADIUS, region)} className={`region-current${overlapping.length ? " overlap" : ""}`} />
        <line x1={CX} y1={CY} x2={tip.x} y2={tip.y} className="region-pointer" />
        <circle cx={CX} cy={CY} r="5" className="region-hand" />
        <text x={tip.x} y={tip.y} textAnchor="middle" className="region-current-label">{label}</text>
      </svg>

      <div className="region-controls">
        <label>
          방향 <output>{center}°</output>
          <input
            type="range"
            min={-180}
            max={180}
            step={1}
            value={center}
            onChange={(event) => onChange(centerToRegion(Number(event.target.value), tolerance))}
          />
        </label>
        <label>
          허용 범위 <output>±{tolerance}°</output>
          <input
            type="range"
            min={2}
            max={90}
            step={1}
            value={tolerance}
            onChange={(event) => onChange(centerToRegion(center, Number(event.target.value)))}
          />
        </label>
        <div className="region-numbers">
          <label>
            최소 각도
            <input
              type="number"
              min={-180}
              max={180}
              step={0.5}
              value={region.min_angle_deg}
              onChange={(event) => onChange({ ...region, min_angle_deg: Number(event.target.value) })}
            />
          </label>
          <label>
            최대 각도
            <input
              type="number"
              min={-180}
              max={180}
              step={0.5}
              value={region.max_angle_deg}
              onChange={(event) => onChange({ ...region, max_angle_deg: Number(event.target.value) })}
            />
          </label>
        </div>
        <p className="muted small">
          카메라 영상 기준 손목→검지 끝 방향입니다. 그림을 누르면 그 방향으로 맞춥니다. 기본 허용 범위는 SAD 기준 ±20°입니다.
        </p>
        {overlapping.length > 0 && (
          <p className="warning-text" role="alert">
            {overlapping.map((device) => device.name).join(", ")}와(과) 방향이 겹칩니다. 겹치는 방향을 가리키면 대상을 정하지 못해 명령이
            취소됩니다.
          </p>
        )}
      </div>
    </div>
  );
}
