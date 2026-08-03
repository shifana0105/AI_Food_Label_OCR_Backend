"""Vitamin and mineral extraction service — redesigned multi-stage parser.

Stage 1  OCR normalisation is applied first (via ``app.utils.ocr_normalizer``).
Stage 2  Each line is classified:
            LABEL_VALUE – canonical name + numeric value on the same line
            LABEL       – canonical name only, value expected on a later line
            VALUE       – bare number + unit, not preceded by a known name
            PERCENT     – percentage-only line (e.g. "100%")  →  skipped
            SKIP        – all other text
Stage 3  Labels are paired with values using sequential structural association:
            1. Same-line value wins (LABEL_VALUE).
            2. For a LABEL-only line, the parser scans forward for the
               next available VALUE line, skipping PERCENT lines.
            3. The scan stops (no value assigned) as soon as another
               LABEL or LABEL_VALUE line is encountered, ensuring that
               no value is ever "shifted" to a wrong nutrient.
            4. Each VALUE line is consumed at most once.

This design fixes all known vitamin-value-shifting bugs (BUG 1-4) and
the unit-precision loss bug (BUG 5) without requiring hundreds of
brand-specific aliases.  All vocabulary lives in
``config/micronutrient_aliases.json``.
"""

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logger import get_logger
from app.utils.ocr_normalizer import normalize_text

logger = get_logger(__name__)

_DEFAULT_CONFIG_PATH = settings.CONFIG_FOLDER / 'micronutrient_aliases.json'

# ---------------------------------------------------------------------------
# Value regex — applied AFTER OCR normalisation so all unit-separator
# variants have already been cleaned up.
# ---------------------------------------------------------------------------
_VALUE_RE = re.compile(
    r'([0-9]+(?:\.[0-9]+)?)'     # integer or decimal (no comma — normaliser fixes those)
    r'\s*'
    r'(mcg|mg|g|iu)\b',
    re.I,
)

_UNIT_ALIASES: Dict[str, str] = {
    'iu': 'iu',
}

# A "bare value" line is one that starts (after optional whitespace /
# comparison symbols) with a number-unit pair and contains nothing else
# substantial.  These are the VALUE lines we pair with preceding labels.
_BARE_VALUE_RE = re.compile(
    r'^\s*'
    r'[<>≤≥~±]?\s*'
    r'[0-9]+(?:\.[0-9]+)?\s*'
    r'(?:mcg|mg|g|iu)\b'
    r'[\s%()0-9.]*$',             # allow trailing %DV annotation
    re.I,
)

# Percentage-only lines like "100%", "28%", "10 %"
_PERCENT_ONLY_RE = re.compile(r'^\s*\d+(?:\.\d+)?\s*%\s*$')

# ---------------------------------------------------------------------------
# Validation: maximum plausible values per unit to reject OCR garbage.
# A mineral or vitamin listed at "500 g" is physically impossible.
# ---------------------------------------------------------------------------
_MAX_VALUES: Dict[str, float] = {
    'g':   50.0,      # no single micro/macro nutrient > 50 g per serving
    'mg':  10_000.0,  # very high; e.g. sodium can approach 2000 mg
    'mcg': 100_000.0, # high tolerable limit for e.g. Vitamin A (3000 mcg RDA)
    'iu':  100_000.0,
}


