"""Report Generation Service.

Generates reports:
- HTML using Jinja2 templates (for web view)
- PDF using ReportLab (delegated to ReportGenerator)
"""

import base64
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.domain.models import MutationAggregate, NatureMutation
from app.repositories.duckdb_repository import DuckDBLandRepository
from app.repositories.dvf_repository import DvfRepository
from app.services.enrichment import EnrichmentService
from app.services.report_generator import ReportGenerator

logger = logging.getLogger(__name__)


class ReportService:
    """Service for generating PDF/HTML reports."""

    def __init__(
        self,
        template_dir: Path | str = "./app/templates",
        duckdb_path: Path | str = "./data/foncier.duckdb",
    ) -> None:
        self._template_dir = Path(template_dir)
        self._duckdb_path = Path(duckdb_path)
        self._dvf_repo = DvfRepository(db_path=duckdb_path)
        self._land_repo = DuckDBLandRepository(db_path=duckdb_path)
        self._enrichment = EnrichmentService(duckdb_path=duckdb_path)
        self._generator = ReportGenerator()

        # Setup Jinja2
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            autoescape=True,
        )

    async def get_mutation_by_id(self, id_mutation: str) -> MutationAggregate | None:
        """Find a mutation by its ID."""
        import duckdb
        conn = duckdb.connect(str(self._duckdb_path), read_only=True)

        result = conn.execute("""
            SELECT id_mutation, date_mutation, nature_mutation, valeur_fonciere,
                   code_commune, parcelles, surface_habitable_totale, nombre_locaux,
                   longitude, latitude
            FROM mutations_aggregated
            WHERE id_mutation = ?
            LIMIT 1
        """, [id_mutation]).fetchone()

        conn.close()

        if not result:
            return None

        mutation_date = result[1]
        if isinstance(mutation_date, str):
            mutation_date = datetime.strptime(mutation_date, "%Y-%m-%d").date()

        return MutationAggregate(
            id_mutation=result[0],
            date_mutation=mutation_date,
            nature_mutation=NatureMutation("Vente"),
            valeur_fonciere=Decimal(str(result[3])),
            code_commune=str(result[4]),
            parcelles=result[5] if result[5] else [],
            surface_habitable_totale=Decimal(str(result[6])),
            nombre_locaux=result[7],
            longitude=result[8],
            latitude=result[9],
        )

    async def generate_report(
        self,
        id_mutation: str,
        format: str = "pdf",
    ) -> bytes:
        """Generate report for a mutation using ReportLab (PDF) or Jinja2 (HTML)."""
        # Data fetching (Common)
        mutation = await self.get_mutation_by_id(id_mutation)
        if not mutation:
            raise ValueError(f"Mutation {id_mutation} not found")

        stats = await self._dvf_repo.get_price_stats(mutation.code_commune)

        # Enrichment
        enrichment_data = {}
        if mutation.latitude and mutation.longitude:
            enrichment = await self._enrichment.calculate_enrichment(
                latitude=mutation.latitude,
                longitude=mutation.longitude,
                parcelle_id=mutation.parcelles[0] if mutation.parcelles else None,
            )
            enrichment_data = {
                'education_score': float(enrichment.schools_score),
                'transport_score': float(enrichment.transport_score),
                'commerce_score': float(enrichment.commerce_score if hasattr(enrichment, 'commerce_score') else 5.0),
                'green_spaces_score': float(enrichment.green_spaces_score),
                'global_score': float(enrichment.global_score),
            }
        else:
            enrichment_data = {k: 5.0 for k in ['education_score', 'transport_score', 'commerce_score', 'green_spaces_score', 'global_score']}

        # Parcel Geometry for Map
        parcelle = None
        if mutation.parcelles:
            # Try to get the first parcel
            parcelle = await self._land_repo.get_parcelle_by_id(mutation.parcelles[0])

        # -- PDF Generation (ReportLab) --
        if format == "pdf":
            price_chart_buf = self._generator.generate_price_chart(mutation, stats)
            radar_chart_buf = self._generator.generate_radar_chart(enrichment_data)
            map_buf = self._generator.generate_parcel_map(parcelle)

            logger.info(f"Generating PDF report (ReportLab) for {id_mutation}")
            return self._generator.create_pdf_report(
                mutation, stats, enrichment_data, price_chart_buf, radar_chart_buf, map_buf
            )

        # -- HTML Generation (Jinja2) --
        # Prepare base64 images for HTML
        price_chart_buf = self._generator.generate_price_chart(mutation, stats)
        radar_chart_buf = self._generator.generate_radar_chart(enrichment_data)

        price_chart_b64 = base64.b64encode(price_chart_buf.getvalue()).decode('utf-8')
        radar_chart_b64 = base64.b64encode(radar_chart_buf.getvalue()).decode('utf-8')

        # Calculate percentile for HTML bar
        min_p = float(stats.get('min_price_m2', 0))
        max_p = float(stats.get('max_price_m2', 1))
        cur_p = float(mutation.prix_m2 or 0)
        rng = max_p - min_p if max_p > min_p else 1
        percentile = min(100, max(0, int((cur_p - min_p) / rng * 100)))

        template = self._jinja_env.get_template('land_report.html')
        html_content = template.render(
            mutation=mutation,
            stats=stats,
            enrichment=enrichment_data,
            price_percentile=percentile,
            price_chart_base64=price_chart_b64,
            radar_chart_base64=radar_chart_b64,
            generated_date=datetime.now().strftime("%d/%m/%Y %H:%M"),
        )

        logger.info(f"Generating HTML report for {id_mutation}")
        return html_content.encode('utf-8')
