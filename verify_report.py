import asyncio
import logging
from pathlib import Path

from app.services.report_service import ReportService

logging.basicConfig(level=logging.INFO)

async def test_report():
    service = ReportService(
        template_dir=Path("./app/templates"),
        duckdb_path=Path("./data/foncier.duckdb")
    )

    # Use the mutation ID found earlier
    id_mutation = "2024-321213"

    print(f"Generating report for {id_mutation}...")
    try:
        html_content = await service.generate_html_report(id_mutation)

        # Check if new scores are in HTML
        has_commerce = "Commerce" in html_content
        has_nuisances = "Absence Nuisances" in html_content

        print(f"Report generated. Size: {len(html_content)}")
        print(f"Contains Commerce score: {has_commerce}")
        print(f"Contains Nuisances score: {has_nuisances}")

        with open("report_verification.html", "w", encoding="utf-8") as f:
            f.write(html_content)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_report())
