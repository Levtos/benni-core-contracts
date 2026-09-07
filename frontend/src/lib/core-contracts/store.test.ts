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
  it('opens the exact diagnostic binding without saving and rejects stale diagnostic context',async()=>{
    const store=new CoreContractsStore();
    store.registry.setHass({user:{id:'admin',is_admin:true}});
    const binding={binding_id:'target',source_id:'source',entity_id:'sensor.real',field:'value',capability:'value',profile_id:'benni',required:true,freshness_ttl_seconds:300,consumer_ids:[],fallback:{action:'none' as const,reason:'',default_value:null},read_only:true};
    store.registry.view={registry:{profile:'benni',revision:{id:'r',revision:7,profile:'benni',status:'active',created_at:'',payload:{profile:'benni',schema_version:1,bindings:[binding],fusions:[],contract_instances:[],consumer_overrides:{},registry_metadata:{}}},source:'postgres',health:'healthy',reason:null,used_last_known_good:false},revisions:[],requirements:[],history_error:null};
    vi.spyOn(store.registry,'refresh').mockResolvedValue();
    await store.repairBinding('benni','target',7);
    expect(store.registry.editor?.binding_id).toBe('target'); expect(store.registry.draft).toBeNull(); expect(store.activeView).toBe('registry');
    await store.repairBinding('benni','target',6); expect(store.registry.notice).toContain('anderen Revision');
    expect(store.registry.draft).toBeNull();
  });
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
