"""Serving information parser.

Detects the nutrition declaration basis (per 100 g, per 100 ml,
per serving, per container) and extracts the serving size from
OCR label text.

Produces a normalized serving structure:
    {"size": float | None, "unit": str | None, "type": str}
"""

import re
import time
from typing import Any, Dict, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)

_NUM = r"([0-9]+(?:[.,][0-9]+)?)"


class ServingParser:
    """Parses serving basis and serving size from label text."""

    PER_100G = "per_100g"
    PER_100ML = "per_100ml"
    PER_SERVING = "per_serving"
    PER_CONTAINER = "per_container"

    _BASIS_PATTERNS = (
        (re.compile(r"per\s*100\s*g(?:ram)?s?\b|/\s*100\s*g\b", re.I), PER_100G),
        (re.compile(r"per\s*100\s*ml\b|/\s*100\s*ml\b", re.I), PER_100ML),
        (re.compile(
            r"per\s*(?:container|pack(?:age)?|bottle|can|pouch)\b", re.I,
        ), PER_CONTAINER),
        (re.compile(
            r"per\s*serving\b|amount\s*per\s*serving|per\s*portion\b", re.I,
        ), PER_SERVING),
    )

    # "(28g)" style parenthesized weight inside a serving-size line.
    _PAREN_SIZE_RE = re.compile(rf"\(\s*(?:about\s*)?{_NUM}\s*(g|ml|l)\s*\)", re.I)

    # Bare "<number> <unit>" inside a serving-size line.
    _BARE_SIZE_RE = re.compile(rf"{_NUM}\s*(g|ml|l)\b", re.I)

    # Lines that describe the serving size.
    _SERVING_LINE_RE = re.compile(
        r"serving\s*size|servlng\s*size|serving\s*slze|"
        r"per\s*serving|portion\s*size",
        re.I,
    )

    # ------------------------------------------------------------------

    def parse(self, text: str) -> Dict[str, Any]:
        """Extract normalized serving information from OCR text.

        Returns:
            ``{"size": float|None, "unit": str|None, "type": str}``
        """
        started = time.perf_counter()

        basis = self._detect_basis(text)

        if basis == self.PER_100G:
            result = {"size": 100.0, "unit": "g", "type": basis}

        elif basis == self.PER_100ML:
            result = {"size": 100.0, "unit": "ml", "type": basis}

        else:
            size, unit = self._extract_size(text)
            result = {"size": size, "unit": unit, "type": basis}

        logger.info(
            "ServingParser result: %s (%.4fs).",
            result,
            time.perf_counter() - started,
        )

        return result

    # ------------------------------------------------------------------

    def _detect_basis(self, text: str) -> str:

        for pattern, basis in self._BASIS_PATTERNS:
            if pattern.search(text):
                logger.debug("ServingParser detected basis: %s", basis)
                return basis

        logger.debug(
            "ServingParser found no explicit basis; defaulting to %s",
            self.PER_SERVING,
        )
        return self.PER_SERVING

    # ------------------------------------------------------------------

    def _extract_size(self, text: str):
        """Find the serving size from a serving-size line.

        Prefers a parenthesized weight, e.g. "2 cookies (28 g)".
        """
        for line in text.split("\n"):

            if not self._SERVING_LINE_RE.search(line):
                continue

            match = self._PAREN_SIZE_RE.search(line)

            if match is None:
                match = self._BARE_SIZE_RE.search(line)

            if match is None:
                continue

            size = float(match.group(1).replace(",", "."))
            unit = match.group(2).lower()

            return size, unit

        return None, None

    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_size(size: Optional[float], unit: Optional[str]):
        """Normalize l -> ml so downstream converters stay simple."""
        if size is None or unit is None:
            return size, unit

        if unit == "l":
            return size * 1000.0, "ml"

        return size, unit


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    samples = [
        "Nutrition Facts\nServing Size 2 cookies (28 g)\nCalories 140",
        "Nutritional Information per 100 g\nEnergy 480 kcal",
        "Typical values per 100 ml\nEnergy 42 kcal",
        "Amount per serving\nServing Size 34 g",
        "Per container\nCalories 250",
    ]

    parser = ServingParser()

    for sample in samples:
        print(parser.parse(sample))
