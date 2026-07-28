"""Constants for the new core-contracts integration."""

DOMAIN = "benni_core_contracts"
NAME = "Benni Core Contracts"

CONFIG_SCHEMA_VERSION = 1
STORAGE_SCHEMA_VERSION = 2
GATE_PACK_VERSION = 1
WEBSOCKET_PAYLOAD_VERSION = 1
RELEASE_VERSION = "0.1.0"
RELEASE_CHANNEL = "shadow_only"

# The only selectable/activatable mode in this release candidate.  A missing
# mode is intentionally invalid; it must never silently become shadow-only.
MODE_SHADOW_ONLY = "shadow_only"
SUPPORTED_MODES = (MODE_SHADOW_ONLY,)

PROFILE_BENNI = "benni"
PROFILE_ELTERN = "eltern"
DEFAULT_PROFILE = PROFILE_BENNI
SUPPORTED_PROFILES = (PROFILE_BENNI, PROFILE_ELTERN)
SUPPORTED_CONFIG_PROFILES = (PROFILE_BENNI,)

STORAGE_KEY_PREFIX = f"{DOMAIN}.shadow_only"
WS_REGISTERED = "_websocket_registered"

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
