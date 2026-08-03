"""
Gemini Adapter

Converts the JSON returned by Gemini Vision into the existing
parsed_label structure expected by UnitConverter,
NutritionEngine and the rest of the backend.
"""


class GeminiAdapter:

    @staticmethod
    def _nutrient(value, unit):
        return {
            "value": value,
            "unit": unit
        }

    def convert(self, gemini_json):

        nutrition = gemini_json.get("nutrition", {})

        parsed_label = {

            "serving": {
                "size": gemini_json.get("serving", {}).get("size"),
                "unit": gemini_json.get("serving", {}).get("unit"),
                "type": "per_serving"
            },

            "nutrition": {

                "energy":
                    self._nutrient(
                        nutrition.get("energy_kcal"),
                        "kcal"
                    ),

                "fat":
                    self._nutrient(
                        nutrition.get("total_fat_g"),
                        "g"
                    ),

                "saturated_fat":
                    self._nutrient(
                        nutrition.get("saturated_fatty_acids_g"),
                        "g"
                    ),

                "trans_fat":
                    self._nutrient(
                        nutrition.get("trans_fatty_acids_g"),
                        "g"
                    ),

                "carbohydrates":
                    self._nutrient(
                        nutrition.get("total_carbohydrates_g"),
                        "g"
                    ),

                "sugars":
                    self._nutrient(
                        nutrition.get("sugar_sucrose_g"),
                        "g"
                    ),

                "added_sugar":
                    self._nutrient(
                        nutrition.get("added_sugars_g"),
                        "g"
                    ),

                "fiber":
                    self._nutrient(
                        nutrition.get("dietary_fibre_g"),
                        "g"
                    ),

                "protein":
                    self._nutrient(
                        nutrition.get("protein_g"),
                        "g"
                    ),

                "sodium":
                    self._nutrient(
                        nutrition.get("sodium_g"),
                        "g"
                    ),

                "cholesterol":
                    self._nutrient(
                        nutrition.get("cholesterol_mg"),
                        "mg"
                    ),

                "monounsaturated_fat":
                    self._nutrient(
                        nutrition.get("monounsaturated_fatty_acids_g"),
                        "g"
                    ),

                "polyunsaturated_fat":
                    self._nutrient(
                        nutrition.get("polyunsaturated_fatty_acids_g"),
                        "g"
                    ),
            },

            "vitamins":
                gemini_json.get("vitamins", {}),

            "minerals":
                gemini_json.get("minerals", {}),

            "ingredients":
                gemini_json.get("ingredients", []),

            "allergens":
                gemini_json.get("allergens", [])
        }

        return parsed_label