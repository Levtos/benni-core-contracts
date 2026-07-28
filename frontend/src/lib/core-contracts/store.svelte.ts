import { CoreContractsClient, reconcileById, reconcileContracts } from "./client";
import { previewData } from "./fixtures";
import type { ConnectionState, DataState } from "../ui/state";
import type {
  Contract,
  DiagnosticProjection,
  GraphSnapshot,
  HassLike,
  HealthItem,
} from "./types";

export type AppView = "overview" | "diagnostics" | "graph" | "health";
export type { ConnectionState, DataState } from "../ui/state";

export class CoreContractsStore {
  activeView = $state<AppView>("overview");
  search = $state("");
  selectedContractId = $state<string | null>(null);
  contracts = $state<Contract[]>([]);
  diagnostics = $state<DiagnosticProjection[]>([]);
  graph = $state<GraphSnapshot | null>(null);
  health = $state<HealthItem[]>([]);
  private selectedDetails = $state<Record<string, Contract>>({});
  connectionState = $state<ConnectionState>("loading");
  dataState = $state<DataState>("loading");
  errorMessage = $state<string | null>(null);
  revision = $state(0);
  lastUpdated = $state<string | null>(null);
  previewMode = $state(false);

  private hass: HassLike | null = null;
  private client: CoreContractsClient | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private refreshing = false;

  get filteredContracts(): Contract[] {
    const query = this.search.trim().toLowerCase();
    if (!query) return this.contracts;
    return this.contracts.filter((contract) =>
      `${contract.contract_id} ${contract.schema_id} ${contract.health}`.toLowerCase().includes(query),
    );
  }

  get selectedContract(): Contract | null {
    if (!this.selectedContractId) return null;
    return this.selectedDetails[this.selectedContractId]
      ?? this.contracts.find((contract) => contract.contract_id === this.selectedContractId)
      ?? null;
  }

  get selectedDiagnostics(): DiagnosticProjection | null {
    return this.diagnostics.find((item) => item.contract_id === this.selectedContractId) ?? null;
  }

  setHass(hass: HassLike | null): void {
    if (hass === this.hass) return;
    this.hass = hass;
    this.client = hass ? new CoreContractsClient(hass) : null;
    if (hass?.connection) {
      this.previewMode = false;
      void this.refresh();
      this.startPolling();
    } else if (!this.previewMode) {
      this.stopPolling();
      this.connectionState = "unavailable";
      this.dataState = "empty";
    }
  }

  start(): void {
    if (!this.hass?.connection) {
      this.connectionState = "unavailable";
      this.dataState = "empty";
      return;
    }
    void this.refresh();
    this.startPolling();
  }

  stop(): void {
    this.stopPolling();
  }

  private startPolling(): void {
    if (this.timer) return;
    this.timer = setInterval(() => void this.refresh(), 5000);
  }

  private stopPolling(): void {
    if (!this.timer) return;
    clearInterval(this.timer);
    this.timer = null;
  }

  async refresh(): Promise<void> {
    if (!this.client || this.refreshing || this.previewMode) return;
    this.refreshing = true;
    this.connectionState = this.contracts.length ? "reconnecting" : "loading";
    this.errorMessage = null;
    try {
      const revision = this.revision || undefined;
      const [contractsPayload, diagnosticsPayload, graphPayload, healthPayload] = await Promise.all([
        this.client.listContracts(revision),
        this.client.getDiagnostics(revision),
        this.client.getGraph(revision),
        this.client.getHealth(revision),
      ]);
      this.contracts = reconcileContracts(this.contracts, contractsPayload.contracts ?? []);
      this.selectedDetails = Object.fromEntries(
        Object.entries(this.selectedDetails).filter(([contractId]) =>
          this.contracts.some((contract) => contract.contract_id === contractId),
        ),
      );
      this.diagnostics = reconcileById(this.diagnostics, diagnosticsPayload.diagnostics ?? [], "projection_id");
      this.health = reconcileById(this.health, healthPayload.health ?? [], "contract_id");
      this.graph = graphPayload.graph ?? null;
      this.revision = Math.max(
        contractsPayload.revision ?? 0,
        diagnosticsPayload.revision ?? 0,
        graphPayload.revision ?? 0,
        healthPayload.revision ?? 0,
      );
      this.lastUpdated = new Date().toISOString();
      this.connectionState = "connected";
      this.dataState = this.deriveDataState(this.contracts);
      if (!this.selectedContractId && this.contracts[0]) {
        this.selectedContractId = this.contracts[0].contract_id;
      }
      if (this.selectedContractId && !this.contracts.some((item) => item.contract_id === this.selectedContractId)) {
        this.selectedContractId = this.contracts[0]?.contract_id ?? null;
      }
    } catch (error) {
      this.connectionState = this.contracts.length ? "offline" : "error";
      this.dataState = this.contracts.length ? "stale" : "empty";
      this.errorMessage = error instanceof Error ? error.message : "Unbekannter read-only Verbindungsfehler.";
    } finally {
      this.refreshing = false;
    }
  }

  private deriveDataState(contracts: Contract[]): DataState {
    if (!contracts.length) return "empty";
    if (contracts.some((item) => item.health === "blocked")) return "blocked";
    if (contracts.some((item) => item.health === "degraded" || item.health === "unknown")) return "degraded";
    return "ready";
  }

  usePreview(): void {
    const data = previewData();
    this.previewMode = true;
    this.stopPolling();
    this.contracts = data.contracts;
    this.diagnostics = data.diagnostics;
    this.graph = data.graph;
    this.health = data.health;
    this.revision = data.graph.revision;
    this.selectedContractId = data.contracts[0]?.contract_id ?? null;
    this.connectionState = "connected";
    this.dataState = this.deriveDataState(data.contracts);
    this.lastUpdated = new Date().toISOString();
  }

  selectContract(contractId: string): void {
    this.selectedContractId = contractId;
    this.activeView = "overview";
    if (this.client && !this.previewMode) {
      void this.client
        .getContract(contractId)
        .then((payload) => {
          if (payload.contract?.contract_id === contractId) {
            this.selectedDetails = { ...this.selectedDetails, [contractId]: payload.contract };
          }
        })
        .catch(() => undefined);
    }
  }

  setView(view: AppView): void {
    this.activeView = view;
  }

  setSearch(value: string): void {
    this.search = value;
  }
}
