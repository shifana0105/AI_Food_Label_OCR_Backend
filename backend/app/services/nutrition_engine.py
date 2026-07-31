"""Nutrition Knowledge Engine.

Deterministic, fully explainable rule-based nutrition scoring.

The engine consumes per-100g nutrition features (as produced by
``UnitConverter.convert_all``) together with the scoring rules defined
in ``backend/config/nutrition_rules.json`` and produces:

    - general_score      (0-100 integer, or None when nothing detected)
    - nutrition_grade    (A-E, or "unknown")
    - positive_reasons   (list of human-readable strings)
    - negative_reasons   (list of human-readable strings)
    - warnings           (list of human-readable strings)

Design notes:

    - No Machine Learning. No LLM calls. Pure rules.
    - Every threshold, weight, label, and grade band comes from the
      JSON configuration. Nothing nutrition-specific is hardcoded.
    - Each nutrient is evaluated independently by its own small
      ``evaluate_<nutrient>()`` method, all delegating to a single
      shared band-matching helper (no duplicated logic).
    - Same input always produces the same output.
"""

import json
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)

_CONFIG_PATH: Path = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "nutrition_rules.json"
)


@lru_cache(maxsize=1)
def _load_rules(config_path: str) -> Dict[str, Any]:
    """Load and cache the nutrition rules configuration."""
    path = Path(config_path)

    with path.open("r", encoding="utf-8") as handle:
        rules = json.load(handle)

    logger.info(
        "Nutrition rules loaded (version=%s, nutrients=%d).",
        rules.get("version", "unknown"),
        len(rules.get("nutrients", {})),
    )

    return rules


