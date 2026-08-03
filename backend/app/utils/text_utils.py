"""Text-related utility helpers used by the text processing service."""

import re


def normalize_whitespace(text: str) -> str:
    """Collapse consecutive whitespace into single spaces and trim.

    Args:
        text: Raw text possibly containing tabs, newlines, or repeated spaces.

    Returns:
        Text with normalized single-space separation.
    """
    return re.sub(r"\s+", " ", text).strip()


def is_meaningful(text: str) -> bool:
    """Return True if the text contains at least one alphanumeric character."""
    return bool(re.search(r"[A-Za-z0-9]", text))


def ends_with_continuation(text: str) -> bool:
    """Heuristic: does this line likely continue onto the next one?

    Two unambiguous signals:
    - Trailing hyphen: a word was split mid-character by OCR (e.g. ``"COCOA POW-"``).
    - Trailing comma: an ingredient-list item continues on the next line.

    A third, guarded signal handles **label/value split-line** formats where
    the nutrient name appears on its own line and the numeric value follows:

        Energy          ← label-only line (no digit)
        374kcal         ← value line

    These must be merged or ``GenericNutritionParser`` sees two orphan
    lines and extracts nothing.  The guard ``not re.search(r'\d', stripped)``
    ensures this branch **never** fires on a complete ``"Label Value Unit"``
    line (e.g. ``"Total Fat 7g"``), which always contains a digit.  This
    preserves the BUG-07 fix (complete entries are not merged together) while
    restoring parsing of split-line labels.
    """
    stripped = text.rstrip()
    if not stripped:
        return False
    # Explicit continuation: hyphen word-break or comma list item.
    if stripped.endswith(("-", ",")):
        return True
    # Label-only line (no digit): last char is lowercase, value is on the
    # next line.  Complete entries (digit present) are never merged here.
    if stripped[-1].islower() and not re.search(r"\d", stripped):
        return True
    return False


def merge_hyphenated(previous: str, current: str) -> str:
    """Merge two lines, joining hyphen-split words without a space.

    Args:
        previous: The earlier line (may end with a hyphen).
        current: The following line.

    Returns:
        The merged line.
    """
    if previous.rstrip().endswith("-"):
        return previous.rstrip().rstrip("-") + current.lstrip()
    return f"{previous.rstrip()} {current.lstrip()}"
