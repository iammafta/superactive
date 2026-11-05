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


def _replace_complete_runs(text: str) -> str:
    """Replace finished card-like runs. A run is digits, spaces, and dashes."""
    parts: list[str] = []
    index = 0
    while index < len(text):
        if text[index].isdigit():
            end = index + 1
            while end < len(text) and text[end] in _CARD_CHARS:
                end += 1
            chunk = text[index:end]
            digits = "".join(char for char in chunk if char.isdigit())
            parts.append("a card number" if luhn_ok(digits) else chunk)
            index = end
        else:
            parts.append(text[index])
            index += 1
    return "".join(parts)


def _split_trailing_run(text: str) -> tuple[str, str]:
    """Hold a trailing digit run that might still grow into a card number."""
    end = len(text)
    while end > 0 and text[end - 1] in _CARD_CHARS:
        end -= 1
    run = text[end:]
    if not any(char.isdigit() for char in run):
        return text, ""
    offset = 0
    while offset < len(run) and not run[offset].isdigit():
        offset += 1
    start = end + offset
    digits = "".join(char for char in text[start:] if char.isdigit())
    if len(digits) > 19:
        return text, ""
    return text[:start], text[start:]


class CardMasker:
    """Reassemble a card number that arrives across streamed text chunks."""

    def __init__(self) -> None:
        self._hold = ""

    def feed(self, text: str) -> str:
        ready, self._hold = _split_trailing_run(self._hold + (text or ""))
        return _replace_complete_runs(ready)

    def flush(self) -> str:
        ready = _replace_complete_runs(self._hold)
        self._hold = ""
        return ready
