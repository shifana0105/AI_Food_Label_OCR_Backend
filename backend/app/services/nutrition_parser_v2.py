"""Nutrition Parser V2.

Orchestrates the full label parsing flow:

    OCR text
        -> ServingParser          (basis + serving size)
        -> NutritionLineExtractor (nutrition lines only)
        -> GenericNutritionParser (label/value/unit per line)
        -> NutrientNormalizer     (config-driven alias mapping)
        -> MicronutrientParser    (vitamins + minerals, separate)
        -> IngredientExtractor    (ordered ingredient list)

Nutrients are never duplicated: the first parsed occurrence wins.
Salt is converted to sodium (1 g salt = 400 mg sodium) when sodium
itself is not declared.
"""

from typing import Dict

from app.core.logger import get_logger
from app.services.nutrition_line_extractor import NutritionLineExtractor
from app.services.generic_nutrition_parser import GenericNutritionParser
from app.services.nutrient_normalizer import NutrientNormalizer
from app.services.micronutrient_parser import MicronutrientParser
from app.services.ingredient_extractor import IngredientExtractor
from app.services.serving_parser import ServingParser

logger = get_logger(__name__)

# 1 g of salt contains 400 mg of sodium (salt = sodium x 2.5).
_SALT_TO_SODIUM_MG_PER_G = 400.0


class NutritionParserV2:

    def __init__(self):

        self.extractor = NutritionLineExtractor()
        self.parser = GenericNutritionParser()
        self.normalizer = NutrientNormalizer()
        self.micronutrients = MicronutrientParser()
        self.ingredients = IngredientExtractor()
        self.serving_parser = ServingParser()

    # ------------------------------------------------------------------

    def parse(self, text: str) -> Dict:

        result = {
            "serving": self.serving_parser.parse(text),
            "nutrition": {},
            "vitamins": {},
            "minerals": {},
            "ingredients": [],
        }

        lines = self.extractor.extract(text)

        logger.debug("Extracted %d nutrition lines.", len(lines))

        for line in lines:

            parsed_list = self.parser.extract_nutrients(line)

            if not parsed_list:
                continue

            logger.debug("LINE %r -> %s", line, parsed_list)

            for parsed in parsed_list:

                canonical = self.normalizer.normalize(parsed["label"])

                if canonical is None:
                    logger.debug(
                        "Unmapped nutrient label skipped: %r",
                        parsed["label"],
                    )
                    continue

                # Serving handled by ServingParser; only fill gaps here.
                if canonical == "serving":

                    if result["serving"]["size"] is None:
                        result["serving"]["size"] = parsed["value"]
                        result["serving"]["unit"] = parsed["unit"]
                    continue

                # ------------------------------------------
                # Never duplicate: first detection wins.
                # ------------------------------------------
                if canonical in result["nutrition"]:
                    continue

                result["nutrition"][canonical] = {
                    "value": parsed["value"],
                    "unit": parsed["unit"],
                }

        self._derive_sodium_from_salt(result["nutrition"])

        # Vitamins & minerals: stored SEPARATELY from nutrition.
        micro = self.micronutrients.parse(text)
        result["vitamins"] = micro["vitamins"]
        result["minerals"] = micro["minerals"]

        # Ingredients in original order (no classification).
        result["ingredients"] = self.ingredients.extract(text)

        logger.info(
            "NutritionParserV2 parsed %d nutrients, %d vitamins, "
            "%d minerals, %d ingredients (serving=%s).",
            len(result["nutrition"]),
            len(result["vitamins"]),
            len(result["minerals"]),
            len(result["ingredients"]),
            result["serving"],
        )

        return result

    # ------------------------------------------------------------------

    @staticmethod
    def _derive_sodium_from_salt(nutrition: Dict) -> None:
        """Convert declared salt to sodium when sodium is missing.

        1 g salt -> 400 mg sodium. The salt entry itself is preserved.
        """

        if "sodium" in nutrition or "salt" not in nutrition:
            return

        salt = nutrition["salt"]
        value = salt.get("value")
        unit = (salt.get("unit") or "g").lower()

        if value is None:
            return

        salt_g = float(value) / 1000.0 if unit == "mg" else float(value)

        nutrition["sodium"] = {
            "value": round(salt_g * _SALT_TO_SODIUM_MG_PER_G, 2),
            "unit": "mg",
        }

        logger.info(
            "Derived sodium %.2f mg from salt %.2f %s.",
            nutrition["sodium"]["value"],
            value,
            unit,
        )


if __name__ == "__main__":

    sample = """
    Nutrition Facts
    Serving Size 34 g
    Calories 160
    Total Fat 7g
    Saturated Fat 2g
    Trans Fat 0g
    Cholesterol 5mg
    Sodium 135mg
    Total Carbohydrate 25g
    Dietary Fiber less than 1g
    Total Sugars 14g
    Includes 14g Added Sugars
    Protein 1g
    Vitamin D 2mcg 10%
    Calcium 120mg
    Iron 1.8mg
    Potassium 250mg
    INGREDIENTS: Wheat Flour, Sugar, Palm Oil,
    Cocoa Powder (12%), Raising Agents (INS 500(ii)),
    Salt, Emulsifier (Soy Lecithin).
    Contains Wheat and Soy.
    """

    parser = NutritionParserV2()

    result = parser.parse(sample)

    from pprint import pprint
    pprint(result)
