"""Generic nutrition value parser.

Extracts ``{label, value, unit}`` entries from single OCR lines using
label-specific patterns first, then a generic ``<label> <value> <unit>``
fallback whose label is resolved later by the alias normalizer.

OCR tolerance:
    - accepts comma decimals ("1,5 g")
    - accepts optional ':' / '-' separators
    - accepts '<' / 'less than' prefixes before the value
"""

import re

from app.core.logger import get_logger

logger = get_logger(__name__)

# Number tolerant of comma decimals: "7", "7.5", "7,5"
_NUM = r"([0-9]+(?:[.,][0-9]+)?)"

# Optional separators / "less than" markers between label and value.
_SEP = r"\s*[:\-]?\s*(?:<|less\s+than)?\s*"


def _to_float(raw: str) -> float:
    """Convert an OCR number (possibly comma-decimal) to float."""
    return float(raw.replace(",", "."))


class GenericNutritionParser:

    def __init__(self):

        # Order matters: specific labels first (e.g. "Saturated Fat"
        # before "Fat", "Added Sugars" before "Sugars").
        # Each entry: (label, pattern, default_unit)
        self.patterns = [

            ("energy", re.compile(
                rf"(?:Energy|Energ[vy]|Calories|Calorles|Calorie)"
                rf"{_SEP}{_NUM}\s*(kcal|kj)?",
                re.I,
            ), "kcal"),

            # "Includes 14g Added Sugars" (value BEFORE label)
            ("added_sugar", re.compile(
                rf"Includes{_SEP}{_NUM}\s*(g|mg)?\s*(?:of\s*)?Added\s*Sug",
                re.I,
            ), "g"),

            # "Added Sugars 5g"
            ("added_sugar", re.compile(
                rf"Added\s*Sug[a-z]*{_SEP}{_NUM}\s*(g|mg)?",
                re.I,
            ), "g"),

            ("saturated_fat", re.compile(
                rf"(?:Saturated\s*Fat|SaturatedFat|Saturates|"
                rf"of\s*which\s*saturates){_SEP}{_NUM}\s*(g|mg)?",
                re.I,
            ), "g"),

            ("trans_fat", re.compile(
                rf"(?:Trans\s*Fat|TransFat){_SEP}{_NUM}\s*(g|mg)?",
                re.I,
            ), "g"),

            ("cholesterol", re.compile(
                rf"Cholest[a-z]*{_SEP}{_NUM}\s*(mg|g)?",
                re.I,
            ), "mg"),

            # Total fat only (never bare "Fat" here; the fallback +
            # normalizer handles bare "Fat 7g" safely).
            ("fat", re.compile(
                rf"(?:Total\s*Fats?|TotalFat){_SEP}{_NUM}\s*(g|mg)?",
                re.I,
            ), "g"),

            ("carbohydrates", re.compile(
                rf"(?:Total\s*Carbohydrates?|TotalCarbohydrates?|"
                rf"Carbohydrates?|Carbohydrales?|Carbs?)"
                rf"{_SEP}{_NUM}\s*(g|mg)?",
                re.I,
            ), "g"),

            # Sugars, but never when preceded by "Added ".
            ("sugars", re.compile(
                rf"(?<![Aa]dded\s)(?:Total\s*Sugars?|TotalSugars?|Sugars?)"
                rf"{_SEP}{_NUM}\s*(g|mg)?",
                re.I,
            ), "g"),

            ("fiber", re.compile(
                rf"(?:Dietary\s*Fib[er]{{2}}|DietaryFib[er]{{2}}|"
                rf"Fib[er]{{2}}){_SEP}{_NUM}\s*(g|mg)?",
                re.I,
            ), "g"),

            ("sodium", re.compile(
                rf"(?:Sodium|Sodlum|S0dium){_SEP}{_NUM}\s*(mg|g)?",
                re.I,
            ), "mg"),

            ("salt", re.compile(
                rf"(?:Salt|Sa1t){_SEP}{_NUM}\s*(g|mg)",
                re.I,
            ), "g"),

            ("protein", re.compile(
                rf"(?:Proteins?|Proteln|Prote1n|Prot\.?)"
                rf"{_SEP}{_NUM}\s*(g|mg)?",
                re.I,
            ), "g"),
        ]

        # Generic fallback: "<label> <value> <unit>". The raw label is
        # returned as-is and resolved via the config-driven alias
        # normalizer, so brand-specific wording is handled by config,
        # not hardcoded rules.
        self.fallback = re.compile(
            rf"^\s*([A-Za-z][A-Za-z .\-']{{1,40}}?)"
            rf"{_SEP}{_NUM}\s*(g|mg|mcg|kcal|kj)\b",
            re.I,
        )

    # ------------------------------------------------------------------

    def extract_nutrients(self, line: str):

        nutrients = []
        matched_labels = set()

        for label, pattern, default_unit in self.patterns:

            if label in matched_labels:
                continue

            match = pattern.search(line)

            if not match:
                continue

            value = _to_float(match.group(1))

            unit = match.group(2) if match.lastindex and match.lastindex >= 2 else None
            unit = (unit or default_unit).lower()

            nutrients.append({
                "label": label,
                "value": value,
                "unit": unit,
            })
            matched_labels.add(label)

        if nutrients:
            return nutrients

        # Fallback: generic "<label> <value> <unit>" (alias-resolved later).
        match = self.fallback.search(line)

        if match:
            raw_label = match.group(1).strip()
            value = _to_float(match.group(2))
            unit = match.group(3).lower()

            logger.debug(
                "GenericNutritionParser fallback matched label=%r "
                "value=%s unit=%s", raw_label, value, unit,
            )

            nutrients.append({
                "label": raw_label,
                "value": value,
                "unit": unit,
            })

        return nutrients
