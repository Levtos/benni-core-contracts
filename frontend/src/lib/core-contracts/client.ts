import type {
  Contract,
  ContractPayload,
  DiagnosticsPayload,
  GraphPayload,
  HassLike,
  HealthPayload,
  ListContractsPayload,
} from "./types";

export const CORE_CONTRACTS_COMMANDS = Object.freeze({
  list: "benni_core_contracts/list_contracts",
  contract: "benni_core_contracts/get_contract",
  diagnostics: "benni_core_contracts/get_diagnostics",
  graph: "benni_core_contracts/get_graph",
  health: "benni_core_contracts/get_health",
} as const);

export class CoreContractsClient {
  constructor(private readonly hass: HassLike) {}

  private async request<T>(
    type: string,
    message: Record<string, unknown> = {},
  ): Promise<T> {
    const connection = this.hass.connection;
    if (!connection) {
      throw new Error("Home-Assistant-Verbindung ist noch nicht verfügbar.");
    }
    const response = await connection.sendMessagePromise<T>({ type, ...message });
    const candidate = response as T & { success?: boolean; result?: T; error?: { message?: string } };
    if (candidate && candidate.success === false) {
      throw new Error(candidate.error?.message || "Read-only Contract-Abfrage fehlgeschlagen.");
    }
    if (candidate && candidate.success === true && "result" in candidate) {
      return candidate.result as T;
    }
    return response;
  }

  listContracts(sinceRevision?: number): Promise<ListContractsPayload> {
    return this.request<ListContractsPayload>(CORE_CONTRACTS_COMMANDS.list, {
      ...(sinceRevision === undefined ? {} : { since_revision: sinceRevision }),
    });
  }

  getContract(contractId: string, sinceRevision?: number): Promise<ContractPayload> {
    return this.request<ContractPayload>(CORE_CONTRACTS_COMMANDS.contract, {
      contract_id: contractId,
      ...(sinceRevision === undefined ? {} : { since_revision: sinceRevision }),
    });
  }

  getDiagnostics(sinceRevision?: number): Promise<DiagnosticsPayload> {
    return this.request<DiagnosticsPayload>(CORE_CONTRACTS_COMMANDS.diagnostics, {
      ...(sinceRevision === undefined ? {} : { since_revision: sinceRevision }),
    });
  }

  getGraph(sinceRevision?: number): Promise<GraphPayload> {
    return this.request<GraphPayload>(CORE_CONTRACTS_COMMANDS.graph, {
      ...(sinceRevision === undefined ? {} : { since_revision: sinceRevision }),
    });
  }

  getHealth(sinceRevision?: number): Promise<HealthPayload> {
    return this.request<HealthPayload>(CORE_CONTRACTS_COMMANDS.health, {
      ...(sinceRevision === undefined ? {} : { since_revision: sinceRevision }),
    });
  }
}

export function reconcileById<T extends object, K extends keyof T>(
  previous: T[],
  next: T[],
  id: K,
): T[] {
  const previousById = new Map<PropertyKey, T>(
    previous.map((item) => [item[id] as PropertyKey, item]),
  );
  return next.map((item) => {
    const old = previousById.get(item[id] as PropertyKey);
    return old && JSON.stringify(old) === JSON.stringify(item) ? old : item;
  });
}

export function reconcileContracts(previous: Contract[], next: Contract[]): Contract[] {
  return reconcileById(previous, next, "contract_id");
}
