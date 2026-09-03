"""Constants for the new core-contracts integration."""

DOMAIN = "benni_core_contracts"
NAME = "Benni Core Contracts"

CONFIG_SCHEMA_VERSION = 1
STORAGE_SCHEMA_VERSION = 2
REGISTRY_SCHEMA_VERSION = 1
REGISTRY_CACHE_SCHEMA_VERSION = 1
GATE_PACK_VERSION = 1
WEBSOCKET_PAYLOAD_VERSION = 1
RELEASE_VERSION = "0.1.4"
RELEASE_CHANNEL = "shadow_only"

# A missing mode is intentionally invalid; it must never silently become
# shadow-only. ``published`` is a separately gated, explicit pilot mode.
MODE_SHADOW_ONLY = "shadow_only"
MODE_PUBLISHED = "published"
SUPPORTED_MODES = (MODE_SHADOW_ONLY, MODE_PUBLISHED)

PROFILE_BENNI = "benni"
PROFILE_ELTERN = "eltern"
DEFAULT_PROFILE = PROFILE_BENNI
SUPPORTED_PROFILES = (PROFILE_BENNI, PROFILE_ELTERN)
SUPPORTED_CONFIG_PROFILES = (PROFILE_BENNI,)

STORAGE_KEY_PREFIX = f"{DOMAIN}.shadow_only"
WS_REGISTERED = "_websocket_registered"
REGISTRY_SERVICE_KEY = "_registry_service"
REGISTRY_RUNTIME_KEY = "_registry_runtime"
CONSUMER_API_KEY = "_consumer_api"
WS_WRITE_REGISTERED = "_registry_write_websocket_registered"

WS_LIST_CONTRACTS = f"{DOMAIN}/list_contracts"
WS_GET_CONTRACT = f"{DOMAIN}/get_contract"
WS_GET_DIAGNOSTICS = f"{DOMAIN}/get_diagnostics"
WS_GET_GRAPH = f"{DOMAIN}/get_graph"
WS_GET_HEALTH = f"{DOMAIN}/get_health"
WS_COMMANDS = (
    WS_LIST_CONTRACTS,
    WS_GET_CONTRACT,
    WS_GET_DIAGNOSTICS,
    WS_GET_GRAPH,
    WS_GET_HEALTH,
)

# Registry writes are a separate, explicit command family.  The existing
# read-only command IDs above remain unchanged for existing clients.
WS_REGISTRY_GET_ACTIVE = f"{DOMAIN}/registry/get_active"
WS_REGISTRY_LIST_REVISIONS = f"{DOMAIN}/registry/list_revisions"
WS_REGISTRY_DRAFT_CREATE = f"{DOMAIN}/registry/draft/create"
WS_REGISTRY_DRAFT_GET = f"{DOMAIN}/registry/draft/get"
WS_REGISTRY_DRAFT_VALIDATE = f"{DOMAIN}/registry/draft/validate"
WS_REGISTRY_DRAFT_SAVE = f"{DOMAIN}/registry/draft/save"
WS_REGISTRY_DRAFT_DISCARD = f"{DOMAIN}/registry/draft/discard"
WS_REGISTRY_ROLLBACK = f"{DOMAIN}/registry/rollback"
WS_REGISTRY_BINDING_CREATE = f"{DOMAIN}/registry/binding/create"
WS_REGISTRY_BINDING_UPDATE = f"{DOMAIN}/registry/binding/update"
WS_REGISTRY_BINDING_DELETE = f"{DOMAIN}/registry/binding/delete"
WS_REGISTRY_BINDING_SET_ENABLED = f"{DOMAIN}/registry/binding/set_enabled"
WS_REGISTRY_CONTRACT_INSTANCE_CREATE = f"{DOMAIN}/registry/contract_instance/create"
WS_REGISTRY_CONTRACT_INSTANCE_UPDATE = f"{DOMAIN}/registry/contract_instance/update"
WS_REGISTRY_CONTRACT_INSTANCE_DELETE = f"{DOMAIN}/registry/contract_instance/delete"
WS_REGISTRY_WRITE_COMMANDS = (
    WS_REGISTRY_GET_ACTIVE,
    WS_REGISTRY_LIST_REVISIONS,
    WS_REGISTRY_DRAFT_CREATE,
    WS_REGISTRY_DRAFT_GET,
    WS_REGISTRY_DRAFT_VALIDATE,
    WS_REGISTRY_DRAFT_SAVE,
    WS_REGISTRY_DRAFT_DISCARD,
    WS_REGISTRY_ROLLBACK,
    WS_REGISTRY_BINDING_CREATE,
    WS_REGISTRY_BINDING_UPDATE,
    WS_REGISTRY_BINDING_DELETE,
    WS_REGISTRY_BINDING_SET_ENABLED,
    WS_REGISTRY_CONTRACT_INSTANCE_CREATE,
    WS_REGISTRY_CONTRACT_INSTANCE_UPDATE,
    WS_REGISTRY_CONTRACT_INSTANCE_DELETE,
)

