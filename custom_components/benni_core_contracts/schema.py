"""Versioned internal contract schema definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping

from .quality import (
    FallbackAction,
    FallbackPolicy,
    FreshnessRequirement,
    SafetyClass,
    ValueState,
)


class ValueType(str, Enum):
    NUMBER = "number"
    BOOLEAN = "boolean"
    TEXT = "text"
    ENUM = "enum"
    OBJECT = "object"


@dataclass(frozen=True)
class ContractFieldSchema:
    name: str
    value_type: ValueType
    unit: str | None = None
    required: bool = False
    safety_class: SafetyClass = SafetyClass.INFORMATIONAL
    fallback: FallbackPolicy = FallbackPolicy()
    freshness_ttl_seconds: int = 300
    freshness_requirement: FreshnessRequirement = FreshnessRequirement.DEVICE_OR_HA_EVENT
    allowed_values: tuple[str, ...] = ()
    unknown_values: tuple[object, ...] = ("unknown",)
    unavailable_values: tuple[object, ...] = ("unavailable",)
    unknown_allowed: bool = True
    unavailable_allowed: bool = True
    safe_default_allowed: bool = False
    safe_default_note: str | None = None
    physical_state: bool = False
    consumer_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("field name is required")
        if self.freshness_ttl_seconds <= 0:
            raise ValueError("field freshness_ttl_seconds must be positive")
        if self.value_type == ValueType.ENUM and not self.allowed_values:
            raise ValueError("enum fields need allowed_values")
        if self.physical_state and not self.unknown_values:
            raise ValueError("physical state fields need an explicit unknown value")
        if self.physical_state and self.fallback.action != FallbackAction.REJECT:
            raise ValueError(
                f"physical state field {self.name} must use fallback=reject"
            )
        if self.fallback.action == FallbackAction.SAFE_DEFAULT:
            if self.physical_state:
                raise ValueError(
                    f"safe_default is forbidden for physical state field {self.name}"
                )
            if not self.safe_default_allowed:
                raise ValueError(
                    f"safe_default must be explicitly allowed for field {self.name}"
                )
            if not self.safe_default_note:
                raise ValueError(
                    f"safe_default requires a field-specific note for {self.name}"
                )
            if "lock" in self.name:
                raise ValueError("safe_default is forbidden for lock fields")
            if "position" in self.name:
                raise ValueError("safe_default is forbidden for position fields")

    def classify(self, value: Any) -> ValueState:
        """Classify factual value state before quality/freshness is considered."""

        if value is None:
            return ValueState.UNAVAILABLE
        if value in self.unavailable_values:
            return ValueState.UNAVAILABLE if self.unavailable_allowed else ValueState.INVALID
        if value in self.unknown_values:
            return ValueState.UNKNOWN if self.unknown_allowed else ValueState.INVALID
        return ValueState.VALID if self.validate(value) else ValueState.INVALID

    def validate(self, value: Any) -> bool:
        if value is None:
            return not self.required
        if self.value_type == ValueType.NUMBER:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if self.value_type == ValueType.BOOLEAN:
            return isinstance(value, bool)
        if self.value_type == ValueType.TEXT:
            return isinstance(value, str)
        if self.value_type == ValueType.ENUM:
            return isinstance(value, str) and value in self.allowed_values
        if self.value_type == ValueType.OBJECT:
            return isinstance(value, Mapping)
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value_type": self.value_type.value,
            "unit": self.unit,
            "required": self.required,
            "safety_class": self.safety_class.value,
            "fallback": self.fallback.as_dict(),
            "freshness_ttl_seconds": self.freshness_ttl_seconds,
            "freshness_requirement": self.freshness_requirement.value,
            "allowed_values": list(self.allowed_values),
            "unknown_values": list(self.unknown_values),
            "unavailable_values": list(self.unavailable_values),
            "unknown_allowed": self.unknown_allowed,
            "unavailable_allowed": self.unavailable_allowed,
            "safe_default_allowed": self.safe_default_allowed,
            "safe_default_note": self.safe_default_note,
            "physical_state": self.physical_state,
            "consumer_ids": list(self.consumer_ids),
        }


@dataclass(frozen=True)
class ContractSchema:
    schema_id: str
    version: int
    fields: tuple[ContractFieldSchema, ...]

    def __post_init__(self) -> None:
        if not self.schema_id or self.version <= 0:
            raise ValueError("schema_id and positive version are required")
        names = [field.name for field in self.fields]
        if len(set(names)) != len(names):
            raise ValueError("contract field names must be unique")

    @property
    def required_fields(self) -> tuple[str, ...]:
        return tuple(field.name for field in self.fields if field.required)

    def field(self, name: str) -> ContractFieldSchema:
        for field in self.fields:
            if field.name == name:
                return field
        raise KeyError(f"unknown field {name!r} in {self.schema_id}.v{self.version}")

    def validate_values(self, values: Mapping[str, Any]) -> tuple[str, ...]:
        errors: list[str] = []
        for field in self.fields:
            if field.name not in values and field.required:
                errors.append(f"missing required field: {field.name}")
            elif field.name in values:
                value = values[field.name]
                if value is None:
                    if field.required:
                        errors.append(f"invalid value for field: {field.name}")
                    continue
                state = field.classify(value)
                if state == ValueState.UNKNOWN and field.unknown_allowed:
                    continue
                if state == ValueState.UNAVAILABLE and field.unavailable_allowed:
                    continue
                if state != ValueState.VALID:
                    errors.append(f"invalid value for field: {field.name}")
        return tuple(errors)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_id": self.schema_id,
            "version": self.version,
            "fields": [field.as_dict() for field in self.fields],
        }


class SchemaRegistry:
    """Strict registry keyed by schema ID and explicit version."""

    def __init__(self, schemas: Iterable[ContractSchema] = ()) -> None:
        self._schemas: dict[tuple[str, int], ContractSchema] = {}
        for schema in schemas:
            self.register(schema)

    def register(self, schema: ContractSchema) -> None:
        key = (schema.schema_id, schema.version)
        if key in self._schemas:
            raise ValueError(f"duplicate contract schema: {schema.schema_id}.v{schema.version}")
        self._schemas[key] = schema

    def get(self, schema_id: str, version: int | None = None) -> ContractSchema:
        if version is not None:
            return self._schemas[(schema_id, version)]
        versions = [
            schema for (current_id, _), schema in self._schemas.items() if current_id == schema_id
        ]
        if not versions:
            raise KeyError(schema_id)
        return max(versions, key=lambda schema: schema.version)

    def all(self) -> tuple[ContractSchema, ...]:
        return tuple(sorted(self._schemas.values(), key=lambda schema: (schema.schema_id, schema.version)))
