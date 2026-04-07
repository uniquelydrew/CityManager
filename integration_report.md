# Integration Report

## Rule Flow

- `engine.py` orchestrates the playable loop and delegates forecast, risk, modifier, report, challenge, water, and food behavior to dedicated modules.
- Forecast generation uses a shared no-action simulation pass and renders separate base, dependency, modifier, recovery, and ranked-risk sections.
- Simulation now applies base energy recovery, direct purchases, policy costs/effects, base consumption, one-pass dependency propagation, recovery bonuses, population/economy recalculation, risk movement, and telemetry updates in deterministic order.

## Module Responsibilities

- `src/forecast.py`: builds causal no-action forecast payloads.
- `src/risk.py`: computes deterministic ranked risks with stable tie ordering.
- `src/modifiers.py`: manages activation, stacking, and expiration of policies/modifiers.
- `src/explanation.py`: provides sectioned explanation containers and ordered outcome chains.
- `src/reports.py`: generates multi-signal report text from the top-ranked issues.
- `src/challenges.py`: validates constrained allocations, RLA ordering, and science reserve targets.
- `src/water.py` and `src/food.py`: encapsulate threshold and modifier calculations.

## Validation Summary

- Determinism: identical state and inputs produce stable risk rankings and the same one-pass propagation order.
- Functional: forecast distinguishes base vs dependency vs recovery effects; persistent policy effects carry across turns; overspending allocations are rejected; energy can recover from zero; science challenge math is explicit and solvable; explanations include recovery and risk-movement sections.

## Known Limitations

- The policy layer still encourages some workaround behavior such as choosing an already-active policy when the player wants to avoid extra spend.
- Persistent infrastructure still modifies thresholds and multipliers through active modifiers rather than a more abstract rule compiler.
- Balance values are baseline defaults and likely need another tuning pass now that recovery and stabilization are possible.
