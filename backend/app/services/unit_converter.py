from copy import deepcopy


class UnitConverter:
    """
    Converts parsed nutrition values into the
    feature format expected by the ML model.
    """

    FEATURE_MAPPING = {
        "energy": "energy_100g",
        "fat": "fat_100g",
        "saturated_fat": "saturated-fat_100g",
        "carbohydrates": "carbohydrates_100g",
        "sugars": "sugars_100g",
        "fiber": "fiber_100g",
        "protein": "proteins_100g",
        "sodium": "sodium_100g"
    }

    def convert(self, parsed_result):

        parsed = deepcopy(parsed_result)

        serving = parsed["serving"]
        nutrition = parsed["nutrition"]

        serving_size = serving.get("size")
        serving_type = serving.get("type")

        features = {}

        for nutrient, feature_name in self.FEATURE_MAPPING.items():

            # -----------------------------
            # Nutrient not detected
            # -----------------------------
            if nutrient not in nutrition:
                features[feature_name] = None
                continue

            value = nutrition[nutrient].get("value")
            unit = nutrition[nutrient].get("unit")

            converted = self.convert_single_value(
                value=value,
                unit=unit,
                serving_size=serving_size,
                serving_type=serving_type,
                nutrient=nutrient
            )

            features[feature_name] = converted

        return features

    def convert_single_value(
        self,
        value,
        unit,
        serving_size,
        serving_type,
        nutrient
    ):

        if value is None:
            return None

        value = float(value)

        if unit is None:
            unit = "g"

        unit = unit.lower()

        # mg -> g
        if unit == "mg":
            value /= 1000

        # kJ -> kcal
        if nutrient == "energy" and unit == "kj":
            value /= 4.184

        # Already per 100g or 100ml
        if serving_type in ("per_100g", "per_100ml"):
            return round(value, 2)

        # Missing serving size
        if serving_size is None:
            return round(value, 2)

        # Per serving -> per 100g/ml
        if serving_type == "per_serving":

            if serving_size <= 0:
                return round(value, 2)

            value = (value / serving_size) * 100

        return round(value, 2)

    def convert_all(self, parsed_result):
        return self.convert(parsed_result)