import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, readCookie, UNAUTHORIZED_EVENT } from "./client";

function respond(status: number, body: unknown) {
  return vi.fn().mockImplementation(
    async () =>
      new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.cookie = "aiot_csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

describe("readCookie", () => {
  it("finds a cookie among others", () => {
    expect(readCookie("b", "a=1; b=two%20words; c=3")).toBe("two words");
    expect(readCookie("x", "a=1")).toBeUndefined();
  });
});

describe("api client", () => {
  it("sends credentials and the CSRF header only on changes", async () => {
    document.cookie = "aiot_csrf_token=csrf-123";
    const fetchMock = respond(200, { success: true, data: [] });
    vi.stubGlobal("fetch", fetchMock);

    await api.rooms.list();
    await api.rooms.create({ name: "안방" });

    const [getUrl, getInit] = fetchMock.mock.calls[0];
    expect(getUrl).toBe("/api/v1/rooms");
    expect(getInit.credentials).toBe("include");
    expect(getInit.headers["X-CSRF-Token"]).toBeUndefined();

    const [, postInit] = fetchMock.mock.calls[1];
    expect(postInit.method).toBe("POST");
    expect(postInit.headers["X-CSRF-Token"]).toBe("csrf-123");
    expect(JSON.parse(postInit.body)).toEqual({ name: "안방" });
  });

  it("returns items with page meta", async () => {
    vi.stubGlobal("fetch", respond(200, { success: true, data: [{ request_id: "r1" }], meta: { total: 3, limit: 1, offset: 0 } }));
    const page = await api.helpRequests.list({ status: "CREATED", limit: 1 });
    expect(page.items).toHaveLength(1);
    expect(page.meta.total).toBe(3);
  });

  it("raises ApiError with the server code and announces 401", async () => {
    vi.stubGlobal("fetch", respond(401, { success: false, error: { code: "UNAUTHORIZED", message: "인증이 필요합니다." } }));
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);
    await expect(api.devices.list()).rejects.toMatchObject({ status: 401, code: "UNAUTHORIZED", message: "인증이 필요합니다." });
    expect(listener).toHaveBeenCalledOnce();
    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });

  it("does not log out on other 401s (wrong login or current password)", async () => {
    vi.stubGlobal("fetch", respond(401, { success: false, error: { code: "INVALID_CREDENTIALS", message: "x" } }));
    const listener = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, listener);
    await expect(api.auth.login("a@b.c", "pw")).rejects.toBeInstanceOf(ApiError);
    await expect(api.auth.changePassword("wrong", "new-password")).rejects.toMatchObject({ code: "INVALID_CREDENTIALS" });
    expect(listener).not.toHaveBeenCalled();
    window.removeEventListener(UNAUTHORIZED_EVENT, listener);
  });

  it("maps network failures to NETWORK_ERROR", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.rooms.list()).rejects.toMatchObject({ status: 0, code: "NETWORK_ERROR" });
  });

  it("handles 204 responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(api.devices.remove("fan-01")).resolves.toBeUndefined();
  });
});
