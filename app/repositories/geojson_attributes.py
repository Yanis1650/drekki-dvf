"""Valeurs par parcelle lues par les trois modes de la carte.

Le frontend colore une parcelle selon `prix_m2_moyen` (mode Prix),
`densification_categorie` (Densification) ou `zone_plu` (Urbanisme), et
hachure celle a qui la propriete manque (frontend/src/composables/
mapColorSchemes.js). Ces champs n'etaient jamais renvoyes : toutes les
parcelles sortaient hachurees, quel que soit le mode.
"""

import logging
from typing import Any

from app.infrastructure.data_availability import column_exists, table_exists

logger = logging.getLogger(__name__)

# Zonage GPU ramene aux quatre familles de la legende. Meme regle que le
# pipeline (etl_build_steps/gpu.py) : AU avant A, sinon 'AU' tombe dans 'A%'.
# Pas de ELSE : une zone hors des quatre familles reste sans valeur.
_ZONE_PLU_SQL = """
    CASE
        WHEN typezone LIKE 'AU%' THEN 'AU'
        WHEN typezone LIKE 'U%'  THEN 'U'
        WHEN typezone LIKE 'A%'  THEN 'A'
        WHEN typezone LIKE 'N%'  THEN 'N'
    END
"""


def parcel_attributes(conn: Any, parcel_ids: list[str]) -> dict[str, dict]:
    """Valeurs de carte par identifiant de parcelle.

    Une propriete n'est posee que si la source la renseigne, jamais a zero ni
    par defaut. Chaque source est facultative : une table absente laisse
    simplement la propriete vide, sans faire echouer la couche.
    """
    if not parcel_ids:
        return {}

    lookups: list[tuple[str, str]] = []
    if column_exists(conn, "france_foncier_test", "cadastre_parcelle_id"):
        # Meme perimetre que les prix agreges du frontend : valeurs atypiques
        # exclues, prix nuls ou absents ignores.
        outliers = (
            "AND NOT COALESCE(is_outlier, FALSE)"
            if column_exists(conn, "france_foncier_test", "is_outlier") else ""
        )
        lookups.append(("prix_m2_moyen", f"""
            SELECT cadastre_parcelle_id, AVG(prix_m2)::DOUBLE
            FROM france_foncier_test
            WHERE cadastre_parcelle_id IN (SELECT UNNEST(?::VARCHAR[]))
              AND prix_m2 > 0 {outliers}
            GROUP BY cadastre_parcelle_id
        """))
    if table_exists(conn, "densification_scores"):
        lookups.append(("densification_categorie", """
            SELECT id_parcelle, categorie
            FROM densification_scores
            WHERE id_parcelle IN (SELECT UNNEST(?::VARCHAR[]))
        """))
    if table_exists(conn, "gpu_parcelles"):
        lookups.append(("zone_plu", f"""
            SELECT id_parcelle, {_ZONE_PLU_SQL}
            FROM gpu_parcelles
            WHERE id_parcelle IN (SELECT UNNEST(?::VARCHAR[]))
        """))

    attributes: dict[str, dict] = {}
    for prop, query in lookups:
        try:
            values = conn.execute(query, [parcel_ids]).fetchall()
        except Exception as e:
            logger.warning("Parcel attribute %s failed: %s", prop, e)
            continue
        for parcel_id, value in values:
            if value is not None:
                attributes.setdefault(parcel_id, {})[prop] = value
    return attributes
