"""Nutrient alias normalization service.

Normalizes raw nutrient labels found on food packaging (e.g. "Proteins",
"Prot.", "Dietary Fibre") into canonical nutrient names (e.g. "protein",
"fiber"). All aliases live in ``config/nutrient_aliases.json`` so the
vocabulary can grow without any Python change.
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_CONFIG_PATH = settings.CONFIG_FOLDER / "nutrient_aliases.json"


class NutrientNormalizer:
    """Maps nutrient label aliases to canonical nutrient names.

    The alias table is loaded once at construction time from a JSON
    configuration file and compiled into a flat lowercase lookup index
    for O(1) matching.
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        started = time.perf_counter()
        logger.info("NutrientNormalizer initialization started.")

        self._config_path = config_path or _DEFAULT_CONFIG_PATH
        aliases = self._load_config(self._config_path)
        self._alias_index = self._build_index(aliases)
        self._canonical_names = frozenset(aliases.keys())

        logger.info(
            "NutrientNormalizer initialized with %d canonical nutrients "
            "and %d aliases in %.4fs.",
            len(self._canonical_names),
            len(self._alias_index),
            time.perf_counter() - started,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(path: Path) -> Dict[str, List[str]]:
        """Load the alias configuration, skipping metadata keys."""
        if not path.exists():
            logger.warning(
                "Nutrient alias config not found at %s; "
                "normalizer will only match canonical names.",
                path,
            )
            return {}

        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        return {
            canonical: alias_list
            for canonical, alias_list in raw.items()
            if not canonical.startswith("_") and isinstance(alias_list, list)
        }

    @staticmethod
    def _build_index(aliases: Dict[str, List[str]]) -> Dict[str, str]:
        """Compile a flat ``alias -> canonical`` lowercase lookup index."""
        index: Dict[str, str] = {}

        for canonical, alias_list in aliases.items():
            index[canonical.lower()] = canonical
            for alias in alias_list:
                index[NutrientNormalizer._normalize_key(alias)] = canonical

        return index

    @staticmethod
    def _normalize_key(label: str) -> str:
        """Lowercase and collapse whitespace for stable matching."""
        return re.sub(r"\s+", " ", label.strip().lower())

    # ------------------------------------------------------------------

    @property
    def canonical_nutrients(self) -> FrozenSet[str]:
        """The set of canonical nutrient names known to the normalizer."""
        return self._canonical_names

    def normalize(self, label: str) -> Optional[str]:
        """Return the canonical name for a raw nutrient label.

        Args:
            label: Raw label text, e.g. ``"Total Sugars"`` or ``"Prot."``.

        Returns:
            The canonical nutrient name, or ``None`` when unknown.
        """
        if not label:
            return None

        return self._alias_index.get(self._normalize_key(label))


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    normalizer = NutrientNormalizer()

    tests = [
        "Protein",
        "Proteins",
        "Prot.",
        "Calories",
        "Energy",
        "Dietary Fibre",
        "Fiber",
        "Total Sugar",
        "Sugars",
        "Serving Size",
        "Unknown Thing",
    ]

    for t in tests:
        print(f"{t} -> {normalizer.normalize(t)}")
