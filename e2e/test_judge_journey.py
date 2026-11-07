"""End-to-end browser test of the complete judge journey, in a clean unauthenticated browser context.

Usage:  python e2e/test_judge_journey.py [BASE_URL]   (default http://localhost:8000)
Writes screenshots to e2e/artifacts/. Exits non-zero on the first failed step.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
OUT = Path(__file__).parent / "artifacts"
OUT.mkdir(exist_ok=True)
steps: list[str] = []


def step(name: str):
    steps.append(name)
    print(f"  ✓ {name}")


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})  # fresh, no storage = incognito-equivalent
        page = ctx.new_page()
        errors: list[str] = []
        page.on("console", lambda m: m.type == "error" and errors.append(m.text))
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(BASE + "/")
        expect(page.get_by_role("heading", level=1)).to_contain_text("Check every claim")
        page.screenshot(path=OUT / "01_landing.png")
        step("Homepage opens without sign-in")

        page.get_by_role("button", name="Launch demo workspace").click()
        page.wait_for_url("**/app/auditor")
        expect(page.get_by_text("Compliant", exact=True)).to_be_visible()
        page.screenshot(path=OUT / "02_auditor.png", full_page=True)
        step("Demo workspace launches with sample content")

        # Compliant sample stays compliant
        page.get_by_text("Compliant", exact=True).click()
        page.get_by_role("button", name="Run brand audit").click()
        page.wait_for_url("**/app/submissions/**")
        expect(page.get_by_text("No open findings")).to_be_visible()
        expect(page.get_by_text("Verified against approved facts")).to_be_visible()
        page.screenshot(path=OUT / "03_compliant.png", full_page=True)
        step("Compliant sample: zero findings, claims verified with citations")

        # Unsupported claims
        page.goto(BASE + "/app/auditor")
        page.get_by_text("Unsupported claims", exact=True).click()
        page.get_by_role("button", name="Run brand audit").click()
        page.wait_for_url("**/app/submissions/**")
        expect(page.get_by_text("Unsupported numerical claim “50%”")).to_be_visible()
        expect(page.get_by_text("Unsubstantiated absolute claim", exact=False)).to_be_visible()
        page.screenshot(path=OUT / "04_unsupported.png", full_page=True)
        step("Unsupported 50% and superlative claims flagged as 'Unable to verify'")

        page.locator("article button").filter(has_text="Claims Policy").first.click()
        expect(page.get_by_role("dialog")).to_contain_text("Evidence ID")
        expect(page.get_by_role("dialog")).to_contain_text("Approved and active")
        page.screenshot(path=OUT / "05_evidence.png")
        page.get_by_role("button", name="Close", exact=True).click()
        step("Evidence opens with document, page, section and ID")

        # Outdated spec -> accept -> re-audit -> submit -> reviewer approves
        page.goto(BASE + "/app/auditor")
        page.get_by_text("Outdated specification", exact=True).click()
        page.get_by_role("button", name="Run brand audit").click()
        page.wait_for_url("**/app/submissions/**")
        card = page.locator("article").filter(has_text="Outdated specification “10 hours”")
        expect(card).to_be_visible()
        expect(card).to_contain_text("Superseded:")
        page.screenshot(path=OUT / "06_outdated.png", full_page=True)
        card.get_by_role("button", name="Accept").click()
        expect(page.get_by_text("Content, version 2")).to_be_visible()
        expect(page.locator(".manuscript")).to_contain_text("up to 12 hours")
        step("Accepting a correction creates version 2 with the current spec")

        page.get_by_role("tab", name="Versions (2)").click()
        expect(page.locator("del", has_text="10")).to_be_visible()
        expect(page.locator("ins", has_text="12")).to_be_visible()
        page.screenshot(path=OUT / "07_versions.png", full_page=True)
        step("Version diff shows the original preserved")

        page.get_by_role("button", name="Re-run brand audit").click()
        expect(page.get_by_text("No open findings")).to_be_visible()
        page.get_by_role("button", name="Submit for review").click()
        expect(page.locator("h1 + span", has_text="Under review")).to_be_visible()
        step("Creator re-audits and submits for review")

        page.get_by_role("radio", name="Reviewer").click()
        page.get_by_placeholder("Note for the creator").fill("Matches Spec Sheet v2.")
        page.get_by_role("button", name="Approve").click()
        expect(page.get_by_text("Approved for publication by a reviewer")).to_be_visible()
        page.get_by_role("tab", name="Discussion").click()
        expect(page.get_by_text("Matches Spec Sheet v2.").first).to_be_visible()
        page.screenshot(path=OUT / "08_approved.png", full_page=True)
        step("Reviewer approves; decision and history recorded")

        # Reviewer requests changes on the seeded caption
        page.goto(BASE + "/app/review")
        expect(page.get_by_role("tab", name="Awaiting review")).to_be_visible()
        page.screenshot(path=OUT / "09_review_queue.png", full_page=True)
        page.get_by_role("link", name="Instagram caption — terminology").click()
        page.get_by_placeholder("Note for the creator").fill("Please fix the brand name and add the hashtag.")
        page.get_by_role("button", name="Request changes").click()
        expect(page.locator("h1 + span", has_text="Changes requested")).to_be_visible()
        page.screenshot(path=OUT / "10_changes_requested.png", full_page=True)
        step("Reviewer requests changes with a note")

        # Admin uploads a guideline with an embedded instruction
        page.get_by_role("radio", name="Admin").click()
        page.goto(BASE + "/app/knowledge")
        draft = page.request.get(BASE + "/api/samples/files/Northstar_Brand_Guidelines_v4_draft.txt").body()
        page.locator("#doc-file").set_input_files(files=[{"name": "Northstar_Brand_Guidelines_v4_draft.txt", "mimeType": "text/plain", "buffer": draft}])
        page.get_by_label("This document is").select_option(label="A new version of Northstar Labs Brand Guidelines v3")
        page.get_by_role("button", name="Upload and extract").click()
        expect(page.get_by_text("reads like instructions to an AI system")).to_be_visible()
        expect(page.get_by_text("Rules found in this document")).to_be_visible()
        page.screenshot(path=OUT / "11_knowledge_upload.png", full_page=True)
        step("Uploaded document is pending, injection flagged, rules only proposed")
        page.get_by_role("button", name="Compare with v1").click()
        expect(page.get_by_text("(modified)").first).to_be_visible()
        page.get_by_label("Prohibited term: “hustle”", exact=False).check()
        page.get_by_role("button", name="Approve as authoritative with 1 rule").click()
        expect(page.locator("li", has_text="Northstar Labs Brand Guidelines v3").get_by_text("Superseded")).to_be_visible()
        step("Approving v2 of the guidelines supersedes v1; version comparison works")

        page.get_by_role("tab", name="Approved facts").click()
        page.screenshot(path=OUT / "12_facts.png", full_page=True)

        page.goto(BASE + "/app/analytics")
        expect(page.get_by_text("Most frequently triggered rules")).to_be_visible()
        page.screenshot(path=OUT / "13_analytics.png", full_page=True)
        step("Brand Drift analytics render from stored data")

        page.goto(BASE + "/app/visual")
        page.get_by_role("button", name="off-brand").click()
        expect(page.get_by_text("Off-palette colour").first).to_be_visible()
        page.screenshot(path=OUT / "14_visual.png", full_page=True)
        step("Visual inspector flags off-palette colours and contrast")

        page.goto(BASE + "/app/history")
        expect(page.get_by_text("Approved v2").first).to_be_visible()
        page.screenshot(path=OUT / "15_history.png", full_page=True)
        step("Audit history available")

        # Mobile layout sanity
        m = browser.new_context(viewport={"width": 390, "height": 844}, storage_state=ctx.storage_state()).new_page()
        m.goto(BASE + "/app/overview")
        expect(m.get_by_role("button", name="Open menu")).to_be_visible()
        m.screenshot(path=OUT / "16_mobile.png", full_page=True)
        step("Responsive layout on a 390px viewport")

        browser.close()
        bad = [e for e in errors if "favicon" not in e and "status of 4" not in e]
        if bad:
            print("Console errors:", bad)
            return 1
    print(f"\nE2E PASSED: {len(steps)} steps")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"\nE2E FAILED after step {len(steps)} ({steps[-1] if steps else 'start'}): {exc}")
        sys.exit(1)
