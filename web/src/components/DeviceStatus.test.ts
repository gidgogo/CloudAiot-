import { describe, expect, it } from "vitest";
import { fingerPoints, poseForAction, stepStates } from "./DeviceStatus";

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
      { gesture: "THUMB_UP", action: "ON", enabled: true, updated_at_ms: 0 },
      { gesture: "THUMB_DOWN", action: "OFF", enabled: false, updated_at_ms: 0 },
    ] as const;
    expect(poseForAction("ON", [...mappings])).toBe("THUMB_UP");
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
