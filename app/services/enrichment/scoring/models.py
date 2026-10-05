"""Type de retour commun aux scores de qualite."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class QualityScore:
    """Score for a single category."""
    category: str
    score: Decimal
    details: dict
