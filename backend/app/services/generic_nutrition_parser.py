"""Generic nutrition value parser.

Extracts ``{label, value, unit}`` entries from single OCR lines using
label-specific patterns first, then a generic ``<label> <value> <unit>``
fallback whose label is resolved later by the alias normaliser.

OCR tolerance:
    - Accepts comma decimals (``"1,5 g"``) — value is cleaned before float().
    - Accepts optional ``':'`` / ``'-'`` separators between label and value.
    - Accepts ``'<'`` / ``'less than'`` prefixes before the value.
    - Expects text to have already been through ``ocr_normaliser.normalize_text``
      so unit-separator variants (``3.3.mg``, ``3·3mg``, etc.) are already
      resolved to canonical ``"3.3 mg"`` form.
"""

import re

from app.core.logger import get_logger

logger = get_logger(__name__)

# Number tolerant of comma decimals: "7", "7.5", "7,5"
_NUM = r'([0-9]+(?:[.,][0-9]+)?)'

# Optional separators / "less than" markers between label and value.
_SEP = r'\s*[:\-]?\s*(?:<|less\s+than)?\s*'


def _to_float(raw: str) -> float:
    """Convert an OCR number (possibly comma-decimal) to float."""
    return float(raw.replace(',', '.'))


class GenericNutritionParser:

    def __init__(self):

        # Order matters: more specific patterns first.
        # Saturated Fat / Trans Fat BEFORE bare Fat.
        # Added Sugar / "of which" variants BEFORE plain Sugars.
        self.patterns = [

            # ── Energy / Calories ───────────────────────────────────────
            ('energy', re.compile(
                rf'(?:Energy|Energ[vy]|Calories|Calorles|Calorie|Cal\.?)'
                rf'{_SEP}{_NUM}\s*(kcal|kj)?',
                re.I,
            ), 'kcal'),

            # ── Added Sugar (5 patterns — most specific first) ──────────
            # A: "Includes 14g Added Sugars" (value BEFORE label)
            ('added_sugar', re.compile(
                rf'Includes{_SEP}{_NUM}\s*(g|mg)?\s*(?:of\s*)?Added\s*Sug',
                re.I,
            ), 'g'),

            # B: "of which Added Sugars 30g" / "of whichAdded 30g"
            ('added_sugar', re.compile(
                rf'of\s+which\s*added\s*sug[a-z]*{_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),

            # C: "of which added 30g" — "Sugars" absent or on next line
            ('added_sugar', re.compile(
                rf'of\s+which\s*added{_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),

            # D: "of which sugars 30g" (UK / EU phrasing)
            ('added_sugar', re.compile(
                rf'of\s+which\s+sugars?{_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),

            # E: "Added Sugars 5g" / "Added Sugar 5g"
            ('added_sugar', re.compile(
                rf'Added\s*Sug[a-z]*{_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),

            # ── Saturated Fat ───────────────────────────────────────────
            ('saturated_fat', re.compile(
                rf'(?:Saturated\s*Fat|SaturatedFat|Saturates|'
                rf'of\s*which\s*saturates){_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),

            # ── Trans Fat ───────────────────────────────────────────────
            ('trans_fat', re.compile(
                rf'(?:Trans\s*Fat|TransFat){_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),

            # ── Cholesterol ─────────────────────────────────────────────
            ('cholesterol', re.compile(
                rf'Cholest[a-z]*{_SEP}{_NUM}\s*(mg|g)?',
                re.I,
            ), 'mg'),

            # ── Total / Bare Fat ────────────────────────────────────────
            # Matches "Total Fat", "Total Fats", bare "Fat", "Fats"
            # Does NOT match "Saturated Fat" or "Trans Fat" because those
            # patterns appear EARLIER in the list and set matched_labels.
            ('fat', re.compile(
                rf'(?:Total\s*Fats?|TotalFat|(?<!\w)Fats?(?!\s*[Aa]cid))'
                rf'{_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),

            # ── Carbohydrates ───────────────────────────────────────────
            ('carbohydrates', re.compile(
                rf'(?:Total\s*Carbohydrates?|TotalCarbohydrates?|'
                rf'Carbohydrates?|Carbohydrales?|Carbs?)'
                rf'{_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),

            # ── Sugars (never "Added Sugars") ───────────────────────────
            ('sugars', re.compile(
                rf'(?<!Added\s)(?<!added\s)'
                rf'(?:Total\s*Sugars?|TotalSugars?|Sugars?)'
                rf'{_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),

            # ── Dietary Fibre ───────────────────────────────────────────
            ('fiber', re.compile(
                rf'(?:Dietary\s*Fib(?:er|re)|DietaryFib(?:er|re)|'
                rf'Fib(?:er|re)|Roughage)'
                rf'{_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),

            # ── Sodium ──────────────────────────────────────────────────
            ('sodium', re.compile(
                rf'(?:Sodium|Sodlum|S0dium){_SEP}{_NUM}\s*(mg|g)?',
                re.I,
            ), 'mg'),

            # ── Salt ────────────────────────────────────────────────────
            ('salt', re.compile(
                rf'(?:Salt|Sa1t){_SEP}{_NUM}\s*(g|mg)',
                re.I,
            ), 'g'),

            # ── Protein ─────────────────────────────────────────────────
            # Covers "Total Protein", "Plant Protein", bare "Protein",
            # and labels with a parenthetical note like "Protein (N×6.25)".
            ('protein', re.compile(
                rf'(?:(?:Total|Plant|Whey|Casein|Soy|Milk)\s+)?'
                rf'(?:Proteins?|Proteln|Prote1n|Pr0tein|Prot\.?)'
                rf'(?:\s*\([^){{0,40}}]*\))?'      # optional "(N×6.25)" etc.
                rf'{_SEP}{_NUM}\s*(g|mg)?',
                re.I,
            ), 'g'),
        ]

        # Generic fallback: "<label> <value> <unit>".
        # The raw label is returned as-is and resolved by the alias normaliser.
        self.fallback = re.compile(
            rf'^\s*([A-Za-z][A-Za-z .:\-\'()]{{1,50}}?)'
            rf'{_SEP}{_NUM}\s*(g|mg|mcg|kcal|kj)\b',
            re.I,
        )

    # ------------------------------------------------------------------

    def extract_nutrients(self, line: str):
        """Extract all nutrient entries from a single (normalised) line.

        Returns a list of dicts: ``[{"label", "value", "unit"}, ...]``.
        An empty list means no nutrient was recognised on this line.
        """
        nutrients = []
        matched_labels = set()

        for label, pattern, default_unit in self.patterns:

            # Skip if we already found this label on this line
            if label in matched_labels:
                continue

            m = pattern.search(line)
            if not m:
                continue

            value = _to_float(m.group(1))
            unit = m.group(2) if m.lastindex and m.lastindex >= 2 else None
            unit = (unit or default_unit).lower()

            nutrients.append({'label': label, 'value': value, 'unit': unit})
            matched_labels.add(label)

        if nutrients:
            return nutrients

        # Fallback: generic "<label> <value> <unit>" (alias-resolved later)
        m = self.fallback.search(line)
        if m:
            raw_label = m.group(1).strip()
            value = _to_float(m.group(2))
            unit = m.group(3).lower()
            logger.debug(
                'GenericNutritionParser fallback: label=%r value=%s unit=%s',
                raw_label, value, unit,
            )
            nutrients.append({'label': raw_label, 'value': value, 'unit': unit})

        return nutrients


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    _LINES = [
        'Energy 374 kcal',
        'Total Fat 8 g',
        'Saturated Fat 3 g',
        'Trans Fat 0 g',
        'Carbohydrate 34 g',
        'Total Sugars 52 g',
        'of whichAdded 30 g',
        'Dietary Fiber 3.5 g',
        'Protein 5 g',
        'Total Protein 7.0 g',
        'Sodium 120 mg',
        'Salt 0.3 g',
    ]

    parser = GenericNutritionParser()
    for ln in _LINES:
        result = parser.extract_nutrients(ln)
        print(f'{ln!r:50s} → {result}')
