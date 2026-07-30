"""Reproducible repository and contract-publication boundary validation."""

from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import tomllib


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "benni_core_contracts"
TEXT_SUFFIXES = {".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
ENTITY_PLATFORM_FILES = {
    "binary_sensor.py",
    "button.py",
    "climate.py",
    "cover.py",
    "lock.py",
    "number.py",
    "select.py",
    "sensor.py",
    "switch.py",
}
ALLOWED_ENTITY_PLATFORM_FILES = {"sensor.py"}
FORBIDDEN_SOURCE_TOKENS = {
    "async_add_entities",
    "hass.services",
    "homeassistant.services",
}
FORBIDDEN_IMPORT = re.compile(
    r"^\s*(?:from|import)\s+[^#\n]*(?:benni_core_devices|core_devices|policy)",
    re.MULTILINE,
)


def tracked_files() -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return tuple(
        ROOT / path.decode("utf-8")
        for path in result.stdout.split(b"\0")
        if path
    )


def validate_json(paths: tuple[Path, ...]) -> int:
    matches = tuple(path for path in paths if path.suffix == ".json")
    for path in matches:
        json.loads(path.read_text(encoding="utf-8"))
    return len(matches)


def validate_toml(paths: tuple[Path, ...]) -> int:
    matches = tuple(path for path in paths if path.suffix == ".toml")
    for path in matches:
        tomllib.loads(path.read_text(encoding="utf-8"))
    return len(matches)


def validate_whitespace(paths: tuple[Path, ...]) -> int:
    checked = 0
    failures: list[str] = []
    for path in paths:
        if path.suffix not in TEXT_SUFFIXES:
            continue
        data = path.read_bytes()
        checked += 1
        if data and not data.endswith((b"\n", b"\r")):
            failures.append(f"{path.relative_to(ROOT)}: missing final newline")
        for line_number, raw_line in enumerate(data.splitlines(), start=1):
            if raw_line.endswith((b" ", b"\t")):
                failures.append(
                    f"{path.relative_to(ROOT)}:{line_number}: trailing whitespace"
                )
    if failures:
        raise SystemExit("\n".join(failures))
    return checked


def validate_shadow_boundary() -> None:
    existing_platforms = sorted(
        path.name
        for path in INTEGRATION.iterdir()
        if path.is_file() and path.name in ENTITY_PLATFORM_FILES
    )
    unexpected_platforms = sorted(
        set(existing_platforms) - ALLOWED_ENTITY_PLATFORM_FILES
    )
    if unexpected_platforms:
        raise SystemExit(
            "unapproved public entity platforms: " + ", ".join(unexpected_platforms)
        )

    sensor_platform = INTEGRATION / "sensor.py"
    if sensor_platform.exists():
        source = sensor_platform.read_text(encoding="utf-8")
        required_tokens = (
            "PublishedRuntime",
            "PILOT_OPENING_ENTITY_ID",
            "async_add_entities",
        )
        for token in required_tokens:
            if token not in source:
                raise SystemExit(
                    f"sensor.py: explicit PublishedContract boundary token missing: {token!r}"
                )

    for path in sorted(INTEGRATION.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        forbidden_tokens = FORBIDDEN_SOURCE_TOKENS - (
            {"async_add_entities"} if path.name == "sensor.py" else set()
        )
        for token in forbidden_tokens:
            if token in source:
                raise SystemExit(f"{path.name}: forbidden boundary token {token!r}")
        if FORBIDDEN_IMPORT.search(source):
            raise SystemExit(f"{path.name}: policy/core-devices import is forbidden")


def main() -> None:
    paths = tracked_files()
    json_count = validate_json(paths)
    toml_count = validate_toml(paths)
    whitespace_count = validate_whitespace(paths)
    validate_shadow_boundary()
    print(
        "repository_validation_ok "
        f"json={json_count} toml={toml_count} "
        f"whitespace_files={whitespace_count} "
        "shadow_entities=0 published_pilot_allowlist=1 "
        "services=0 actuation=0 policy_imports=0"
    )


if __name__ == "__main__":
    main()
