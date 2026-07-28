import { describe, expect, it, vi } from "vitest";
import { CoreContractsStore } from "./store.svelte";
import type { HassLike } from "./types";

const responseFor = (type: string): Record<string, unknown> => {
  const base = { payload_version: 1, command: type, revision: 1 };
  if (type.endsWith("/list_contracts")) return { ...base, contracts: [] };
  if (type.endsWith("/get_diagnostics")) return { ...base, diagnostics: [] };
  if (type.endsWith("/get_graph")) return { ...base, graph: null };
  return { ...base, health: [] };
};

describe("Core Contracts refresh stability", () => {
  it("keeps a connected shell stable during a background refresh", async () => {
    let callCount = 0;
    let releaseSecondRefresh!: () => void;
    const secondRefreshGate = new Promise<void>((resolve) => {
      releaseSecondRefresh = resolve;
    });
    const sendMessagePromise = vi.fn(async ({ type }: { type: string }) => {
      callCount += 1;
      if (callCount > 4) await secondRefreshGate;
      return responseFor(type);
    });
    const store = new CoreContractsStore();
    const hass = { connection: { sendMessagePromise } } as HassLike;

    store.setHass(hass);
    await vi.waitFor(() => expect(store.connectionState).toBe("connected"));

    const secondRefresh = store.refresh();
    expect(store.connectionState).toBe("connected");

    releaseSecondRefresh();
    await secondRefresh;
    store.stop();
    expect(store.connectionState).toBe("connected");
  });
});
