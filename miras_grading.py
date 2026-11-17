# Name: MIRAS 
# Date: 11/14/26
# Details: Grading code for the MIRAS project. Follows the 5 R's on a scale of 0-100

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

R_NAMES = ["Robustness", "Redundancy", "Resourcefulness", "Response", "Recovery"]


class _DataMissing:
    def __repr__(self) -> str:
        return "DATA_MISSING"


DATA_MISSING = _DataMissing()


@dataclass
class MetricDefinition:
    key: str
    r_category: str
    name: str
    unit: str
    # `worst` earns 0 points; `best` earns 100 points.
    # Set both to None until the team approves the scoring thresholds.
    worst: Optional[ float] = None
    best: Optional[float] = None
    weight_in_r: float = 1.0
    standard_ref: str = ""
    status: str = "THRESHOLD_REQUIRED"

    def __post_init__(self) -> None:
        if self.r_category not in R_NAMES:
            raise ValueError(f"{self.key}: invalid R category {self.r_category!r}")
        if self.weight_in_r <= 0 or not math.isfinite(self.weight_in_r):
            raise ValueError(f"{self.key}: weight_in_r must be positive and finite")
        if (self.worst is None) != (self.best is None):
            raise ValueError(f"{self.key}: set both worst and best, or neither")
        if self.worst is not None:
            if not (math.isfinite(self.worst) and math.isfinite(self.best)):
                raise ValueError(f"{self.key}: thresholds must be finite")
            if self.worst == self.best:
                raise ValueError(f"{self.key}: worst and best must be different")


@dataclass
class ExtractedValue:
    value: Any = DATA_MISSING
    unit: Optional[str] = None
    page: Optional[int] = None
    source_text: Optional[str] = None


@dataclass
class MetricResult:
    key: str
    name: str
    r_category: str
    status: str
    score: Optional[float]
    value: Any = None
    unit: Optional[str] = None
    page: Optional[int] = None
    source_text: Optional[str] = None
    note: str = ""


@dataclass
class RScore:
    name: str
    score: Optional[float]
    coverage: float
    low_bound: float
    high_bound: float
    metrics: list[MetricResult] = field(default_factory=list)


@dataclass
class ScoreReport:
    overall_score: Optional[float]
    band: str
    coverage: float
    low_bound: float
    high_bound: float
    provisional: bool
    r_scores: list[RScore]
    warnings: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str, allow_nan=False)


@dataclass
class ScoringConfig:
    # Figure 3.1: each R contributes 20% of the total.
    r_weights: dict[str, float] = field(
        default_factory=lambda: {name: 0.20 for name in R_NAMES}
    )
    # Figure 3.1 bands: 0–<50 Low, 50–<80 Medium, 80–<100 High, 100 Exceeds.
    medium_threshold: float = 50.0
    high_threshold: float = 80.0
    # This is a configurable team decision, not a threshold stated in the PDR.
    min_coverage: float = 0.60
    max_recommendations: int = 5

    def __post_init__(self) -> None:
        if set(self.r_weights) != set(R_NAMES):
            raise ValueError("r_weights must contain exactly the five Rs")
        if any((not math.isfinite(v) or v < 0) for v in self.r_weights.values()):
            raise ValueError("R weights must be finite and nonnegative")
        if sum(self.r_weights.values()) <= 0:
            raise ValueError("R weights must sum to a positive number")
        if not (0 <= self.medium_threshold < self.high_threshold <= 100):
            raise ValueError("Score-band thresholds must satisfy 0 <= medium < high <= 100")
        if not (0 <= self.min_coverage <= 1):
            raise ValueError("min_coverage must be between 0 and 1")
        if self.max_recommendations < 0:
            raise ValueError("max_recommendations cannot be negative")


# Unit conversion uses a common base unit within each dimension.
_UNIT_TABLE = {
    # time -> seconds
    "s": ("time", 1.0), "sec": ("time", 1.0), "second": ("time", 1.0),
    "seconds": ("time", 1.0), "min": ("time", 60.0), "minute": ("time", 60.0),
    "minutes": ("time", 60.0), "h": ("time", 3600.0), "hr": ("time", 3600.0),
    "hour": ("time", 3600.0), "hours": ("time", 3600.0),
    "day": ("time", 86400.0), "days": ("time", 86400.0),
    # power -> kW
    "kw": ("power", 1.0), "kilowatt": ("power", 1.0), "kilowatts": ("power", 1.0),
    "mw": ("power", 1000.0), "megawatt": ("power", 1000.0),
    "megawatts": ("power", 1000.0),
    # energy -> kWh
    "kwh": ("energy", 1.0), "mwh": ("energy", 1000.0),
    # fraction -> decimal ratio
    "%": ("fraction", 0.01), "percent": ("fraction", 0.01),
    "percentage": ("fraction", 0.01), "ratio": ("fraction", 1.0),
    # count-like units
    "count": ("count", 1.0), "scenario": ("count", 1.0),
    "scenarios": ("count", 1.0), "feed": ("count", 1.0), "feeds": ("count", 1.0),
}


