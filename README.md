# CityManager

CityManager is a deterministic town-recovery simulator with a PySide6 player-mode GUI. The project models linked resource systems, budget pressure, policies, and recovery under constraint, with an emphasis on explainable cause-and-effect rather than randomness.

## What It Does

The current simulation focuses on:

- core town supplies: water, power, and food
- supporting inputs: fuel, repair materials, and available workers
- persistent policies and infrastructure effects
- logistics-style flow tracking for production, imports, losses, and consumption
- risk ranking and plain-language player guidance in the GUI

The engine is deterministic: the same starting state and same actions produce the same result.

## Project Structure

- [data](C:\workspace\Python\CityManager\data): scenario data, state, policies, resource types, units, and interaction registries
- [src](C:\workspace\Python\CityManager\src): simulation engine, registries, verb executors, and GUI code
- [tests](C:\workspace\Python\CityManager\tests): unit and integration-oriented tests
- [integration_report.md](C:\workspace\Python\CityManager\integration_report.md): implementation notes and validation summary

Key modules:

- [src/engine.py](C:\workspace\Python\CityManager\src\engine.py): main orchestration layer
- [src/resource_utils.py](C:\workspace\Python\CityManager\src\resource_utils.py): typed resource normalization, compatibility helpers, and ledgers
- [src/resource_registry.py](C:\workspace\Python\CityManager\src\resource_registry.py): resource-type registry loader
- [src/interaction_registry.py](C:\workspace\Python\CityManager\src\interaction_registry.py): verb interaction registry loader
- [src/verbs.py](C:\workspace\Python\CityManager\src\verbs.py): shared verb executors such as `allocate`, `transform`, `produce`, `consume`, `repair`, and `decay`
- [src/ui](C:\workspace\Python\CityManager\src\ui): PySide6 GUI

## Data Model

The current refactor uses three JSON registries:

- [data/resource_types.json](C:\workspace\Python\CityManager\data\resource_types.json): nouns and default metadata
- [data/units.json](C:\workspace\Python\CityManager\data\units.json): display units and formatting metadata
- [data/interactions.json](C:\workspace\Python\CityManager\data\interactions.json): shared verb interactions between resource types

Runtime resources are normalized into typed records with fields like:

- `resource_type_id`
- `unit_id`
- `quantity`
- `capacity`
- `base_production`
- `flow`

Legacy compatibility is still present, so older runtime keys like `energy` and `workforce_capacity` continue to work while the internal model maps them to `electricity` and `labor_hours`.

## Running the App

From the repository root:

```powershell
.\\.venv\\Scripts\\python.exe -m src
```

You can also run the module entry file directly:

```powershell
.\\.venv\\Scripts\\python.exe src\\__main__.py
```

## Running Tests

```powershell
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v
```

Optional compile check:

```powershell
.\\.venv\\Scripts\\python.exe -m compileall src tests
```

## GUI Overview

The GUI is a player-first mode intended to surface:

- the most urgent problem
- what happens next if the player does nothing
- emergency purchases and policy choices
- what changed and why after each turn

The GUI is a thin layer over the engine. It should not duplicate simulation logic.

## Current Design Principles

- deterministic simulation only
- JSON-backed data and policies
- explainable outcomes
- persistent effects across turns
- player-facing plain language where possible
- modular simulation internals for future extension

## Next Refactor Direction

The registry-and-verb system is in place, but there is still compatibility code in the engine and resource helpers. A likely next step is to continue removing legacy noun-specific assumptions from the orchestration layer so more behavior can be driven directly from the registries.
