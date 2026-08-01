"""Unit conversion service.

Converts parsed nutrition values into ML model features, and provides
config-driven unit normalization/base conversion helpers backed by
``config/unit_conversion.json`` (used by ServingConverter and the
micronutrient pipeline).
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_CONFIG_PATH = settings.CONFIG_FOLDER / "unit_conversion.json"


class UnitConverter:
    """
    Converts parsed nutrition values into the
    feature format expected by the ML model.
    """

    FEATURE_MAPPING = {
        "energy": "energy_100g",
        "fat": "fat_100g",
        "saturated_fat": "saturated-fat_100g",
        "carbohydrates": "carbohydrates_100g",
        "sugars": "sugars_100g",
        "fiber": "fiber_100g",
        "protein": "proteins_100g",
        "sodium": "sodium_100g"
    }

    def __init__(self, config_path: Optional[Path] = None):

        self._config_path = config_path or _DEFAULT_CONFIG_PATH

        self._unit_aliases = {}

        # unit -> (category, factor, base_unit)
        self._unit_index = {}

        self._load_config(self._config_path)

    # ----------------------------------------------------------

    def _load_config(self, path: Path) -> None:

        if not path.exists():
            logger.warning(
                "Unit conversion config not found at %s; "
                "normalize_unit/to_base will be limited.", path,
            )
            return

        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        for alias, canonical in raw.get("unit_aliases", {}).items():
            self._unit_aliases[alias.strip().lower()] = canonical.lower()

        for category, spec in raw.get("categories", {}).items():
            base_unit = spec.get("base_unit")

            for unit, factor in spec.get("units", {}).items():
                self._unit_index[unit.lower()] = (
                    category, float(factor), base_unit,
                )

        logger.info(
            "UnitConverter loaded %d units and %d aliases from config.",
            len(self._unit_index),
            len(self._unit_aliases),
        )

    # ----------------------------------------------------------

    def normalize_unit(self, unit) -> Optional[str]:
        """Return the canonical unit symbol, or None when unknown."""

        if not unit:
            return None

        candidate = str(unit).strip().lower()
        candidate = self._unit_aliases.get(candidate, candidate)

        if candidate in self._unit_index:
            return candidate

        return None

    # ----------------------------------------------------------

    def to_base(self, value, unit) -> Optional[Tuple[float, str]]:
        """Convert a value to its category base unit.

        Returns:
            ``(base_value, base_unit)`` or ``None`` when the unit
            is unknown.
        """

        canonical = self.normalize_unit(unit)

        if canonical is None or value is None:
            return None

        _category, factor, base_unit = self._unit_index[canonical]

        return float(value) * factor, base_unit

    # ----------------------------------------------------------

    def convert(self, parsed_result):

        parsed = deepcopy(parsed_result)

        serving = parsed["serving"]
        nutrition = parsed["nutrition"]

        serving_size = serving.get("size")
        serving_type = serving.get("type")

        features = {}

        for nutrient, feature_name in self.FEATURE_MAPPING.items():

            # -----------------------------
            # Nutrient not detected
            # -----------------------------
            if nutrient not in nutrition:
                features[feature_name] = None
                continue

            value = nutrition[nutrient].get("value")
            unit = nutrition[nutrient].get("unit")

            converted = self.convert_single_value(
                value=value,
                unit=unit,
                serving_size=serving_size,
                serving_type=serving_type,
                nutrient=nutrient
            )

            features[feature_name] = converted

        return features

    def convert_single_value(
        self,
        value,
        unit,
        serving_size,
        serving_type,
        nutrient
    ):

        if value is None:
            return None

        value = float(value)

        if unit is None:
            unit = "g"

        unit = unit.lower()

        # mcg -> g
        if unit == "mcg":
            value /= 1_000_000

        # mg -> g
        if unit == "mg":
            value /= 1000

        # kJ -> kcal
        if nutrient == "energy" and unit == "kj":
            value /= 4.184

        # Already per 100g or 100ml
        if serving_type in ("per_100g", "per_100ml"):
            return round(value, 2)

        # Missing serving size
        if serving_size is None:
            return round(value, 2)

        # Per serving -> per 100g/ml
        if serving_type in ("per_serving", "per_container"):

            if serving_size <= 0:
                return round(value, 2)

            value = (value / serving_size) * 100

        return round(value, 2)

    def convert_all(self, parsed_result):
        return self.convert(parsed_result)