class UnitMismatchError(ValueError):
    pass


def convert_units(value: float, from_unit: str, to_unit: str) -> float:
    if not from_unit:
        raise UnitMismatchError("reported unit is missing")
    source = _UNIT_TABLE.get(from_unit.strip().lower())
    target = _UNIT_TABLE.get(to_unit.strip().lower())
    if source is None or target is None or source[0] != target[0]:
        raise UnitMismatchError(f"cannot convert {from_unit!r} to {to_unit!r}")
    return value * source[1] / target[1]


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def default_metric_registry() -> list[MetricDefinition]:
    M = MetricDefinition
    return [
        # ROBUSTNESS
        M("scenarios_zero_critical_load_unserved", "Robustness",
          "Number of scenarios with zero critical load not served", "scenarios"),
        M("total_harmonic_distortion_deviation_pct", "Robustness",
          "Total harmonic distortion deviation", "%"),
        M("voltage_sag_swell_deviation_pct", "Robustness",
          "Voltage sag/swell deviation", "%"),

        # REDUNDANCY
        M("critical_or_nominal_load_not_served_kw", "Redundancy",
          "Critical or nominal load not served", "kW"),
        M("independent_utility_feeds_or_n_plus_1_generators", "Redundancy",
          "Independent utility feeds or N+1 critical generators", "count"),
        M("microgrid_capability_pct_critical_load", "Redundancy",
          "Microgrid capability as a percentage of critical load", "%"),

        # RESOURCEFULNESS
        M("energy_produced_or_procured_pct", "Resourcefulness",
          "Energy produced or procured as a percentage of electricity", "%"),
        M("critical_load_shed_or_prioritized_pct", "Resourcefulness",
          "Share of critical load that can be shed or prioritized", "%"),

        # RESPONSE
        # Supply actual restoration time divided by the required restoration
        # time (e.g., 30 min / 1 hr = 0.5). A ratio <= 1 meets the requirement.
        M("critical_function_restoration_time_ratio", "Response",
          "Time to restore critical functions relative to the requirement", "ratio"),

        # RECOVERY
        M("nominal_operations_restoration_time", "Recovery",
          "Time to restore nominal operations", "seconds"),
    ]


def score_metric(defn: MetricDefinition,
                 extracted: Optional[ExtractedValue]) -> MetricResult:
    base = dict(key=defn.key, name=defn.name, r_category=defn.r_category)

    if extracted is None or extracted.value is DATA_MISSING or extracted.value is None:
        return MetricResult(**base, status="not_reported", score=None,
                            note="Not found in the provided documents")

    carry = dict(value=extracted.value, unit=extracted.unit,
                 page=extracted.page, source_text=extracted.source_text)

    if defn.worst is None or defn.best is None:
        return MetricResult(**base, status="threshold_required", score=None, **carry,
                            note="Metric thresholds have not yet been approved/configured")

    try:
        if isinstance(extracted.value, bool):
            raise ValueError("boolean supplied for a numeric metric")
        numeric_value = float(extracted.value)
        if not math.isfinite(numeric_value):
            raise ValueError("value must be finite")
        canonical_value = convert_units(numeric_value, extracted.unit, defn.unit)
    except (TypeError, ValueError, UnitMismatchError) as exc:
        return MetricResult(**base, status="invalid", score=None, **carry,
                            note=f"Could not use extracted value: {exc}")

    # Works for both higher-is-better and lower-is-better metrics.
    points = (canonical_value - defn.worst) / (defn.best - defn.worst) * 100.0
    return MetricResult(**base, status="scored", score=clamp(points), **carry)


