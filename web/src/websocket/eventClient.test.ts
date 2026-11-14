import { describe, expect, it, vi } from "vitest";
import { EventClient, type SocketStatus } from "./eventClient";

class FakeSocket {
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  close = vi.fn();
  open() {
    this.readyState = 1;
    this.onopen?.();
  }
  receive(data: unknown) {
    this.onmessage?.({ data: typeof data === "string" ? data : JSON.stringify(data) } as MessageEvent);
  }
  drop(code: number) {
    this.readyState = 3;
    this.onclose?.({ code } as CloseEvent);
  }
}

function setup() {
  const sockets: FakeSocket[] = [];
  const timers: { callback: () => void; ms: number }[] = [];
  const statuses: SocketStatus[] = [];
  const events: unknown[] = [];
  const onUnauthorized = vi.fn();
  const client = new EventClient({
    url: "ws://test/ws/v1/events",
    createSocket: () => {
      const socket = new FakeSocket();
      sockets.push(socket);
      return socket as unknown as WebSocket;
    },
    setTimer: (callback, ms) => timers.push({ callback, ms }),
    clearTimer: () => undefined,
    onEvent: (event) => events.push(event),
    onStatus: (status) => statuses.push(status),
    onUnauthorized,
  });
  return { client, sockets, timers, statuses, events, onUnauthorized };
}

describe("EventClient", () => {
  it("delivers valid events and ignores malformed messages", () => {
    const { client, sockets, events, statuses } = setup();
    client.start();
    sockets[0].open();
    sockets[0].receive({ event_type: "help.created", data: {} });
    sockets[0].receive("not json");
    sockets[0].receive({ nope: true });
    expect(events).toHaveLength(1);
    expect(statuses).toEqual(["connecting", "open"]);
  });

  it("reconnects with backoff 1s, 2s, 4s … and resets after a successful open", () => {
    const { client, sockets, timers } = setup();
    client.start();
    sockets[0].drop(1006);
    timers.shift()!.callback();
    sockets[1].drop(1006);
    timers.shift()!.callback();
    sockets[2].drop(1006);
    expect(timers[0].ms).toBe(4000);
    timers.shift()!.callback();
    sockets[3].open();
    sockets[3].drop(1006);
    expect(timers[0].ms).toBe(1000);
  });

  it("stops reconnecting on 4401 and reports unauthorized", () => {
    const { client, sockets, timers, statuses, onUnauthorized } = setup();
    client.start();
    sockets[0].open();
    sockets[0].drop(4401);
    expect(timers).toHaveLength(0);
    expect(statuses.at(-1)).toBe("unauthorized");
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("does not reconnect after stop()", () => {
    const { client, sockets, timers } = setup();
    client.start();
    sockets[0].open();
    client.stop();
    sockets[0].drop(1000);
    expect(sockets[0].close).toHaveBeenCalledWith(1000);
    expect(timers).toHaveLength(0);
  });
});
