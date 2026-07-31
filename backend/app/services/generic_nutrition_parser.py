import re


class GenericNutritionParser:

    def __init__(self):

        number = r"([0-9]+(?:\.[0-9]*)?)"

        self.patterns = {

            "energy": re.compile(
                rf"Energy\s*<?\s*{number}\s*(kcal|kj)",
                re.I
            ),

            "protein": re.compile(
                rf"Protein\s*<?\s*{number}\.?\s*g",
                re.I
            ),

            # Specific fat types FIRST
            "saturated_fat": re.compile(
                rf"(?:Saturated\s*Fat|SaturatedFat)\s*<?\s*{number}\.?\s*g?",
                re.I
            ),

            "trans_fat": re.compile(
                rf"(?:Trans\s*Fat|TransFat)\s*<?\s*{number}\.?\s*g?",
                re.I
            ),

            # Total fat ONLY
            "fat": re.compile(
                rf"(?:Total\s*Fat|TotalFat)\s*<?\s*{number}\.?\s*g?",
                re.I
            ),

            "carbohydrates": re.compile(
                rf"(?:Total\s*Carbohydrate|TotalCarbohydrates|Carbohydrate|Carbohydrates)\s*<?\s*{number}\.?\s*g?",
                re.I
            ),

            "sugars": re.compile(
                rf"(?:Total\s*Sugars?|TotalSugars?|Sugars?|Sugar)\s*<?\s*{number}\.?\s*g?",
                re.I
            ),

            "fiber": re.compile(
                rf"(?:Dietary\s*Fiber|DietaryFiber|Dietary\s*Fibre|DietaryFibre|Fiber|Fibre)\s*<?\s*{number}\.?\s*g?",
                re.I
            ),

            "sodium": re.compile(
                rf"Sodium\s*<?\s*{number}\s*mg",
                re.I
            ),
        }

    def extract_nutrients(self, line: str):

        nutrients = []

        for label, pattern in self.patterns.items():

            match = pattern.search(line)

            if not match:
                continue

            value = float(match.group(1))

            if label == "energy":
                unit = match.group(2)
            elif label == "sodium":
                unit = "mg"
            else:
                unit = "g"

            nutrients.append({
                "label": label,
                "value": value,
                "unit": unit
            })

        return nutrients