def score_r_category(r_name: str, definitions: list[MetricDefinition],
                     extracted: dict[str, ExtractedValue]) -> RScore:
    metrics = [d for d in definitions if d.r_category == r_name]
    results = [score_metric(d, extracted.get(d.key)) for d in metrics]
    total_weight = sum(d.weight_in_r for d in metrics)

    scored = [(d, result) for d, result in zip(metrics, results)
              if result.status == "scored"]
    reported_weight = sum(d.weight_in_r for d, _ in scored)
    weighted_points = sum(d.weight_in_r * result.score for d, result in scored)

    score = weighted_points / reported_weight if reported_weight else None
    coverage = reported_weight / total_weight if total_weight else 0.0
    low_bound = weighted_points / total_weight if total_weight else 0.0
    high_bound = ((weighted_points + (total_weight - reported_weight) * 100.0)
                  / total_weight if total_weight else 100.0)

    return RScore(r_name, score, coverage, low_bound, high_bound, results)


def score_overall(r_scores: list[RScore], config: ScoringConfig):
    total_weight = sum(config.r_weights.values())
    scored_rs = [r for r in r_scores if r.score is not None]
    scored_weight = sum(config.r_weights[r.name] for r in scored_rs)

    # Available-data score: normalize across Rs that actually have scores.
    overall = (sum(config.r_weights[r.name] * r.score for r in scored_rs)
               / scored_weight) if scored_weight else None

    coverage = (sum(config.r_weights[r.name] * r.coverage for r in r_scores)
                / total_weight)
    low = (sum(config.r_weights[r.name] * r.low_bound for r in r_scores)
           / total_weight)
    high = (sum(config.r_weights[r.name] * r.high_bound for r in r_scores)
            / total_weight)
    return overall, coverage, low, high


def classify_band(score: Optional[float], config: ScoringConfig) -> str:
    if score is None:
        return "Not enough data"
    if score >= 100.0 - 1e-9:
        return "Exceeds"
    if score >= config.high_threshold:
        return "High"
    if score >= config.medium_threshold:
        return "Medium"
    return "Low"


def build_warnings(r_scores: list[RScore], coverage: float,
                   provisional: bool, low: float, high: float) -> list[str]:
    warnings = []
    for r in r_scores:
        for metric in r.metrics:
            if metric.status == "not_reported":
                warnings.append(f"Not reported: {metric.name} ({metric.r_category})")
            elif metric.status == "invalid":
                warnings.append(f"Invalid value: {metric.name} ({metric.r_category}) — {metric.note}")
            elif metric.status == "threshold_required":
                warnings.append(f"Threshold required: {metric.name} ({metric.r_category})")
        if r.score is None:
            warnings.append(f"No scored metrics for {r.name}; it is not contributing to the available-data score")
    if provisional:
        warnings.append(
            f"PROVISIONAL: {coverage:.0%} of metric weight has been scored. "
            f"The overall score bounds are {low:.1f}–{high:.1f}."
        )
    return warnings


def build_recommendations(r_scores: list[RScore], band: str,
                           config: ScoringConfig) -> list[str]:
    # Figure 3.1 shows recommendations for Low, Medium, and High, but not Exceeds.
    if band in ("Exceeds", "Not enough data"):
        return []

    scored = [m for r in r_scores for m in r.metrics if m.status == "scored"]
    weak = sorted((m for m in scored if m.score < config.high_threshold),
                  key=lambda m: m.score)
    recommendations = [
        f"Improve {m.name} ({m.r_category}); current score: {m.score:.1f}/100"
        for m in weak
    ]

    unreported = [m for r in r_scores for m in r.metrics
                  if m.status == "not_reported"]
    recommendations.extend(
        f"Collect/report data for {m.name} ({m.r_category})"
        for m in unreported
    )
    return recommendations[:config.max_recommendations]


def grade_installation(extracted: dict[str, ExtractedValue],
                       config: Optional[ScoringConfig] = None,
                       definitions: Optional[list[MetricDefinition]] = None) -> ScoreReport:
    config = config or ScoringConfig()
    definitions = definitions or default_metric_registry()

    # Catch duplicate keys; otherwise one extracted value could silently score
    # the wrong definition.
    keys = [d.key for d in definitions]
    if len(keys) != len(set(keys)):
        raise ValueError("Metric registry contains duplicate metric keys")

    r_scores = [score_r_category(name, definitions, extracted) for name in R_NAMES]
    overall, coverage, low, high = score_overall(r_scores, config)
    band = classify_band(overall, config)
    provisional = coverage < config.min_coverage

    return ScoreReport(
        overall_score=None if overall is None else round(overall, 1),
        band=band,
        coverage=round(coverage, 3),
        low_bound=round(low, 1),
        high_bound=round(high, 1),
        provisional=provisional,
        r_scores=r_scores,
        warnings=build_warnings(r_scores, coverage, provisional, low, high),
        recommendations=build_recommendations(r_scores, band, config),
    )


def export_for_dashboard(report: ScoreReport) -> str:
    return report.to_json()
