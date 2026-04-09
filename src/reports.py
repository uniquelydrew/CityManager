"""State-driven report generation from ranked risks."""

from typing import Dict, List


ISSUE_LABELS = {
    "water_shortage": "water service under strain",
    "energy_instability": "core operating capacity bottleneck",
    "food_collapse": "food system shortfall",
    "budget_erosion": "budget under strain",
    "unrest_spike": "workforce and community strain",
    "institutional_breakdown": "institutional breakdown risk",
    "political_stalemate": "political stalemate risk",
    "public_trust_collapse": "public trust collapse risk",
}


def issue_label(issue_id: str) -> str:
    """Return a player-facing label for an issue id."""
    return ISSUE_LABELS.get(issue_id, issue_id.replace("_", " "))


def generate_report_text(risk_ranking: List[Dict[str, float]]) -> str:
    """Generate a multi-signal report from the top two risks."""
    top = risk_ranking[0]["issue_id"] if risk_ranking else "water_shortage"
    second = risk_ranking[1]["issue_id"] if len(risk_ranking) > 1 else top
    fragments = {
        "water_shortage": "water access is becoming less reliable",
        "energy_instability": "core operating capacity is falling below what essential services need",
        "food_collapse": "food access is shrinking as production and distribution slow",
        "budget_erosion": "operating costs are overtaking available revenue",
        "unrest_spike": "residents and workers are growing more strained and reactive",
        "institutional_breakdown": "institutions are struggling to carry relief, distribution, and repair work",
        "political_stalemate": "political bargaining is stalling urgent action",
        "public_trust_collapse": "public confidence is slipping as visible strain spreads",
    }
    return f"{fragments[top]}, and {fragments[second]}."
