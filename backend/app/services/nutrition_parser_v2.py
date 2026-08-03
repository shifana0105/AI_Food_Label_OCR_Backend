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

from typing import Dict, Optional

from app.core.logger import get_logger
from app.services.allergen_detector import AllergenDetector
from app.services.nutrition_line_extractor import NutritionLineExtractor
from app.services.generic_nutrition_parser import GenericNutritionParser
from app.services.nutrient_normalizer import NutrientNormalizer
from app.services.micronutrient_parser import MicronutrientParser
from app.services.ingredient_extractor import IngredientExtractor
from app.services.serving_parser import ServingParser
from app.utils.ocr_normalizer import normalize_text

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
        self.allergen_detector = AllergenDetector()

    # ------------------------------------------------------------------

    def parse(self, text: str, raw_text: Optional[str] = None) -> Dict:
        """Parse the full nutrition label.

        Step 0: Apply OCR normalisation to *text*.  All downstream
                parsers operate on the normalised copy; *raw_text*
                (unmerged per-line OCR output) is only used by
                IngredientExtractor to recover one-per-line ingredient
                layouts.

        Args:
            text:     Merged/cleaned OCR text from TextProcessor.
            raw_text: Optional unmerged text (one OCR line per \n).
                      Passed to IngredientExtractor so that per-line
                      ingredient layouts without trailing commas are
                      correctly split.
        """

        # ── Step 0: OCR normalisation ──────────────────────────────────
        # norm_text = normalize_text(text)

        # result = {
        #     "serving": self.serving_parser.parse(norm_text),
        #     "nutrition": {},
        #     "vitamins": {},
        #     "minerals": {},
        #     "ingredients": [],
        #     "allergens": [],
        # }

        # lines = self.extractor.extract(norm_text)

        # logger.debug("Extracted %d nutrition lines.", len(lines))


        # ── Step 0: OCR normalisation ──────────────────────────────────
        norm_text = normalize_text(text)

        # TEMP DEBUG ---------------------------------------------------
        logger.info("========================")
        logger.info("AFTER OCR NORMALIZER")
        logger.info("========================")
        for i, ln in enumerate(norm_text.split("\n")):
            logger.info("%d: %s", i, ln)
        # END TEMP DEBUG -------------------------------------------------

        result = {
            "serving": self.serving_parser.parse(norm_text),
            "nutrition": {},
            "vitamins": {},
            "minerals": {},
            "ingredients": [],
            "allergens": [],
        }

        lines = self.extractor.extract(norm_text)

        logger.debug("Extracted %d nutrition lines.", len(lines))

        # TEMP DEBUG ---------------------------------------------------
        logger.info("========================")
        logger.info("AFTER NUTRITION LINE EXTRACTOR")
        logger.info("========================")
        for ln in lines:
            logger.info("%s", ln)
        # END TEMP DEBUG -------------------------------------------------

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

        # self._derive_sodium_from_salt(result["nutrition"])

        # # Vitamins & minerals: stored SEPARATELY from nutrition.
        # # MicronutrientParser applies its own normalize_text internally;
        # # passing norm_text is idempotent and avoids double-parsing the raw.
        # micro = self.micronutrients.parse(norm_text)
        # result["vitamins"] = micro["vitamins"]
        # result["minerals"] = micro["minerals"]

        # # Ingredients in original order (no classification).
        # # raw_text (unmerged) is preferred so that one-per-line layouts
        # # without trailing commas are correctly split by the extractor.
        # result["ingredients"] = self.ingredients.extract(
        #     text, raw_text=raw_text
        # )


        # TEMP DEBUG ---------------------------------------------------
        logger.info("========================")
        logger.info("AFTER GENERIC NUTRITION PARSER")
        logger.info("========================")
        for nutrient, data in result["nutrition"].items():
            logger.info("%s: %s", nutrient, data)
        # END TEMP DEBUG -------------------------------------------------

        self._derive_sodium_from_salt(result["nutrition"])

        # Vitamins & minerals: stored SEPARATELY from nutrition.
        # MicronutrientParser applies its own normalize_text internally;
        # passing norm_text is idempotent and avoids double-parsing the raw.
        micro = self.micronutrients.parse(norm_text)
        result["vitamins"] = micro["vitamins"]
        result["minerals"] = micro["minerals"]

        # TEMP DEBUG ---------------------------------------------------
        logger.info("========================")
        logger.info("AFTER MICRONUTRIENT PARSER")
        logger.info("========================")
        logger.info("Vitamins:")
        for name, data in result["vitamins"].items():
            logger.info("  %s: %s", name, data)
        logger.info("Minerals:")
        for name, data in result["minerals"].items():
            logger.info("  %s: %s", name, data)
        # END TEMP DEBUG -------------------------------------------------

        # Ingredients in original order (no classification).
        # raw_text (unmerged) is preferred so that one-per-line layouts
        # without trailing commas are correctly split by the extractor.
        result["ingredients"] = self.ingredients.extract(
            text, raw_text=raw_text
        )

        # TEMP DEBUG ---------------------------------------------------
        logger.info("========================")
        logger.info("AFTER INGREDIENT EXTRACTOR")
        logger.info("========================")
        for ing in result["ingredients"]:
            logger.info("- %s", ing)
        if not result["ingredients"]:
            logger.info("(none extracted)")
        # END TEMP DEBUG -------------------------------------------------

        # Allergens: detected from ingredient list + full OCR text
        # (catches explicit "Contains:" statements + inline mentions).
        result["allergens"] = self.allergen_detector.detect_combined(
            result["ingredients"], norm_text
        )

        logger.info(
            "NutritionParserV2 parsed %d nutrients, %d vitamins, "
            "%d minerals, %d ingredients, %d allergens (serving=%s).",
            len(result["nutrition"]),
            len(result["vitamins"]),
            len(result["minerals"]),
            len(result["ingredients"]),
            len(result["allergens"]),
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
