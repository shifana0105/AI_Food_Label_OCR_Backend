import re
from typing import Dict, List, Optional


class NutritionParser:
    """
    Extracts structured nutrition information from OCR text.

    This parser ONLY extracts information.
    It DOES NOT:
        - convert serving values to per 100g
        - validate missing features
        - predict nutrition grade

    Those tasks belong to:
        unit_converter.py
        feature_validator.py
        ml_predictor.py
    """

    def __init__(self):

        # Nutrient aliases
        self.nutrient_patterns = {
            "energy": [
                r"energy",
                r"calories?",
                r"kcal"
            ],

            "fat": [
                r"total\s*fat",
                r"fat"
            ],

            "saturated_fat": [
                r"saturated\s*fat",
                r"sat\.?\s*fat"
            ],

            "carbohydrates": [
                r"carbohydrates?",
                r"carbs?",
                r"carbohydrate"
            ],

            "sugars": [
                r"total\s*sugars?",
                r"sugars?",
                r"sugar"
            ],

            "fiber": [
                r"dietary\s*fiber",
                r"dietary\s*fibre",
                r"fiber",
                r"fibre"
            ],

            "protein": [
                r"proteins?",
                r"protein"
            ],

            "sodium": [
                r"sodium",
                r"salt"
            ]
        }

        # Allergens
        self.allergen_keywords = [
            "milk",
            "soy",
            "soya",
            "wheat",
            "gluten",
            "egg",
            "eggs",
            "peanut",
            "peanuts",
            "tree nuts",
            "nuts",
            "cashew",
            "almond",
            "hazelnut",
            "walnut",
            "sesame",
            "mustard",
            "fish",
            "shellfish"
        ]

    # -------------------------------------------------------------

    def preprocess_text(self, text: str) -> str:
        """
        Clean OCR output before parsing.
        """

        if not text:
            return ""

        text = text.lower()

        text = text.replace("\r", "\n")

        text = re.sub(r"[ \t]+", " ", text)

        text = re.sub(r"\n+", "\n", text)

        return text.strip()

    # -------------------------------------------------------------

    def create_empty_result(self) -> Dict:

        return {

            "serving": {
                "size": None,
                "unit": None,
                "type": None
            },

            "nutrition": {

                "energy": {
                    "value": None,
                    "unit": None
                },

                "fat": {
                    "value": None,
                    "unit": None
                },

                "saturated_fat": {
                    "value": None,
                    "unit": None
                },

                "carbohydrates": {
                    "value": None,
                    "unit": None
                },

                "sugars": {
                    "value": None,
                    "unit": None
                },

                "fiber": {
                    "value": None,
                    "unit": None
                },

                "protein": {
                    "value": None,
                    "unit": None
                },

                "sodium": {
                    "value": None,
                    "unit": None
                }

            },

            "ingredients": [],

            "allergens": []

        }

    # -------------------------------------------------------------

    def _extract_numeric_value(self, text: str) -> Optional[float]:

        match = re.search(r"(\d+(?:\.\d+)?)", text)

        if not match:
            return None

        try:
            return float(match.group(1))
        except Exception:
            return None

    # -------------------------------------------------------------

    def _extract_unit(self, text: str) -> Optional[str]:

        units = [
            "kcal",
            "kj",
            "mg",
            "g",
            "mcg",
            "µg",
            "ml"
        ]

        for unit in units:
            if unit in text:
                return unit

        return None

    # -------------------------------------------------------------

    def detect_serving_information(self, text: str, result: dict):
        
        """
        Detect serving size from different label formats.

        Supported examples:
            Serving Size: 34 g
            Serving size 34g
            3 cookies (34g)
            Per 100 g
            Per 100 ml
        """

        patterns = [

            r"serving\s*size\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(g|ml)",

            r"\((\d+(?:\.\d+)?)\s*(g|ml)\)",

            r"per\s*(\d+(?:\.\d+)?)\s*(g|ml)"

        ]

        for pattern in patterns:

            match = re.search(pattern, text)

            if match:

                size = float(match.group(1))

                unit = match.group(2)

                result["serving"]["size"] = size

                result["serving"]["unit"] = unit

                if size == 100:
                    result["serving"]["type"] = f"per_100{unit}"
                else:
                    result["serving"]["type"] = "per_serving"

                return result

        return result

        # -------------------------------------------------------------

    def _extract_nutrient(self, text: str, aliases: List[str]):
        """
        Extract a nutrient value and its unit from OCR text.
        """

        for alias in aliases:

            # Special handling for Total Sugars
            if alias == r"total\s*sugars?":

                match = re.search(
                    r"Total\s+Sugars\s+(\d+(?:\.\d+)?)g",
                    text,
                    re.IGNORECASE,
                )

                if match:
                    return float(match.group(1)), "g"

            # ------------------------------
            # Special handling for Calories
            # ------------------------------
            if alias in [r"energy", r"calories?"]:

                calorie_patterns = [

                    r"Amount\s*per\s*serving\s*(\d+(?:\.\d+)?)",

                    r"Calories\s*(\d+(?:\.\d+)?)",

                    r"(\d+(?:\.\d+)?)\s*Calories",

                ]

                for pattern in calorie_patterns:

                    match = re.search(
                        pattern,
                        text,
                        re.IGNORECASE | re.DOTALL,
                    )

                    if match:
                        return float(match.group(1)), "kcal"

            # ------------------------------
            # Generic nutrient extraction
            # ------------------------------
            patterns = [

                # Prefer "Total Sugars", "Total Fat", etc.
                rf"total\s+{alias}\s*[:\-]?\s*(?:less\s+than\s+)?(\d+(?:\.\d+)?)\s*(kcal|kj|g|mg|mcg|µg|ml)?",

                rf"total\s+{alias}\s*\n\s*(?:less\s+than\s+)?(\d+(?:\.\d+)?)\s*(kcal|kj|g|mg|mcg|µg|ml)?",

                rf"total\s+{alias}\s+(\d+(?:\.\d+)?)\s*(kcal|kj|g|mg|mcg|µg|ml)?",

                # Normal format
                rf"{alias}\s*[:\-]?\s*(?:less\s+than\s+)?(\d+(?:\.\d+)?)\s*(kcal|kj|g|mg|mcg|µg|ml)?",

                rf"{alias}\s*\n\s*(?:less\s+than\s+)?(\d+(?:\.\d+)?)\s*(kcal|kj|g|mg|mcg|µg|ml)?",

                rf"{alias}\s+(\d+(?:\.\d+)?)\s*(kcal|kj|g|mg|mcg|µg|ml)?",
            ]

            for pattern in patterns:

                match = re.search(
                    pattern,
                    text,
                    re.IGNORECASE,
                )

                if match:

                    value = float(match.group(1))
                    unit = match.group(2)

                    if unit is None:

                        if alias in [r"energy", r"calories?"]:
                            unit = "kcal"

                        elif "sodium" in alias.lower():
                            unit = "mg"

                        else:
                            unit = "g"

                    return value, unit

        return None, None

    # -------------------------------------------------------------

    def extract_nutrients(
        self,
        text: str,
        result: Dict
    ) -> Dict:

        """
        Extract all nutrition values from OCR text.
        """

        nutrition = result["nutrition"]

        # Special handling for Total Sugars
        if nutrient == "sugars":
            match = re.search(
                r"Total\s+Sugars\s+(\d+(?:\.\d+)?)\s*g",
                text,
                re.IGNORECASE,
            )

            if match:
                value = float(match.group(1))
                unit = "g"
            else:
                value, unit = self._extract_nutrient(text, aliases)

        else:
            value, unit = self._extract_nutrient(text, aliases)

        nutrition[nutrient]["value"] = value
        nutrition[nutrient]["unit"] = unit

        return result

    # -------------------------------------------------------------

    def print_debug(self, result: Dict):

        """
        Debug helper.
        """

        print("\n------------- PARSER OUTPUT -------------")

        print("\nServing")

        print(result["serving"])

        print("\nNutrition")

        for nutrient, values in result["nutrition"].items():

            print(
                f"{nutrient:18} : "
                f"{values['value']} "
                f"{values['unit']}"
            )

        print("-----------------------------------------\n")

    
        # -------------------------------------------------------------

    def extract_ingredients(
        self,
        text: str,
        result: Dict
    ) -> Dict:

        """
        Extract ingredients from OCR text.
        """

        ingredient_patterns = [

            r"ingredients\s*[:\-]\s*(.*?)(?:allergen|contains|nutrition|storage|$)",

            r"ingredient\s*[:\-]\s*(.*?)(?:allergen|contains|nutrition|storage|$)"

        ]

        ingredients = []

        for pattern in ingredient_patterns:

            match = re.search(
                pattern,
                text,
                re.IGNORECASE | re.DOTALL
            )

            if match:

                ingredient_text = match.group(1)

                ingredient_text = ingredient_text.replace("\n", " ")

                ingredient_text = re.sub(r"\s+", " ", ingredient_text)

                ingredients = [

                    item.strip()

                    for item in ingredient_text.split(",")

                    if item.strip()

                ]

                break

        result["ingredients"] = ingredients

        return result

    # -------------------------------------------------------------

    def extract_allergens(
        self,
        text: str,
        result: Dict
    ) -> Dict:

        """
        Detect allergens from OCR text.
        """

        allergens = set()

        contains_match = re.search(

            r"contains\s*[:\-]?\s*(.*)",

            text,

            re.IGNORECASE

        )

        if contains_match:

            contains_text = contains_match.group(1).lower()

            for keyword in self.allergen_keywords:

                if keyword in contains_text:

                    allergens.add(keyword)

        for keyword in self.allergen_keywords:

            pattern = rf"\b{re.escape(keyword)}\b"

            if re.search(pattern, text, re.IGNORECASE):

                allergens.add(keyword)

        result["allergens"] = sorted(list(allergens))

        return result

    
        # -------------------------------------------------------------

    def parse(self, text: str) -> Dict:
        """
        Main parser entry point.

        Returns:
            {
                serving,
                nutrition,
                ingredients,
                allergens
            }
        """

        text = self.preprocess_text(text)

        result = self.create_empty_result()

        result = self.detect_serving_information(
            text,
            result
        )

        result = self.extract_nutrients(
            text,
            result
        )

        result = self.extract_ingredients(
            text,
            result
        )

        result = self.extract_allergens(
            text,
            result
        )

        return result


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    sample_text = """
    Nutrition Facts

    Serving Size 34 g

    Energy 160 kcal

    Total Fat 7 g

    Saturated Fat 2 g

    Carbohydrates 25 g

    Sugars 14 g

    Dietary Fiber 1 g

    Protein 2 g

    Sodium 135 mg

    Ingredients:
    Wheat Flour, Sugar, Palm Oil,
    Cocoa Powder, Corn Starch,
    Raising Agents,
    Salt,
    Soy Lecithin

    Contains Wheat and Soy.
    """

    parser = NutritionParser()

    parsed = parser.parse(sample_text)

    parser.print_debug(parsed)

    from pprint import pprint

    pprint(parsed)