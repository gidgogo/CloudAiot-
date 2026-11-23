import { describe, expect, it } from "vitest";
import type { EventType, RealtimeEvent } from "../types";
import { fingerPoints, IDLE_LIVE, liveResult, nextLiveState, poseForAction, stepStates } from "./DeviceStatus";

function event<K extends EventType>(event_type: K, data: RealtimeEvent<K>["data"]): RealtimeEvent {
  return { schema_version: "1.0", event_id: "e", event_type, correlation_id: "c", timestamp_ms: 0, data } as RealtimeEvent;
}

const command = { command_id: "cmd-1", device_id: "light-01", action: "ON" as const, latency_ms: 420, error_code: null, result: null };

describe("stepStates", () => {
  it("대기 중에는 카메라 칸만 연결 여부를 따른다", () => {
    expect(stepStates("camera", false, true)).toEqual(["done", "off", "off", "off", "off"]);
    expect(stepStates("camera", false, false)).toEqual(["off", "off", "off", "off", "off"]);
  });

  it("지금 단계 앞은 완료, 지금 단계는 진행 중으로 표시한다", () => {
    expect(stepStates("gesture", false, true)).toEqual(["done", "done", "active", "off", "off"]);
  });

  it("제어 실패면 마지막 칸을 실패로 표시한다", () => {
    expect(stepStates("done", true, true)).toEqual(["done", "done", "done", "done", "fail"]);
  });
});

describe("손 모양", () => {
  it("확정된 명령을 매핑에서 그 명령을 내는 제스처로 되돌린다", () => {
    const mappings = [
      { gesture: "OPEN_PALM", action: "ON", enabled: true, updated_at_ms: 0 },
      { gesture: "FIST", action: "OFF", enabled: false, updated_at_ms: 0 },
    ] as const;
    expect(poseForAction("ON", [...mappings])).toBe("OPEN_PALM");
    expect(poseForAction("OFF", [...mappings])).toBe("IDLE");
    expect(poseForAction(null, [...mappings])).toBe("IDLE");
  });

  it("펴진 손가락은 뿌리에서 멀어지고 접힌 손가락은 손바닥 아래로 내려간다", () => {
    const extended = fingerPoints("middle", true);
    const folded = fingerPoints("middle", false);
    expect(extended).toHaveLength(4);
    expect(extended[3][1]).toBeLessThan(extended[0][1]);
    expect(folded[3][1]).toBeGreaterThan(folded[0][1]);
  });
});

describe("실시간 제어 상태", () => {
  it("가리키기 → 확정 → 전송 → 완료 순서로 따라간다", () => {
    let state = nextLiveState(IDLE_LIVE, event("device.selected", { device_id: "light-01" }));
    expect(state).toMatchObject({ step: "selected", target: "light-01" });
    state = nextLiveState(state, event("gesture.confirmed", { action: "ON", target_device_id: "light-01" }));
    expect(state).toMatchObject({ step: "gesture", action: "ON" });
    state = nextLiveState(state, event("command.created", { ...command, status: "PENDING" }));
    expect(state.step).toBe("command");
    state = nextLiveState(state, event("command.completed", { ...command, status: "COMPLETED", result: "OK" }));
    expect(state).toMatchObject({ step: "done", failed: false, latency: 420 });
    expect(liveResult(state)).toEqual({ text: "완료 · 420ms", tone: "ok" });
  });

  it("새로 가리키면 이전 결과를 지운다", () => {
    const failed = nextLiveState(IDLE_LIVE, event("command.failed", { ...command, status: "FAILED", error_code: "DEVICE_OFFLINE" }));
    expect(liveResult(failed)).toEqual({ text: "실패 · DEVICE_OFFLINE", tone: "bad" });
    const next = nextLiveState(failed, event("device.selected", { device_id: "fan-01" }));
    expect(next).toEqual({ ...IDLE_LIVE, step: "selected", target: "fan-01" });
  });

  it("도움 요청 손동작은 대상 기기 없이도 알림 보냄으로 표시한다", () => {
    const state = nextLiveState(IDLE_LIVE, event("gesture.confirmed", { action: "HELP", target_device_id: null }));
    expect(state.target).toBeNull();
    expect(liveResult(state)).toEqual({ text: "보호자에게 알림 보냄", tone: "ok" });
  });

  it("관계없는 이벤트는 상태를 바꾸지 않는다", () => {
    expect(nextLiveState(IDLE_LIVE, event("edge.connected", {}))).toBe(IDLE_LIVE);
    expect(liveResult(IDLE_LIVE)).toEqual({ text: "대기 중", tone: "idle" });
  });
});
