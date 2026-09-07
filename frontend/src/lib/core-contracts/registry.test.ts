import { describe, expect, it } from 'vitest';
import { RegistryEditor, type Draft, type EditableBinding, type Profile, type RegistryPayload, type RegistryView } from './registry.svelte';

const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value));
function fixture(admin = true) {
  const calls: Record<string, unknown>[] = [];
  const empty = (profile: Profile): RegistryPayload => ({profile, schema_version: 1, bindings: [], fusions: [], contract_instances: [], consumer_overrides: {}, registry_metadata: {}});
  const makeView = (profile: Profile): RegistryView => ({registry: {profile, revision: {id: profile+'1', revision: 1, profile, status: 'active', created_at: '', payload: empty(profile)}, source: 'postgres', health: 'healthy', reason: null, used_last_known_good: false}, revisions: [], requirements: [], history_error: null});
  const views: Record<Profile, RegistryView> = {benni: makeView('benni'), eltern: makeView('eltern')};
  let draft: Draft;
  let failure: string | null = null;
  const editor = new RegistryEditor();
  editor.setHass({ user: {id: 'admin', is_admin: admin}, states: {'media_player.sonos': {entity_id:'media_player.sonos', attributes:{friendly_name:'Wohnzimmer'}}}, connection: {async sendMessagePromise<T>(msg: Record<string, unknown>): Promise<T> {
    calls.push(clone(msg));
    const cmd = (msg.type as string).split('/registry/')[1];
    if (failure && cmd !== 'view') throw {code:failure, message:failure};
    const profile = (msg.profile ?? draft?.profile ?? 'benni') as Profile;
    const view = views[profile];
    let result: unknown;
    if (cmd === 'view') result = view;
    else if (cmd === 'export') result = {result:{format:'core-contracts-registry',format_version:1,payload:view.registry.revision!.payload}};
    else if (cmd === 'import') { draft={draft_id:'imported',profile,base_revision:view.registry.revision!.revision,payload:clone((msg.document as {payload:RegistryPayload}).payload)}; result={result:{draft,validation:{valid:true,errors:[]}}}; }
    else if (cmd === 'migration_candidates') result={result:{candidates:[]}};
    else if (cmd === 'draft/create') { draft = {draft_id:'draft', profile, base_revision: view.registry.revision!.revision, payload: clone(view.registry.revision!.payload)}; result = {draft}; }
    else if (cmd === 'binding/create') { draft.payload.bindings.push(clone(msg.binding as EditableBinding)); result = {draft}; }
    else if (cmd === 'binding/update') { draft.payload.bindings = draft.payload.bindings.map(b => b.binding_id === msg.binding_id ? clone(msg.binding as EditableBinding) : b); result = {draft}; }
    else if (cmd === 'binding/delete') { draft.payload.bindings = draft.payload.bindings.filter(b => b.binding_id !== msg.binding_id); result = {draft}; }
    else if (cmd === 'binding/set_enabled') { draft.payload.bindings.find(b => b.binding_id === msg.binding_id)!.enabled = msg.enabled as boolean; result = {draft}; }
    else if (cmd === 'contract_instance/create') { draft.payload.contract_instances.push(clone(msg.instance as Record<string,unknown>)); result={draft}; }
    else if (cmd === 'fusion/create') { draft.payload.fusions.push(clone(msg.fusion as RegistryPayload['fusions'][number])); result={draft}; }
    else if (cmd === 'fusion/update') { draft.payload.fusions=draft.payload.fusions.map(f=>f.fusion_id===msg.fusion_id?clone(msg.fusion as RegistryPayload['fusions'][number]):f); result={draft}; }
    else if (cmd === 'fusion/delete') { draft.payload.fusions=draft.payload.fusions.filter(f=>f.fusion_id!==msg.fusion_id); result={draft}; }
    else if (cmd === 'draft/validate') result = {validation: {valid: true, errors: []}};
    else if (cmd === 'draft/save') { view.registry.revision!.payload = clone(draft.payload); view.registry.revision!.revision++; result = {revision:view.registry.revision}; }
    else if (cmd === 'draft/discard') result = {discarded:true};
    else if (cmd === 'rollback') result = {revision:view.registry.revision};
    else throw Error(cmd);
    return clone(result) as T;
  }}});
  return {editor, calls, views, fail: (code: string | null) => failure = code};
}
function enter(editor: RegistryEditor) {
  editor.select(null);
  Object.assign(editor.editor!, {display_name:'Aktivität', entity_id:'media_player.sonos', capability:'media_activity', field:'activity'});
}

