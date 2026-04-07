"""State-driven report generation from ranked risks."""

from typing import Dict, List


ISSUE_LABELS = {
    "water_shortage": "water shortage",
    "energy_instability": "energy instability",
    "food_collapse": "food insecurity",
    "budget_erosion": "budget erosion",
    "unrest_spike": "civil unrest",
}


def issue_label(issue_id: str) -> str:
    """Return a player-facing label for an issue id."""
    return ISSUE_LABELS.get(issue_id, issue_id.replace("_", " "))


def generate_report_text(risk_ranking: List[Dict[str, float]]) -> str:
    """Generate a multi-signal report from the top two risks."""
    top = risk_ranking[0]["issue_id"] if risk_ranking else "water_shortage"
    second = risk_ranking[1]["issue_id"] if len(risk_ranking) > 1 else top
    fragments = {
        "water_shortage": "Water pressure is falling across town",
        "energy_instability": "pumping interruptions are straining utilities",
        "food_collapse": "produce deliveries are shrinking",
        "budget_erosion": "department heads warn that costs are overtaking revenue",
        "unrest_spike": "residents are growing more anxious and disruptive",
    }
    return f"{fragments[top]}, and {fragments[second]}."
