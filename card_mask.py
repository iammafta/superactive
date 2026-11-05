"""Mask payment-card numbers in streamed speech text.

LLM text arrives in short chunks, so a card number can be split across
frames. CardMasker holds a trailing digit run until a non-card character
ends it, then keeps the run only when it is 13 to 19 digits and passes Luhn.
"""

from __future__ import annotations

_CARD_CHARS = set("0123456789 -")


def luhn_ok(digits: str) -> bool:
    """True when digits are a 13 to 19 digit Luhn-valid number."""
    if not digits.isdigit() or not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0
