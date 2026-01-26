"""
Screenshot capture script for ACI Migrator v2.0 documentation
Captures all required UI screenshots for README.md
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
from playwright.sync_api import sync_playwright

# Set UTF-8 encoding for console output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration
SCREENSHOTS_DIR = "docs/screenshots"
VIEWPORT = {"width": 1920, "height": 1080}

# Create screenshots directory if it doesn't exist
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def resolve_base_url():
    env_url = os.getenv("ACI_BASE_URL")
    if env_url:
        return env_url.rstrip("/")

    candidate_ports = list(range(5001, 5051)) + [5000]
    for port in candidate_ports:
        url = f"http://127.0.0.1:{port}"
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2) as resp:
                if resp.status == 200:
                    return url
        except Exception:
            continue

    raise RuntimeError("Could not detect running ACI Migrator instance on 127.0.0.1:5000-5050")


def prepare_demo_data(page, base_url):
    """Ensure a demo fabric exists and mock data is loaded for screenshots."""
    demo_fabric = "demo-fabric"
    page.goto(f"{base_url}/ui/select?mode=legacy&next=/", wait_until="networkidle", timeout=30000)

    js = f"""
    (async () => {{
        const fabricName = "{demo_fabric}";
        try {{
            await fetch('/fabrics', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{name: fabricName}})
            }});
        }} catch (e) {{}}

        try {{
            await fetch('/api/mcp/import', {{
                method: 'POST',
                headers: {{'Content-Type': 'application/json'}},
                body: JSON.stringify({{mcp_url: 'mock', fabric_name: fabricName}})
            }});
        }} catch (e) {{}}
    }})()
    """
    page.evaluate(js)
    page.wait_for_timeout(1500)

def capture_screenshots():
    """Capture all required screenshots"""
    print("Starting screenshot capture for ACI Migrator v2.0...")

    base_url = resolve_base_url()
    print(f"Using base URL: {base_url}")

    with sync_playwright() as p:
        # Launch browser
        print("Launching Chromium browser...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()

        prepare_demo_data(page, base_url)

        screenshots = [
            {
                "name": "home-classic.png",
                "url": "/ui/select?mode=legacy&next=/",
                "title": "Dashboard/Home Page (Classic UI)",
                "wait": 2000
            },
            {
                "name": "home-new.png",
                "url": "/ui/select?mode=new&next=/",
                "title": "Dashboard/Home Page (New UI)",
                "wait": 2000
            },
            {
                "name": "upload.png",
                "url": "/upload_page",
                "title": "Upload Data Page",
                "wait": 1500
            },
            {
                "name": "analyze.png",
                "url": "/analyze",
                "title": "Analyze Data Page",
                "wait": 1500
            },
            {
                "name": "analyze-validation.png",
                "url": "/analyze",
                "title": "Analyze Validation Tab",
                "wait": 1500,
                "tab": "validation"
            },
            {
                "name": "analyze-data-explorer.png",
                "url": "/analyze",
                "title": "Analyze Data Explorer Tab",
                "wait": 1500,
                "tab": "data"
            },
            {
                "name": "analyze-spreadsheet.png",
                "url": "/analyze",
                "title": "Analyze Spreadsheet Tab",
                "wait": 1500,
                "tab": "spreadsheet"
            },
            {
                "name": "analyze-ports.png",
                "url": "/analyze",
                "title": "Analyze Port Status Tab",
                "wait": 1500,
                "tab": "ports"
            },
            {
                "name": "visualize.png",
                "url": "/visualize",
                "title": "Visualization Dashboard",
                "wait": 2000
            },
            {
                "name": "plan.png",
                "url": "/plan",
                "title": "Migration Planning Page",
                "wait": 1500
            },
            {
                "name": "report.png",
                "url": "/report",
                "title": "Reports Page",
                "wait": 1000
            }
        ]

        for i, screenshot in enumerate(screenshots, 1):
            try:
                print(f"\n[{i}/{len(screenshots)}] Capturing {screenshot['title']}...")

                # Navigate to page
                url = f"{base_url}{screenshot['url']}"
                print(f"   URL: {url}")
                page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait for animations and content to load
                page.wait_for_timeout(screenshot['wait'])

                if screenshot.get("tab"):
                    tab_selector = f"button.analysis-tab[data-panel='{screenshot['tab']}']"
                    page.click(tab_selector, timeout=10000)
                    page.wait_for_timeout(800)

                # Take screenshot
                filepath = os.path.join(SCREENSHOTS_DIR, screenshot['name'])
                page.screenshot(path=filepath, full_page=True)

                # Get file size
                size = os.path.getsize(filepath) / 1024
                print(f"   Saved: {screenshot['name']} ({size:.1f} KB)")

            except Exception as e:
                print(f"   Error capturing {screenshot['name']}: {str(e)}")

        # Optional: Capture sidebar collapsed view
        try:
            print("\n[Extra] Capturing Sidebar Collapsed View...")
            page.goto(f"{base_url}/ui/select?mode=legacy&next=/", wait_until="networkidle")
            page.wait_for_timeout(1000)

            try:
                page.click("button[aria-label='Toggle sidebar']", timeout=5000)
            except Exception:
                try:
                    page.click("#sidebar-toggle", timeout=5000)
                except Exception:
                    print("   Could not find sidebar toggle button")

            page.wait_for_timeout(500)
            filepath = os.path.join(SCREENSHOTS_DIR, "sidebar-collapsed.png")
            page.screenshot(path=filepath, full_page=True)
            size = os.path.getsize(filepath) / 1024
            print(f"   Saved: sidebar-collapsed.png ({size:.1f} KB)")
        except Exception as e:
            print(f"   Could not capture collapsed sidebar: {str(e)}")

        # Optional: Capture mobile view
        try:
            print("\n[Extra] Capturing Mobile View...")
            mobile_context = browser.new_context(
                viewport={"width": 375, "height": 812},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
            )
            mobile_page = mobile_context.new_page()
            mobile_page.goto(f"{base_url}/ui/select?mode=legacy&next=/", wait_until="networkidle")
            mobile_page.wait_for_timeout(2000)

            filepath = os.path.join(SCREENSHOTS_DIR, "mobile-view.png")
            mobile_page.screenshot(path=filepath, full_page=True)
            size = os.path.getsize(filepath) / 1024
            print(f"   Saved: mobile-view.png ({size:.1f} KB)")

            mobile_context.close()
        except Exception as e:
            print(f"   Could not capture mobile view: {str(e)}")

        browser.close()

    print("\nScreenshot capture complete.")
    print(f"Screenshots saved to: {os.path.abspath(SCREENSHOTS_DIR)}")
    print("\nCaptured files:")

    for filename in sorted(os.listdir(SCREENSHOTS_DIR)):
        if filename.endswith('.png'):
            filepath = os.path.join(SCREENSHOTS_DIR, filename)
            size = os.path.getsize(filepath) / 1024
            print(f"   - {filename} ({size:.1f} KB)")

if __name__ == "__main__":
    print("=" * 70)
    print("ACI Migrator v2.0 Screenshot Capture Tool")
    print("=" * 70)
    print("\nIMPORTANT: Make sure the Flask application is running.")
    print("Expected URL: http://127.0.0.1:<port>")
    print("\nPress Ctrl+C to cancel, or wait 3 seconds to continue...")

    try:
        time.sleep(3)
        capture_screenshots()
    except KeyboardInterrupt:
        print("\nScreenshot capture cancelled by user.")
    except Exception as e:
        print(f"\nError: {str(e)}")
        print("\nMake sure:")
        print("1. Flask app is running (python app.py)")
        print("2. App is accessible at http://127.0.0.1:5000")
        print("3. You have created a fabric and uploaded some data")
