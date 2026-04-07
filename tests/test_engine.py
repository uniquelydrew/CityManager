import os
import unittest

from src.challenges import required_generation, validate_allocation, validate_science_generation
from src.engine import SimulationEngine
from src.modifiers import activate_policy, can_select_policy, decrement_temporary_effects
from src.risk import compute_risk_ranking


class SimulationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
        )
        self.engine = SimulationEngine(data_dir)

    def blank_actions(self) -> dict:
        return {
            "emergency_allocation": {
                "energy_amount": 0.0,
                "water_amount": 0.0,
                "food_amount": 0.0,
                "total_cost": 0.0,
            },
            "selected_policy_id": None,
            "risk_assessment": {"primary_risk": "", "secondary_risk": ""},
            "parsed_report_issue": {"primary_issue": "", "secondary_issue": ""},
            "science_generation_answer": 0.0,
        }

    def test_energy_recovery_from_zero_and_purchase_applies(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        state["resources"]["energy"] = 0.0
        actions = self.blank_actions()
        actions["emergency_allocation"]["energy_amount"] = 10.0
        actions["emergency_allocation"]["total_cost"] = 50.0
        new_state, outcome = self.engine.simulate_turn(state, actions, False)

        self.assertIn("Base grid recovery restored 10.0 energy", "\n".join(outcome["recovery_effects"]))
        self.assertIn("+10.0 energy", "\n".join(outcome["direct_effects"]))
        self.assertGreaterEqual(new_state["resources"]["energy"], 0.0)

    def test_science_generation_math_is_solvable(self) -> None:
        context = self.engine.build_context(self.engine.state)
        required = required_generation(
            self.engine.state["resources"]["energy"],
            context["effective_energy_demand"],
            context["pump_threshold"],
            context["constants"]["science_safety_margin"],
        )
        self.assertEqual(required, 15.0)
        self.assertTrue(validate_science_generation(required, required))
        self.assertFalse(validate_science_generation(required - 1.0, required))

    def test_forecast_includes_recovery_and_risk_changes(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        state["resources"]["energy"] = 0.0
        forecast = self.engine.build_forecast(state)

        self.assertIn("recovery_projection", forecast)
        self.assertIn("risk_changes", forecast)
        self.assertTrue(forecast["risk_ranking"])

    def test_persistent_policy_remains_active_across_turns(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        policy = self.engine.policy_map["grid_maintenance"]
        activate_policy(state, policy)
        next_state, _ = self.engine.simulate_turn(state, self.blank_actions(), False)

        self.assertIn("grid_maintenance", next_state["modifiers"]["active_policies"])
        next_context = self.engine.build_context(next_state)
        self.assertLess(
            next_context["effective_energy_demand"],
            self.engine.scenario["constants"]["energy_demand"],
        )

    def test_unique_policy_cannot_duplicate(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        policy = self.engine.policy_map["pump_repair_program"]
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
                "energy_amount": 30.0,
                "water_amount": 20.0,
                "food_amount": 20.0,
            },
            self.engine.scenario,
            forecast["risk_ranking"],
        )

        self.assertFalse(valid)
        self.assertGreater(total_cost, self.engine.scenario["available_emergency_budget"])

    def test_full_cycle_closure_reaches_economy(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        state["resources"]["energy"] = 0.0
        state["resources"]["water"] = 15.0
        state["resources"]["food"] = 10.0
        state["population"]["happiness"] = 0.4
        new_state, outcome = self.engine.simulate_turn(state, self.blank_actions(), False)

        self.assertLess(new_state["population"]["health"], state["population"]["health"])
        self.assertLess(new_state["economy"]["income"], new_state["economy"]["base_income"])
        self.assertTrue(outcome["dependency_effects"])
        self.assertTrue(outcome["economy_effects"])

    def test_risk_normalization_drops_with_recovery(self) -> None:
        stressed = self.engine.clone_state(self.engine.state)
        stressed["resources"]["energy"] = 0.0
        stressed["resources"]["water"] = 10.0
        stressed["resources"]["food"] = 10.0
        context_a = self.engine.build_context(stressed)
        ranking_a = compute_risk_ranking(stressed, context_a, ["energy water food"], {})

        recovered = self.engine.clone_state(self.engine.state)
        recovered["resources"]["energy"] = 40.0
        recovered["resources"]["water"] = 50.0
        recovered["resources"]["food"] = 60.0
        context_b = self.engine.build_context(recovered)
        ranking_b = compute_risk_ranking(
            recovered,
            context_b,
            [],
            {"energy_recovery": True, "water_recovery": True, "food_recovery": True},
        )

        top_a = {risk["issue_id"]: risk["severity"] for risk in ranking_a}
        top_b = {risk["issue_id"]: risk["severity"] for risk in ranking_b}
        self.assertGreater(top_a["energy_instability"], top_b["energy_instability"])

    def test_stabilization_window_increments_and_resets(self) -> None:
        state = self.engine.clone_state(self.engine.state)
        state["resources"]["energy"] = 40.0
        state["resources"]["water"] = 50.0
        state["resources"]["food"] = 60.0
        state["population"]["health"] = 0.8
        state["economy"]["budget"] = 10000.0
        actions = self.blank_actions()
        actions["emergency_allocation"]["energy_amount"] = 20.0
        actions["emergency_allocation"]["water_amount"] = 5.0
        actions["emergency_allocation"]["food_amount"] = 5.0
        actions["emergency_allocation"]["total_cost"] = 150.0
        stable_state, _ = self.engine.simulate_turn(state, actions, False)
        self.assertGreaterEqual(stable_state["telemetry"]["stable_turn_streak"], 1)

        unstable = self.engine.clone_state(stable_state)
        unstable["resources"]["water"] = 0.0
        unstable_state, _ = self.engine.simulate_turn(unstable, self.blank_actions(), False)
        self.assertEqual(unstable_state["telemetry"]["stable_turn_streak"], 0)


if __name__ == "__main__":
    unittest.main()
