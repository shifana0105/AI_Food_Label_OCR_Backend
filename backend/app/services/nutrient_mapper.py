from typing import Optional


class NutrientMapper:
    """
    Maps different nutrition labels to canonical names.
    """

    def __init__(self):

        self.mapping = {

            "serving": [
                "serving size",
                "serving",
                "serving_size"
            ],

            "energy": [
                "calories",
                "energy"
            ],

            "fat": [
                "total fat",
                "totalfat",
                "fat"
            ],

            "saturated_fat": [
                "saturated fat",
                "saturatedfat",
                "saturated_fat"
            ],

            "trans_fat": [
                "trans fat",
                "transfat",
                "trans_fat"
            ],

            "cholesterol": [
                "cholesterol"
            ],

            "sodium": [
                "sodium"
            ],

            "carbohydrates": [
                "total carbohydrate",
                "total carbohydrates",
                "totalcarbohydrate",
                "totalcarbohydrates",
                "carbohydrate",
                "carbohydrates"
            ],

            "fiber": [
                "dietary fiber",
                "dietary fibre",
                "dietaryfiber",
                "dietaryfibre",
                "fiber",
                "fibre"
            ],

            "sugars": [
                "total sugars",
                "totalsugars",
                "sugars",
                "sugar"
            ],

            "protein": [
                "protein"
            ]
        }

    def map(self, label: str) -> Optional[str]:

        label = label.lower().strip()

        for canonical, aliases in self.mapping.items():

            if label == canonical:
                return canonical

            if label in aliases:
                return canonical

        return None


if __name__ == "__main__":

    mapper = NutrientMapper()

    tests = [

        "Calories",
        "Total Fat",
        "TotalFat",
        "fat",
        "Saturated Fat",
        "SaturatedFat",
        "saturated_fat",
        "Trans Fat",
        "TransFat",
        "trans_fat",
        "Total Carbohydrate",
        "Dietary Fiber",
        "Total Sugars",
        "Protein",
        "Serving Size"
    ]

    for t in tests:

        print(f"{t} -> {mapper.map(t)}")