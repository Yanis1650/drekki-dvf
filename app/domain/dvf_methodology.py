"""Regles DVF stables, partagees par le pipeline et les analyses."""

from decimal import Decimal
from typing import Final

METHODOLOGY_VERSION: Final = "mericskay_2021"
SALE_NATURE: Final = "Vente"
MIN_TRANSACTION_VALUE_EUR: Final = Decimal("1000")
MIN_HABITABLE_SURFACE_M2: Final = Decimal("9")
HABITABLE_LOCAL_TYPES: Final = ("Maison", "Appartement")
