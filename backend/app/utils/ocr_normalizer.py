"""
Generic OCR text normalizer for food label parsing.

Stage 1 of the multi-stage parser pipeline.  Applied to every OCR
text string BEFORE any sub-parser runs, so all downstream parsers see
clean, structurally consistent text.

No brand-specific or product-specific logic.  Every rule corrects a
structural OCR error pattern that appears across all label types.

Normalizations (applied in order per line):
    1. Vitamin stem repair  – Vltamin / V1tamin / Vitarnin → Vitamin
    2. Vitamin letter fix   – VitaminA → Vitamin A
                             Vitamin81 → Vitamin B1
    3. Unit separator fix   – 3·3mg / 3.3.mg / 3,3mg / 3 3mg → 3.3 mg
    4. Unit alias fix       – µg → mcg, MG → mg, KJ → kJ
    5. Number-unit spacing  – 374kcal → 374 kcal, 120mg → 120 mg
"""

import re
from typing import Callable, List, Tuple, Union

# ---------------------------------------------------------------------------
# 1. Vitamin stem repairs
# ---------------------------------------------------------------------------
# OCR frequently confuses: i↔l, i↔1, m↔rn.  Ordered most-specific first.

_STEM_FIXES: List[Tuple[re.Pattern, str]] = [
    # "Vitarnin"  m read as rn
    (re.compile(r'\bVitarn[il1]n\b', re.I), 'Vitamin'),
    # "Vitarmin"  m read as rm
    (re.compile(r'\bVitarmin\b', re.I), 'Vitamin'),
    # "Vitamln" / "Vitamlm"  i read as l in suffix
    (re.compile(r'\bVitam[l1][nm]\b', re.I), 'Vitamin'),
    # "Vltamin" / "Vltamln"  i read as l in first syllable
    (re.compile(r'\bVl[lt]am[il1]n\b', re.I), 'Vitamin'),
    # "V1tamin"  i read as 1
    (re.compile(r'\bV[1l]tam[il1]n\b', re.I), 'Vitamin'),
    # "Vitaman"  i→a in the 'amin' portion
    (re.compile(r'\bVitaman\b', re.I), 'Vitamin'),
    # "Vitamim"  n→m in suffix
    (re.compile(r'\bVitamim\b', re.I), 'Vitamin'),
    # Generic mop-up: Vitam?n when not already 'Vitamins'
    (re.compile(r'\bVitam[il1]n(?!s\b)', re.I), 'Vitamin'),
]

# ---------------------------------------------------------------------------
# 1b. General nutrient-name stem repairs
# ---------------------------------------------------------------------------
# Common OCR error: i (lowercase i) is read as l (lowercase L) or 1 (digit).
# Applied in the same normalize_line() pass as vitamin repairs.

_NUTRIENT_STEM_FIXES: List[Tuple[re.Pattern, str]] = [
    # Sodium: Sodlum, S0dium, Sod1um
    (re.compile(r'\bSod[l1]um\b', re.I), 'Sodium'),
    (re.compile(r'\bS0dium\b', re.I), 'Sodium'),
    # Protein: Proteln, Prote1n
    (re.compile(r'\bProte[l1]n\b', re.I), 'Protein'),
    # Calcium: Calclum, Calc1um
    (re.compile(r'\bCalc[l1]um\b', re.I), 'Calcium'),
    # Fiber / Fibre: F1bre, Flbre
    (re.compile(r'\bF[l1]b(?:er|re)\b', re.I), 'Fibre'),
    # Cholesterol: Cholestero1
    (re.compile(r'\bCholestero[l1]\b', re.I), 'Cholesterol'),
    # Carbohydrate: Carbohydrale, Carbohydrates
    (re.compile(r'\bCarbohydra[lt]es?\b', re.I), 'Carbohydrates'),
    # Iron: lron (capital I read as lowercase l)
    (re.compile(r'\bl[Rr]on\b'), 'Iron'),
    # Serving: Servlng, Serv1ng
    (re.compile(r'\bServ[l1]ng\b', re.I), 'Serving'),
    # Calories: Calorles
    (re.compile(r'\bCalor[l1]es\b', re.I), 'Calories'),
]


# ---------------------------------------------------------------------------
# 2. Vitamin letter / number spacing
# ---------------------------------------------------------------------------

# "Vitamin81" / "Vitamin 81" → "Vitamin B1"
# OCR mistakes the capital letter B for the digit 8.
_VIT_DIGIT_B: re.Pattern = re.compile(r'\b(Vitamin)\s*8(\d+)\b', re.I)

