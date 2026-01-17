"""Parcel Report Service.

Generates professional PDF reports for parcels using Playwright (headless Chromium).
Renders HTML templates with full CSS/JS support for charts and visualizations.
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader

from app.repositories.duckdb_repository import DuckDBLandRepository
from app.services.enrichment import EnrichmentService
from app.services.filiation_service import FiliationService

logger = logging.getLogger(__name__)

# Playwright browser instance (lazy-loaded singleton)
_browser = None
_playwright = None


class ParcelReportService:
    """Service for generating PDF reports for cadastral parcels.
    
    Uses Playwright to render HTML templates with full CSS support,
    enabling ApexCharts, Tailwind glassmorphism, and satellite imagery.
    """

    def __init__(
        self,
        template_dir: Path | str = "./app/templates",
        duckdb_path: Path | str = "./data/foncier.duckdb",
    ) -> None:
        self._template_dir = Path(template_dir)
        self._duckdb_path = Path(duckdb_path)
        self._land_repo = DuckDBLandRepository(db_path=duckdb_path)
        self._filiation_service = FiliationService(duckdb_path=str(duckdb_path))
        self._enrichment_service = EnrichmentService(duckdb_path=duckdb_path)

        # Setup Jinja2
        self._jinja_env = Environment(
            loader=FileSystemLoader(str(self._template_dir)),
            autoescape=True,
        )
        # Add custom filters
        self._jinja_env.filters["format_currency"] = self._format_currency
        self._jinja_env.filters["format_date"] = self._format_date

    @staticmethod
    def _format_currency(value: float | Decimal | None) -> str:
        """Format value as French currency."""
        if value is None:
            return "N/A"
        return f"{float(value):,.0f} €".replace(",", " ")

    @staticmethod
    def _format_date(date_str: str | None) -> str:
        """Format date string to French format."""
        if not date_str:
            return "N/A"
        try:
            dt = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
            return dt.strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return str(date_str)

    def _get_browser_sync(self):
        """Get or create Playwright browser instance (sync API for Windows compat)."""
        global _browser, _playwright

        if _browser is None:
            from playwright.sync_api import sync_playwright
            _playwright = sync_playwright().start()
            _browser = _playwright.chromium.launch(
                headless=True,
                args=["--disable-gpu", "--no-sandbox"]
            )
            logger.info("Playwright browser launched")

        return _browser

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
                        "events": [{"type_filiation": "Division", "date_acte": str(node.date_division) if node.date_division else None, "parcelles_filles": [node.parent.id_parcelle]}]
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

        # Run Playwright in a separate thread (sync API can't run in async loop)
        import concurrent.futures
        loop = asyncio.get_event_loop()

        def _generate_pdf_sync(html: str) -> bytes:
            """Sync function to generate PDF with Playwright."""
            import time

            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-gpu", "--no-sandbox"]
                )
                page = browser.new_page()

                try:
                    # Set content
                    page.set_content(html, wait_until="networkidle", timeout=15000)
                    time.sleep(0.3)  # Brief wait for rendering

                    # Generate PDF
                    pdf_bytes = page.pdf(
                        format="A4",
                        margin={"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"},
                        print_background=True,
                        prefer_css_page_size=False,
                    )
                    return pdf_bytes
                finally:
                    page.close()
                    browser.close()

        # Run in thread pool
        with concurrent.futures.ThreadPoolExecutor() as executor:
            pdf_bytes = await loop.run_in_executor(executor, _generate_pdf_sync, html_content)

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
