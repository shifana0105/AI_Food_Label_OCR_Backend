import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


class GeminiService:

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise ValueError("GEMINI_API_KEY not found.")

        self.client = genai.Client(api_key=api_key)

        self.model = "gemini-flash-latest"

    def extract(self, image_bytes: bytes):

        prompt = """
You are an expert AI system for reading food nutrition labels.

Analyze the uploaded food label image carefully.

Return ONLY valid JSON.

Do NOT return markdown.

Do NOT return explanations.

Do NOT invent values.

If a value is not visible, return null.

Use EXACTLY the following schema.

{
  "product_name": null,
  "brand": null,

  "serving": {
    "size": null,
    "unit": null,
    "type": null
  },

  "nutrition": {
    "energy_kcal": null,
    "energy_from_fat_kcal": null,

    "total_fat_g": null,
    "saturated_fatty_acids_g": null,
    "monounsaturated_fatty_acids_g": null,
    "polyunsaturated_fatty_acids_g": null,
    "trans_fatty_acids_g": null,

    "cholesterol_mg": null,

    "total_carbohydrates_g": null,
    "sugar_sucrose_g": null,
    "added_sugars_g": null,
    "dietary_fibre_g": null,

    "protein_g": null,

    "sodium_g": null
  },

  "vitamins": {},

  "minerals": {},

  "ingredients": [],

  "allergens": []
}

Rules:

- Use numbers only for numeric values.
- Never include units inside numeric values.
- Units are already encoded in the field names.
- Return null if unreadable.
- Preserve ingredient order.
- Preserve allergen names exactly.
- Detect vitamins and minerals even if they appear outside the nutrition table.
- Do not rename any JSON keys.
- Return ONLY valid JSON.
"""

#         prompt = """
# You are an expert Nutrition Label Reader.

# Analyze this food label image.

# Extract every visible nutrition value.

# Extract ingredients.

# Extract allergens.

# Extract vitamins.

# Extract minerals.

# Extract serving information.

# Return ONLY valid JSON.

# Never explain.

# Never use markdown.

# If something is missing return null.

# JSON:

# {
#   "product_name":"",
#   "brand":"",
#   "serving":{
#       "size":null,
#       "unit":null,
#       "type":null
#   },
#   "nutrition":{},
#   "vitamins":{},
#   "minerals":{},
#   "ingredients":[],
#   "allergens":[]
# }
# """

        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                prompt,
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg",
                ),
            ],
        )

        text = response.text.strip()

        if text.startswith("```json"):
            text = text.replace("```json", "").replace("```", "").strip()

        elif text.startswith("```"):
            text = text.replace("```", "").strip()

        return json.loads(text)