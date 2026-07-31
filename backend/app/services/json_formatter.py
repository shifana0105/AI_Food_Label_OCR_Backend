"""JSON formatting service.

Converts internal OCR results into the public API response schema.
"""

from typing import List

from app.models.response import (
    AnalysisResultModel,
    OCRData,
    OCRLine,
    UploadData,
    ParsedServing,
    ParsedNutrition,
    ParsedNutritionValue,
    ParsedLabel,
    PredictionResult,
)
from app.services.ocr_engine import OCRLineResult


class JSONFormatter:
    """Builds the final API response payload from processed OCR data."""

    def format(
        self,
        processing_time_seconds: float,
        lines: List[OCRLineResult],
        raw_text: str,
        clean_text: str,
        parsed_label: dict | None = None,
        ml_features: dict | None = None,
        analysis: dict | None = None,
        prediction: dict | None = None,
    ) -> UploadData:

        average_confidence = (
            sum(line.confidence for line in lines) / len(lines)
            if lines
            else 0.0
        )

        parsed_label_model = None

        if parsed_label:

            nutrition = parsed_label.get("nutrition", {})

            def nutrient(name):
                data = nutrition.get(name)

                if data is None:
                    return ParsedNutritionValue(
                        value=None,
                        unit=None,
                    )

                return ParsedNutritionValue(**data)

            parsed_label_model = ParsedLabel(
                serving=ParsedServing(
                    **parsed_label["serving"]
                ),
                nutrition=ParsedNutrition(
                    energy=nutrient("energy"),
                    fat=nutrient("fat"),
                    saturated_fat=nutrient("saturated_fat"),
                    carbohydrates=nutrient("carbohydrates"),
                    sugars=nutrient("sugars"),
                    fiber=nutrient("fiber"),
                    protein=nutrient("protein"),
                    sodium=nutrient("sodium"),
                ),
                ingredients=parsed_label.get("ingredients", []),
                allergens=parsed_label.get("allergens", []),
            )

        analysis_model = None

        if analysis:
            analysis_model = AnalysisResultModel(**analysis)

        prediction_model = None

        if prediction:
            prediction_model = PredictionResult(
                nutrition_grade=prediction["nutrition_grade"],
                confidence=prediction["confidence"],
            )

        return UploadData(
            processing_time=f"{processing_time_seconds:.2f}s",
            ocr=OCRData(
                average_confidence=round(
                    average_confidence,
                    4,
                ),
                raw_text=raw_text,
                clean_text=clean_text,
                lines=[
                    OCRLine(
                        text=line.text,
                        confidence=round(
                            line.confidence,
                            4,
                        ),
                        bounding_box=line.bounding_box,
                    )
                    for line in lines
                ],
            ),
            parsed_label=parsed_label_model,
            ml_features=ml_features or {},
            analysis=analysis_model,
            prediction=prediction_model,
        )
