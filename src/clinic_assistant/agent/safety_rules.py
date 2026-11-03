"""Rule-based emergency detection; runs before any LLM call so safety never depends on the model.

The list errs on the side of caution: a false alarm costs a polite emergency notice, while a
missed emergency is the worst failure the assistant can have (FR-6, ADR 0005).
"""

import re

# Phrases are matched as whole words after normalising case, apostrophes and punctuation.
EMERGENCY_PHRASES: tuple[str, ...] = (
    "chest pain",
    "chest pressure",
    "heart attack",
    "cant breathe",
    "can not breathe",
    "cannot breathe",
    "trouble breathing",
    "difficulty breathing",
    "short of breath",
    "shortness of breath",
    "choking",
    "stroke",
    "face drooping",
    "slurred speech",
    "unconscious",
    "passed out",
    "fainted",
    "seizure",
    "severe bleeding",
    "heavy bleeding",
    "bleeding heavily",
    "wont stop bleeding",
    "overdose",
    "poisoned",
    "suicide",
    "kill myself",
    "severe allergic reaction",
    "anaphylaxis",
    "throat swelling",
)

EMERGENCY_INSTRUCTION = (
    "This sounds like it could be an emergency. Please call 9999 now or go to the nearest "
    "emergency department. Front-desk staff have been alerted to your message."
)

_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in EMERGENCY_PHRASES) + r")\b"
)


def normalise(text: str) -> str:
    """Lowercase, drop apostrophes (can't → cant) and turn other punctuation into spaces."""
    text = text.lower().replace("'", "").replace("’", "")
    return re.sub(r"[^\w\s]", " ", text)


def is_emergency(text: str) -> bool:
    """True when the message contains any emergency phrase."""
    return _PATTERN.search(normalise(text)) is not None
