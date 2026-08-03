from app.services.nutrition_parser_v2 import NutritionParserV2
from app.services.unit_converter import UnitConverter
from app.services.feature_validator import FeatureValidator
from app.services.ml_predictor import MLPredictor
from app.services.nutrition_engine import NutritionEngine


class NutritionPipeline:
    """
    Complete nutrition prediction pipeline.

    OCR Text
        ↓
    Nutrition Parser
        ↓
    Unit Converter
        ↓
    Feature Validator
        ↓
    Nutrition Knowledge Engine
        ↓
    ML Predictor
    """

    def __init__(self, predictor=None, engine=None):

        self.parser = NutritionParserV2()

        self.converter = UnitConverter()

        self.validator = FeatureValidator()

        self.engine = engine or NutritionEngine()

        self.predictor = predictor or MLPredictor()

    # ----------------------------------------------------------

    def process(self, clean_text: str, raw_text: str = None):

        """
        Executes the entire nutrition prediction pipeline.

        Args:
            clean_text: Merged/normalised OCR text from TextProcessor.
            raw_text:   Optional unmerged line-by-line OCR text.  Passed
                        to NutritionParserV2 for ingredient extraction so
                        that one-per-line ingredient layouts (no trailing
                        commas) are correctly split rather than merged
                        into a single space-separated blob.

        Returns:

        {
            parsed_label,
            ml_features,
            analysis,
            prediction
        }
        """

        # Step 1
        parsed_label = self.parser.parse(
            clean_text, raw_text=raw_text
        )

        # Step 2
        converted_features = self.converter.convert_all(
            parsed_label
        )

        # Step 3
        validated_features = self.validator.validate(
            converted_features
        )

        # Step 4
        # Nutrition Knowledge Engine (deterministic, rule-based).
        # Uses the pre-validation converted features so that missing
        # nutrients (None) are reported as "not detected" instead of
        # being scored as zero.
        analysis = self.engine.evaluate(
            converted_features
        )

        # Step 5
        model_input = self.validator.to_model_input(
            validated_features
        )

        # Step 6
        prediction = self.predictor.predict(
            model_input
        )

        return {

            "parsed_label": parsed_label,

            "ml_features": validated_features,

            "analysis": analysis.to_dict(),

            "prediction": prediction

        }

    def process_parsed_label(self, parsed_label):
        """
        Executes the pipeline starting from an already
        structured parsed_label (Gemini output).

        Skips the OCR parser completely.
        """

        # Step 1
        converted_features = self.converter.convert_all(
            parsed_label
        )

        # Step 2
        validated_features = self.validator.validate(
            converted_features
        )

        # Step 3
        analysis = self.engine.evaluate(
            converted_features
        )

        # Step 4
        model_input = self.validator.to_model_input(
            validated_features
        )

        # Step 5
        prediction = self.predictor.predict(
            model_input
        )

        return {

            "parsed_label": parsed_label,

            "ml_features": validated_features,

            "analysis": analysis.to_dict(),

            "prediction": prediction

        }


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

    pipeline = NutritionPipeline()

    result = pipeline.process(sample_text)

    from pprint import pprint

    pprint(result)
