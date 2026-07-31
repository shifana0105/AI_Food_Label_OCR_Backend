"""Serving basis detection and normalization service.

Detects the declaration basis of a nutrition panel (per serving,
per 100 g, per 100 ml, per container) and, when a serving size is
available, computes normalized per-100g/per-100ml nutrition values.

Original OCR values are NEVER modified: normalized values are returned
in a separate structure alongside the untouched parsed label.
"""

import re
import time
from copy import deepcopy
from typing import Any, Dict, Optional

from app.core.logger import get_logger
from app.services.unit_converter import UnitConverter

logger = get_logger(__name__)


class ServingConverter:
    """Normalizes nutrition values to a per-100g/per-100ml basis."""

    PER_100G = "per_100g"
    PER_100ML = "per_100ml"
    PER_SERVING = "per_serving"
    PER_CONTAINER = "per_container"

    _BASIS_PATTERNS = (
        (re.compile(r"per\s*100\s*g(?:ram)?s?\b", re.I), PER_100G),
        (re.compile(r"per\s*100\s*ml\b", re.I), PER_100ML),
        (re.compile(r"per\s*(?:container|pack(?:age)?|bottle)\b", re.I), PER_CONTAINER),
        (re.compile(r"per\s*serving\b|amount\s*per\s*serving", re.I), PER_SERVING),
    )

    _VOLUME_SERVING_UNITS = frozenset({"ml", "l"})

    def __init__(self, unit_converter: Optional[UnitConverter] = None) -> None:
        self.unit_converter = unit_converter or UnitConverter()

    # ------------------------------------------------------------------

    def detect_basis(self, text: str, fallback: str = PER_SERVING) -> str:
        """Detect the declaration basis from raw label text.

        Args:
            text: OCR text of the label.
            fallback: Basis returned when no pattern matches.
        """
        for pattern, basis in self._BASIS_PATTERNS:
            if pattern.search(text):
                logger.info("ServingConverter detected basis: %s", basis)
                return basis

        logger.info(
            "ServingConverter found no explicit basis; using fallback: %s",
            fallback,
        )
        return fallback

    # ------------------------------------------------------------------

    def normalize(
        self,
        parsed_label: Dict[str, Any],
        clean_text: str = "",
    ) -> Dict[str, Any]:
        """Compute per-100g/ml normalized values for a parsed label.

        Args:
            parsed_label: Output of the nutrition parser, containing
                ``serving`` and ``nutrition`` keys. Never mutated.
            clean_text: Optional raw text used to detect the basis when
                the parser did not classify it.

        Returns:
            ``{"basis": str, "serving": {...}, "nutrition": {...}}``
            where nutrition values are normalized per 100g/100ml.
            Original values in ``parsed_label`` are preserved untouched.
        """
        started = time.perf_counter()
        logger.info("ServingConverter normalization started.")

        label = deepcopy(parsed_label)

        serving = label.get("serving", {}) or {}
        nutrition = label.get("nutrition", {}) or {}

        serving_size = serving.get("size")
        serving_unit = serving.get("unit")
        basis = serving.get("type") or self.detect_basis(clean_text)

        target_basis = self._target_basis(basis, serving_unit)

        normalized_nutrition: Dict[str, Dict[str, Any]] = {}

        for nutrient, data in nutrition.items():
            normalized_nutrition[nutrient] = self._normalize_nutrient(
                nutrient=nutrient,
                data=data,
                basis=basis,
                serving_size=serving_size,
            )

        result = {
            "basis": target_basis,
            "serving": {
                "size": serving_size,
                "unit": serving_unit,
                "declared_basis": basis,
            },
            "nutrition": normalized_nutrition,
        }

        logger.info(
            "ServingConverter normalization completed in %.4fs "
            "(%d nutrients, basis=%s).",
            time.perf_counter() - started,
            len(normalized_nutrition),
            target_basis,
        )

        return result

    # ------------------------------------------------------------------

    def _target_basis(self, basis: str, serving_unit: Optional[str]) -> str:
        """Decide whether the normalized basis is per 100 g or 100 ml."""
        if basis == self.PER_100ML:
            return self.PER_100ML

        canonical_unit = self.unit_converter.normalize_unit(serving_unit)

        if canonical_unit in self._VOLUME_SERVING_UNITS:
            return self.PER_100ML

        return self.PER_100G

    def _normalize_nutrient(
        self,
        nutrient: str,
        data: Dict[str, Any],
        basis: str,
        serving_size: Optional[float],
    ) -> Dict[str, Any]:
        """Normalize a single nutrient value to the per-100 basis.

        Values are first converted to their category base unit
        (g for mass, kcal for energy), then scaled by serving size
        when the label is declared per serving/container.
        """
        value = data.get("value")
        unit = data.get("unit")

        if value is None:
            return {"value": None, "unit": None}

        # Convert to the base unit of the value's category.
        base = self.unit_converter.to_base(value, unit or "g")

        if base is None:
            logger.warning(
                "ServingConverter: unknown unit '%s' for nutrient '%s'; "
                "keeping original value without scaling.",
                unit,
                nutrient,
            )
            base_value, base_unit = float(value), unit
        else:
            base_value, base_unit = base

        # Already declared per 100 g / 100 ml: no scaling needed.
        if basis in (self.PER_100G, self.PER_100ML):
            return {"value": round(base_value, 2), "unit": base_unit}

        # Per serving / per container: scale when serving size is known.
        if serving_size and serving_size > 0:
            scaled = (base_value / float(serving_size)) * 100
            return {"value": round(scaled, 2), "unit": base_unit}

        logger.warning(
            "ServingConverter: serving size unavailable; "
            "cannot scale nutrient '%s' to per-100 basis.",
            nutrient,
        )
        return {"value": round(base_value, 2), "unit": base_unit}


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    parsed = {
        "serving": {"size": 34.0, "unit": "g", "type": "per_serving"},
        "nutrition": {
            "energy": {"value": 160.0, "unit": "kcal"},
            "fat": {"value": 7.0, "unit": "g"},
            "sodium": {"value": 135.0, "unit": "mg"},
            "protein": {"value": 2.0, "unit": "g"},
        },
    }

    converter = ServingConverter()

    from pprint import pprint

    pprint(converter.normalize(parsed))
    print("\nOriginal preserved:")
    pprint(parsed)
