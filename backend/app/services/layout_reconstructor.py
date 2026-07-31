"""
Layout reconstruction service.

Reconstructs OCR reading order using bounding box coordinates.
Useful for tables such as nutrition facts.
"""

from collections import defaultdict
from typing import List

from app.services.ocr_engine import OCRLineResult


class LayoutReconstructor:
    """
    Groups OCR detections into rows using their Y coordinates,
    then sorts each row from left to right.
    """

    def reconstruct(self, lines: List[OCRLineResult]) -> List[OCRLineResult]:

        if not lines:
            return []

        ROW_THRESHOLD = 15

        rows = defaultdict(list)

        for line in lines:

            box = line.bounding_box

            y_center = sum(point[1] for point in box) / 4

            matched_key = None

            for existing in rows:

                if abs(existing - y_center) <= ROW_THRESHOLD:
                    matched_key = existing
                    break

            if matched_key is None:
                rows[y_center].append(line)
            else:
                rows[matched_key].append(line)

        reconstructed = []

        for row_key in sorted(rows.keys()):

            row = rows[row_key]

            row.sort(
                key=lambda l: min(point[0] for point in l.bounding_box)
            )

            reconstructed.extend(row)

        return reconstructed