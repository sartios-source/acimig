# ACI Analysis Tool v2

A professional, local-only tool for analyzing Cisco ACI fabrics with support for both **Onboarding** and **Offboarding** workflows.

## Features

- **Dual Mode**: Toggle between Onboard and Offboard workflows
- **Multi-Fabric Analysis**: Manage and analyze 20+ fabrics simultaneously
- **Multiple Data Sources**:
  - ACI JSON/XML exports
  - Legacy network configs (IOS, CatOS, NX-OS, Arista EOS)
  - CMDB CSV data
- **Deep Analysis Engine**: 12+ analysis types including port utilization, VLAN distribution, EPG complexity, vPC symmetry, and more
- **Interactive Visualizations**: Topology diagrams, density charts, rack layouts
- **Comprehensive Planning**: Consolidation recommendations, migration steps, risk analysis
- **Professional Reports**: Export to Markdown, CSV, and HTML

## Quick Start (Windows 10/11)

1. **Clone or download this repository**

2. **Run the setup script** (PowerShell):
   ```powershell
   .\scripts\win-setup.ps1
   ```

3. **Access the application**:
   Open your browser to `http://127.0.0.1:5000`

## Quick Start (macOS/Linux)

1. **Clone or download this repository**

2. **Run the setup script**:
   ```bash
   bash ./scripts/unix-setup.sh
   ```

3. **Access the application**:
   Open your browser to `http://127.0.0.1:5000`

## Manual Setup

If you prefer manual setup:

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (Windows CMD)
.\venv\Scripts\activate.bat

# Activate (macOS/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run application
python app.py
```

## Security

- **Local-only**: No external network calls (except when using offline collector)
- **No database**: All data stored in local files
- **No authentication**: Designed for trusted local use
- **File-based storage**: Easy to backup and audit

## Directory Structure

```
aciv2/
├── data/           # Uploaded datasets
├── fabrics/        # Per-fabric storage
├── cmdb/           # CMDB uploads
├── output/         # Generated reports
├── templates/      # HTML templates
├── static/         # CSS, JS, assets
├── analysis/       # Analysis engine
└── scripts/        # Setup scripts
```

## License

Internal use only.
