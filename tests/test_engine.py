import os
import unittest

from src.challenges import required_generation, validate_allocation, validate_science_generation
from src.case_loader import load_cases
from src.engine import SimulationEngine
from src.interaction_registry import InteractionRegistry
from src.modifiers import activate_policy, can_select_policy, decrement_temporary_effects
from src.resource_registry import ResourceRegistry
from src.resource_utils import normalize_resource_record, stock
from src.risk import compute_risk_ranking


class SimulationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        self.engine = SimulationEngine(data_dir)
        self.data_dir = data_dir

    def blank_actions(self) -> dict:
        return {
            "resource_purchases": {
                "energy": 0.0,
                "water": 0.0,
                "food": 0.0,
                "fuel": 0.0,
                "materials": 0.0,
            },
            "allocation_priority": "balance_services",
            "selected_policy_id": None,
            "risk_assessment": {"primary_risk": "", "secondary_risk": ""},
            "parsed_report_issue": {"primary_issue": "", "secondary_issue": ""},
            "science_generation_answer": 0.0,
            "emergency_total_cost": 0.0,
        }

    def test_energy_recovery_from_zero_and_purchase_applies(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        state["resources"]["energy"]["stock"] = 0.0
        actions = self.blank_actions()
        actions["resource_purchases"]["energy"] = 10.0
        new_state, outcome = self.engine.simulate_turn(state, actions, False)

        self.assertIn("Base grid recovery restored 10.0 energy", "\n".join(outcome["recovery_effects"]))
        self.assertIn("+10.0 energy", "\n".join(outcome["direct_effects"]))
        self.assertGreaterEqual(stock(new_state["resources"], "energy"), 0.0)

    def test_science_generation_math_is_solvable(self) -> None:
        context = self.engine.build_context(self.engine.state)
        required = required_generation(
            stock(self.engine.state["resources"], "energy"),
            context["effective_energy_demand"],
            context["pump_threshold"],
            context["constants"]["science_safety_margin"],
        )
        self.assertGreater(required, 0.0)
        self.assertTrue(validate_science_generation(required, required))
        self.assertFalse(validate_science_generation(required - 1.0, required))

    def test_forecast_includes_resource_flow_and_constraints(self) -> None:
        forecast = self.engine.build_forecast(self.engine.state)
        self.assertIn("resource_flow_projection", forecast)
        self.assertIn("constraint_preview", forecast)
        self.assertIn("energy", forecast["resource_flow_projection"])
        self.assertEqual(forecast["resource_flow_projection"]["energy"]["resource_type_id"], "electricity")
        self.assertIn("historical_situation", forecast)
        self.assertIn("political_constraints", forecast)
        self.assertIn("affected_groups", forecast)

    def test_persistent_policy_remains_active_across_turns(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        policy = self.engine.policy_map["substation_upgrade"]
        activate_policy(state, policy)
        next_state, _ = self.engine.simulate_turn(state, self.blank_actions(), False)
        self.assertIn("substation_upgrade", next_state["modifiers"]["active_policies"])
        next_context = self.engine.build_context(next_state)
        self.assertLess(
            next_context["effective_energy_demand"],
            self.engine.scenario["constants"]["energy_demand"],
        )

    def test_unique_policy_cannot_duplicate(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        policy = self.engine.policy_map["maintenance_depot"]
        activate_policy(state, policy)
        can_use, reason = can_select_policy(state, policy)
        self.assertFalse(can_use)
        self.assertIn("already active", reason)

    def test_temporary_effects_expire(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        activate_policy(state, self.engine.policy_map["water_emergency_crews"])
        decrement_temporary_effects(state)
        self.assertEqual(state["modifiers"]["temporary_effects"], [])

    def test_constrained_allocation_rejects_overspend(self) -> None:
        forecast = self.engine.build_forecast(self.engine.state)
        valid, total_cost = validate_allocation(
            {
                "energy": 30.0,
                "water": 20.0,
                "food": 20.0,
                "fuel": 25.0,
                "materials": 25.0,
            },
            self.engine.scenario,
            forecast["risk_ranking"],
        )
        self.assertFalse(valid)
        self.assertGreater(total_cost, self.engine.scenario["available_emergency_budget"])

    def test_fuel_increases_energy_generation(self) -> None:
        low_fuel = self.engine.clone_state(self.engine.state)
        low_fuel["resources"]["fuel"]["stock"] = 0.0
        baseline_state, _ = self.engine.simulate_turn(low_fuel, self.blank_actions(), False)

        fueled = self.engine.clone_state(low_fuel)
        actions = self.blank_actions()
        actions["resource_purchases"]["fuel"] = 20.0
        fueled_state, _ = self.engine.simulate_turn(fueled, actions, False)
        self.assertGreater(
            fueled_state["telemetry"]["turn_resource_ledger"]["energy"]["produced"],
            baseline_state["telemetry"]["turn_resource_ledger"]["energy"]["produced"],
        )

    def test_low_workforce_reduces_production(self) -> None:
        stressed = self.engine.clone_state(self.engine.state)
        stressed["population"]["health"] = 0.35
        stressed["population"]["unrest"] = 0.4
        result, _ = self.engine.simulate_turn(stressed, self.blank_actions(), False)
        ledger = result["telemetry"]["turn_resource_ledger"]
        self.assertLess(ledger["workforce_capacity"]["start"], 30.0)
        self.assertTrue(result["telemetry"]["turn_constraint_log"])

    def test_resource_ledger_reconciles_end_stock(self) -> None:
        state, _ = self.engine.simulate_turn(self.engine.clone_state(self.engine.state), self.blank_actions(), False)
        ledger = state["telemetry"]["turn_resource_ledger"]
        for key in ["water", "energy", "food", "fuel", "materials"]:
            entry = ledger[key]
            reconciled = entry["start"] + entry["produced"] + entry["imported"] - entry["consumed"] - entry["lost"]
            self.assertAlmostEqual(reconciled, entry["end"], places=5)

    def test_risk_ranking_responds_to_supporting_resource_bottleneck(self) -> None:
        stressed = self.engine.clone_state(self.engine.state)
        stressed["resources"]["fuel"]["stock"] = 0.0
        context = self.engine.build_context(stressed)
        ranking = compute_risk_ranking(stressed, context, [], {}, {}, ["Power generation was limited by low fuel."])
        top_ids = [risk["issue_id"] for risk in ranking[:2]]
        self.assertIn("energy_instability", top_ids)

    def test_stabilization_window_increments_and_resets(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        actions = self.blank_actions()
        actions["resource_purchases"]["energy"] = 10.0
        actions["resource_purchases"]["fuel"] = 10.0
        stable_state, _ = self.engine.simulate_turn(state, actions, False)
        self.assertGreaterEqual(stable_state["telemetry"]["stable_turn_streak"], 0)

        unstable = self.engine.clone_state(stable_state)
        unstable["resources"]["water"]["stock"] = 0.0
        unstable_state, _ = self.engine.simulate_turn(unstable, self.blank_actions(), False)
        self.assertEqual(unstable_state["telemetry"]["stable_turn_streak"], 0)

    def test_resource_registry_loads_and_resolves_aliases(self) -> None:
        registry = ResourceRegistry.load(self.data_dir)
        self.assertEqual(registry.resolve("energy"), "electricity")
        self.assertEqual(registry.runtime_key("electricity"), "energy")
        self.assertEqual(registry.get("workforce_capacity")["resource_type_id"], "labor_hours")

    def test_case_loader_finds_two_historical_cases(self) -> None:
        cases = load_cases(self.data_dir)
        self.assertIn("berlin_airlift_1948", cases)
        self.assertIn("new_york_fiscal_crisis_1975", cases)

    def test_case_policy_affects_politics_and_society(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        actions = self.blank_actions()
        actions["selected_policy_id"] = "night_unloading_compact"
        next_state, outcome = self.engine.simulate_turn(state, actions, False)
        self.assertNotEqual(
            next_state["politics"]["coalition_stability"],
            state["politics"]["coalition_stability"],
        )
        self.assertTrue(outcome["stakeholder_effects"] or outcome["political_effects"])

    def test_case_reports_trigger_in_forecast(self) -> None:
        forecast = self.engine.build_forecast(self.engine.state)
        self.assertTrue(forecast["case_reports"])

    def test_interaction_registry_sorts_deterministically(self) -> None:
        registry = InteractionRegistry.load(self.data_dir)
        interactions = registry.all()
        self.assertTrue(interactions)
        orders = [(item["priority_order"], item["interaction_id"]) for item in interactions]
        self.assertEqual(orders, sorted(orders))

    def test_legacy_resource_normalizes_into_typed_record(self) -> None:
        record = normalize_resource_record(
            {"stock": 12.0, "capacity": 50.0, "base_production": 2.0},
            resource_type_id="energy",
            unit_id="kwh",
            capacity=50.0,
            base_production=2.0,
        )
        self.assertEqual(record["resource_type_id"], "electricity")
        self.assertEqual(record["quantity"], 12.0)
        self.assertEqual(record["stock"], 12.0)
        self.assertIn("flow", record)


if __name__ == "__main__":
    unittest.main()