describe('Registry UI lifecycle', () => {
  it.each(['benni', 'eltern'] as Profile[])('loads %s with explicit isolated selector', async profile => {
    const {editor,calls} = fixture(); await editor.switchProfile(profile); await editor.refresh();
    expect(editor.view?.registry.profile).toBe(profile); expect(calls.at(-1)?.profile).toBe(profile);
    expect(calls.every(c => c.type === 'benni_core_contracts/registry/view')).toBe(true);
  });
  it('creates, edits and deletes only a draft; source identity survives entity replacement', async () => {
    const {editor,views,calls} = fixture(); await editor.refresh(); enter(editor);
    const id = editor.editor!.binding_id; const source = editor.editor!.source_id;
    expect(calls).toHaveLength(1); await editor.apply();
    expect(editor.bindings).toHaveLength(1); expect(views.benni.registry.revision!.payload.bindings).toHaveLength(0);
    editor.editor!.entity_id='media_player.replacement'; await editor.apply();
    expect(editor.bindings[0]).toMatchObject({binding_id:id,source_id:source,entity_id:'media_player.replacement'});
    await editor.remove(editor.bindings[0]); expect(editor.bindings).toHaveLength(0);
    expect(calls.some(c => c.type === 'benni_core_contracts/registry/draft/save')).toBe(false);
  });
  it('deactivates and reactivates without deleting the binding', async () => {
    const {editor} = fixture(); await editor.refresh(); enter(editor); await editor.apply(); editor.editor=null; editor.original=null;
    await editor.toggle(editor.bindings[0]); expect(editor.bindings[0].enabled).toBe(false);
    await editor.toggle(editor.bindings[0]); expect(editor.bindings[0].enabled).toBe(true);
  });
  it('uses actual HA entity candidates without automatically choosing', () => {
    const {editor} = fixture(); enter(editor); expect(editor.entities[0].entity_id).toBe('media_player.sonos');
    editor.editor!.entity_id=''; expect(editor.editor!.entity_id).toBe('');
  });
  it('protects IDs and profile before sending writes', async () => {
    const {editor,calls} = fixture(); await editor.refresh(); enter(editor); await editor.apply();
    const count = calls.length; editor.editor!.binding_id='rename'; await editor.apply();
    expect(editor.error?.code).toBe('validation_error'); expect(calls).toHaveLength(count);
  });
  it('validates without save or activation, then explicitly saves with OCC', async () => {
    const {editor,calls,views} = fixture(); await editor.refresh(); enter(editor); await editor.validate();
    expect(editor.validation?.valid).toBe(true); expect(views.benni.registry.revision!.revision).toBe(1);
    await editor.save(); expect(editor.dirty).toBe(false); expect(editor.base).toBe(2);
    expect(calls.find(c => c.type === 'benni_core_contracts/registry/draft/save')?.expected_base_revision).toBe(1);
  });
  it.each(['validation_error','revision_conflict','backend_unavailable'])('retains draft and active on %s', async code => {
    const {editor,fail,views} = fixture(); await editor.refresh(); enter(editor); await editor.apply(); const id=editor.draft!.draft_id;
    fail(code); await editor.save(); expect(editor.error?.code).toBe(code); expect(editor.draft?.draft_id).toBe(id);
    expect(editor.dirty).toBe(true); expect(views.benni.registry.revision!.revision).toBe(1);
  });
  it('discard is explicit and refresh does not discard dirty data', async () => {
    const {editor,calls} = fixture(); await editor.refresh(); enter(editor); await editor.apply(); editor.editor!.display_name='Noch lokal';
    await editor.refresh(); expect(editor.editor!.display_name).toBe('Noch lokal'); expect(editor.dirty).toBe(true);
    await editor.discard(); expect(editor.dirty).toBe(false); expect(editor.bindings).toHaveLength(0);
    expect(calls.some(c => c.type === 'benni_core_contracts/registry/draft/discard')).toBe(true);
  });
  it('blocks dirty profile switch and preserves filter/editor on live refresh', async () => {
    const {editor} = fixture(); await editor.refresh(); enter(editor); editor.filter='activity';
    await editor.switchProfile('eltern'); expect(editor.profile).toBe('benni');
    await editor.refresh(); expect(editor.filter).toBe('activity'); expect(editor.editor!.display_name).toBe('Aktivität');
  });
  it('shows new active revision without silently rebasing own edits', async () => {
    const {editor,views} = fixture(); await editor.refresh(); enter(editor); await editor.apply();
    views.benni.registry.revision!.revision=43; await editor.refresh();
    expect(editor.view?.registry.revision?.revision).toBe(43); expect(editor.base).toBe(1);
  });
  it('freezes OCC base already when editing locally, before creating a backend draft', async () => {
    const {editor,views,calls} = fixture(); await editor.refresh(); enter(editor);
    views.benni.registry.revision!.revision=43; await editor.refresh(); await editor.apply();
    expect(calls.find(c=>c.type==='benni_core_contracts/registry/draft/create')?.expected_base_revision).toBe(1);
  });
  it('keeps invalid fallback text dirty across navigation and blocks save', async () => {
    const {editor,calls} = fixture(); await editor.refresh(); enter(editor); editor.setFallback('{');
    await editor.refresh(); await editor.save(); expect(editor.fallbackText).toBe('{');
    expect(editor.error?.code).toBe('validation_error'); expect(editor.dirty).toBe(true);
    expect(calls.every(c=> c.type==='benni_core_contracts/registry/view')).toBe(true);
  });
  it('reads history/LKG and performs explicit profile-scoped rollback', async () => {
    const {editor,views,calls} = fixture(); views.eltern.registry.used_last_known_good=true;
    views.eltern.registry.health='degraded'; views.eltern.revisions=[clone(views.eltern.registry.revision!)];
    await editor.switchProfile('eltern'); expect(editor.view?.registry.used_last_known_good).toBe(true); expect(editor.view?.revisions).toHaveLength(1);
    await editor.rollback('old'); expect(calls.find(c=> c.type==='benni_core_contracts/registry/rollback')).toMatchObject({profile:'eltern',revision_id:'old',expected_base_revision:1});
  });
  it('keeps non-admin read-only and forbids writes even through UI methods', async () => {
    const {editor,calls} = fixture(false); await editor.refresh(); editor.select(null); expect(editor.editor).toBeNull();
    await editor.validate(); expect(editor.error?.code).toBe('unauthorized'); expect(calls).toHaveLength(1);
  });
  it('derives consumer usage read-only from declared roles', async () => {
    const {editor,views} = fixture(); views.benni.requirements=[{consumer_id:'core_state',contract_id:null,role:'activity',status:'healthy'}];
    await editor.refresh(); enter(editor); expect(editor.consumers(editor.editor!)).toEqual(['core_state']);
  });
  it('creates a fusion and typed instance in the same draft, edits strategy and deletes without autosave', async()=>{
    const {editor,views,calls}=fixture(); views.eltern.schemas=[{schema_id:'presence',version:1,fields:[{name:'present',value_type:'boolean'}]}];
    await editor.switchProfile('eltern'); editor.selectFusion(null); editor.fusionSchema='presence:1';
    Object.assign(editor.fusionEditor!,{contract_id:'household',field:'present',strategy:'any_true',input_binding_ids:['mutter','vater']});
    expect(editor.dirty).toBe(true); await editor.applyFusion(); expect(editor.error).toBeNull();
    expect(editor.fusions[0].strategy).toBe('any_true'); expect(editor.instances[0].profile).toBe('eltern');
    editor.fusionEditor!.strategy='all_true'; await editor.applyFusion(); expect(editor.fusions[0].strategy).toBe('all_true');
    await editor.removeFusion(editor.fusions[0]); expect(editor.fusions).toHaveLength(0);
    expect(calls.some(c=>c.type==='benni_core_contracts/registry/draft/save')).toBe(false);
  });
  it('does not lose dirty fusion inputs on profile switch or refresh', async()=>{
    const {editor}=fixture(); await editor.refresh(); editor.selectFusion(null); editor.fusionEditor!.contract_id='household';
    await editor.switchProfile('eltern'); await editor.refresh(); expect(editor.profile).toBe('benni'); expect(editor.fusionEditor!.contract_id).toBe('household');
  });
  it('exports active config and imports into a validated unsaved draft',async()=>{
    const {editor,calls}=fixture(); await editor.refresh(); await editor.exportRegistry();
    editor.importText=editor.exportText; await editor.importRegistry();
    expect(editor.draft?.draft_id).toBe('imported'); expect(editor.validation?.valid).toBe(true); expect(editor.dirty).toBe(true);
    expect(calls.some(c=>c.type==='benni_core_contracts/registry/draft/save')).toBe(false);
  });
  it('rejects malformed JSON and dirty import without losing input',async()=>{
    const {editor,calls}=fixture(); await editor.refresh(); editor.importText='{'; await editor.importRegistry();
    expect(editor.error?.code).toBe('validation_error'); expect(editor.importText).toBe('{');
    await editor.switchProfile('eltern'); expect(editor.profile).toBe('benni');
    enter(editor); await editor.importRegistry(); expect(editor.error?.code).toBe('dirty_draft'); expect(calls).toHaveLength(1);
  });
  it('bulk selection creates only candidates and requires explicit role/capability',()=>{
    const {editor,calls}=fixture(); editor.selectedEntities=['media_player.sonos']; editor.createCandidates();
    expect(editor.draft).toBeNull(); editor.openCandidate('media_player.sonos');
    expect(editor.editor?.entity_id).toBe('media_player.sonos'); expect(editor.editor?.field).toBe(''); expect(editor.editor?.capability).toBe(''); expect(calls).toHaveLength(0);
  });
});
