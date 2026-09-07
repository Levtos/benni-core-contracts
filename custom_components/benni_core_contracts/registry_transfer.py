"""Versioned configuration transfer and read-only migration candidates.

No repository, HA mutation or runtime state belongs to this boundary.
"""
from collections.abc import Mapping
import json
import re

from .registry import RegistryPayload, RegistryValidationError

FORMAT = 'core-contracts-registry'
FORMAT_VERSION = 1
MAX_BYTES = 2_000_000
_SENSITIVE = ('password', 'passwd', 'secret', 'token', 'credential', 'dsn', 'database_url', 'connection_string', 'postgres')
_BINDING = {'binding_id','source_id','entity_id','field','capability','profile_id','required','freshness_ttl_seconds','consumer_ids','fallback','read_only','display_name','enabled'}
_FUSION = {'fusion_id','contract_id','field','input_binding_ids','input_fusion_ids','strategy','consumer_ids'}
_INSTANCE = {'contract_id','schema_id','schema_version','profile','display_name','metadata'}


def _object(value, allowed, path):
    if not isinstance(value, dict) or set(value) - allowed:
        raise RegistryValidationError(f'{path}: unknown fields or invalid object')


def _safe(value, depth=0):
    if depth > 32:
        raise RegistryValidationError('configuration nesting exceeds transfer limit')
    if isinstance(value, Mapping):
        for key, child in value.items():
            if any(part in str(key).casefold() for part in _SENSITIVE):
                raise RegistryValidationError('configuration contains a sensitive field')
            _safe(child, depth+1)
    elif isinstance(value, (list, tuple)):
        for child in value: _safe(child, depth+1)
    elif isinstance(value, str) and re.search(r'\w+://[^\s/@]+:[^\s/@]+@', value):
        raise RegistryValidationError('configuration contains a credential URL')


def decode_document(document, profile):
    """Strict structural validation before constructing existing RegistryPayload."""
    try:
        encoded = json.dumps(document, allow_nan=False)
    except (ValueError, TypeError, RecursionError) as err:
        raise RegistryValidationError('import is not finite JSON') from err
    if len(encoded.encode('utf-8')) > MAX_BYTES:
        raise RegistryValidationError('import exceeds 2 MB')
    _object(document, {'format','format_version','payload'}, 'document')
    if document.get('format') != FORMAT or type(document.get('format_version')) is not int or document['format_version'] != FORMAT_VERSION:
        raise RegistryValidationError('unsupported import format/version')
    data = document.get('payload')
    _object(data, {'profile','schema_version','bindings','fusions','contract_instances','consumer_overrides','registry_metadata'}, 'payload')
    if data.get('profile') != profile or type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise RegistryValidationError('unsupported registry schema or profile mismatch')
    _safe(data)
    for name, fields in (('bindings', _BINDING), ('fusions', _FUSION), ('contract_instances', _INSTANCE)):
        if not isinstance(data.get(name), list):
            raise RegistryValidationError(f'{name} must be an array')
        for item in data[name]:
            _object(item, fields, name)
            if name == 'bindings':
                if item.get('profile_id') != profile:
                    raise RegistryValidationError('binding profile mismatch')
                for key in ('required','enabled','read_only'):
                    if key in item and type(item[key]) is not bool:
                        raise RegistryValidationError(f'{key} must be boolean')
                if type(item.get('freshness_ttl_seconds')) is not int:
                    raise RegistryValidationError('TTL must be an integer')
                _object(item.get('fallback'), {'action','default_value','reason'}, 'fallback')
            if name == 'contract_instances' and item.get('profile',profile) != profile:
                raise RegistryValidationError('contract profile mismatch')
            for key in ('input_binding_ids','input_fusion_ids','consumer_ids'):
                if key in item and (not isinstance(item[key], list) or any(not isinstance(x,str) for x in item[key])):
                    raise RegistryValidationError(f'{key} must be an array of IDs')
    try:
        return RegistryPayload.from_dict(data)
    except (ValueError, KeyError, TypeError) as err:
        raise RegistryValidationError('invalid registry payload') from err


def export_document(payload: RegistryPayload):
    # Exact configuration, no revision status, actor, DB connection or runtime data.
    data = payload.as_dict()
    _safe(data)
    return {'format':FORMAT,'format_version':FORMAT_VERSION,'payload':data}


def migration_candidates(entries, entity_ids, profile):
    """Only explicit same-profile ConfigEntries; hints never become bindings."""
    found = {}
    def walk(value, domain, path='', depth=0):
        if depth > 16: return
        if isinstance(value, Mapping):
            for key, child in value.items():
                if not any(part in str(key).casefold() for part in _SENSITIVE):
                    walk(child, domain, f'{path}.{key}' if path else str(key), depth+1)
        elif isinstance(value, (list,tuple)):
            for child in value: walk(child,domain,path,depth+1)
        elif isinstance(value,str) and value in entity_ids:
            found.setdefault(value,set()).add((domain,path))
    for entry in entries:
        data=getattr(entry,'data',{})
        options=getattr(entry,'options',{})
        if options.get('profile',data.get('profile')) != profile: continue
        walk(data,entry.domain); walk(options,entry.domain)
    return [{'entity_id':entity, 'references':[{'integration':domain,'field':path} for domain,path in sorted(refs)],
             'shared_candidate':len({domain for domain,_ in refs})>1, 'requires_confirmation':True}
            for entity,refs in sorted(found.items())]