# "VitaminA"   → "Vitamin A"
# "VitaminB1"  → "Vitamin B1"
# "VitaminB12" → "Vitamin B12"
# "VitaminK2"  → "Vitamin K2"
# Guard: only matches when the vitamin letter IMMEDIATELY follows "Vitamin"
# with NO whitespace (so "Vitamin A" — already spaced — is unchanged).
_VIT_COMPACT: re.Pattern = re.compile(r'\b(Vitamin)([A-K])(\d*)\b', re.I)

# ---------------------------------------------------------------------------
# 3–5. Unit separator, alias, and spacing fixes
# ---------------------------------------------------------------------------

_UNIT_PAT = r'(?:mcg|mg|g|iu|kcal|kj)'  # all supported unit tokens

_UNIT_FIXES: List[Tuple[re.Pattern, Union[str, Callable]]] = [

    # 3a. Middle-dot / interpunct as decimal:  "3·3" → "3.3"
    (re.compile(r'(\d)\s*[·•]\s*(\d)'), r'\1.\2'),

    # 3b. "3.3.mg" → "3.3 mg"  (spurious period directly before unit)
    (re.compile(
        r'(\d+\.\d+)\.\s*(' + _UNIT_PAT + r')\b', re.I,
    ), r'\1 \2'),

    # 3c. "3.mg" → "3 mg"  (lone spurious period before unit)
    (re.compile(r'(\d)\.\s*(' + _UNIT_PAT + r')\b', re.I), r'\1 \2'),

    # 3d. EU comma-decimal glued to unit: "3,3mg" → "3.3 mg"
    #     Guard: 1–2 decimal digits ONLY (3-digit groups = thousands separators)
    (re.compile(
        r'(\d),(\d{1,2})\s*(' + _UNIT_PAT + r')\b', re.I,
    ), lambda m: f'{m.group(1)}.{m.group(2)} {m.group(3).lower()}'),

    # 3e. "3,3 mg" → "3.3 mg"  (EU comma-decimal, space before unit)
    (re.compile(
        r'(\d),(\d{1,2})\s+(mg|g|mcg|iu|kcal|kj)\b', re.I,
    ), lambda m: f'{m.group(1)}.{m.group(2)} {m.group(3).lower()}'),

    # 3f. "3 3mg" → "3.3 mg"  (space-as-decimal, unit glued)
    #     Only single digit on each side of the space.
    (re.compile(
        r'\b(\d) (\d)(' + _UNIT_PAT + r')\b', re.I,
    ), lambda m: f'{m.group(1)}.{m.group(2)} {m.group(3).lower()}'),

    # 3g. "200m<g" / "200m[g" / "200m c g" → "200 mcg"
    (re.compile(r'(\d+)\s*m\s*[<\[{(]\s*g\b', re.I), r'\1 mcg'),
    (re.compile(r'(\d+)\s*m\s+c\s*g\b', re.I), r'\1 mcg'),

    # 4a. Unit alias normalization
    # Pre-space pass: insert space between digit and uppercase/ambiguous unit
    # so the word-boundary alias rules below can fire.
    (re.compile(r'(\.\d+|\d)(ug)\b', re.I), r'\1 \2'),
    (re.compile(r'(\.\d+|\d)(MG)\b'), r'\1 \2'),
    (re.compile(r'(\.\d+|\d)(KJ)\b'), r'\1 \2'),
    (re.compile(r'(\.\d+|\d)(KCAL)\b'), r'\1 \2'),
    # Now apply the aliases (unit token is already separated)
    # µg: \b does not work with non-ASCII chars — use context-sensitive match.
    # Handles "500µg", "500 µg", "500µg 10%"
    (re.compile(r'(\d)\s*µg'), r'\1 mcg'),   # digit-glued or spaced
    (re.compile(r'(?<=\s)µg(?=\s|$|,|;|%)'), 'mcg'),   # standalone
    (re.compile(r'^µg(?=\s|$)'), 'mcg'),                 # start of line
    (re.compile(r'\bug\b', re.I), 'mcg'),
    (re.compile(r'\bMG\b'), 'mg'),
    (re.compile(r'\bKJ\b'), 'kJ'),
    (re.compile(r'\bKCAL\b'), 'kcal'),

    # 5. Add space between digit and unit when glued together.
    #    Longer / more specific unit tokens first to avoid partial matches.
    (re.compile(r'(\d)(mcg|kcal)\b', re.I), r'\1 \2'),
    (re.compile(r'(\d)(kj)\b', re.I), r'\1 \2'),
    (re.compile(r'(\d)(mg)\b', re.I), r'\1 \2'),
    (re.compile(r'(\d)(iu)\b', re.I), r'\1 \2'),
    # 'g' last — only when standalone (word-boundary), to avoid hitting
    # 'serving', 'sugar', etc.
    (re.compile(r'(\d)(g)\b', re.I), r'\1 \2'),
]

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def normalize_line(line: str) -> str:
    """Apply all OCR normalizations to a single text line.

    Args:
        line: A single OCR output line (no embedded newlines).

    Returns:
        Normalised line.  The input is never mutated.
    """
    # Step 1: vitamin stem repairs
    for pattern, replacement in _STEM_FIXES:
        line = pattern.sub(replacement, line)

    # Step 1b: general nutrient stem repairs (Sodlum→Sodium, Proteln→Protein…)
    for pattern, replacement in _NUTRIENT_STEM_FIXES:
        line = pattern.sub(replacement, line)

    # Step 2: vitamin letter / number spacing
    line = _VIT_DIGIT_B.sub(
        lambda m: f'{m.group(1)} B{m.group(2)}', line
    )
    line = _VIT_COMPACT.sub(
        lambda m: f'{m.group(1)} {m.group(2)}{m.group(3)}', line
    )

    # Steps 3-5: unit fixes, aliases, number-unit spacing
    for pattern, replacement in _UNIT_FIXES:
        line = pattern.sub(replacement, line)

    return line


