import type { HassLike, SourceBinding, Fusion } from './types';

export type Profile = 'benni' | 'eltern';
export interface EditableBinding extends SourceBinding { display_name?: string; enabled?: boolean }
export interface RegistryPayload {
  profile: Profile; schema_version: number; bindings: EditableBinding[];
  fusions: Fusion[]; contract_instances: Record<string, unknown>[];
  consumer_overrides: Record<string, unknown>; registry_metadata: Record<string, unknown>;
}
export interface Revision { id: string; revision: number; profile: Profile; status: string; created_at: string; payload: RegistryPayload }
export interface Draft { draft_id: string; profile: Profile; base_revision: number; payload: RegistryPayload }
export interface Validation { valid: boolean; errors: { code: string; message: string; path?: string }[] }
export interface RequirementUsage { consumer_id: string; contract_id: string | null; role: string | null; status: string }
export interface MigrationHint {entity_id:string; shared_candidate:boolean; references:{integration:string;field:string}[]}
export interface RegistryView {
  schemas?: {schema_id: string; version: number; fields: {name: string; value_type: string}[]}[];
  registry: { profile: Profile; revision: Revision | null; source: string; health: string; reason: string | null; used_last_known_good: boolean };
  revisions: Revision[]; history_error: string | null; requirements: RequirementUsage[];
}
export class RegistryError extends Error {
  constructor(public code: string, message: string) { super(message); }
}
const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value));

