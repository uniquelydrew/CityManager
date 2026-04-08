"""Helpers for typed resource records, compatibility accessors, and flow ledgers."""

from __future__ import annotations

from typing import Any, Dict, Iterable


FLOW_KEYS = (
    "produced",
    "imported",
    "allocated",
    "consumed",
    "lost",
    "transformed_in",
    "transformed_out",
)

LEGACY_NAME_MAP = {
    "energy": "electricity",
    "workforce_capacity": "labor_hours",
}

RUNTIME_ALIAS_MAP = {
    "electricity": "energy",
    "labor_hours": "workforce_capacity",
}


def canonical_resource_id(resource_id: str) -> str:
    return LEGACY_NAME_MAP.get(resource_id, resource_id)


def runtime_resource_key(resource_id: str) -> str:
    return RUNTIME_ALIAS_MAP.get(resource_id, resource_id)


def resource_record(
    quantity: float,
    capacity: float,
    base_production: float,
    resource_type_id: str | None = None,
    unit_id: str | None = None,
    category: str | None = None,
    tags: Iterable[str] | None = None,
) -> Dict[str, Any]:
    """Create a typed resource record while preserving legacy compatibility fields."""
    flow = {
        "produced": 0.0,
        "imported": 0.0,
        "allocated": {},
        "consumed": 0.0,
        "lost": 0.0,
        "transformed_in": 0.0,
        "transformed_out": 0.0,
    }
    record = {
        "resource_type_id": canonical_resource_id(resource_type_id or ""),
        "unit_id": unit_id or "",
        "category": category or "",
        "baseline_quantity": float(quantity),
        "quantity": float(quantity),
        "stock": float(quantity),
        "capacity": float(capacity),
        "base_production": float(base_production),
        "flow": flow,
        "allocated": flow["allocated"],
        "consumed": 0.0,
        "lost": 0.0,
        "imported": 0.0,
        "produced": 0.0,
        "constraint": "",
        "constraints": [],
        "tags": list(tags or []),
    }
    return record


def normalize_resource_record(
    value: Any,
    *,
    resource_type_id: str,
    unit_id: str,
    capacity: float,
    base_production: float,
    category: str = "",
    tags: Iterable[str] | None = None,
) -> Dict[str, Any]:
    """Normalize legacy scalar or dict resource values into a typed resource record."""
    canonical_id = canonical_resource_id(resource_type_id)
    if not isinstance(value, dict):
        return resource_record(
            float(value),
            capacity,
            base_production,
            canonical_id,
            unit_id,
            category,
            tags,
        )

    quantity = float(value.get("stock", value.get("quantity", value.get("base_quantity", 0.0))))
    record = resource_record(
        quantity,
        float(value.get("capacity", capacity)),
        float(value.get("base_production", base_production)),
        value.get("resource_type_id", canonical_id),
        value.get("unit_id", unit_id),
        value.get("category", category),
        value.get("tags", tags or []),
    )
    record["baseline_quantity"] = float(value.get("baseline_quantity", quantity))
    flow_source = value.get("flow", {})
    for key in FLOW_KEYS:
        if key == "allocated":
            record["flow"]["allocated"] = dict(flow_source.get("allocated", value.get("allocated", {})))
            record["allocated"] = record["flow"]["allocated"]
        else:
            amount = float(flow_source.get(key, value.get(key, 0.0)))
            record["flow"][key] = amount
            if key in {"produced", "imported", "consumed", "lost"}:
                record[key] = amount
    record["constraint"] = value.get("constraint", "")
    record["constraints"] = list(value.get("constraints", []))
    if record["constraint"] and record["constraint"] not in record["constraints"]:
        record["constraints"].append(record["constraint"])
    record["start"] = float(value.get("start", quantity))
    return record


