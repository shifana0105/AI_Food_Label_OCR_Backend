import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# -----------------------------------------------------
# Load API Key
# -----------------------------------------------------

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise Exception("GEMINI_API_KEY not found in .env")

client = genai.Client(api_key=API_KEY)

# -----------------------------------------------------
# Image
# -----------------------------------------------------

image_path = input("Enter image path: ").strip()

if not os.path.exists(image_path):
    raise FileNotFoundError(f"Image not found:\n{image_path}")

with open(image_path, "rb") as f:
    image_bytes = f.read()

# -----------------------------------------------------
# Prompt
# -----------------------------------------------------

prompt = """
You are an expert AI Nutrition Label Reader.

Your task is to analyze ANY packaged food label image from ANY brand.

Examples include (but are not limited to):

- Kellogg's
- Horlicks
- Nestle
- Britannia
- Amul
- Cadbury
- Coca-Cola
- Pepsi
- Oreo
- Maggi
- General Mills

The layout may be:

• single column
• double column
• table
• rotated
• curved packaging
• blurry
• partially visible

Never assume a fixed format.

Understand the label exactly like a human nutrition expert.

------------------------------------
RULES
------------------------------------

1. Read every visible nutrition value.

2. Never guess missing values.

3. If unreadable return null.

4. Preserve original units.

5. Extract all vitamins.

6. Extract all minerals.

7. Extract ingredients.

8. Extract allergen statements.

9. Detect serving size.

10. Detect serving unit.

11. Detect serving type.

12. If multiple nutrition tables exist,
use the main Nutrition Facts table.

13. Return ONLY JSON.

No markdown.

No explanation.

No comments.

------------------------------------
OUTPUT JSON
------------------------------------

{
  "product_name": "",
  "brand": "",

  "serving": {
      "size": null,
      "unit": null,
      "type": null
  },

  "nutrition": {
      "energy": null,
      "protein": null,
      "carbohydrate": null,
      "total_sugars": null,
      "added_sugars": null,
      "dietary_fibre": null,
      "fat": null,
      "saturated_fat": null,
      "trans_fat": null,
      "monounsaturated_fat": null,
      "polyunsaturated_fat": null,
      "cholesterol": null,
      "sodium": null
  },

  "vitamins": {},

  "minerals": {},

  "ingredients": [],

  "allergens": [],

  "ocr_confidence": "high | medium | low"
}
"""

# -----------------------------------------------------
# Gemini Call
# -----------------------------------------------------

response = client.models.generate_content(
    model="gemini-flash-latest",
    contents=[
        prompt,
        types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg"
        )
    ]
)

# -----------------------------------------------------
# Response
# -----------------------------------------------------

text = response.text.strip()

# Remove markdown if Gemini wraps JSON
if text.startswith("```json"):
    text = text.replace("```json", "").replace("```", "").strip()

elif text.startswith("```"):
    text = text.replace("```", "").strip()

print("\n================ RAW RESPONSE ================\n")
print(text)

# -----------------------------------------------------
# Parse JSON
# -----------------------------------------------------

try:

    data = json.loads(text)

    print("\n================ FORMATTED JSON ================\n")
    print(json.dumps(data, indent=4))

    with open("gemini_output.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print("\n✅ JSON saved as gemini_output.json")

except json.JSONDecodeError as e:

    print("\n❌ Invalid JSON returned")
    print(e)

    with open("gemini_raw_response.txt", "w", encoding="utf-8") as f:
        f.write(text)

    print("Raw response saved to gemini_raw_response.txt")