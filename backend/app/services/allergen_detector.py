"""Allergen detection service.

Detects allergens from the extracted ingredient list and full OCR label
text. All allergen keyword groups live in ``config/allergen_keywords.json``
so the vocabulary can be extended (or trimmed) without any Python change.

Implements the :class:`~app.services.interfaces.AllergenDetector` Protocol
defined in ``app.services.interfaces``.

Detection strategy
------------------
1. **Ingredient scan**: join all parsed ingredient strings and scan for
   keyword matches (word-boundary, case-insensitive).
2. **Full-text scan**: scan the entire OCR text including any explicit
   ``Contains: ...`` declarations that may mention allergens not listed
   as ingredients (e.g. ``"May contain traces of nuts"``).
3. **Union**: results from both scans are deduplicated and returned in
   sorted order.

``detect_combined`` is the primary entry point used by the pipeline.
``detect`` and ``detect_from_text`` are available for standalone use.
"""

import json
import re
import time
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_CONFIG_PATH = settings.CONFIG_FOLDER / "allergen_keywords.json"


class AllergenDetector:
    """Detects allergens from ingredient lists and OCR label text.

    Usage::

        detector = AllergenDetector()
        allergens = detector.detect_combined(ingredients, clean_text)
    """

    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Load the allergen keyword config.

        Args:
            config_path: Optional override path to ``allergen_keywords.json``.
                Defaults to ``config/allergen_keywords.json``.
        """
        started = time.perf_counter()

        self._config_path = config_path or _DEFAULT_CONFIG_PATH
        self._allergen_map: Dict[str, List[str]] = self._load_config(
            self._config_path
        )

        logger.info(
            "AllergenDetector initialized with %d allergen groups in %.4fs.",
            len(self._allergen_map),
            time.perf_counter() - started,
        )

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(path: Path) -> Dict[str, List[str]]:
        """Load and validate the allergen keyword JSON config.

        Skips keys starting with ``_`` (metadata comments).

        Returns:
            Mapping of ``allergen_group -> [lowercase_keyword, ...]``.
        """
        if not path.exists():
            logger.warning(
                "Allergen config not found at %s; allergen detection "
                "will return empty results.",
                path,
            )
            return {}

        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        return {
            group: [kw.lower() for kw in keywords]
            for group, keywords in raw.get("allergens", {}).items()
            if not group.startswith("_") and isinstance(keywords, list)
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(self, ingredients: List[str]) -> List[str]:
        """Detect allergens from a parsed ingredient list.

        Args:
            ingredients: Ordered ingredient strings as extracted from the
                label. Each string is individually scanned.

        Returns:
            Sorted list of detected allergen group names.
        """
        joined = " ".join(ingredients).lower()
        return self._scan(joined)

    def detect_from_text(self, text: str) -> List[str]:
        """Detect allergens from full OCR label text.

        Scans the entire text body including any explicit ``Contains:``
        and ``May contain:`` declarations.

        Args:
            text: Full OCR text of the label (already cleaned).

        Returns:
            Sorted list of detected allergen group names.
        """
        return self._scan(text.lower())

    def detect_combined(
        self,
        ingredients: List[str],
        text: str,
    ) -> List[str]:
        """Union of allergens found in the ingredient list and label text.

        This is the primary method used by the nutrition parsing pipeline.

        Args:
            ingredients: Parsed ingredient list.
            text: Full OCR text of the label.

        Returns:
            Sorted, deduplicated list of allergen group names.
        """
        started = time.perf_counter()

        from_ingredients = set(self.detect(ingredients))
        from_text = set(self.detect_from_text(text))
        combined = sorted(from_ingredients | from_text)

        logger.info(
            "AllergenDetector found %d allergen(s) in %.4fs: %s",
            len(combined),
            time.perf_counter() - started,
            combined or "none",
        )
        return combined

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _scan(self, lower_text: str) -> List[str]:
        """Scan lowercased text for all configured allergen keyword groups.

        Uses whole-word (``\\b``) matching so ``"wheat"`` does not trigger
        inside ``"buckwheat"``.

        Args:
            lower_text: Pre-lowercased text to scan.

        Returns:
            Sorted list of allergen group names that matched.
        """
        detected: set = set()

        for group, keywords in self._allergen_map.items():
            for keyword in keywords:
                # Sort longest keywords first inside each group to avoid
                # short fragments pre-empting more specific matches.
                pattern = rf"\b{re.escape(keyword)}\b"
                if re.search(pattern, lower_text):
                    detected.add(group)
                    break  # One keyword match per group is sufficient.

        return sorted(detected)


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    sample_ingredients = [
        "Wheat Flour",
        "Sugar",
        "Palm Oil",
        "Cocoa Powder (12%)",
        "Corn Starch",
        "Raising Agents (INS 500(ii))",
        "Salt",
        "Emulsifier (Soy Lecithin)",
    ]

    sample_text = """
    INGREDIENTS: Wheat Flour, Sugar, Palm Oil,
    Cocoa Powder (12%), Corn Starch,
    Raising Agents (INS 500(ii)), Salt,
    Emulsifier (Soy Lecithin).
    Contains Wheat and Soy.
    """

    detector = AllergenDetector()

    print("\n--- Allergens from ingredients ---")
    print(detector.detect(sample_ingredients))

    print("\n--- Allergens from text ---")
    print(detector.detect_from_text(sample_text))

    print("\n--- Combined ---")
    print(detector.detect_combined(sample_ingredients, sample_text))
