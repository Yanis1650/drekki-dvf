"""Mixin pour find_parcelle_with_spatial_fallback et get_parcelle_fiche."""

import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class DuckDBFicheMixin:
    """Mixin fiche parcelle et fallback spatial."""

    def find_parcelle_with_spatial_fallback(
        self,
        id_parcelle_dvf: str,
        longitude: float,
        latitude: float,
        buffer_meters: float = -2.0,
    ) -> str | None:
        """Find parcel by ID, fallback to spatial intersection."""
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle_dvf))

        try:
            result = conn.execute(
                "SELECT id_parcelle FROM parcelles WHERE id_parcelle = ? LIMIT 1",
                [id_parcelle_dvf],
            ).fetchone()
            if result:
                return result[0]
        except Exception as e:
            logger.warning("Direct lookup failed for %s: %s", id_parcelle_dvf, e)

        logger.info("Parcelle %s not found, spatial fallback", id_parcelle_dvf)
        buffer_degrees = buffer_meters / 111000

        query = """
            SELECT p.id_parcelle,
                ST_Distance(
                    ST_Transform(p.geometry, 'EPSG:2154', 'EPSG:4326'),
                    ST_Point(?, ?)
                ) * 111000 as distance_meters
            FROM parcelles p
            WHERE ST_Intersects(
                ST_Buffer(
                    ST_Transform(p.geometry, 'EPSG:2154', 'EPSG:4326'),
                    ?
                ),
                ST_Point(?, ?)
            )
            ORDER BY distance_meters LIMIT 1
        """

        try:
            result = conn.execute(
                query, [longitude, latitude, buffer_degrees, longitude, latitude]
            ).fetchone()
            if result:
                logger.info("Spatial fix: %s -> %s (%.2fm)", id_parcelle_dvf, result[0], result[1])
                return result[0]
        except Exception as e:
            logger.error("Spatial fallback failed: %s", e)

        return None

    async def get_parcelle_fiche(self, id_parcelle: str) -> dict | None:
        """Fiche parcelle complète : DVF + BDNB + densification + confiance."""
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle))

        result = conn.execute("""
            WITH transactions AS (
                SELECT
                    cadastre_parcelle_id,
                    COUNT(*) AS nb_transactions,
                    MAX(date_mutation) AS derniere_mutation,
                    MIN(date_mutation) AS premiere_mutation,
                    MAX(valeur_fonciere) AS derniere_valeur,
                    MAX(prix_m2) AS dernier_prix_m2,
                    MAX(surface_habitable_totale) AS surface_habitable,
                    MAX(dpe_energie) AS dpe_energie,
                    MAX(annee_construction) AS annee_construction,
                    MAX(hauteur_moyenne) AS hauteur_moyenne,
                    MAX(nb_niveau) AS nb_niveau,
                    MAX(type_usage) AS type_usage,
                    MAX(nb_log) AS nb_log
                FROM france_foncier_test
                WHERE cadastre_parcelle_id = ?
                GROUP BY cadastre_parcelle_id
            )
            SELECT
                t.cadastre_parcelle_id   AS id_parcelle,
                t.nb_transactions,
                t.derniere_mutation,
                t.premiere_mutation,
                t.derniere_valeur,
                t.dernier_prix_m2,
                t.surface_habitable,
                t.dpe_energie,
                t.annee_construction,
                t.hauteur_moyenne,
                t.nb_niveau,
                t.type_usage,
                t.nb_log,
                d.surface_parcelle_m2,
                d.surface_plancher_m2,
                d.emprise_sol_m2,
                d.ces_actuel,
                d.ces_potentiel,
                d.potentiel_densification,
                d.surface_constructible_restante,
                d.categorie          AS categorie_densification,
                d.source_ces,
                c.confidence_global,
                c.confidence_label,
                c.score_bdnb,
                c.score_dvf,
                -- La colonne physique s'appelle encore score_zan (heritage ETL) ;
                -- l'API expose score_densification, nom retenu cote contrat.
                c.score_zan AS score_densification,
                c.score_fraicheur
            FROM transactions t
            LEFT JOIN densification_scores d
                ON t.cadastre_parcelle_id = d.id_parcelle
            LEFT JOIN confidence_scores c
                ON t.cadastre_parcelle_id = c.id_parcelle
        """, [id_parcelle]).fetchone()

        if result is None:
            return None

        cols = [
            "id_parcelle", "nb_transactions", "derniere_mutation",
            "premiere_mutation", "derniere_valeur", "dernier_prix_m2",
            "surface_habitable",
            "dpe_energie", "annee_construction", "hauteur_moyenne",
            "nb_niveau", "type_usage", "nb_log",
            "surface_parcelle_m2", "surface_plancher_m2", "emprise_sol_m2",
            "ces_actuel", "ces_potentiel", "potentiel_densification",
            "surface_constructible_restante", "categorie_densification",
            "source_ces",
            "confidence_global", "confidence_label", "score_bdnb",
            "score_dvf", "score_densification", "score_fraicheur",
        ]

        fiche = {}
        for col, val in zip(cols, result):
            if isinstance(val, Decimal):
                fiche[col] = float(val)
            elif val is None:
                fiche[col] = None
            else:
                fiche[col] = val

        float_keys = [
            "derniere_valeur", "dernier_prix_m2", "surface_habitable",
            "surface_parcelle_m2", "surface_plancher_m2", "emprise_sol_m2",
            "ces_actuel", "ces_potentiel", "potentiel_densification",
            "surface_constructible_restante",
            "confidence_global", "score_bdnb", "score_dvf",
            "score_densification", "score_fraicheur",
        ]
        for key in float_keys:
            if fiche.get(key) is not None:
                fiche[key] = round(float(fiche[key]), 4)

        conf = fiche.get("confidence_global")
        if conf is not None and conf < 0.55:
            fiche["warning"] = "Données partielles — fiabilité limitée pour cette parcelle"

        return fiche
