"""Helpers for structured resource records and flow ledgers."""

from __future__ import annotations

from typing import Any, Dict


RESOURCE_FIELDS = [
    "stock",
    "capacity",
    "base_production",
    "allocated",
    "consumed",
    "lost",
    "imported",
    "produced",
    "constraint",
]


def resource_record(stock: float, capacity: float, base_production: float) -> Dict[str, Any]:
    return {
        "stock": float(stock),
        "capacity": float(capacity),
        "base_production": float(base_production),
        "allocated": {},
        "consumed": 0.0,
        "lost": 0.0,
        "imported": 0.0,
        "produced": 0.0,
        "constraint": "",
    }


def ensure_resource_records(resources: Dict[str, Any], defaults: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for name, default in defaults.items():
        value = resources.get(name, default["stock"])
        if isinstance(value, dict):
            record = dict(default)
            record.update(value)
        else:
            record = dict(default)
            record["stock"] = float(value)
        for field in RESOURCE_FIELDS:
            if field == "allocated":
                record.setdefault(field, {})
            elif field == "constraint":
                record.setdefault(field, "")
            else:
                record.setdefault(field, 0.0)
        normalized[name] = record
    return normalized


def stock(resources: Dict[str, Any], name: str) -> float:
    value = resources[name]
    if isinstance(value, dict):
        return float(value.get("stock", 0.0))
    return float(value)


def set_stock(resources: Dict[str, Any], name: str, value: float) -> None:
    resources[name]["stock"] = float(value)


def add_stock(resources: Dict[str, Any], name: str, delta: float) -> None:
    resources[name]["stock"] = float(resources[name].get("stock", 0.0) + delta)


def reset_turn_metrics(resources: Dict[str, Any]) -> None:
    for record in resources.values():
        record["allocated"] = {}
        record["consumed"] = 0.0
        record["lost"] = 0.0
        record["imported"] = 0.0
        record["produced"] = 0.0
        record["constraint"] = ""


def allocate(resources: Dict[str, Any], name: str, target: str, amount: float) -> float:
    usable = max(0.0, min(stock(resources, name), amount))
    resources[name]["allocated"][target] = resources[name]["allocated"].get(target, 0.0) + usable
    resources[name]["consumed"] = resources[name].get("consumed", 0.0) + usable
    add_stock(resources, name, -usable)
    return usable


def record_import(resources: Dict[str, Any], name: str, amount: float) -> None:
    if amount <= 0:
        return
    resources[name]["imported"] += amount
    add_stock(resources, name, amount)


def record_production(resources: Dict[str, Any], name: str, amount: float) -> None:
    if amount <= 0:
        return
    resources[name]["produced"] += amount
    add_stock(resources, name, amount)


def record_loss(resources: Dict[str, Any], name: str, amount: float) -> float:
    actual = max(0.0, min(stock(resources, name), amount))
    if actual <= 0:
        return 0.0
    resources[name]["lost"] += actual
    add_stock(resources, name, -actual)
    return actual


def end_of_turn_ledger(resources: Dict[str, Any]) -> Dict[str, Any]:
    ledger: Dict[str, Any] = {}
    for name, record in resources.items():
        ledger[name] = {
            "start": record.get("start", record.get("stock", 0.0)),
            "produced": record.get("produced", 0.0),
            "imported": record.get("imported", 0.0),
            "allocated": dict(record.get("allocated", {})),
            "consumed": record.get("consumed", 0.0),
            "lost": record.get("lost", 0.0),
            "end": record.get("stock", 0.0),
            "constraint": record.get("constraint", ""),
        }
    return ledger

