import joblib
from pathlib import Path


MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "food_grade_model.pkl"
)


GRADE_MAPPING = {
    0: "A",
    1: "B",
    2: "C",
    3: "D",
    4: "E"
}


class MLPredictor:

    def __init__(self):

        self.model = joblib.load(MODEL_PATH)

    # --------------------------------------------------------

    def predict(self, features):

        """
        features must be a list in the order:

        [
            energy_100g,
            fat_100g,
            saturated-fat_100g,
            carbohydrates_100g,
            sugars_100g,
            fiber_100g,
            proteins_100g,
            sodium_100g
        ]
        """

        prediction = self.model.predict([features])[0]

        grade = GRADE_MAPPING[int(prediction)]

        confidence = None

        if hasattr(self.model, "predict_proba"):

            probabilities = self.model.predict_proba([features])[0]

            confidence = round(
                float(max(probabilities)) * 100,
                2
            )

        return {

            "nutrition_grade": grade,

            "confidence": confidence

        }


        # --------------------------------------------------------

    def predict_with_features(self, validated_features):
        """
        Accepts a validated feature dictionary directly.
        """

        features = [

            validated_features["energy_100g"],

            validated_features["fat_100g"],

            validated_features["saturated-fat_100g"],

            validated_features["carbohydrates_100g"],

            validated_features["sugars_100g"],

            validated_features["fiber_100g"],

            validated_features["proteins_100g"],

            validated_features["sodium_100g"]

        ]

        return self.predict(features)


# ----------------------------------------------------------------------
# Standalone Test
# ----------------------------------------------------------------------

if __name__ == "__main__":

    sample_features = {

        "energy_100g": 470.59,

        "fat_100g": 20.59,

        "saturated-fat_100g": 5.88,

        "carbohydrates_100g": 73.53,

        "sugars_100g": 41.18,

        "fiber_100g": 2.94,

        "proteins_100g": 5.88,

        "sodium_100g": 0.40

    }

    predictor = MLPredictor()

    prediction = predictor.predict_with_features(
        sample_features
    )

    print("\n----------- PREDICTION -----------\n")

    print(f"Nutrition Grade : {prediction['nutrition_grade']}")

    print(f"Confidence      : {prediction['confidence']} %")

    print("\n----------------------------------")