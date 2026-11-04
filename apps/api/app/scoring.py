"""Deterministic maturity scoring; this is not a compliance certification."""
from dataclasses import dataclass
from typing import Literal

Status = Literal["not_implemented", "planned", "partial", "implemented", "validated", "not_applicable", "unknown"]
VALUES = {"not_implemented": 0, "planned": 25, "partial": 50, "implemented": 75, "validated": 100}
DOMAIN_WEIGHTS = {"governance": 30, "security": 30, "privacy": 20, "vendor_oversight": 10, "operational_readiness": 10}
SCORING_VERSION = "mvp-1.0"

@dataclass(frozen=True)
class Answer:
    domain: str
    status: Status
    weight: float = 1.0

def calculate(answers: list[Answer]) -> dict:
    """Unknown answers lower coverage; N/A requires justification from caller."""
    output = {}
    for domain, domain_weight in DOMAIN_WEIGHTS.items():
        subset = [a for a in answers if a.domain == domain and a.status != "not_applicable"]
        if any(a.weight <= 0 for a in subset):
            raise ValueError("Control weights must be positive")
        total = sum(a.weight for a in subset)
        rated = [a for a in subset if a.status in VALUES]
        covered = sum(a.weight for a in rated)
        output[domain] = {
            "score": round(sum(a.weight * VALUES[a.status] for a in rated) / covered, 2) if covered else None,
            "coverage": round(covered / total * 100, 2) if total else 0,
            "weight": domain_weight,
        }
    eligible = all(output[d]["score"] is not None and output[d]["coverage"] >= 80 for d in DOMAIN_WEIGHTS)
    overall = round(sum(output[d]["score"] * w for d, w in DOMAIN_WEIGHTS.items()) / 100, 2) if eligible else None
    return {"version": SCORING_VERSION, "overall_score": overall, "domains": output}
