"""Acces brut aux liens de filiation DFI : parents et enfants.

Les deux sens ne different que par la colonne interrogee — `parcelle_fille`
pour remonter aux meres, `parcelle_mere` pour descendre aux filles. Ils
partageaient jusqu'ici une requete et un mapping recopies mot pour mot.
"""

import logging

from app.domain.filiation_models import ParcelFiliation

logger = logging.getLogger(__name__)

_COLONNES = """
    id_dfi,
    code_departement,
    code_commune,
    prefixe,
    nature_dfi,
    date_validation,
    numero_lot,
    parcelle_mere,
    parcelle_fille
"""


def _vers_filiations(resultats: list) -> list[ParcelFiliation]:
    """Lignes de `dfi_filiations` vers le domaine, colonnes dans l'ordre ci-dessus."""
    return [
        ParcelFiliation(
            id_dfi=row[0],
            code_departement=row[1],
            code_commune=row[2],
            prefixe=row[3],
            nature_dfi=row[4],
            date_validation=row[5],
            numero_lot=row[6],
            parcelle_mere=row[7],
            parcelle_fille=row[8],
        )
        for row in resultats
    ]


class FiliationLineageMixin:
    """Lectures directes de la table `dfi_filiations`."""

    def _liens(
        self, code_commune: str, section: str, numero: str, *, colonne: str, sens: str
    ) -> list[ParcelFiliation]:
        """Interroge `dfi_filiations` sur `colonne`, index composite a l'appui.

        `colonne` est un litteral interne (jamais une entree utilisateur) :
        `parcelle_fille` ou `parcelle_mere`.
        """
        conn = self._get_connection()
        self._require_dfi(conn)
        parcelle_id = section + numero.zfill(4)

        query = f"""
            SELECT {_COLONNES}
            FROM dfi_filiations
            WHERE code_commune = ?
              AND {colonne} = ?
            ORDER BY date_validation DESC
        """

        try:
            resultats = conn.execute(query, [code_commune, parcelle_id]).fetchall()
            return _vers_filiations(resultats)
        except Exception as e:
            logger.error("Error fetching %s for %s%s: %s", sens, section, numero, e)
            return []

    def get_parents(
        self, code_commune: str, section: str, numero: str
    ) -> list[ParcelFiliation]:
        """Retrieve parent parcels using optimized index scan.

        Query uses idx_dfi_fille index for fast lookup.
        """
        return self._liens(
            code_commune, section, numero, colonne="parcelle_fille", sens="parents"
        )

    def get_children(
        self, code_commune: str, section: str, numero: str
    ) -> list[ParcelFiliation]:
        """Retrieve children parcels using optimized index scan.

        Query uses idx_dfi_mere index for fast lookup.
        """
        return self._liens(
            code_commune, section, numero, colonne="parcelle_mere", sens="children"
        )
