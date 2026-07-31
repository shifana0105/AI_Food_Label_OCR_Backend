class FeatureValidator:
    """
    Validates and sanitizes nutrition features
    before passing them to the ML model.
    """

    REQUIRED_FEATURES = {

        "energy_100g": (0, 1000),

        "fat_100g": (0, 100),

        "saturated-fat_100g": (0, 100),

        "carbohydrates_100g": (0, 100),

        "sugars_100g": (0, 100),

        "fiber_100g": (0, 100),

        "proteins_100g": (0, 100),

        "sodium_100g": (0, 10)

    }

    # ----------------------------------------------------------

    def validate(self, features):

        validated = {}

        for feature, limits in self.REQUIRED_FEATURES.items():

            minimum, maximum = limits

            value = features.get(feature)

            value = self._sanitize(
                value,
                minimum,
                maximum
            )

            validated[feature] = value

        return validated

    # ----------------------------------------------------------

    def _sanitize(
        self,
        value,
        minimum,
        maximum
    ):

        if value is None:
            return 0.0

        try:
            value = float(value)

        except Exception:
            return 0.0

        if value < minimum:
            value = minimum

        if value > maximum:
            value = maximum

        return round(value, 2)

    
        # ----------------------------------------------------------

    def to_model_input(self, validated_features):
        """
        Convert validated feature dictionary into
        the exact order expected by the Random Forest model.
        """

        return [

            validated_features["energy_100g"],

            validated_features["fat_100g"],

            validated_features["saturated-fat_100g"],

            validated_features["carbohydrates_100g"],

            validated_features["sugars_100g"],

            validated_features["fiber_100g"],

            validated_features["proteins_100g"],

            validated_features["sodium_100g"]

        ]


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

    validator = FeatureValidator()

    validated = validator.validate(sample_features)

    print("\n----------- VALIDATED FEATURES -----------\n")

    for key, value in validated.items():
        print(f"{key:22}: {value}")

    print("\n----------- MODEL INPUT -----------\n")

    print(
        validator.to_model_input(validated)
    )

    print("\n------------------------------------------")