class MicronutrientParser:
    """Extracts vitamins and minerals from OCR label text.

    Uses a classification + sequential-pairing approach to avoid
    value-shifting between nutrients.
    """

    # ------------------------------------------------------------------

    def __init__(self, config_path: Optional[Path] = None) -> None:
        started = time.perf_counter()

        self._config_path = config_path or _DEFAULT_CONFIG_PATH
        config = self._load_config(self._config_path)

        # alias (lowercase, whitespace-normalised) → (group, canonical)
        self._alias_map: Dict[str, Tuple[str, str]] = {}

        for group in ('vitamins', 'minerals'):
            for canonical, aliases in config.get(group, {}).items():
                # Register the canonical name itself
                self._alias_map[self._norm(canonical.replace('_', ' '))] = (
                    group, canonical,
                )
                for alias in aliases:
                    self._alias_map[self._norm(alias)] = (group, canonical)

        self._alias_re = self._build_alias_re(self._alias_map.keys())

        logger.info(
            'MicronutrientParser initialized with %d aliases in %.4fs.',
            len(self._alias_map),
            time.perf_counter() - started,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(path: Path) -> Dict:
        if not path.exists():
            logger.warning(
                'Micronutrient alias config not found at %s; '
                'vitamin/mineral extraction disabled.', path,
            )
            return {}
        with path.open('r', encoding='utf-8') as fh:
            raw = json.load(fh)
        return {k: v for k, v in raw.items()
                if not k.startswith('_') and isinstance(v, dict)}

    @staticmethod
    def _norm(label: str) -> str:
        return re.sub(r'\s+', ' ', label.strip().lower())

    @staticmethod
    def _build_alias_re(aliases) -> Optional[re.Pattern]:
        if not aliases:
            return None
        ordered = sorted(aliases, key=len, reverse=True)
        joined = '|'.join(re.escape(a) for a in ordered)
        return re.compile(rf'\b(?:{joined})\b', re.I)

    # ------------------------------------------------------------------
    # Value extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_value(text: str, start: int = 0) -> Tuple[Optional[float], Optional[str]]:
        """Return (value, unit) from *text* starting at *start*, or (None, None)."""
        m = _VALUE_RE.search(text, start)
        if not m:
            return None, None
        val = float(m.group(1))
        unit = m.group(2).lower()
        unit = _UNIT_ALIASES.get(unit, unit)
        # Reject physically impossible values
        if val > _MAX_VALUES.get(unit, float('inf')):
            return None, None
        return val, unit

    # ------------------------------------------------------------------
    # Line classification (Stage 2)
    # ------------------------------------------------------------------

    def _classify(self, lines: List[str]) -> List[Tuple[str, Any]]:
        """Classify each (already OCR-normalised) line.

        Returns a list of tuples:
            ('LABEL_VALUE', (group, canonical, value, unit))
            ('LABEL',       (group, canonical))
            ('VALUE',       (value, unit))
            ('PERCENT',     None)
            ('SKIP',        None)
        """
        result: List[Tuple[str, Any]] = []

        for raw in lines:
            line = raw.strip()

            # Empty
            if not line:
                result.append(('SKIP', None))
                continue

            # Percentage-only
            if _PERCENT_ONLY_RE.match(line):
                result.append(('PERCENT', None))
                continue

            # Try alias match
            alias_hit = self._alias_re.search(line) if self._alias_re else None

            if alias_hit:
                key = self._norm(alias_hit.group(0))
                entry = self._alias_map.get(key)

                if entry:
                    group, canonical = entry
                    # Look for a value AFTER the alias on the same line
                    value, unit = self._extract_value(line, alias_hit.end())
                    if value is not None:
                        result.append(('LABEL_VALUE', (group, canonical, value, unit)))
                    else:
                        result.append(('LABEL', (group, canonical)))
                    continue

            # No alias — check if it is a bare value line
            if _BARE_VALUE_RE.match(line):
                value, unit = self._extract_value(line, 0)
                if value is not None:
                    result.append(('VALUE', (value, unit)))
                    continue

            result.append(('SKIP', None))

        return result

    # ------------------------------------------------------------------
    # Label-value association (Stage 3)
    # ------------------------------------------------------------------

    @staticmethod
    def _pair(classified: List[Tuple[str, Any]]) -> Dict[str, Tuple[str, Optional[float], Optional[str]]]:
        """Associate each label with its value.

        Rules (in priority order):
        1. LABEL_VALUE lines → direct extraction (no scan needed).
        2. LABEL lines       → scan forward for the next unconsumed VALUE,
                               skipping PERCENT; stop at any other LABEL.
        3. Each VALUE line is consumed (used) at most once.

        Returns: { canonical → (group, value, unit) }
        """
        result: Dict[str, Tuple[str, Optional[float], Optional[str]]] = {}
        consumed: set = set()  # indices of VALUE lines already assigned

        n = len(classified)

        for i, (ltype, ldata) in enumerate(classified):

            if ltype == 'LABEL_VALUE':
                group, canonical, value, unit = ldata
                if canonical not in result:
                    result[canonical] = (group, value, unit)

            elif ltype == 'LABEL':
                group, canonical = ldata
                if canonical in result:
                    continue

                # Scan forward for the next available VALUE
                found = False
                for j in range(i + 1, n):
                    if j in consumed:
                        continue
                    jtype, jdata = classified[j]

                    if jtype == 'PERCENT' or jtype == 'SKIP':
                        # Skip %DV-only / empty lines
                        continue

                    if jtype == 'VALUE':
                        value, unit = jdata
                        result[canonical] = (group, value, unit)
                        consumed.add(j)
                        found = True
                        break

                    # LABEL or LABEL_VALUE → next nutrient starts, stop
                    break

                if not found and canonical not in result:
                    result[canonical] = (group, None, None)

        return result

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, text: str) -> Dict[str, Dict[str, Any]]:
        """Extract vitamins and minerals from *text*.

        The text is OCR-normalised before classification so all
        downstream matching sees clean, structurally consistent tokens.

        Returns:
            ``{"vitamins": {canonical: {"value": v, "unit": u}},
               "minerals": {canonical: {"value": v, "unit": u}}}``
        """
        started = time.perf_counter()
        result: Dict[str, Dict[str, Any]] = {'vitamins': {}, 'minerals': {}}

        if self._alias_re is None:
            return result

        # Stage 1 – OCR normalisation (per line)
        norm_text = normalize_text(text)

        # Strip everything from the ingredient-section header onwards.
        # This prevents mineral names inside ingredient lists (e.g.
        # "Calcium Phosphate") from being mis-classified as nutrients.
        ing_match = re.search(r'\bingredients?\b', norm_text, re.I)
        if ing_match:
            norm_text = norm_text[:ing_match.start()]

        lines = norm_text.split('\n')

        # Stage 2 – classify lines
        classified = self._classify(lines)

        # Stage 3 – pair labels with values
        paired = self._pair(classified)

        # Build result dict
        for canonical, (group, value, unit) in paired.items():
            result[group][canonical] = {'value': value, 'unit': unit}

        logger.info(
            'MicronutrientParser found %d vitamins, %d minerals in %.4fs.',
            len(result['vitamins']),
            len(result['minerals']),
            time.perf_counter() - started,
        )

        return result


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    sample = """
    Nutrition Information
    Serving size 30g
    Energy 374 kcal

    VitaminA
    1000 mcg
    100%
    VitaminD
    16.7 mcg
    83%
    VitaminE
    5 mg
    50%
    VitaminK
    15 mcg
    19%
    Vitamin C 60 mg
    Vitamin81
    2 mg
    Vitamin82
    2.3 mg
    Vitamin83
    26.6 mg
    Vltamin D 2.5 mcg

    Calcium 120 mg
    lron 1.8 mg
    Zinc
    3.3 mg
    Magnesium 25 mg

    INGREDIENTS: Wheat Flour, Sugar, ...
    Calcium Phosphate (this must NOT be extracted as calcium)
    """

    parser = MicronutrientParser()
    from pprint import pprint
    pprint(parser.parse(sample))
