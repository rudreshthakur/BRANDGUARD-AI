"""Render docs/report/report.html to the project PDF with headless Chromium.

Usage: python docs/build_report.py      (requires: pip install playwright && playwright install chromium)
To refresh screenshots first, run the E2E test (it writes e2e/artifacts/) and re-crop into docs/report/img/.
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "report" / "report.html"
OUT = ROOT / "BrandGuard_AI_Round2_Project_Report.pdf"

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(SRC.as_uri())
    page.wait_for_load_state("networkidle")
    page.evaluate("document.fonts.ready")
    page.pdf(path=str(OUT), format="A4", print_background=True, prefer_css_page_size=True,
             display_header_footer=True, header_template="<span></span>",
             footer_template=('<div style="font-size:7.5pt;color:#6B7385;width:100%;padding:0 17mm;display:flex;'
                              'justify-content:space-between;font-family:sans-serif"><span>BrandGuard AI · Team Khiladi 786 · '
                              'Round 2 project report</span><span class="pageNumber"></span></div>'),
             margin={"top": "16mm", "bottom": "18mm", "left": "17mm", "right": "17mm"})
    browser.close()
print(f"Wrote {OUT}")