# Descriptive aliases keep integrations from depending on one verb spelling.
WS_REGISTRY_CREATE_DRAFT = WS_REGISTRY_DRAFT_CREATE
WS_REGISTRY_GET_DRAFT = WS_REGISTRY_DRAFT_GET
WS_REGISTRY_VALIDATE_DRAFT = WS_REGISTRY_DRAFT_VALIDATE
WS_REGISTRY_SAVE_DRAFT = WS_REGISTRY_DRAFT_SAVE
WS_REGISTRY_DISCARD_DRAFT = WS_REGISTRY_DRAFT_DISCARD
WS_REGISTRY_BINDING_TOGGLE = WS_REGISTRY_BINDING_SET_ENABLED

DATA_VIEW_STATIC = "_view_static_registered"
DATA_VIEW_PANEL = "_view_panel_registered"
PANEL_URL_PATH = "benni_core_contracts"
PANEL_TITLE = "Core Contracts"
PANEL_ICON = "mdi:vector-polyline"
FRONTEND_DIR_URL = "/benni_core_contracts_app"
FRONTEND_ENTRY = f"{FRONTEND_DIR_URL}/index.js"
PANEL_ELEMENT = "benni-core-contracts-panel"

CONF_PROFILE = "profile"
CONF_MODE = "mode"
CONF_ENTITY_ALLOWLIST = "entity_allowlist"
CONF_BINDINGS = "bindings"
CONF_PUBLISHED_CONTRACTS = "published_contracts"

# The first public projection is deliberately a single, named pilot.  These
# IDs are contract/configuration IDs, not raw-source IDs.  Raw source IDs must
# still be supplied explicitly as SourceBindings in the ConfigEntry.
PILOT_OPENING_CONTRACT_ID = "benni.opening.kitchen_patio_door"
PILOT_OPENING_ENTITY_ID = "sensor.benni_opening_kitchen_patio_door"
PILOT_OPENING_BINDING_OPEN = "benni.opening.kitchen_patio_door.open_contact"
PILOT_OPENING_BINDING_TILT = "benni.opening.kitchen_patio_door.tilt_contact"
PILOT_OPENING_BINDING_IDS = (
    PILOT_OPENING_BINDING_OPEN,
    PILOT_OPENING_BINDING_TILT,
)
PILOT_OPENING_OPEN_SOURCE_ENTITY_ID = (
    "binary_sensor.kitchen_patio_door_open_contact"
)
PILOT_OPENING_TILT_SOURCE_ENTITY_ID = (
    "binary_sensor.kitchen_patio_door_tilt_contact"
)
PILOT_OPENING_SOURCE_ENTITY_IDS = (
    PILOT_OPENING_OPEN_SOURCE_ENTITY_ID,
    PILOT_OPENING_TILT_SOURCE_ENTITY_ID,
)
