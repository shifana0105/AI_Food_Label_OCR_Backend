from typing import Dict

from app.services.nutrition_line_extractor import NutritionLineExtractor
from app.services.generic_nutrition_parser import GenericNutritionParser
from app.services.nutrient_mapper import NutrientMapper


class NutritionParserV2:

    def __init__(self):

        self.extractor = NutritionLineExtractor()
        self.parser = GenericNutritionParser()
        self.mapper = NutrientMapper()

    def parse(self, text: str) -> Dict:

        result = {
            "serving": {
                "size": None,
                "unit": None,
                "type": "per_serving"
            },
            "nutrition": {}
        }

        lines = self.extractor.extract(text)

        print("\n========== EXTRACTED LINES ==========\n")
        for line in lines:
            print(line)

        for line in lines:

            parsed_list = self.parser.extract_nutrients(line)

            print("\nLINE:", line)
            print("PARSED:", parsed_list)

            if not parsed_list:
                continue

            for parsed in parsed_list:

                canonical = self.mapper.map(parsed["label"])

                if canonical is None:
                    continue

                # Handle serving separately
                if canonical == "serving":

                    result["serving"]["size"] = parsed["value"]
                    result["serving"]["unit"] = parsed["unit"]
                    continue

                # ------------------------------------------
                # Don't overwrite an already detected nutrient
                # ------------------------------------------
                if canonical in result["nutrition"]:
                    continue

                result["nutrition"][canonical] = {
                    "value": parsed["value"],
                    "unit": parsed["unit"]
                }

        print("\n========== FINAL PARSED RESULT ==========\n")
        from pprint import pprint
        pprint(result)
        print("\n=========================================\n")

        return result


if __name__ == "__main__":

    sample = """
    Nutrition Facts
    Serving Size 34 g
    Calories 160
    Total Fat 7g
    Saturated Fat 2g
    Sodium 135mg
    Total Carbohydrate 25g
    Dietary Fiber less than 1g
    Total Sugars 14g
    Includes 14g Added Sugars
    Protein 1g
    """

    parser = NutritionParserV2()

    result = parser.parse(sample)

    from pprint import pprint
    pprint(result)

    from app.services.unit_converter import UnitConverter

    converter = UnitConverter()

    features = converter.convert_all(result)

    print("\nML Features\n")
    pprint(features)

    from app.services.feature_validator import FeatureValidator

    validator = FeatureValidator()

    validated = validator.validate(features)

    print("\nValidated Features\n")
    pprint(validated)

    print("\nModel Input\n")
    print(validator.to_model_input(validated))