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

    Lines ending with a hyphen, comma, or an unfinished lowercase word
    are treated as continuations so they can be merged with the next line.
    """
    stripped = text.rstrip()
    if not stripped:
        return False
    return stripped.endswith(("-", ",")) or stripped[-1].islower()


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
