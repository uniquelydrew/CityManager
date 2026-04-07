"""Registry loader for resource type metadata and legacy aliases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from src.resource_utils import canonical_resource_id, runtime_resource_key


LEGACY_ALIASES = {
    "energy": "electricity",
    "workforce_capacity": "labor_hours",
}


@dataclass(frozen=True)
class ResourceRegistry:
    definitions: Dict[str, Dict[str, Any]]
    aliases: Dict[str, str]

    @classmethod
    def load(cls, data_dir: str) -> "ResourceRegistry":
        path = Path(data_dir) / "resource_types.json"
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        resources = payload.get("resource_types", [])
        definitions: Dict[str, Dict[str, Any]] = {}
        for item in resources:
            resource_type_id = canonical_resource_id(item["resource_type_id"])
            definitions[resource_type_id] = item
        registry = cls(definitions=definitions, aliases=dict(LEGACY_ALIASES))
        registry.validate()
        return registry

    def validate(self) -> None:
        required = {"resource_type_id", "display_name", "unit_id", "defaults", "storage", "supported_verbs"}
        for resource_id, definition in self.definitions.items():
            missing = required - definition.keys()
            if missing:
                raise ValueError(f"Resource definition {resource_id} is missing keys: {sorted(missing)}")

    def resolve(self, resource_id: str) -> str:
        return self.aliases.get(resource_id, canonical_resource_id(resource_id))

    def runtime_key(self, resource_id: str) -> str:
        return runtime_resource_key(self.resolve(resource_id))

    def get(self, resource_id: str) -> Dict[str, Any]:
        resolved = self.resolve(resource_id)
        return self.definitions[resolved]

    def all(self) -> List[Dict[str, Any]]:
        return list(self.definitions.values())
