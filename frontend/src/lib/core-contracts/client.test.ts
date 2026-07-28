import { describe, expect, it, vi } from "vitest";
import {
  CoreContractsClient,
  CORE_CONTRACTS_COMMANDS,
  reconcileById,
} from "./client";
import type { HassLike } from "./types";

describe("Core Contracts WebSocket client", () => {
  it("keeps the five transport commands read-only and version-independent", () => {
    expect(Object.values(CORE_CONTRACTS_COMMANDS)).toEqual([
      "benni_core_contracts/list_contracts",
      "benni_core_contracts/get_contract",
      "benni_core_contracts/get_diagnostics",
      "benni_core_contracts/get_graph",
      "benni_core_contracts/get_health",
    ]);
    expect(Object.values(CORE_CONTRACTS_COMMANDS).some((command) => /actuat|set_|write|service/i.test(command))).toBe(false);
  });

  it("sends HA-native read-only messages and unwraps a HA result envelope", async () => {
    const sendMessagePromise = vi.fn(async (_message: Record<string, unknown>) => ({
      success: true,
      result: {
        payload_version: 1,
        command: CORE_CONTRACTS_COMMANDS.list,
        revision: 7,
        delta: { supported: true, mode: "revision_reconciliation", since_revision: 6, unchanged: false },
        contracts: [],
      },
    }));
    const client = new CoreContractsClient({ connection: { sendMessagePromise } } as HassLike);

    const payload = await client.listContracts(6);

    expect(sendMessagePromise).toHaveBeenCalledWith({
      type: CORE_CONTRACTS_COMMANDS.list,
      since_revision: 6,
    });
    expect(payload.revision).toBe(7);
    expect(payload.contracts).toEqual([]);
  });

  it("surfaces application-level HA errors", async () => {
    const sendMessagePromise = vi.fn(async (_message: Record<string, unknown>) => ({
      success: false,
      error: { message: "no active core-contracts runtime" },
    }));
    const client = new CoreContractsClient({ connection: { sendMessagePromise } } as HassLike);

    await expect(client.getHealth()).rejects.toThrow("no active core-contracts runtime");
  });
});

describe("revision reconciliation", () => {
  it("reuses unchanged objects and replaces changed records by stable id", () => {
    const oldA = { id: "a", value: 1 };
    const oldB = { id: "b", value: 2 };
    const nextB = { id: "b", value: 3 };

    const result = reconcileById([oldA, oldB], [{ id: "a", value: 1 }, nextB], "id");

    expect(result[0]).toBe(oldA);
    expect(result[1]).toEqual(nextB);
    expect(result[1]).not.toBe(oldB);
  });
});
