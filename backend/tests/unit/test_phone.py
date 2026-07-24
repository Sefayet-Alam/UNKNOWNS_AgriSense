"""Unit tests for Bangladeshi phone normalization."""
from __future__ import annotations

import pytest

from app.schemas import normalize_bd_phone

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "raw",
    [
        "01712345678",         # already canonical
        "+8801712345678",      # +880 prefix
        "8801712345678",       # 880 prefix
        "1712345678",          # dropped leading zero (10 digits starting 1)
        "017-1234-5678",       # separators stripped
        " 01712345678 ",       # surrounding whitespace
    ],
)
def test_normalize_valid_variants_to_canonical(raw):
    assert normalize_bd_phone(raw) == "01712345678"


@pytest.mark.parametrize(
    "raw",
    [
        "0171234",             # too short
        "01234567890",         # 11 digits but 012... not a valid BD mobile prefix
        "017123456780",        # too long
        "abcdefghijk",         # letters
        "",                    # empty
        "01212345678",         # 012 prefix invalid (must be 01[3-9])
    ],
)
def test_normalize_invalid_raises(raw):
    with pytest.raises(ValueError):
        normalize_bd_phone(raw)


def test_all_valid_operator_prefixes():
    for d in "3456789":
        num = f"01{d}12345678"
        assert normalize_bd_phone(num) == num