/** UI session only. Canonical persistence, validation and OCC remain in DomainService. */
export class RegistryEditor {
  onActivated: (()=>void) | null = null;
  profile = $state<Profile>('benni');
  view = $state<RegistryView | null>(null);
  draft = $state<Draft | null>(null);
  editor = $state<EditableBinding | null>(null);
  original = $state<EditableBinding | null>(null);
  fusionEditor = $state<Fusion | null>(null);
  originalFusion = $state<Fusion | null>(null);
  fusionSchema = $state('');
  importText = $state('');
  exportText = $state('');
  migrationHints = $state<MigrationHint[]>([]);
  selectedEntities = $state<string[]>([]);
  candidateQueue = $state<string[]>([]);
  filter = $state('');
  changed = $state(false);
  busy = $state(false);
  error = $state<RegistryError | null>(null);
  validation = $state<Validation | null>(null);
  notice = $state('');
  fallbackText = $state('null');
  fallbackError = $state('');
  private editBase = $state<number | null>(null);
  hass = $state.raw<HassLike | null>(null);
  private generation = 0;
  get admin() { return this.hass?.user?.is_admin === true; }
  get fusionDirty() { return this.fusionEditor !== null && JSON.stringify(this.fusionEditor) !== JSON.stringify(this.originalFusion); }
  get dirty() { return this.changed || this.fusionDirty || !!this.fallbackError || (this.editor !== null && JSON.stringify(this.editor) !== JSON.stringify(this.original)); }
  get fusions() { return this.draft?.payload.fusions ?? this.view?.registry.revision?.payload.fusions ?? []; }
  get instances() { return this.draft?.payload.contract_instances ?? this.view?.registry.revision?.payload.contract_instances ?? []; }
  get bindings() { return this.draft?.payload.bindings ?? this.view?.registry.revision?.payload.bindings ?? []; }
  get filteredBindings() { const q = this.filter.toLowerCase(); return this.bindings.filter(b => `${b.binding_id} ${b.display_name ?? ''} ${b.entity_id} ${b.field}`.toLowerCase().includes(q)); }
  get base() { return this.draft?.base_revision ?? this.editBase ?? this.view?.registry.revision?.revision ?? 0; }
  get entities() { return Object.values(this.hass?.states ?? {}); }
  setHass(hass: HassLike | null) {
    if (this.hass?.user?.id && this.hass.user.id !== hass?.user?.id) {
      this.generation++; this.view = null; this.clear();
    }
    this.hass = hass;
  }
  async request<T>(command: string, args: Record<string, unknown> = {}): Promise<T> {
    if (!this.hass?.connection) throw new RegistryError('backend_unavailable', 'Keine Home-Assistant-Verbindung.');
    if (command !== 'view' && !this.admin) throw new RegistryError('unauthorized', 'Nur Administratoren dürfen Registry-Entwürfe bearbeiten.');
    try {
      const response = await this.hass.connection.sendMessagePromise<T & { success?: boolean; result?: T; error?: { code: string; message: string } }>({type: `benni_core_contracts/registry/${command}`, ...args});
      if (response.success === false) throw response.error;
      return response.success === true ? response.result as T : response;
    } catch (cause) {
      const e = cause as { code?: string; message?: string };
      throw new RegistryError(e?.code ?? 'backend_unavailable', e?.message ?? 'Registry-Abfrage fehlgeschlagen.');
    }
  }
  private async run(action: () => Promise<void>) {
    if (this.busy) return;
    this.busy = true; this.error = null;
    try { await action(); } catch (e) { this.error = e instanceof RegistryError ? e : new RegistryError('validation_error', e instanceof Error ? e.message : 'Ungültige Eingabe.'); }
    finally { this.busy = false; }
  }
  private async read() {
    const generation = this.generation; const profile = this.profile;
    const next = await this.request<RegistryView>('view', {profile});
    if (generation !== this.generation || profile !== this.profile) return;
    if (next.registry.profile !== profile) throw new RegistryError('profile_mismatch', 'Antwort gehört zu einem anderen Profil.');
    this.view = next;
  }
  async refresh() { await this.run(async () => {
    await this.read();
    this.notice = this.dirty ? 'Aktiver Stand aktualisiert. Eigene Änderungen und Basisrevision bleiben erhalten.' : 'Aktiver Stand aktualisiert.';
  }); }
  async switchProfile(profile: Profile) {
    if (profile === this.profile) return;
    if (this.dirty || this.importText || this.busy) { this.notice = 'Zuerst Änderungen speichern oder ausdrücklich verwerfen. Profil bleibt unverändert.'; return; }
    await this.run(async () => {
      if (this.draft) await this.request('draft/discard', {draft_id: this.draft.draft_id});
      this.generation++; this.profile = profile; this.clear(); this.view = null; this.importText=''; this.exportText=''; this.migrationHints=[]; this.selectedEntities=[]; this.candidateQueue=[];
      await this.read();
    });
  }
  select(binding: EditableBinding | null) {
    if (!this.admin || this.busy) return;
    if (this.fallbackError || (this.editor && JSON.stringify(this.editor) !== JSON.stringify(this.original))) { this.notice = 'Offene Eingabe zuerst in den Entwurf übernehmen oder verwerfen.'; return; }
    this.editBase ??= this.base;
    this.original = binding ? {...copy(binding), enabled: binding.enabled !== false} : null;
    this.editor = this.original ? copy(this.original) : {
      binding_id: `binding.${crypto.randomUUID()}`, source_id: `source.${crypto.randomUUID()}`,
      entity_id: '', field: '', capability: '', profile_id: this.profile, required: true,
      freshness_ttl_seconds: 300, consumer_ids: [], fallback: {action: 'none', default_value: null, reason: ''}, read_only: true,
      display_name: '', enabled: true,
    };
    this.fallbackText = JSON.stringify(this.editor.fallback.default_value ?? null); this.fallbackError = '';
    this.notice = '';
  }
  async ensureDraft() {
    if (!this.draft) {
      const result = await this.request<{draft: Draft}>('draft/create', {profile: this.profile, expected_base_revision: this.base});
      if (result.draft.profile !== this.profile) throw new RegistryError('profile_mismatch', 'Entwurf gehört zu einem anderen Profil.');
      this.draft = result.draft;
    }
    return this.draft;
  }
  private async applyEditor() {
    if (this.fallbackError) throw new RegistryError('validation_error', this.fallbackError);
    if (!this.editor || JSON.stringify(this.editor) === JSON.stringify(this.original)) return;
    const binding = copy(this.editor);
    if (binding.profile_id !== this.profile || (this.original && (binding.binding_id !== this.original.binding_id || binding.source_id !== this.original.source_id))) throw new RegistryError('validation_error', 'Technische Identität und Profil sind geschützt.');
    if (!binding.entity_id || !binding.field || !binding.capability || !binding.display_name?.trim()) throw new RegistryError('validation_error', 'Anzeigename, Entity, Rolle/Feld und Capability sind erforderlich.');
    const draft = await this.ensureDraft();
    const response = await this.request<{draft: Draft}>(this.original ? 'binding/update' : 'binding/create', {draft_id: draft.draft_id, ...(this.original ? {binding_id: binding.binding_id} : {}), binding});
    this.draft = response.draft; this.changed = true; this.original = copy(binding); this.validation = null;
  }
  async apply() { await this.run(() => this.applyEditor()); }
  setFallback(value: string) {
    this.fallbackText = value;
    try { const parsed: unknown = JSON.parse(value); if (this.editor) this.editor.fallback.default_value = parsed; this.fallbackError = ''; }
    catch { this.fallbackError = 'Fallback-Wert muss gültiges JSON sein (z. B. false, 0 oder "unknown").'; }
  }
  async remove(binding: EditableBinding) { await this.run(async () => {
    const draft = await this.ensureDraft();
    this.draft = (await this.request<{draft: Draft}>('binding/delete', {draft_id: draft.draft_id, binding_id: binding.binding_id})).draft;
    this.changed = true; this.validation = null;
    if (this.editor?.binding_id === binding.binding_id) { this.editor = null; this.original = null; }
  }); }
  async toggle(binding: EditableBinding) { await this.run(async () => {
    if (this.editor?.binding_id === binding.binding_id && this.dirty) throw new RegistryError('dirty_editor', 'Offene Eingabe zuerst übernehmen.');
    const draft = await this.ensureDraft();
    this.draft = (await this.request<{draft: Draft}>('binding/set_enabled', {draft_id: draft.draft_id, binding_id: binding.binding_id, enabled: binding.enabled === false})).draft;
    this.changed = true; this.validation = null;
  }); }
  async validate() { await this.run(async () => {
    await this.applyEditor(); await this.applyFusionEditor(); const draft = await this.ensureDraft();
    this.validation = (await this.request<{validation: Validation}>('draft/validate', {draft_id: draft.draft_id})).validation;
  }); }
  async save() { await this.run(async () => {
    await this.applyEditor(); await this.applyFusionEditor(); const draft = await this.ensureDraft();
    await this.request('draft/save', {draft_id: draft.draft_id, expected_base_revision: draft.base_revision});
    this.clear(); this.notice = 'Revision gespeichert und aktiviert.'; await this.read(); this.onActivated?.();
  }); }
  private clear() { this.draft = null; this.editor = null; this.original = null; this.fusionEditor = null; this.originalFusion = null; this.changed = false; this.validation = null; this.editBase = null; this.fallbackText = 'null'; this.fallbackError = ''; }
  selectFusion(fusion: Fusion | null) {
    if (!this.admin || this.busy) return;
    if (this.fusionDirty) { this.notice='Offene Fusion zuerst in den Entwurf übernehmen oder verwerfen.'; return; }
    this.editBase ??= this.base;
    this.originalFusion=fusion ? copy(fusion) : null;
    this.fusionEditor=fusion ? copy(fusion) : {fusion_id:`fusion.${crypto.randomUUID()}`, contract_id:'', field:'', strategy:'first_healthy', input_binding_ids:[], input_fusion_ids:[], consumer_ids:[]};
    const instance=this.instances.find(i=>i.contract_id===fusion?.contract_id);
    this.fusionSchema=instance ? `${instance.schema_id}:${instance.schema_version ?? 1}` : '';
  }
  private async applyFusionEditor() {
    if (!this.fusionEditor || !this.fusionDirty) return;
    const fusion=copy(this.fusionEditor);
    if (this.originalFusion && fusion.fusion_id!==this.originalFusion.fusion_id) throw new RegistryError('validation_error','Fusion-ID ist geschützt.');
    const draft=await this.ensureDraft();
    if (!this.instances.some(i=>i.contract_id===fusion.contract_id)) {
      const schema=this.view?.schemas?.find(s=>`${s.schema_id}:${s.version}`===this.fusionSchema);
      if (!schema) throw new RegistryError('validation_error','Für eine neue Contract-Instanz ein vorhandenes Schema auswählen.');
      this.draft=(await this.request<{draft:Draft}>('contract_instance/create',{draft_id:draft.draft_id,instance:{contract_id:fusion.contract_id,schema_id:schema.schema_id,schema_version:schema.version,profile:this.profile}})).draft;
      this.changed=true;
    }
    this.draft=(await this.request<{draft:Draft}>(this.originalFusion?'fusion/update':'fusion/create',{draft_id:draft.draft_id, ...(this.originalFusion?{fusion_id:fusion.fusion_id}:{}), fusion})).draft;
    this.originalFusion=copy(fusion); this.changed=true; this.validation=null;
  }
  async applyFusion() { await this.run(()=>this.applyFusionEditor()); }
  async removeFusion(fusion: Fusion) { await this.run(async()=>{
    const draft=await this.ensureDraft();
    this.draft=(await this.request<{draft:Draft}>('fusion/delete',{draft_id:draft.draft_id,fusion_id:fusion.fusion_id})).draft;
    this.changed=true; this.validation=null;
    if (this.fusionEditor?.fusion_id===fusion.fusion_id) { this.fusionEditor=null; this.originalFusion=null; }
  }); }
  async exportRegistry() { await this.run(async()=>{
    const response=await this.request<{result:unknown}>('export',{profile:this.profile});
    this.exportText=JSON.stringify(response.result,null,2);
    this.notice='Aktive Registry exportiert. Ungespeicherte Änderungen sind nicht enthalten.';
  }); }
  async importRegistry() { await this.run(async()=>{
    if (this.dirty) throw new RegistryError('dirty_draft','Vor Import vorhandene Änderungen speichern oder verwerfen.');
    if (new TextEncoder().encode(this.importText).length>2_000_000) throw new RegistryError('validation_error','Import ist größer als 2 MB.');
    const document:unknown=JSON.parse(this.importText);
    if (this.draft) { await this.request('draft/discard',{draft_id:this.draft.draft_id}); this.draft=null; }
    const response=await this.request<{result:{draft:Draft;validation:Validation}}>('import',{profile:this.profile,expected_base_revision:this.base,document});
    this.clear(); this.draft=response.result.draft; this.validation=response.result.validation; this.changed=true;
    this.importText='';
    this.notice='Import geprüft und als Entwurf geladen. Erst Speichern aktiviert ihn.';
  }); }
  async migrationCandidates() { await this.run(async()=>{
    const response=await this.request<{result:{candidates:MigrationHint[]}}>('migration_candidates',{profile:this.profile});
    this.migrationHints=response.result.candidates;
  }); }
  createCandidates() {
    this.candidateQueue=[...new Set(this.selectedEntities)].filter(id=>this.entities.some(e=>e.entity_id===id));
    this.notice='Nur Kandidaten erzeugt. Für jede Entity Rolle und Capability ausdrücklich bestätigen.';
  }
  openCandidate(entityId:string) {
    if (!this.candidateQueue.includes(entityId) && !this.migrationHints.some(h=>h.entity_id===entityId)) return;
    this.select(null);
    if (this.editor && this.original===null && this.editor.entity_id==='') this.editor.entity_id=entityId;
  }
  async discard() { await this.run(async () => {
    if (this.draft) await this.request('draft/discard', {draft_id: this.draft.draft_id});
    this.clear(); this.importText=''; this.notice = 'Entwurf verworfen. Aktive Registry unverändert.'; await this.read();
  }); }
  async rollback(revisionId: string) { await this.run(async () => {
    if (this.dirty) throw new RegistryError('dirty_draft', 'Vor Rollback Änderungen speichern oder verwerfen.');
    await this.request('rollback', {profile: this.profile, revision_id: revisionId, expected_base_revision: this.base});
    this.clear(); this.notice = 'Rollback aktiviert.'; await this.read(); this.onActivated?.();
  }); }
  consumers(binding: EditableBinding) {
    const payload = this.draft?.payload ?? this.view?.registry.revision?.payload;
    const affected = new Set<string>(); const contracts = new Set<string>();
    let changed = true;
    while (changed) { changed = false;
      for (const fusion of payload?.fusions ?? []) {
        if (!affected.has(fusion.fusion_id) && (fusion.input_binding_ids.includes(binding.binding_id) || fusion.input_fusion_ids.some(id => affected.has(id)))) {
          affected.add(fusion.fusion_id); contracts.add(fusion.contract_id); changed = true;
        }
      }
    }
    return [...new Set((this.view?.requirements ?? []).filter(r => r.role === binding.field || r.role === binding.binding_id || (r.contract_id && contracts.has(r.contract_id))).map(r => r.consumer_id))];
  }
}