def normalize_text(text: str) -> str:
    """Apply all OCR normalizations to a full multi-line OCR text.

    Processes line by line so corrections never bleed across line
    boundaries (e.g. a unit on one line never merges with a digit on
    the previous line).

    Args:
        text: Full OCR text, possibly many lines.

    Returns:
        Normalised text with the same number of lines.
    """
    return '\n'.join(normalize_line(ln) for ln in text.split('\n'))


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    _TESTS = [
        # stem fixes
        ('Vltamin D 2.5 mcg',        'Vitamin D 2.5 mcg'),
        ('V1tamin B12 1.2 mcg',       'Vitamin B12 1.2 mcg'),
        ('Vitarnin C 60mg',           'Vitamin C 60 mg'),
        ('Vitaman A 1000 mcg',        'Vitamin A 1000 mcg'),
        # letter spacing
        ('VitaminA',                  'Vitamin A'),
        ('VitaminD',                  'Vitamin D'),
        ('Vitamin81',                 'Vitamin B1'),
        ('Vitamin82',                 'Vitamin B2'),
        ('Vitamin83',                 'Vitamin B3'),
        ('VitaminB1',                 'Vitamin B1'),
        ('VitaminB12',                'Vitamin B12'),
        ('VitaminK',                  'Vitamin K'),
        ('VitaminK2',                 'Vitamin K2'),
        # unit separator fixes
        ('3·3mg',                     '3.3 mg'),
        ('3.3.mg',                    '3.3 mg'),
        ('3,3mg',                     '3.3 mg'),
        ('3 3mg',                     '3.3 mg'),
        ('200m<g',                    '200 mcg'),
        ('16.7mcg',                   '16.7 mcg'),
        # unit alias fixes
        ('2.5 µg',                    '2.5 mcg'),
        ('2.5ug',                     '2.5 mcg'),
        ('120MG',                     '120 mg'),
        ('374kcal',                   '374 kcal'),
        # number-unit spacing
        ('120mg',                     '120 mg'),
        ('1000mcg',                   '1000 mcg'),
        ('5g',                        '5 g'),
        # already correct — must be unchanged
        ('Vitamin A 1000 mcg',        'Vitamin A 1000 mcg'),
        ('Vitamin B12 1.2 mcg',       'Vitamin B12 1.2 mcg'),
        ('Calcium 120 mg',            'Calcium 120 mg'),
    ]

    passed = 0
    for raw, expected in _TESTS:
        got = normalize_line(raw)
        ok = '✓' if got == expected else '✗'
        if got != expected:
            print(f'{ok}  {raw!r}')
            print(f'     expected {expected!r}')
            print(f'     got      {got!r}')
        else:
            print(f'{ok}  {raw!r}  →  {got!r}')
            passed += 1

    print(f'\n{passed}/{len(_TESTS)} passed')
