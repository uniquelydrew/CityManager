"""Historical case loading and validation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


REQUIRED_CASE_KEYS = {
    "historical_case_id",
    "case_metadata",
    "world_state",
    "actors",
    "institutions",
    "groups",
    "resources",
    "policy_options",
    "events_and_reports",
    "teaching_signals",
    "historical_notes",
}


def load_cases(data_dir: str) -> Dict[str, Dict[str, Any]]:
    cases_dir = Path(data_dir) / "cases"
    loaded: Dict[str, Dict[str, Any]] = {}
    if not cases_dir.exists():
        return loaded
    for case_path in cases_dir.glob("*/case.json"):
        with case_path.open("r", encoding="utf-8") as handle:
            case = json.load(handle)
        validate_case(case)
        loaded[case["historical_case_id"]] = case
    return loaded


def validate_case(case: Dict[str, Any]) -> None:
    missing = REQUIRED_CASE_KEYS - case.keys()
    if missing:
        raise ValueError(
            f"Historical case {case.get('historical_case_id', '<unknown>')} missing keys: {sorted(missing)}"
        )
    metadata = case["case_metadata"]
    for key in ("title", "place", "timeframe", "summary"):
        if key not in metadata:
            raise ValueError(f"Historical case {case['historical_case_id']} missing metadata key: {key}")