def ensure_resource_records(
    resources: Dict[str, Any],
    defaults: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for name, default in defaults.items():
        source = resources.get(name, default)
        normalized[name] = normalize_resource_record(
            source,
            resource_type_id=default.get("resource_type_id", name),
            unit_id=default.get("unit_id", ""),
            capacity=float(default.get("capacity", 0.0)),
            base_production=float(default.get("base_production", 0.0)),
            category=default.get("category", ""),
            tags=default.get("tags", []),
        )
    return normalized


def get_quantity(resources: Dict[str, Any], name: str) -> float:
    value = resources[name]
    if not isinstance(value, dict):
        return float(value)
    if "stock" in value:
        stock_value = float(value.get("stock", 0.0))
        if float(value.get("quantity", stock_value)) != stock_value:
            value["quantity"] = stock_value
        return stock_value
    return float(value.get("quantity", 0.0))


def set_quantity(resources: Dict[str, Any], name: str, value: float) -> None:
    resources[name]["quantity"] = float(value)
    resources[name]["stock"] = float(value)


def add_quantity(resources: Dict[str, Any], name: str, delta: float) -> None:
    set_quantity(resources, name, get_quantity(resources, name) + delta)


def record_flow(resources: Dict[str, Any], name: str, flow_key: str, amount: float, *, target: str | None = None) -> float:
    record = resources[name]
    record.setdefault("flow", {})
    if flow_key == "allocated":
        target_name = target or "general"
        allocated = record["flow"].setdefault("allocated", {})
        allocated[target_name] = allocated.get(target_name, 0.0) + amount
        record["allocated"] = allocated
        return amount
    current = float(record["flow"].get(flow_key, 0.0))
    record["flow"][flow_key] = current + amount
    if flow_key in {"produced", "imported", "consumed", "lost"}:
        record[flow_key] = record["flow"][flow_key]
    return amount


def stock(resources: Dict[str, Any], name: str) -> float:
    return get_quantity(resources, name)


def set_stock(resources: Dict[str, Any], name: str, value: float) -> None:
    set_quantity(resources, name, value)


def add_stock(resources: Dict[str, Any], name: str, delta: float) -> None:
    add_quantity(resources, name, delta)


def reset_turn_metrics(resources: Dict[str, Any]) -> None:
    for record in resources.values():
        record["start"] = get_quantity({"x": record}, "x")
        record["flow"] = {
            "produced": 0.0,
            "imported": 0.0,
            "allocated": {},
            "consumed": 0.0,
            "lost": 0.0,
            "transformed_in": 0.0,
            "transformed_out": 0.0,
        }
        record["allocated"] = record["flow"]["allocated"]
        record["consumed"] = 0.0
        record["lost"] = 0.0
        record["imported"] = 0.0
        record["produced"] = 0.0
        record["constraint"] = ""
        record["constraints"] = []


def allocate(resources: Dict[str, Any], name: str, target: str, amount: float) -> float:
    usable = max(0.0, min(stock(resources, name), amount))
    if usable <= 0:
        return 0.0
    record_flow(resources, name, "allocated", usable, target=target)
    record_flow(resources, name, "consumed", usable)
    add_stock(resources, name, -usable)
    return usable


def record_import(resources: Dict[str, Any], name: str, amount: float) -> None:
    if amount <= 0:
        return
    record_flow(resources, name, "imported", amount)
    add_stock(resources, name, amount)


def record_production(resources: Dict[str, Any], name: str, amount: float) -> None:
    if amount <= 0:
        return
    record_flow(resources, name, "produced", amount)
    add_stock(resources, name, amount)


def record_loss(resources: Dict[str, Any], name: str, amount: float) -> float:
    actual = max(0.0, min(stock(resources, name), amount))
    if actual <= 0:
        return 0.0
    record_flow(resources, name, "lost", actual)
    add_stock(resources, name, -actual)
    return actual


def add_constraint(resources: Dict[str, Any], name: str, text: str) -> None:
    record = resources[name]
    record["constraint"] = text
    constraints = record.setdefault("constraints", [])
    if text not in constraints:
        constraints.append(text)


def build_turn_ledger(resources: Dict[str, Any]) -> Dict[str, Any]:
    ledger: Dict[str, Any] = {}
    for name, record in resources.items():
        flow = record.get("flow", {})
        ledger[name] = {
            "resource_type_id": record.get("resource_type_id", canonical_resource_id(name)),
            "unit_id": record.get("unit_id", ""),
            "start_quantity": float(record.get("start", record.get("quantity", record.get("stock", 0.0)))),
            "start": float(record.get("start", record.get("quantity", record.get("stock", 0.0)))),
            "projected_flow": {
                "produced": float(flow.get("produced", record.get("produced", 0.0))),
                "imported": float(flow.get("imported", record.get("imported", 0.0))),
                "allocated": dict(flow.get("allocated", record.get("allocated", {}))),
                "consumed": float(flow.get("consumed", record.get("consumed", 0.0))),
                "lost": float(flow.get("lost", record.get("lost", 0.0))),
                "transformed_in": float(flow.get("transformed_in", 0.0)),
                "transformed_out": float(flow.get("transformed_out", 0.0)),
            },
            "produced": float(flow.get("produced", record.get("produced", 0.0))),
            "imported": float(flow.get("imported", record.get("imported", 0.0))),
            "allocated": dict(flow.get("allocated", record.get("allocated", {}))),
            "consumed": float(flow.get("consumed", record.get("consumed", 0.0))),
            "lost": float(flow.get("lost", record.get("lost", 0.0))),
            "end_quantity": float(record.get("quantity", record.get("stock", 0.0))),
            "end": float(record.get("quantity", record.get("stock", 0.0))),
            "primary_constraint": record.get("constraint", ""),
            "constraint": record.get("constraint", ""),
            "constraints": list(record.get("constraints", [])),
        }
    return ledger


def end_of_turn_ledger(resources: Dict[str, Any]) -> Dict[str, Any]:
    return build_turn_ledger(resources)
