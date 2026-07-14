"""Interfaces for future pipeline modules.

The long-term pipeline is:

    Image Upload -> Preprocessing -> PaddleOCR -> Text Processing
        -> Structured Extraction -> Ingredient Parser -> Nutrition Parser
        -> Allergen Detector -> AI Recommendation Engine -> Frontend

The stages after Text Processing are NOT implemented yet. These
``Protocol`` interfaces define the contracts those future services must
satisfy, so they can be added without changing the existing pipeline.
Implementations should be wired up via ``app.api.deps`` like the
current services.
"""

from typing import Dict, List, Protocol


class StructuredExtractor(Protocol):
    """Splits clean OCR text into labeled label sections."""

    def extract(self, clean_text: str) -> Dict[str, str]:
        """Map section names (e.g. 'ingredients', 'nutrition') to text."""
        ...


class IngredientParser(Protocol):
    """Parses an ingredients section into individual ingredients."""

    def parse(self, ingredients_text: str) -> List[str]:
        """Return the normalized list of ingredient names."""
        ...


class NutritionParser(Protocol):
    """Parses a nutrition facts section into structured values."""

    def parse(self, nutrition_text: str) -> Dict[str, float]:
        """Map nutrient names to their numeric amounts."""
        ...


class AllergenDetector(Protocol):
    """Detects allergens from a parsed ingredient list."""

    def detect(self, ingredients: List[str]) -> List[str]:
        """Return the allergens found in the given ingredients."""
        ...


class RecommendationEngine(Protocol):
    """Produces AI-driven dietary recommendations for a label."""

    def recommend(
        self,
        ingredients: List[str],
        nutrition: Dict[str, float],
        allergens: List[str],
    ) -> str:
        """Return a human-readable recommendation for the product."""
        ...
