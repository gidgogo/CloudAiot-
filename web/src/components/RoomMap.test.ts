import { describe, expect, it } from "vitest";
import type { Device } from "../types";
import {
  angleFromCenter,
  centerToRegion,
  findOverlaps,
  isValidRegion,
  regionsOverlap,
  regionToCenter,
  wedgePath,
} from "./RoomMap";

// 포인팅 방향 영역 계산(서버 device_matcher와 같은 기준) 테스트

function device(id: string, min: number, max: number, enabled = true): Device {
  return {
    device_id: id,
    room_id: "room-01",
    name: id,
    device_type: "FAN",
    map_position: { x: 0.5, y: 0.5 },
    pointing_region: { min_angle_deg: min, max_angle_deg: max },
    enabled,
    state: "UNKNOWN",
    connection_status: "OFFLINE",
    state_updated_at_ms: null,
    created_at_ms: 0,
    updated_at_ms: 0,
  };
}

describe("angle convention (same as server device_matcher)", () => {
  it("uses screen coordinates: right 0°, down +90°, up -90°", () => {
    expect(angleFromCenter(0, 0, 1, 0)).toBeCloseTo(0);
    expect(angleFromCenter(0, 0, 0, 1)).toBeCloseTo(90);
    expect(angleFromCenter(0, 0, 0, -1)).toBeCloseTo(-90);
    expect(Math.abs(angleFromCenter(0, 0, -1, 0))).toBeCloseTo(180);
  });
});

describe("overlaps", () => {
  it("treats touching edges as overlapping because matching is inclusive", () => {
    expect(regionsOverlap({ min_angle_deg: 0, max_angle_deg: 10 }, { min_angle_deg: 10, max_angle_deg: 20 })).toBe(true);
    expect(regionsOverlap({ min_angle_deg: 0, max_angle_deg: 10 }, { min_angle_deg: 11, max_angle_deg: 20 })).toBe(false);
  });

  it("ignores disabled devices", () => {
    const pairs = findOverlaps([device("a", 0, 30), device("b", 20, 40), device("c", 25, 35, false)]);
    expect(pairs.map(([a, b]) => `${a.device_id}-${b.device_id}`)).toEqual(["a-b"]);
  });
});

describe("region helpers", () => {
  it("converts between min/max and center/tolerance", () => {
    expect(regionToCenter({ min_angle_deg: -20, max_angle_deg: 20 })).toEqual({ center: 0, tolerance: 20 });
    expect(centerToRegion(-90, 25)).toEqual({ min_angle_deg: -115, max_angle_deg: -65 });
    expect(centerToRegion(170, 20)).toEqual({ min_angle_deg: 150, max_angle_deg: 180 });
  });

  it("validates regions like the server", () => {
    expect(isValidRegion({ min_angle_deg: -15, max_angle_deg: 15 })).toBe(true);
    expect(isValidRegion({ min_angle_deg: 15, max_angle_deg: 15 })).toBe(false);
    expect(isValidRegion({ min_angle_deg: -200, max_angle_deg: 0 })).toBe(false);
  });

  it("draws a wedge path", () => {
    expect(wedgePath(0, 0, 10, { min_angle_deg: 0, max_angle_deg: 90 })).toBe("M 0.00 0.00 L 10.00 0.00 A 10 10 0 0 1 0.00 10.00 Z");
  });
});
