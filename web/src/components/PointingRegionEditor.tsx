import type { MouseEvent } from "react";
import type { Device, PointingRegion } from "../types";
import { angleFromCenter, clamp, polarPoint, regionsOverlap, round, wedgePath } from "../utils/geometry";

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
