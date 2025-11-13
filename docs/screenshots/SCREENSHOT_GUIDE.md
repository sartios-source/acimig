# Screenshot Guide for acimig v1.0

## Required Screenshots

To complete the documentation, please capture the following screenshots after starting the Flask application.

### How to Capture Screenshots

1. Start the Flask application:
   ```bash
   python app.py
   ```

2. Open your browser to `http://127.0.0.1:5000`

3. Create a test fabric and upload sample data

4. Capture the following pages:

### Screenshot List

#### 1. `home.png` - Dashboard/Home Page
- **URL**: `http://127.0.0.1:5000/`
- **What to capture**: Full page showing:
  - Left sidebar navigation with acimig v1.0 branding
  - Hero section with animated network topology
  - Statistics cards (EPGs, FEX, Migrations, Uptime)
  - Mode selection cards (EVPN/VXLAN and Onboard)
  - Fabric Manager section
- **Recommended size**: 1920x1080 (full HD)
- **Notes**: Make sure sidebar is expanded to show full navigation

#### 2. `upload.png` - Upload Data Page
- **URL**: `http://127.0.0.1:5000/upload_page`
- **What to capture**: Full page showing:
  - Sidebar navigation
  - Upload page header
  - Drag & drop zone with animations
  - Uploaded datasets section (if any exist)
- **Recommended size**: 1920x1080
- **Notes**: Capture with a fabric selected

#### 3. `analyze.png` - Analyze Data Page
- **URL**: `http://127.0.0.1:5000/analyze`
- **What to capture**: Full page showing:
  - Sidebar navigation
  - Overview statistics cards
  - Tab navigation (FEX, Leafs, EPGs, etc.)
  - Data table with sample data
- **Recommended size**: 1920x1080
- **Notes**: Make sure you have uploaded data to show in tables

#### 4. `plan.png` - Migration Planning Page
- **URL**: `http://127.0.0.1:5000/plan`
- **What to capture**: Full page showing:
  - Sidebar navigation
  - Migration recommendations cards
  - Priority badges
  - Implementation steps
- **Recommended size**: 1920x1080
- **Notes**: Capture with recommendations visible

#### 5. `visualize.png` - Visualization Dashboard
- **URL**: `http://127.0.0.1:5000/visualize`
- **What to capture**: Full page showing:
  - Sidebar navigation
  - Tab navigation for different visualizations
  - Charts and graphs (Overview dashboard)
  - Metrics cards
- **Recommended size**: 1920x1080
- **Notes**: Make sure charts are rendered

#### 6. `report.png` - Reports Page
- **URL**: `http://127.0.0.1:5000/report`
- **What to capture**: Full page showing:
  - Sidebar navigation
  - Export options (HTML, Markdown, CSV)
  - Report preview section
- **Recommended size**: 1920x1080

#### 7. `sidebar-collapsed.png` - Collapsed Sidebar View (Optional)
- **URL**: Any page
- **What to capture**: Page with sidebar collapsed showing icon-only navigation
- **Recommended size**: 1920x1080
- **Notes**: Click the sidebar toggle button to collapse

#### 8. `mobile-view.png` - Mobile Responsive View (Optional)
- **URL**: Any page
- **What to capture**: Mobile view of the application
- **Recommended size**: 375x812 (iPhone X)
- **Notes**: Use browser dev tools to simulate mobile

### Screenshot Tools

**Recommended Tools**:
- **Windows**: Snipping Tool, Snip & Sketch (Win + Shift + S)
- **macOS**: Screenshot (Cmd + Shift + 4)
- **Cross-platform**:
  - Browser DevTools (F12) - Full page screenshots
  - Lightshot
  - ShareX (Windows)
  - Firefox built-in screenshot tool

### Tips for High-Quality Screenshots

1. **Use high resolution**: Capture at 1920x1080 or higher
2. **Clean browser**: Remove browser extensions/toolbars from view
3. **Full page**: Use full-page screenshot tools when possible
4. **Consistent window size**: Keep browser window same size for all screenshots
5. **Sample data**: Use realistic sample data, not empty states
6. **Hide personal info**: Make sure no sensitive information is visible
7. **Good lighting**: If capturing dark mode, ensure good contrast

### Image Format

- **Format**: PNG (preferred for UI screenshots)
- **Compression**: Use lossless compression
- **File size**: Try to keep under 500KB per image while maintaining quality

### File Naming Convention

Use the exact filenames listed above:
- `home.png`
- `upload.png`
- `analyze.png`
- `plan.png`
- `visualize.png`
- `report.png`
- `sidebar-collapsed.png` (optional)
- `mobile-view.png` (optional)

### After Capturing

Place all screenshots in this directory (`docs/screenshots/`) and they will be automatically referenced in the README.md.

## Example Screenshot Command (if using Playwright or Selenium)

```python
from playwright.sync_api import sync_playwright

def capture_screenshots():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1920, 'height': 1080})

        # Home page
        page.goto('http://127.0.0.1:5000/')
        page.screenshot(path='docs/screenshots/home.png', full_page=True)

        # Upload page
        page.goto('http://127.0.0.1:5000/upload_page')
        page.screenshot(path='docs/screenshots/upload.png', full_page=True)

        # Add more pages...

        browser.close()

capture_screenshots()
```
