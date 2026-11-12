import type { Device, PointingRegion } from "../types";

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