@dataclass(frozen=True)
class NutrientEvaluation:
    """Result of evaluating a single nutrient against its rule bands."""

    nutrient: str
    display_name: str
    value: Optional[float]
    unit: Optional[str]
    detected: bool
    score: Optional[float]
    weight: float
    label: Optional[str]
    sentiment: Optional[str]
    warnings: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisResult:
    """Aggregated, explainable output of the Nutrition Knowledge Engine."""

    general_score: Optional[int]
    nutrition_grade: str
    positive_reasons: List[str]
    negative_reasons: List[str]
    warnings: List[str]
    evaluations: List[NutrientEvaluation]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the public analysis payload (API-facing shape)."""
        return {
            "general_score": self.general_score,
            "nutrition_grade": self.nutrition_grade,
            "positive_reasons": list(self.positive_reasons),
            "negative_reasons": list(self.negative_reasons),
            "warnings": list(self.warnings),
        }


class NutritionEngine:
    """Rule-based nutrition scoring engine.

    Usage:

        engine = NutritionEngine()
        analysis = engine.evaluate(per_100g_features)
        payload = analysis.to_dict()
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self._config_path = Path(config_path or _CONFIG_PATH)
        self._rules: Dict[str, Any] = _load_rules(str(self._config_path))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, features: Dict[str, Optional[float]]) -> AnalysisResult:
        """Evaluate per-100g nutrition features and produce the analysis.

        Args:
            features: Mapping of feature keys (e.g. ``sugars_100g``) to
                per-100g values. ``None`` means the nutrient was not
                detected on the label.

        Returns:
            A fully populated, deterministic :class:`AnalysisResult`.
        """
        started = time.perf_counter()

        logger.info("Nutrition Knowledge Engine started.")

        evaluations: List[NutrientEvaluation] = [
            self.evaluate_energy(features),
            self.evaluate_sugar(features),
            self.evaluate_added_sugar(features),
            self.evaluate_protein(features),
            self.evaluate_fiber(features),
            self.evaluate_total_fat(features),
            self.evaluate_saturated_fat(features),
            self.evaluate_trans_fat(features),
            self.evaluate_sodium(features),
        ]

        result = self._aggregate(evaluations)

        for warning in result.warnings:
            logger.warning("Nutrition warning: %s", warning)

        elapsed = time.perf_counter() - started

        logger.info(
            "Nutrition Knowledge Engine completed in %.4fs "
            "(score=%s, grade=%s, positives=%d, negatives=%d, warnings=%d).",
            elapsed,
            result.general_score,
            result.nutrition_grade,
            len(result.positive_reasons),
            len(result.negative_reasons),
            len(result.warnings),
        )

        return result

    # ------------------------------------------------------------------
    # Independent per-nutrient evaluators (Task 4)
    # ------------------------------------------------------------------

    def evaluate_energy(
        self, features: Dict[str, Optional[float]]
    ) -> NutrientEvaluation:
        """Evaluate energy density (kcal per 100 g)."""
        return self._evaluate_nutrient("energy", features)

    def evaluate_sugar(
        self, features: Dict[str, Optional[float]]
    ) -> NutrientEvaluation:
        """Evaluate total sugars (g per 100 g)."""
        return self._evaluate_nutrient("sugar", features)

    def evaluate_added_sugar(
        self, features: Dict[str, Optional[float]]
    ) -> NutrientEvaluation:
        """Evaluate added sugars (g per 100 g)."""
        return self._evaluate_nutrient("added_sugar", features)

    def evaluate_protein(
        self, features: Dict[str, Optional[float]]
    ) -> NutrientEvaluation:
        """Evaluate protein content (g per 100 g)."""
        return self._evaluate_nutrient("protein", features)

    def evaluate_fiber(
        self, features: Dict[str, Optional[float]]
    ) -> NutrientEvaluation:
        """Evaluate dietary fiber (g per 100 g)."""
        return self._evaluate_nutrient("fiber", features)

    def evaluate_total_fat(
        self, features: Dict[str, Optional[float]]
    ) -> NutrientEvaluation:
        """Evaluate total fat (g per 100 g)."""
        return self._evaluate_nutrient("total_fat", features)

    def evaluate_saturated_fat(
        self, features: Dict[str, Optional[float]]
    ) -> NutrientEvaluation:
        """Evaluate saturated fat (g per 100 g)."""
        return self._evaluate_nutrient("saturated_fat", features)

    def evaluate_trans_fat(
        self, features: Dict[str, Optional[float]]
    ) -> NutrientEvaluation:
        """Evaluate trans fat (g per 100 g)."""
        return self._evaluate_nutrient("trans_fat", features)

    def evaluate_sodium(
        self, features: Dict[str, Optional[float]]
    ) -> NutrientEvaluation:
        """Evaluate sodium (g per 100 g)."""
        return self._evaluate_nutrient("sodium", features)

    # ------------------------------------------------------------------
    # Shared rule evaluation (single source of truth)
    # ------------------------------------------------------------------

    def _evaluate_nutrient(
        self,
        nutrient: str,
        features: Dict[str, Optional[float]],
    ) -> NutrientEvaluation:
        """Evaluate one nutrient against its configured rule bands."""
        rule: Optional[Dict[str, Any]] = (
            self._rules.get("nutrients", {}).get(nutrient)
        )

        if rule is None:
            logger.warning(
                "No rule configured for nutrient '%s'; skipping.", nutrient
            )
            return NutrientEvaluation(
                nutrient=nutrient,
                display_name=nutrient,
                value=None,
                unit=None,
                detected=False,
                score=None,
                weight=0.0,
                label=None,
                sentiment=None,
            )

        display_name: str = rule.get("display_name", nutrient)
        unit: Optional[str] = rule.get("unit")
        weight: float = float(rule.get("weight", 1.0))

        raw_value = features.get(rule["feature_key"])
        value = self._sanitize_value(raw_value)

        if value is None:
            return NutrientEvaluation(
                nutrient=nutrient,
                display_name=display_name,
                value=None,
                unit=unit,
                detected=False,
                score=None,
                weight=weight,
                label=None,
                sentiment=None,
            )

        band = self._match_band(value, rule.get("bands", []))

        warnings = self._collect_warnings(value, rule.get("warnings", []))

        return NutrientEvaluation(
            nutrient=nutrient,
            display_name=display_name,
            value=value,
            unit=unit,
            detected=True,
            score=float(band["score"]) if band else None,
            weight=weight,
            label=band.get("label") if band else None,
            sentiment=band.get("sentiment") if band else None,
            warnings=warnings,
        )

    @staticmethod
    def _sanitize_value(raw_value: Any) -> Optional[float]:
        """Coerce a raw feature value into a non-negative float or None."""
        if raw_value is None:
            return None

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None

        if value < 0:
            return None

        return value

    @staticmethod
    def _match_band(
        value: float,
        bands: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """Return the first band whose upper bound covers the value.

        A band with ``"max": null`` is an open-ended catch-all.
        """
        for band in bands:
            upper = band.get("max")

            if upper is None or value <= float(upper):
                return band

        return None

    @staticmethod
    def _collect_warnings(
        value: float,
        warning_rules: List[Dict[str, Any]],
    ) -> List[str]:
        """Collect all warning messages triggered by the value."""
        return [
            rule["message"]
            for rule in warning_rules
            if value > float(rule.get("min", 0))
        ]

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate(
        self,
        evaluations: List[NutrientEvaluation],
    ) -> AnalysisResult:
        """Combine per-nutrient evaluations into the final analysis."""
        scored = [
            evaluation
            for evaluation in evaluations
            if evaluation.detected and evaluation.score is not None
        ]

        positive_reasons: List[str] = []
        negative_reasons: List[str] = []
        warnings: List[str] = []

        for evaluation in evaluations:
            if not evaluation.detected:
                continue

            if evaluation.sentiment == "positive" and evaluation.label:
                positive_reasons.append(evaluation.label)

            elif evaluation.sentiment == "negative" and evaluation.label:
                negative_reasons.append(evaluation.label)

            warnings.extend(evaluation.warnings)

        if not scored:
            warnings.append(
                "No nutrition values could be evaluated; "
                "the label may be unreadable or incomplete."
            )

            return AnalysisResult(
                general_score=None,
                nutrition_grade="unknown",
                positive_reasons=positive_reasons,
                negative_reasons=negative_reasons,
                warnings=warnings,
                evaluations=evaluations,
            )

        total_weight = sum(evaluation.weight for evaluation in scored)

        weighted_sum = sum(
            evaluation.score * evaluation.weight  # type: ignore[operator]
            for evaluation in scored
        )

        general_score = int(round(weighted_sum / total_weight))

        nutrition_grade = self._resolve_grade(general_score)

        return AnalysisResult(
            general_score=general_score,
            nutrition_grade=nutrition_grade,
            positive_reasons=positive_reasons,
            negative_reasons=negative_reasons,
            warnings=warnings,
            evaluations=evaluations,
        )

    def _resolve_grade(self, score: int) -> str:
        """Map a general score to a letter grade using configured bands."""
        grade_bands = sorted(
            self._rules.get("grade_bands", []),
            key=lambda band: band["min_score"],
            reverse=True,
        )

        for band in grade_bands:
            if score >= int(band["min_score"]):
                return str(band["grade"])

        return "unknown"


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    sample_features = {
        "energy_100g": 470.59,
        "fat_100g": 20.59,
        "saturated-fat_100g": 5.88,
        "carbohydrates_100g": 73.53,
        "sugars_100g": 41.18,
        "fiber_100g": 2.94,
        "proteins_100g": 5.88,
        "sodium_100g": 0.40,
    }

    engine = NutritionEngine()

    analysis = engine.evaluate(sample_features)

    print("\n----------- NUTRITION ANALYSIS -----------\n")

    print(f"General Score : {analysis.general_score}")
    print(f"Grade         : {analysis.nutrition_grade}")

    print("\nPositive Reasons:")
    for reason in analysis.positive_reasons:
        print(f"  + {reason}")

    print("\nNegative Reasons:")
    for reason in analysis.negative_reasons:
        print(f"  - {reason}")

    print("\nWarnings:")
    for warning in analysis.warnings:
        print(f"  ! {warning}")

    print("\n-------------------------------------------")
