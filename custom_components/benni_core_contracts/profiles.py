"""Profile metadata for shared binding rules.

Profiles select configuration scope only. They do not fork graph, quality,
freshness, fusion, or contract logic; Benni and Eltern use the same runtime
semantics and the same schema registry.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import ProfileId, ProfileScope, SourceBinding


@dataclass(frozen=True)
class ProfileDefinition:
    profile_id: ProfileId
    schema_ids: tuple[str, ...]
    activation_scope: ProfileScope
    productive_target: bool
    config_activation_allowed: bool = False
    shadow_runtime_allowed: bool = False

    def validate_bindings(self, bindings: tuple[SourceBinding, ...]) -> None:
        mismatched = [
            binding.binding_id
            for binding in bindings
            if binding.profile_id != self.profile_id
        ]
        if mismatched:
            raise ValueError(
                f"bindings do not belong to profile {self.profile_id.value}: "
                + ", ".join(mismatched)
            )


PROFILE_DEFINITIONS = {
    ProfileId.BENNI: ProfileDefinition(
        profile_id=ProfileId.BENNI,
        schema_ids=(
            "room_climate",
            "opening",
            "weather_environment",
            "technical_device",
        ),
        activation_scope=ProfileScope.BENNI_PRODUCTION,
        productive_target=True,
        shadow_runtime_allowed=True,
    ),
    ProfileId.ELTERN: ProfileDefinition(
        profile_id=ProfileId.ELTERN,
        schema_ids=(
            "room_climate",
            "opening",
            "weather_environment",
            "technical_device",
        ),
        activation_scope=ProfileScope.PARENT_FUTURE,
        productive_target=False,
    ),
}


def profile_definition(profile: ProfileId) -> ProfileDefinition:
    """Return metadata for a supported profile without selecting logic."""

    return PROFILE_DEFINITIONS[profile]
