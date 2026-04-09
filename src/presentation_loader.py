"""Presentation-profile loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from src.schema_models import PresentationProfile


def load_presentation_profiles(data_dir: str) -> Dict[str, Dict[str, Any]]:
    path = Path(data_dir) / "presentation" / "presentation_profiles.json"
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    profiles = {}
    for raw_profile in payload.get("profiles", []):
        profile = PresentationProfile.from_dict(raw_profile)
        profiles[profile.key] = profile.data
    return profiles


def load_presentation_profile(data_dir: str, profile_key: str) -> Dict[str, Any]:
    profiles = load_presentation_profiles(data_dir)
    return profiles[profile_key]
