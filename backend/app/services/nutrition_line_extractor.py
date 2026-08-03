import re
from typing import List


class NutritionLineExtractor:
    """
    Extracts only nutrition-related lines from OCR text.

    Responsibility:
    - Keep nutrition lines
    - Remove ingredients
    - Remove percentages
    - Remove marketing text
    - Remove allergens
    """

    def __init__(self):

        self.nutrition_keywords = [

            "serving",
            "calories",
            "energy",

            "fat",
            "saturated",
            "saturates",
            "trans",

            "cholesterol",
            "sodium",

            "carbohydrate",
            "carbohydrates",

            "fiber",
            "fibre",

            "sugars",
            "sugar",
            # Added-sugar OCR variants: "of whichAdded 30g", "of which added"
            "added",
            "of which",
            "includes",

            "protein",

            "salt",
            "kcal",
            "kj",

            "vitamin",
            "calcium",
            "iron",
            "potassium",
            # Additional minerals so their split-line values are not filtered
            "zinc",
            "magnesium",
            "phosphorus",
            "manganese",
            "selenium",
            "iodine",
            "copper",
            "chromium",
        ]

    # -------------------------------------------------------------

    def clean_line(self, line: str) -> str:
        """
        Normalize one OCR line.
        """

        line = line.strip()

        line = re.sub(r"\s+", " ", line)

        return line

    # -------------------------------------------------------------

    def is_percentage_only(self, line: str) -> bool:
        """
        Ignore lines like:
            9%
            28%
            0%
        """

        return bool(
            re.fullmatch(r"\d+\s*%", line)
        )

    # -------------------------------------------------------------

    def contains_keyword(self, line: str) -> bool:

        lower = line.lower()

        for keyword in self.nutrition_keywords:

            if keyword in lower:
                return True

        return False

    # -------------------------------------------------------------

    def extract(self, text: str) -> List[str]:
        """
        Return only nutrition-related OCR lines.
        """

        lines = text.split("\n")

        nutrition_lines = []

        for line in lines:

            line = self.clean_line(line)

            if not line:
                continue

            if self.is_percentage_only(line):
                continue

            lower = line.lower()

            # Skip common headings
            if lower in [
                "nutrition facts",
                "amount per serving",
                "ingredients",
            ]:
                continue

            # Skip bare ingredient list entries (no amounts)
            if lower in ("sugar", "salt"):
                continue

            if self.contains_keyword(line):
                nutrition_lines.append(line)

        return nutrition_lines


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    sample = """
    Nutrition Facts
    Serving Size 34 g
    Amount per serving
    Calories 160
    Total Fat 7g
    9%
    Saturated Fat 2g
    Sodium 135mg
    Total Carbohydrate 25g
    Dietary Fiber less than 1g
    Total Sugars 14g
    Includes 14g Added Sugars
    28%
    Protein 1g
    Ingredients:
    Wheat Flour
    Sugar
    Palm Oil
    Contains Wheat and Soy
    """

    extractor = NutritionLineExtractor()

    lines = extractor.extract(sample)

    print("\nNutrition Lines\n")

    for line in lines:
        print(line)
