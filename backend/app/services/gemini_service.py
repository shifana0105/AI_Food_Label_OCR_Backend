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
You are an expert Nutrition Label Reader.

Analyze this food label image.

Extract every visible nutrition value.

Extract ingredients.

Extract allergens.

Extract vitamins.

Extract minerals.

Extract serving information.

Return ONLY valid JSON.

Never explain.

Never use markdown.

If something is missing return null.

JSON:

{
  "product_name":"",
  "brand":"",
  "serving":{
      "size":null,
      "unit":null,
      "type":null
  },
  "nutrition":{},
  "vitamins":{},
  "minerals":{},
  "ingredients":[],
  "allergens":[]
}
"""

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