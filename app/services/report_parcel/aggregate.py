"""Collecte des donnees d'un rapport parcelle.

Reunit DVF, BDNB, filiation et scores d'enrichissement en un seul
dictionnaire, celui que le gabarit consomme.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class ReportAggregateMixin:
    """Assemblage du contexte de rendu."""

    async def _aggregate_parcel_data(self, parcel_id: str) -> dict[str, Any]:
        """Aggregate all data needed for the parcel report.

        Fetches from DVF, BDNB, Filiation, and calculates enrichment scores.
        """
        data: dict[str, Any] = {
            "parcel_id": parcel_id,
            "generated_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "transactions": [],
            "densification": None,
            "filiation": None,
            "enrichment": None,
            "parcel_info": None,
            "error_sections": [],
        }

        # 1. Get parcelle basic info (note: parcelles table has no surface_m2 column)
        try:
            parcelle = await self._land_repo.get_parcelle_by_id(parcel_id)
            if parcelle:
                data["parcel_info"] = {
                    "id": parcelle.id_parcelle,
                    "surface": None,  # surface_m2 not in parcelles table
                    "code_commune": parcelle.code_commune,
                    "centroid": None,  # Need to compute from geometry if needed
                }
        except Exception as e:
            logger.warning(f"Could not fetch parcel info: {e}")
            data["error_sections"].append("parcel_info")

        # 2. Get transaction history
        try:
            transactions = await self._land_repo.get_transactions_for_parcel(parcel_id)
            data["transactions"] = [
                {
                    "id": tx.id_mutation,
                    "date": str(tx.date_mutation),
                    "valeur_fonciere": float(tx.valeur_fonciere),
                    "prix_m2": float(tx.prix_m2) if tx.prix_m2 else None,
                    "surface": float(tx.surface_habitable_totale) if tx.surface_habitable_totale else None,
                }
                for tx in transactions[:10]  # Last 10 transactions
            ]
        except Exception as e:
            logger.warning(f"Could not fetch transactions: {e}")
            data["error_sections"].append("transactions")

        # 3. Get densification score
        try:
            densif = await self._land_repo.get_densification_score(parcel_id)
            if densif:
                data["densification"] = {
                    "ces_actuel": float(densif.ces_actuel),
                    "ces_potentiel": float(densif.ces_potentiel),
                    "surface_constructible": float(densif.surface_constructible_restante),
                    "categorie": densif.categorie,
                    "potentiel": float(densif.potentiel_densification),
                }
        except Exception as e:
            logger.warning(f"Could not fetch densification: {e}")
            data["error_sections"].append("densification")

        # 4. Get filiation (use get_ancestors which is sync, not get_full_filiation)
        try:
            # Parse parcel ID to extract section and numero
            # Format: code_commune(5-6) + prefixe(3) + section(2) + numero(4) = 14-15 chars
            if len(parcel_id) >= 14:
                code_commune = parcel_id[:5]
                section = parcel_id[8:10]  # After prefixe
                numero = parcel_id[10:14]
                node = self._filiation_service.get_ancestors(code_commune[:3], section, numero)
                if node and node.parent:
                    data["filiation"] = {
                        "events": [{
                            "type_filiation": "Division",
                            "date_acte": (
                                str(node.date_division) if node.date_division else None
                            ),
                            "parcelles_filles": [node.parent.id_parcelle],
                        }]
                    }
        except Exception as e:
            logger.warning(f"Could not fetch filiation: {e}")
            data["error_sections"].append("filiation")

        # 5. Get enrichment scores
        try:
            if data.get("parcel_info", {}).get("centroid"):
                lon, lat = data["parcel_info"]["centroid"]
                enrichment = await self._enrichment_service.calculate_enrichment(
                    latitude=lat,
                    longitude=lon,
                    parcelle_id=parcel_id,
                )
                data["enrichment"] = {
                    "education": float(enrichment.schools_score),
                    "transport": float(enrichment.transport_score),
                    "green_spaces": float(enrichment.green_spaces_score),
                    "nuisances": float(enrichment.nuisances_score),
                    "global": float(enrichment.global_score),
                }
        except Exception as e:
            logger.warning(f"Could not calculate enrichment: {e}")
            data["error_sections"].append("enrichment")

        # Calculate summary stats
        if data["transactions"]:
            prices = [tx["prix_m2"] for tx in data["transactions"] if tx.get("prix_m2")]
            if prices:
                data["avg_price_m2"] = sum(prices) / len(prices)
                data["min_price_m2"] = min(prices)
                data["max_price_m2"] = max(prices)

        return data
