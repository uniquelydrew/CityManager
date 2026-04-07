"""Unit metadata loading and formatting helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_units(data_dir: str) -> Dict[str, Dict[str, Any]]:
    path = Path(data_dir) / "units.json"
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    units = {item["unit_id"]: item for item in payload.get("units", [])}
    for unit_id, item in units.items():
        for key in ("display_name", "abbrev", "precision", "display_scale"):
            if key not in item:
                raise ValueError(f"Unit {unit_id} missing key {key}")
    return units


def format_unit_value(value: float, unit_id: str, units: Dict[str, Dict[str, Any]]) -> str:
    unit = units.get(unit_id, {})
    precision = int(unit.get("precision", 1))
    scale = float(unit.get("display_scale", 1.0)) or 1.0
    abbrev = unit.get("abbrev", "")
    scaled = value / scale
    if abbrev:
        return f"{scaled:.{precision}f} {abbrev}"
    return f"{scaled:.{precision}f}"
