"""
Screenshot capture script for acimig v1.0 documentation
Captures all required UI screenshots for README.md
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

# Set UTF-8 encoding for console output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Configuration
BASE_URL = "http://127.0.0.1:5000"
SCREENSHOTS_DIR = "docs/screenshots"
VIEWPORT = {"width": 1920, "height": 1080}

# Create screenshots directory if it doesn't exist
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def capture_screenshots():
    """Capture all required screenshots"""
    print("🎬 Starting screenshot capture for acimig v1.0...")

    with sync_playwright() as p:
        # Launch browser
        print("🌐 Launching Chromium browser...")
        browser = p.chromium.launch(headless=False)  # Set to True for headless mode
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()

        screenshots = [
            {
                "name": "home.png",
                "url": "/",
                "title": "Dashboard/Home Page",
                "wait": 2000  # Wait for animations
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
                "name": "visualize.png",
                "url": "/visualize",
                "title": "Visualization Dashboard",
                "wait": 2000  # Wait for charts to render
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
                print(f"\n📸 [{i}/{len(screenshots)}] Capturing {screenshot['title']}...")

                # Navigate to page
                url = f"{BASE_URL}{screenshot['url']}"
                print(f"   📍 URL: {url}")
                page.goto(url, wait_until="networkidle", timeout=30000)

                # Wait for animations and content to load
                page.wait_for_timeout(screenshot['wait'])

                # Take screenshot
                filepath = os.path.join(SCREENSHOTS_DIR, screenshot['name'])
                page.screenshot(path=filepath, full_page=True)

                # Get file size
                size = os.path.getsize(filepath) / 1024  # KB
                print(f"   ✅ Saved: {screenshot['name']} ({size:.1f} KB)")

            except Exception as e:
                print(f"   ❌ Error capturing {screenshot['name']}: {str(e)}")

        # Optional: Capture sidebar collapsed view
        try:
            print(f"\n📸 [Extra] Capturing Sidebar Collapsed View...")
            page.goto(f"{BASE_URL}/", wait_until="networkidle")
            page.wait_for_timeout(1000)

            # Try to find and click sidebar toggle
            # This depends on the actual HTML structure - adjust selector if needed
            try:
                page.click("button[aria-label='Toggle sidebar']", timeout=5000)
            except:
                # Alternative selectors
                try:
                    page.click("#sidebar-toggle", timeout=5000)
                except:
                    print("   ⚠️  Could not find sidebar toggle button")

            page.wait_for_timeout(500)
            filepath = os.path.join(SCREENSHOTS_DIR, "sidebar-collapsed.png")
            page.screenshot(path=filepath, full_page=True)
            size = os.path.getsize(filepath) / 1024
            print(f"   ✅ Saved: sidebar-collapsed.png ({size:.1f} KB)")
        except Exception as e:
            print(f"   ⚠️  Could not capture collapsed sidebar: {str(e)}")

        # Optional: Capture mobile view
        try:
            print(f"\n📱 [Extra] Capturing Mobile View...")
            mobile_context = browser.new_context(
                viewport={"width": 375, "height": 812},
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15"
            )
            mobile_page = mobile_context.new_page()
            mobile_page.goto(f"{BASE_URL}/", wait_until="networkidle")
            mobile_page.wait_for_timeout(2000)

            filepath = os.path.join(SCREENSHOTS_DIR, "mobile-view.png")
            mobile_page.screenshot(path=filepath, full_page=True)
            size = os.path.getsize(filepath) / 1024
            print(f"   ✅ Saved: mobile-view.png ({size:.1f} KB)")

            mobile_context.close()
        except Exception as e:
            print(f"   ⚠️  Could not capture mobile view: {str(e)}")

        # Close browser
        browser.close()

    print("\n✨ Screenshot capture complete!")
    print(f"📂 Screenshots saved to: {os.path.abspath(SCREENSHOTS_DIR)}")
    print("\n📋 Captured files:")

    # List all captured screenshots
    for filename in sorted(os.listdir(SCREENSHOTS_DIR)):
        if filename.endswith('.png'):
            filepath = os.path.join(SCREENSHOTS_DIR, filename)
            size = os.path.getsize(filepath) / 1024
            print(f"   • {filename} ({size:.1f} KB)")

if __name__ == "__main__":
    print("=" * 70)
    print("acimig v1.0 Screenshot Capture Tool")
    print("=" * 70)
    print("\n⚠️  IMPORTANT: Make sure the Flask application is running!")
    print(f"   Expected URL: {BASE_URL}")
    print("\nPress Ctrl+C to cancel, or wait 3 seconds to continue...")

    try:
        time.sleep(3)
        capture_screenshots()
    except KeyboardInterrupt:
        print("\n\n❌ Screenshot capture cancelled by user.")
    except Exception as e:
        print(f"\n\n❌ Error: {str(e)}")
        print("\nMake sure:")
        print("1. Flask app is running (python app.py)")
        print("2. App is accessible at http://127.0.0.1:5000")
        print("3. You have created a fabric and uploaded some data")
