"""Drive the UI in a real browser, capture screenshots, and fail on regressions.

Doubles as an end-to-end smoke test: it loads an example, presses Solve, waits
for the pipeline to actually finish, and reports any console or page errors.
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/shots")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:3000"

problems: list[str] = []


def watch(page) -> None:
    page.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    page.on("console", lambda m: problems.append(f"console.{m.type}: {m.text}")
            if m.type == "error" else None)


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": 1440, "height": 1000},
                                device_scale_factor=2, color_scheme="dark")
        watch(page)

        page.goto(BASE, wait_until="networkidle")
        page.wait_for_timeout(700)
        page.screenshot(path=OUT / "01-landing.png", full_page=True)
        print("landing")

        page.get_by_role("button", name="Maximum Subarray Sum").click()
        page.wait_for_timeout(250)
        page.get_by_role("button", name="Solve", exact=True).click()

        # The pipeline must appear quickly, or the stream is being buffered.
        page.wait_for_selector("text=Derive the complexity budget", timeout=15_000)
        page.wait_for_timeout(400)
        page.screenshot(path=OUT / "02-running.png", full_page=True)
        print("running (stream is live)")

        # Wait for the real completion signal: the result tabs.
        page.wait_for_selector('[role="tab"]:has-text("Explanation")', timeout=180_000)
        page.wait_for_timeout(600)
        page.screenshot(path=OUT / "03-solved.png", full_page=True)
        print("solved")

        for tab, name in [("Explanation", "04-explanation"),
                          ("Verification", "05-verification"),
                          ("Analysis", "06-analysis")]:
            page.get_by_role("tab", name=tab).click()
            page.wait_for_timeout(450)
            page.screenshot(path=OUT / f"{name}.png", full_page=True)
            print(tab.lower())

        # Light mode, to confirm the second theme is usable and not an afterthought.
        light = browser.new_page(viewport={"width": 1440, "height": 1000},
                                 device_scale_factor=2, color_scheme="light")
        watch(light)
        light.goto(BASE, wait_until="networkidle")
        light.wait_for_timeout(600)
        light.screenshot(path=OUT / "07-light.png", full_page=True)
        print("light mode")

        mobile = browser.new_page(viewport={"width": 390, "height": 844},
                                  device_scale_factor=2, color_scheme="dark")
        watch(mobile)
        mobile.goto(BASE, wait_until="networkidle")
        mobile.wait_for_timeout(600)
        mobile.screenshot(path=OUT / "08-mobile.png", full_page=True)
        print("mobile")

        browser.close()

    if problems:
        print("\nBrowser reported problems:")
        for issue in problems:
            print("  -", issue)
        return 1
    print(f"\nClean run. Screenshots in {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
