"""Ingredient list extraction service.

Extracts the ordered ingredients list from OCR label text.

Handles:
    - OCR mistakes in the "Ingredients" header (Ingredlents, 1ngredients)
    - Multi-line and wrapped ingredient lists
    - Commas inside parentheses/brackets (never split there)
    - Terminator sections (allergen statements, nutrition panel, etc.)

When *raw_text* (the line-per-line OCR output before TextProcessor
merging) is supplied to :meth:`extract`, the parser uses it for
block collection.  This correctly handles food labels where each
ingredient appears on its own line *without* a trailing comma — a
layout that otherwise causes TextProcessor to merge all ingredient
names into a single space-separated blob.

Ingredients are returned in their ORIGINAL label order and are NOT
classified in any way.
"""

import re
import time
from typing import List, Optional

from app.core.logger import get_logger

logger = get_logger(__name__)

# "Ingredients:\" header, tolerant of common OCR confusions.
_HEADER_RE = re.compile(
    r"\b(?:ingredients?|ingred[il1]ents?|lngredients?|1ngredients?)\b\s*[:\-]?",
    re.I,
)

# Lines that mark the END of the ingredient list.
_TERMINATOR_RE = re.compile(
    r"^\s*(?:"
    r"contains?(?:\s+and\b)?\s+\w|\bmay\s+contain|allerg[ey]n|allergy\s+advice|"
    r"nutrition|nutritional|serving|per\s+100|energy|calories|"
    r"manufactured|marketed|packed|produced|imported|"
    r"store\b|storage|keep\s+in|best\s+before|use\s+by|expiry|exp\.|"
    r"net\s+(?:wt|weight|quantity)|batch|mrp|customer\s+care|"
    r"directions|how\s+to|preparation|method|"
    r"manufacturer|marketed\s+by"
    r")",
    re.I,
)

# Tokens that are clearly not ingredients (pure numbers, percents, codes).
_JUNK_TOKEN_RE = re.compile(r"^[\d\s.,%()[\]\-]*$")


class IngredientExtractor:
    """Extracts an ordered ingredient list from OCR text."""

    def extract(
        self,
        text: str,
        raw_text: Optional[str] = None,
    ) -> List[str]:
        """Return the ingredient list in original order.

        Args:
            text:     Merged/cleaned OCR text (from TextProcessor).
            raw_text: Optional unmerged text (one OCR line per line).
                      When supplied, the ingredient block is collected
                      from *raw_text* so that line-per-line ingredient
                      layouts (no trailing commas) are split correctly.

        Returns:
            List of ingredient strings; empty when no ingredient
            section is found.
        """
        started = time.perf_counter()

        # Prefer raw_text for collection so each OCR line is a
        # potential ingredient boundary.  Fall back to merged text.
        source = raw_text if raw_text is not None else text

        block = self._collect_block(source)

        if not block:
            # Last-chance fallback: try the merged text if raw_text
            # collection found nothing (e.g. header only visible
            # after TextProcessor normalization).
            if raw_text is not None:
                block = self._collect_block(text)

        if not block:
            logger.info("IngredientExtractor: no ingredient section found.")
            return []

        ingredients = self._split_ingredients(block)

        logger.info(
            "IngredientExtractor extracted %d ingredients in %.4fs.",
            len(ingredients),
            time.perf_counter() - started,
        )

        return ingredients

    # ------------------------------------------------------------------

    def _collect_block(self, text: str) -> str:
        """Collect the raw ingredient text between header and terminator.

        Joins wrapped/multi-line content into a single string.
        When consecutive collected lines don't already end with a
        comma or semicolon, a ``", "`` separator is inserted so that
        ``_split_ingredients`` can correctly split them.
        """
        lines = text.split("\n")

        collected: List[str] = []
        in_section = False

        for raw_line in lines:

            line = re.sub(r"\s+", " ", raw_line).strip()

            if not line:
                continue

            if not in_section:
                header = _HEADER_RE.search(line)

                if header:
                    in_section = True
                    remainder = line[header.end():].strip()

                    if remainder:
                        collected.append(remainder)

                continue

            # Inside the section: stop at terminators.
            if _TERMINATOR_RE.search(line):
                break

            collected.append(line)

        if not collected:
            return ""

        # Join lines, adding ", " between items that don't already
        # end with a comma or semicolon.  This handles the case where
        # each ingredient appears on its own line without a trailing
        # comma.
        parts: List[str] = []
        for segment in collected:
            if parts and not parts[-1].rstrip().endswith((",", ";")):
                parts.append(", ")
            parts.append(segment)

        return "".join(parts).strip()

    # ------------------------------------------------------------------

    def _split_ingredients(self, block: str) -> List[str]:
        """Split on commas/semicolons at parenthesis depth 0 only."""

        tokens: List[str] = []
        current: List[str] = []
        depth = 0

        for char in block:

            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth = max(0, depth - 1)

            if char in ",;" and depth == 0:
                tokens.append("".join(current))
                current = []
            else:
                current.append(char)

        tokens.append("".join(current))

        ingredients: List[str] = []

        for token in tokens:
            cleaned = self._clean_token(token)

            if cleaned:
                ingredients.append(cleaned)

        return ingredients

    # ------------------------------------------------------------------

    @staticmethod
    def _clean_token(token: str) -> str:
        """Normalize a single ingredient token; return '' when junk."""

        token = token.strip()
        token = token.rstrip(".")
        token = re.sub(r"\s+", " ", token).strip()

        if len(token) < 2:
            return ""

        if _JUNK_TOKEN_RE.match(token):
            return ""

        return token


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    # Case 1: comma-terminated multi-line (typical)
    sample_merged = """
    Net Wt: 100 g
    INGREDIENTS: Wheat Flour, Sugar, Palm Oil,
    Cocoa Powder (12%), Corn Starch,
    Raising Agents (INS 500(ii), INS 503(ii)),
    Salt,
    Emulsifier (Soy Lecithin).
    Contains Wheat and Soy.
    Nutrition Facts
    Energy 480 kcal
    """

    # Case 2: one ingredient per line (no trailing commas)
    sample_raw = """
    INGREDIENTS:
    Skimmed Milk Powder
    Protein Products (Soy Protein Isolate)
    Barley Malt Extract
    Millet Extract
    Cocoa Solids
    Sugar
    Contains Wheat and Milk.
    """

    extractor = IngredientExtractor()

    print("=== Case 1: comma-terminated ===")
    for ing in extractor.extract(sample_merged):
        print(f"  - {ing}")

    print("\n=== Case 2: one-per-line (raw_text) ===")
    for ing in extractor.extract("", raw_text=sample_raw):
        print(f"  - {ing}")
