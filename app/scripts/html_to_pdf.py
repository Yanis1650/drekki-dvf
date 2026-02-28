"""CLI standalone: HTML → PDF via Playwright.

S'exécute en processus séparé pour éviter NotImplementedError asyncio sur Windows.
Usage: python -m app.scripts.html_to_pdf input.html output.pdf
"""

import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python -m app.scripts.html_to_pdf <input.html> <output.pdf>", file=sys.stderr)
        return 1

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f"Input not found: {input_path}", file=sys.stderr)
        return 1

    html_content = input_path.read_text(encoding="utf-8")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright non installé: pip install playwright && playwright install chromium", file=sys.stderr)
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--disable-gpu", "--no-sandbox"])
        page = browser.new_page()
        page.set_content(html_content, wait_until="load", timeout=15000)
        import time
        time.sleep(0.3)
        page.emulate_media(media="print")
        pdf_bytes = page.pdf(
            format="A4",
            margin={"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"},
            print_background=True,
            prefer_css_page_size=False,
        )
        page.close()
        browser.close()

    output_path.write_bytes(pdf_bytes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
