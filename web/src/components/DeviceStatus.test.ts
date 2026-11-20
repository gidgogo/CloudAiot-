import { describe, expect, it } from "vitest";
import { stepStates } from "./DeviceStatus";

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
