"""Parcel Report Service.

Generates professional PDF reports for parcels using Playwright (headless Chromium).
Renders HTML templates with full CSS/JS support for charts and visualizations.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

from app.services.enrichment import EnrichmentService
from app.services.filiation_service import FiliationService
from app.services.report_parcel import ReportAggregateMixin, ReportFormattingMixin

if TYPE_CHECKING:
    from app.repositories.interfaces import ILandRepository

logger = logging.getLogger(__name__)

# Playwright browser instance (lazy-loaded singleton)
_browser = None
_playwright = None

# Racine du depot, d'ou le sous-processus Playwright est lance. La profondeur
# depend de l'emplacement de ce fichier : app/services/ est a deux crans.
# `tests/test_parcel_report_service.py` la verrouille.
RACINE_DEPOT = Path(__file__).resolve().parents[2]

# Rendus PDF simultanes par worker. Chacun lance un Python et un Chromium
# (~170 Mo mesures) ; sans borne, le pool d'executeurs en autorisait 10 par
# worker, soit ~3,4 Go de plus pour 20 demandes : le conteneur (4 Go) aurait
# ete tue. Au-dela de 2, les demandes attendent leur tour dans la boucle.
PDF_SIMULTANES = 2
_creneaux_pdf = asyncio.Semaphore(PDF_SIMULTANES)


class ParcelReportService(ReportFormattingMixin, ReportAggregateMixin):
    """Service for generating PDF reports for cadastral parcels.

    Uses Playwright to render HTML templates with full CSS support, so the
    report carries the same charts and the same design tokens as the
    application. See docs/CHARTE_GRAPHIQUE.md.
    """

    def __init__(
        self,
        land_repository: "ILandRepository",
        duckdb_path: str | Path = "./data/foncier.duckdb",
        template_dir: Path | str = "./app/templates",
    ) -> None:
        self._template_dir = Path(template_dir)
        self._duckdb_path = Path(duckdb_path)
        self._land_repo = land_repository
        self._filiation_service = FiliationService(duckdb_path=str(duckdb_path))
        self._enrichment_service = EnrichmentService(duckdb_path=str(duckdb_path))

        # Setup Jinja2
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            autoescape=True,
        )
        # Add custom filters
        self._jinja_env.filters["format_currency"] = self._format_currency
        self._jinja_env.filters["format_date"] = self._format_date

    def _render_html_to_pdf_sync(self, html_content: str) -> bytes:
        """Render HTML to PDF via sous-processus (contourne NotImplementedError asyncio sur Windows).

        Playwright utilise asyncio en interne ; sous Windows le subprocess échoue
        quand il est lancé depuis un thread/loop existant. Un process séparé évite le conflit.
        """
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            inp = Path(tmp) / "report.html"
            out = Path(tmp) / "report.pdf"
            inp.write_text(html_content, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "app.scripts.html_to_pdf", str(inp), str(out)],
                capture_output=True,
                timeout=60,
                cwd=RACINE_DEPOT,
            )

            if result.returncode != 0:
                err = (result.stderr or b"").decode("utf-8", errors="replace")
                if "chromium" in err.lower() or "executable" in err.lower():
                    raise RuntimeError(
                        "Playwright Chromium non installé. Exécutez : playwright install chromium"
                    )
                raise RuntimeError(f"PDF conversion failed: {err or result.returncode}")

            return out.read_bytes()

    async def _render_html_to_pdf(self, html_content: str) -> bytes:
        """Render HTML to PDF (process séparé pour compatibilité Windows)."""
        loop = asyncio.get_running_loop()
        async with _creneaux_pdf:
            return await loop.run_in_executor(
                None,
                self._render_html_to_pdf_sync,
                html_content,
            )

    async def generate_parcel_pdf(self, parcel_id: str) -> bytes:
        """Generate a professional PDF report for a parcel.

        Args:
            parcel_id: The 14-character cadastral parcel ID

        Returns:
            PDF file as bytes

        Raises:
            ValueError: If parcel not found
            TimeoutError: If PDF generation times out
        """
        logger.info(f"Generating PDF report for parcel {parcel_id}")

        # Aggregate all data
        data = await self._aggregate_parcel_data(parcel_id)

        # Log warning if no data found, but proceed anyway (template handles missing sections)
        if not data.get("parcel_info") and not data.get("transactions"):
            logger.warning(f"No parcel_info or transactions for {parcel_id}, generating minimal report")

        # Render HTML template
        template = self._jinja_env.get_template("parcel_report.html")
        html_content = template.render(**data)

        # Use async Playwright to avoid thread/event-loop conflicts on Windows
        pdf_bytes = await self._render_html_to_pdf(html_content)

        logger.info(f"PDF generated successfully: {len(pdf_bytes)} bytes")
        return pdf_bytes

    async def generate_html_preview(self, parcel_id: str) -> str:
        """Generate HTML preview (for debugging).

        Returns the rendered HTML without PDF conversion.
        """
        data = await self._aggregate_parcel_data(parcel_id)
        template = self._jinja_env.get_template("parcel_report.html")
        return template.render(**data)


async def cleanup_browser():
    """Cleanup Playwright browser on shutdown."""
    global _browser, _playwright
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None
    logger.info("Playwright browser closed")
