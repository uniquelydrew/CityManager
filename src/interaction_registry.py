"""Registry loader for verb-based resource interactions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


@dataclass(frozen=True)
class InteractionRegistry:
    interactions: List[Dict[str, Any]]

    @classmethod
    def load(cls, data_dir: str) -> "InteractionRegistry":
        path = Path(data_dir) / "interactions.json"
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        registry = cls(interactions=sorted(payload.get("interactions", []), key=lambda item: (item["priority_order"], item["interaction_id"])))
        registry.validate()
        return registry

    def validate(self) -> None:
        required = {"interaction_id", "verb", "inputs", "outputs", "constraints", "coefficients", "priority_order", "explanation_template"}
        for item in self.interactions:
            missing = required - item.keys()
            if missing:
                raise ValueError(f"Interaction {item.get('interaction_id', '<unknown>')} is missing keys: {sorted(missing)}")

    def all(self) -> List[Dict[str, Any]]:
        return list(self.interactions)

    def by_verb(self, verb: str) -> List[Dict[str, Any]]:
        return [item for item in self.interactions if item["verb"] == verb]
