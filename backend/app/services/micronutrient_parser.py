"""Vitamin and mineral extraction service.

Extracts vitamins and minerals from OCR text into two SEPARATE
structures (never mixed into macro nutrition). All aliases (including
OCR-error variants) live in ``config/micronutrient_aliases.json`` so
the vocabulary can grow without Python changes.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_CONFIG_PATH = settings.CONFIG_FOLDER / "micronutrient_aliases.json"

# Value + unit after an alias: "60 mg", "2.5mcg", "1,8 mg", "400 IU"
_VALUE_RE = re.compile(
    r"([0-9]+(?:[.,][0-9]+)?)\s*(mcg|µg|ug|mg|g|iu)\b",
    re.I,
)

_UNIT_ALIASES = {
    "µg": "mcg",
    "ug": "mcg",
    "iu": "iu",
}


class MicronutrientParser:
    """Parses vitamins and minerals from OCR label text."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        started = time.perf_counter()

        self._config_path = config_path or _DEFAULT_CONFIG_PATH
        config = self._load_config(self._config_path)

        # alias (lowercase) -> (group, canonical)
        self._alias_map: Dict[str, Tuple[str, str]] = {}

        for group in ("vitamins", "minerals"):
            for canonical, aliases in config.get(group, {}).items():
                self._alias_map[canonical.lower().replace("_", " ")] = (
                    group, canonical,
                )
                for alias in aliases:
                    self._alias_map[self._norm(alias)] = (group, canonical)

        self._alias_re = self._compile_alias_regex(self._alias_map.keys())

        logger.info(
            "MicronutrientParser initialized with %d aliases in %.4fs.",
            len(self._alias_map),
            time.perf_counter() - started,
        )

    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(path: Path) -> Dict[str, Dict[str, List[str]]]:
        if not path.exists():
            logger.warning(
                "Micronutrient alias config not found at %s; "
                "vitamin/mineral extraction disabled.", path,
            )
            return {}

        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        return {
            key: value
            for key, value in raw.items()
            if not key.startswith("_") and isinstance(value, dict)
        }

    @staticmethod
    def _norm(label: str) -> str:
        return re.sub(r"\s+", " ", label.strip().lower())

    @staticmethod
    def _compile_alias_regex(aliases) -> Optional[re.Pattern]:
        if not aliases:
            return None

        # Longest alias first so "vitamin b12" wins over "vitamin b1".
        ordered = sorted(aliases, key=len, reverse=True)
        joined = "|".join(re.escape(alias) for alias in ordered)
        return re.compile(rf"\b(?:{joined})\b", re.I)

    # ------------------------------------------------------------------

    def parse(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Extract vitamins and minerals from OCR text.

        Returns:
            ``{"vitamins": {canonical: {value, unit}},
               "minerals": {canonical: {value, unit}}}``
            Values may be None when the label is present without a
            parseable amount (e.g. only a %DV). Never duplicates a
            micronutrient: first parsed occurrence wins.
        """
        started = time.perf_counter()

        result: Dict[str, Dict[str, Any]] = {"vitamins": {}, "minerals": {}}

        if self._alias_re is None:
            return result

        for line in text.split("\n"):

            for match in self._alias_re.finditer(line):

                key = self._norm(match.group(0))
                entry = self._alias_map.get(key)

                if entry is None:
                    continue

                group, canonical = entry

                if canonical in result[group]:
                    continue

                value, unit = self._extract_value(line, match.end())

                result[group][canonical] = {
                    "value": value,
                    "unit": unit,
                }

        logger.info(
            "MicronutrientParser found %d vitamins, %d minerals in %.4fs.",
            len(result["vitamins"]),
            len(result["minerals"]),
            time.perf_counter() - started,
        )

        return result

    # ------------------------------------------------------------------

    @staticmethod
    def _extract_value(line: str, start: int):
        """Find the first amount+unit after the alias in the line."""
        match = _VALUE_RE.search(line, start)

        if not match:
            return None, None

        value = float(match.group(1).replace(",", "."))
        unit = match.group(2).lower()
        unit = _UNIT_ALIASES.get(unit, unit)

        return value, unit


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    sample = """
    Vitamin A 250 mcg 28%
    Vitamin C 60mg
    Vltamin D 2.5 mcg 10%
    Thiamine 0,4 mg
    Vitamin B12 1.2 mcg
    Calcium 120 mg 12%
    lron 1.8mg
    Zinc 2 mg
    Potassium 250mg
    """

    parser = MicronutrientParser()

    from pprint import pprint
    pprint(parser.parse(sample))
