"""Mixin pour densification et search_parcelles."""

from decimal import Decimal

from app.domain.models import DensificationScore


class DuckDBDensificationMixin:
    """Mixin densification et recherche parcelles."""

    async def get_densification_score(self, id_parcelle: str) -> DensificationScore | None:
        """Retrieve densification score for a single parcel."""
        conn = self._get_connection(self._dept_from_parcelle(id_parcelle))
        result = conn.execute(
            """
            SELECT id_parcelle, surface_parcelle_m2, surface_plancher_m2,
                   ces_actuel, ces_potentiel
            FROM densification_scores
            WHERE id_parcelle = ?
            """,
            [id_parcelle],
        ).fetchone()

        if result is None:
            return None

        return DensificationScore(
            id_parcelle=result[0],
            surface_parcelle_m2=Decimal(str(result[1])),
            surface_plancher_m2=Decimal(str(result[2])),
            ces_actuel=Decimal(str(result[3])),
            ces_potentiel=Decimal(str(result[4])),
        )

    async def get_densification_scores_by_commune(
        self, code_commune: str
    ) -> list[DensificationScore]:
        """Retrieve all densification scores for a commune."""
        conn = self._get_connection(self._dept_from_commune(code_commune))
        results = conn.execute(
            """
            SELECT id_parcelle, surface_parcelle_m2, surface_plancher_m2,
                   ces_actuel, ces_potentiel
            FROM densification_scores
            WHERE code_commune = ?
            ORDER BY potentiel_densification DESC
            """,
            [code_commune],
        ).fetchall()

        return [
            DensificationScore(
                id_parcelle=r[0],
                surface_parcelle_m2=Decimal(str(r[1])),
                surface_plancher_m2=Decimal(str(r[2])),
                ces_actuel=Decimal(str(r[3])),
                ces_potentiel=Decimal(str(r[4])),
            )
            for r in results
        ]

    async def get_top_densification_opportunities(
        self, code_commune: str, limit: int = 20
    ) -> list[DensificationScore]:
        """Retrieve top densification opportunities for a commune."""
        conn = self._get_connection(self._dept_from_commune(code_commune))
        results = conn.execute(
            """
            SELECT id_parcelle, surface_parcelle_m2, surface_plancher_m2,
                   ces_actuel, ces_potentiel
            FROM densification_scores
            WHERE code_commune = ?
              AND categorie = 'FORT'
            ORDER BY surface_constructible_restante DESC
            LIMIT ?
            """,
            [code_commune, limit],
        ).fetchall()

        return [
            DensificationScore(
                id_parcelle=r[0],
                surface_parcelle_m2=Decimal(str(r[1])),
                surface_plancher_m2=Decimal(str(r[2])),
                ces_actuel=Decimal(str(r[3])),
                ces_potentiel=Decimal(str(r[4])),
            )
            for r in results
        ]

    async def search_parcelles(
        self,
        code_commune: str | None = None,
        categorie: str | None = None,
        confidence_min: float = 0.0,
        prix_m2_max: float | None = None,
        surface_min: float | None = None,
        annee_min: int | None = None,
        limit: int = 500,
    ) -> list[dict]:
        """Multi-criteria parcel search joining DVF, densification and confidence."""
        dept = self._dept_from_commune(code_commune) if code_commune else None
        conn = self._get_connection(dept)

        clauses = ["COALESCE(f.is_outlier, FALSE) = FALSE"]
        params: list = []

        if code_commune:
            clauses.append("f.code_commune = ?")
            params.append(code_commune)
        if categorie:
            clauses.append("d.categorie = ?")
            params.append(categorie.upper())
        if confidence_min > 0:
            clauses.append("c.confidence_global >= ?")
            params.append(confidence_min)
        if prix_m2_max is not None:
            clauses.append("f.prix_m2 <= ?")
            params.append(prix_m2_max)
        if surface_min is not None:
            clauses.append("d.surface_parcelle_m2 >= ?")
            params.append(surface_min)
        if annee_min is not None:
            clauses.append("YEAR(f.date_mutation) >= ?")
            params.append(annee_min)

        where = " AND ".join(clauses)

        query = f"""
            SELECT
                f.cadastre_parcelle_id   AS id_parcelle,
                f.code_commune,
                f.valeur_fonciere,
                f.prix_m2,
                d.surface_parcelle_m2,
                f.date_mutation,
                d.categorie,
                d.potentiel_densification,
                d.surface_constructible_restante,
                d.source_ces,
                c.confidence_global,
                c.confidence_label
            FROM france_foncier_test f
            LEFT JOIN densification_scores d
                ON f.cadastre_parcelle_id = d.id_parcelle
            LEFT JOIN confidence_scores c
                ON f.cadastre_parcelle_id = c.id_parcelle
            WHERE {where}
            ORDER BY d.potentiel_densification DESC NULLS LAST
            LIMIT ?
        """
        params.append(limit)

        results = conn.execute(query, params).fetchall()
        cols = [
            "id_parcelle", "code_commune", "valeur_fonciere", "prix_m2",
            "surface_parcelle_m2", "date_mutation", "categorie",
            "potentiel_densification", "surface_constructible_restante",
            "source_ces", "confidence_global", "confidence_label",
        ]

        rows = []
        for row in results:
            d = {}
            for col, val in zip(cols, row):
                if isinstance(val, Decimal):
                    d[col] = float(val)
                else:
                    d[col] = val
            rows.append(d)
        return rows
