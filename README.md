# ACI Analysis Tool v2

**Professional, local-only tool for analyzing, migrating, and optimizing Cisco ACI fabrics**

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/sartios-source/acimig)
[![Python](https://img.shields.io/badge/python-3.8%2B-green.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Internal-red.svg)](#license)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [What Can This Tool Do?](#what-can-this-tool-do)
- [Quick Start](#quick-start)
- [Detailed Installation](#detailed-installation)
- [Usage Guide](#usage-guide)
- [Workflows Explained](#workflows-explained)
- [Sample Data](#sample-data)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Performance](#performance)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

The ACI Analysis Tool is a **comprehensive, web-based application** designed to help network teams analyze, optimize, and migrate Cisco ACI fabrics. Whether you're looking to consolidate underutilized FEX devices, plan new deployments, or migrate to standards-based EVPN/VXLAN fabrics, this tool provides **actionable insights and automated configuration generation**.

### Why This Tool?

- ✅ **No External Dependencies**: Runs 100% locally - your data never leaves your machine
- ✅ **Multi-Fabric Support**: Manage and compare 20+ fabrics simultaneously
- ✅ **Enterprise Scale**: Tested with 110+ leafs and 316+ FEX devices
- ✅ **Actionable Insights**: Get specific recommendations with risk assessments
- ✅ **Config Generation**: Auto-generate EVPN configs for Cisco, Arista, and Juniper
- ✅ **ROI Analysis**: Built-in cost savings calculations
- ✅ **Zero Database**: File-based storage - easy to backup and audit

---

## Key Features

### 🎯 Three Powerful Modes

| Mode | Purpose | Key Outputs |
|------|---------|-------------|
| **🔴 Offboard** | Analyze existing FEX deployments and plan consolidation | Consolidation scores, port savings, migration steps |
| **🟢 Onboard** | Plan new FEX/leaf deployments with policy scaffolding | Onboarding checklist, policy templates, prerequisites |
| **🔵 EVPN Migration** | Migrate from ACI to standards-based EVPN/VXLAN | Migration plan, complexity scoring, auto-generated configs |

### 🔍 Deep Analysis Engine (12+ Analysis Types)

1. **Port Utilization Statistics** - Identify underutilized devices
2. **Leaf-to-FEX Mapping** - Detect overload and imbalances
3. **Rack-Level Grouping** - Cross-fabric consolidation opportunities
4. **BD/EPG/VRF Mapping** - Policy distribution analysis
5. **VLAN Distribution** - Overlap and collision detection
6. **EPG Complexity Scoring** - Quantify migration difficulty
7. **vPC Symmetry** - Redundancy validation
8. **PDOM Analysis** - Physical domain VLAN conflicts
9. **Migration Flags** - Topology change requirements
10. **Contract Scope** - Security policy leakage detection
11. **Multi-EPG VLAN Spread** - VLAN bleed risk assessment
12. **CMDB Correlation** - Asset location insights

### 📊 Multi-Source Data Support

- **ACI Exports**: JSON and XML from APIC
- **Legacy Configs**: IOS, CatOS, NX-OS, Arista EOS text files
- **CMDB Data**: CSV with asset locations (Rack, Building, Site)
- **Offline Collector**: Downloadable Python script for APIC data collection

### 🎨 Professional UI

- Clean, modern interface with context-sensitive help
- Interactive topology visualizations
- Real-time validation feedback
- Downloadable reports (HTML, Markdown, CSV)
- Platform-specific configuration downloads

---

## What Can This Tool Do?

### For Network Architects

- **Capacity Planning**: Understand current utilization across your fabric
- **Cost Optimization**: Identify consolidation opportunities with ROI calculations
- **Risk Assessment**: Evaluate migration complexity before starting projects
- **Vendor Strategy**: Plan your exit strategy from ACI with confidence

### For Network Engineers

- **Configuration Generation**: Get ready-to-use EVPN configs for multiple platforms
- **Validation Checklists**: Step-by-step validation for migrations
- **Topology Visualization**: Interactive diagrams of your fabric
- **Policy Translation**: Understand how ACI contracts map to ACLs/route-maps

### For Management

- **ROI Reports**: Concrete cost savings analysis (hardware, power, maintenance)
- **Timeline Estimates**: Realistic migration schedules with risk levels
- **Executive Summaries**: High-level insights for decision-making
- **Multi-Fabric Comparison**: Compare efficiency across data centers

---

## Quick Start

### Windows 10/11 (Recommended)

```powershell
# 1. Clone or download this repository
git clone https://github.com/sartios-source/acimig.git
cd acimig

# 2. Run the automated setup script
.\scripts\win-setup.ps1

# 3. Open your browser to http://127.0.0.1:5000
```

**That's it!** The script will:
- Create a Python virtual environment
- Install all dependencies
- Start the Flask application
- Open your default browser

### macOS / Linux

```bash
# 1. Clone or download this repository
git clone https://github.com/sartios-source/acimig.git
cd acimig

# 2. Run the automated setup script
bash ./scripts/unix-setup.sh

# 3. Open your browser to http://127.0.0.1:5000
```

### Quick Test with Sample Data

1. Once the app is running, click **"Create New Fabric"**
2. Name it: `"Test-Fabric"`
3. Go to **Analyze** tab
4. Upload: `data/samples/sample_aci.json`
5. See instant analysis results!

---

## Detailed Installation

### Prerequisites

- **Python 3.8 or higher** ([Download here](https://www.python.org/downloads/))
- **Git** (optional, for cloning)
- **Modern web browser** (Chrome, Firefox, Edge, Safari)
- **4 GB RAM minimum** (8 GB recommended for large fabrics)
- **200 MB disk space**

### Manual Installation (All Platforms)

If the automated scripts don't work, follow these steps:

```bash
# 1. Navigate to the project directory
cd /path/to/aciv2

# 2. Create a virtual environment
python -m venv venv

# 3. Activate the virtual environment

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On Windows (CMD):
.\venv\Scripts\activate.bat

# On macOS/Linux:
source venv/bin/activate

# 4. Upgrade pip
pip install --upgrade pip

# 5. Install dependencies
pip install -r requirements.txt

# 6. Run the application
python app.py

# 7. Open browser to http://127.0.0.1:5000
```

### Verifying Installation

Once the app starts, you should see:

```
======================================================================
ACI Analysis Tool - Starting
======================================================================
Data directory: C:\Users\...\aciv2\data
Fabrics directory: C:\Users\...\aciv2\fabrics
Output directory: C:\Users\...\aciv2\output
======================================================================
Access the application at: http://127.0.0.1:5000
======================================================================
```

---

## Usage Guide

### First-Time Setup

#### Step 1: Create a Fabric

1. Open http://127.0.0.1:5000
2. Click **"Create New Fabric"**
3. Enter a name (e.g., `Production-DC1`, `Lab-Fabric`)
4. Click **"Create"**
5. The fabric is now selected (shown in top navigation)

#### Step 2: Choose Your Mode

Select the workflow that matches your goal:

- **Offboard**: Analyzing existing deployment for consolidation
- **Onboard**: Planning new deployment
- **EVPN Migration**: Planning migration from ACI to EVPN

You can switch modes anytime from the top navigation bar.

#### Step 3: Upload Data

Go to the **Analyze** tab:

1. **For Offboard/EVPN**: Upload ACI JSON or XML export
2. **Optional**: Upload legacy network configs (TXT/CFG)
3. **Optional**: Upload CMDB CSV for location data
4. Wait for validation (usually <5 seconds)

#### Step 4: Explore Analysis

Navigate through the tabs:

- **Analyze**: Upload data and see validation results
- **Visualize**: Interactive topology, density charts, rack layouts
- **Plan**: Recommendations, migration steps, what-if scenarios
- **Report**: Generate and download reports
- **EVPN Migration** (in EVPN mode): Complete migration plan and configs

---

## Workflows Explained

### 🔴 Offboard Workflow: FEX Consolidation

**Goal**: Identify opportunities to consolidate underutilized FEX devices

#### When to Use
- Annual hardware refresh planning
- Cost reduction initiatives
- Decommissioning old equipment
- Optimizing rack space and power

#### Process

1. **Upload Data**
   ```
   Analyze → Upload ACI JSON + CMDB CSV
   ```

2. **Review Validation**
   - Check for errors/warnings
   - Verify object counts
   - Ensure CMDB correlation

3. **Explore Visualizations**
   ```
   Visualize → Port Density tab
   ```
   - See utilization per FEX
   - Identify devices <40% utilized
   - View rack-level distribution

4. **Review Recommendations**
   ```
   Plan → Consolidation Recommendations
   ```
   - Sorted by consolidation score
   - Risk levels indicated
   - Port savings calculated

5. **Generate Migration Plan**
   ```
   Plan → Migration Steps
   ```
   - Step-by-step consolidation process
   - Commands and validation checks
   - Rollback procedures

6. **Export Report**
   ```
   Report → Download HTML/Markdown/CSV
   ```
   - Share with stakeholders
   - Include ROI calculations
   - Document decisions

#### Example Output

```
Consolidation Opportunities Found:

Top 5 Candidates:
1. FEX-105 (NYC-DC1-Rack-R03): 22% utilized → Score 84/100 (Low Risk)
2. FEX-112 (NYC-DC1-Rack-R05): 28% utilized → Score 78/100 (Low Risk)
3. FEX-089 (NYC-DC2-Rack-R12): 35% utilized → Score 71/100 (Medium Risk)
...

Potential Savings:
- Reclaim: 95 FEX devices
- Free ports: 4,560
- Annual power savings: $33,000
- Hardware refresh avoidance: $475,000
```

---

### 🟢 Onboard Workflow: New Deployment Planning

**Goal**: Plan and configure new FEX/leaf deployments

#### When to Use
- New data center buildouts
- Expanding existing fabrics
- Greenfield ACI deployments
- Capacity additions

#### Process

1. **Switch to Onboard Mode**
   ```
   Home → Click "Onboard" card
   ```

2. **Upload Planning Data** (optional)
   - Target infrastructure specs
   - Existing fabric exports (if expanding)

3. **Review Checklist**
   ```
   Plan → Onboarding Checklist
   ```
   - Infrastructure prerequisites
   - Policy configuration steps
   - Tenant setup requirements
   - Path binding validation

4. **Use Policy Scaffolding**
   ```
   Plan → Policy Scaffolding
   ```
   - Physical Domain templates
   - AEP configuration
   - FEX Policy profiles
   - EPG static bindings

5. **Export Deployment Plan**
   ```
   Report → Download
   ```
   - Complete onboarding guide
   - Configuration templates
   - Prerequisites checklist

#### Example Output

```
Onboarding Checklist:

Infrastructure Prerequisites:
☐ Physical cabling verified
☐ Power and cooling confirmed
☐ FEX discovered in APIC

Policy Configuration:
☐ Physical domain created
☐ VLAN pool allocated (suggested: 100-500)
☐ AEP configured
☐ FEX policy profile applied

Tenant Configuration:
☐ Tenant created/selected
☐ VRF configured
☐ Bridge Domains created
☐ EPGs defined
☐ Contracts configured
```

---

### 🔵 EVPN Migration Workflow: The ACI Off-Ramp

**Goal**: Plan and execute migration from ACI to standards-based EVPN/VXLAN

#### When to Use
- Vendor diversification strategy
- Reducing licensing costs
- Standardizing on EVPN across organization
- Multi-vendor fabric design

#### Process

1. **Switch to EVPN Mode**
   ```
   Home → Click "EVPN Migration" card
   ```

2. **Upload ACI Data**
   ```
   Analyze → Upload ACI JSON (same as Offboard)
   ```

3. **Choose Target Platform**
   ```
   EVPN Migration → Select Platform
   ```
   - Cisco NX-OS
   - Arista EOS
   - Juniper Junos

4. **Review Complexity Assessment**
   ```
   EVPN Migration → Complexity Assessment card
   ```
   - Complexity score (0-100)
   - Contributing factors
   - Key risks identified
   - Estimated duration

5. **Explore Object Mappings**
   ```
   EVPN Migration → Mapping tabs
   ```
   - **L3 VNI**: VRFs → L3 VNIs + Route Targets
   - **L2 VNI**: Bridge Domains → L2 VNIs + VLANs
   - **VLANs**: EPGs → VLAN access ports

6. **Review Migration Plan**
   ```
   EVPN Migration → Migration Plan section
   ```
   - 7-phase migration timeline
   - Duration per phase
   - Risk level per phase
   - Tasks and warnings

7. **Download Configurations**
   ```
   EVPN Migration → Configuration Samples
   ```
   - Leaf switch config
   - Spine switch config
   - Border leaf config
   - Platform-specific syntax

8. **Use Validation Checklist**
   ```
   EVPN Migration → Validation Checklist
   ```
   - Underlay validation
   - BGP EVPN checks
   - Data plane verification
   - Policy enforcement tests

#### Example Output

```
Migration Complexity Assessment:

Score: 68/100 (Medium-High)
Estimated Duration: 12-16 weeks

Complexity Factors:
✓ 8 tenants (moderate multi-tenancy)
✓ 50 contracts (moderate policy complexity)
✓ 3 L3Outs (external connectivity)
✓ 240 EPGs across 80 BDs

Key Risks:
⚠ ACI contracts have finer granularity than ACLs
⚠ Service graphs require L4-7 redesign
⚠ Policy translation may require app-level changes

ACI → EVPN Mapping:
- 16 VRFs → L3 VNIs 50000-50015
- 80 BDs → L2 VNIs 10000-10079
- 240 EPGs → VLANs 100-339

Migration Timeline:
Phase 1-3 (Pre-Migration): 4-6 weeks
Phase 4-6 (Migration): 6-8 weeks
Phase 7 (Post-Migration): 2 weeks
```

---

## Sample Data

### Small-Scale Samples (Quick Testing)

Perfect for learning the tool:

- **`data/samples/sample_aci.json`** - 3 FEX, 2 leafs, 3 EPGs
- **`data/samples/sample_aci.xml`** - XML format variant
- **`data/samples/sample_nxos.txt`** - NX-OS configuration
- **`data/samples/sample_cmdb.csv`** - Asset location data

**Upload these to see the tool in action immediately!**

### Large-Scale Enterprise Sample

Realistic enterprise deployment for testing at scale:

- **`data/samples/sample_large_scale.json`** - **1.2 MB, 4,237 objects**
  - 110 leaf switches (5 data centers)
  - 316 FEX devices
  - 8 tenants, 240 EPGs, 80 BDs, 16 VRFs
  - 50 contracts, 3 L3Outs

- **`data/samples/sample_large_scale_cmdb.csv`** - **26 KB, 426 devices**
  - Matching CMDB records with rack/site locations

**See detailed analysis:** `docs/LARGE_SCALE_EXAMPLE.md`

### Generate Custom Samples

Create your own test data matching your environment:

```bash
cd scripts
python generate_large_scale_sample.py
```

**Customize the script** to change:
- Number of leafs: `NUM_LEAFS = 110`
- Number of FEX: `NUM_FEX = 316`
- Number of tenants: `NUM_TENANTS = 8`
- Number of BDs per VRF: `NUM_BDS_PER_VRF = 5`
- Number of EPGs per BD: `NUM_EPGS_PER_BD = 3`
- Geographic distribution: Edit `sites` list

---

## Data Collection

### Option 1: Offline Collector (Recommended for Production)

The tool includes a **stdlib-only Python script** that collects data directly from APIC:

1. **Download the collector**:
   ```
   Analyze → Download Offline Collector button
   ```

2. **Run against your APIC**:
   ```bash
   python offline_collector.py --apic 10.1.1.1 --username admin --output ./collected_data
   ```

3. **Upload the generated files** via the Analyze page

**Benefits:**
- No pip dependencies required
- Collects all necessary ACI objects
- Works with APIC 3.x, 4.x, 5.x
- Creates organized directory structure

### Option 2: Manual APIC Export

From APIC GUI:

1. Navigate to **Tenants → Export Policies**
2. Select **Operational → Configuration Export**
3. Choose **JSON** or **XML** format
4. Export the following classes:
   - `eqptFex` - FEX equipment
   - `fabricNode` - Fabric nodes
   - `fvRsPathAtt` - EPG path attachments
   - `fvAEPg` - EPGs
   - `fvBD` - Bridge domains
   - `fvCtx` - VRFs
   - `vzBrCP` - Contracts
   - `l3extInstP` - External EPGs
   - `ethpmPhysIf` - Physical interfaces

### Option 3: APIC REST API

```bash
# Example using curl
curl -X GET "https://apic-ip/api/class/eqptFex.json" \
  -H "Cookie: APIC-Cookie=<token>" \
  -o fex_data.json
```

### CMDB Data Format

If you have asset management data, create a CSV with these columns:

```csv
SerialNumber,Rack,Building,Hall,Site
FEX001ABC,R01,Building-A,Hall-1,Site-NYC
FEX002DEF,R01,Building-A,Hall-1,Site-NYC
LEAF001SN,R01,Building-A,Hall-1,Site-NYC
```

**Required:**
- `SerialNumber` - Must match ACI serial numbers exactly

**Optional (but recommended):**
- `Rack` - Rack identifier
- `Building` - Building name
- `Hall` - Floor/hall identifier
- `Site` - Data center/site name

The tool will automatically correlate CMDB data with ACI objects for enhanced analysis.

---

## Troubleshooting

### Common Issues and Solutions

#### ❌ "Port 5000 is already in use"

**Solution 1**: Change the port in `app.py`

```python
# Line at bottom of app.py
app.run(debug=True, host='127.0.0.1', port=5001)  # Changed from 5000
```

**Solution 2**: Kill the process using port 5000

```bash
# Windows
netstat -ano | findstr :5000
taskkill /PID <pid> /F

# macOS/Linux
lsof -ti:5000 | xargs kill -9
```

#### ❌ "Python not found" or "python command not recognized"

**Windows**:
1. Download Python from python.org
2. During installation, check ✅ "Add Python to PATH"
3. Restart terminal

**macOS**:
```bash
brew install python3
```

**Linux**:
```bash
sudo apt-get install python3 python3-pip  # Ubuntu/Debian
sudo yum install python3 python3-pip      # RHEL/CentOS
```

#### ❌ "ModuleNotFoundError: No module named 'flask'"

**Cause**: Virtual environment not activated or dependencies not installed

**Solution**:
```bash
# Ensure venv is activated (you should see (venv) in prompt)
# Windows
.\venv\Scripts\Activate.ps1

# macOS/Linux
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

#### ❌ "Upload failed: Invalid format"

**Cause**: File is not valid JSON/XML/CSV

**Solution**:
1. Validate JSON: Use jsonlint.com
2. Check encoding: Should be UTF-8
3. Verify file extension matches content

#### ❌ "No fabric selected" when trying to analyze

**Solution**:
1. Go to Home page
2. Click "Create New Fabric"
3. Enter a name and click Create
4. Fabric will be automatically selected

#### ❌ PowerShell script execution error

```
cannot be loaded because running scripts is disabled on this system
```

**Solution**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then run the script again.

#### ❌ Browser shows "Connection refused"

**Cause**: App not running or wrong URL

**Solution**:
1. Check terminal - app should show "Running on http://127.0.0.1:5000"
2. Don't use `localhost`, use `127.0.0.1` specifically
3. Check Windows Firewall isn't blocking

#### ❌ "EVPN migration shows no data"

**Cause**: No ACI data uploaded

**Solution**:
1. Must upload ACI JSON/XML first in Analyze page
2. Wait for validation to complete
3. Then navigate to EVPN Migration page

#### ❌ "Analysis is slow with large datasets"

**Normal**: Large fabrics (100+ leafs) may take 5-10 seconds

**If unusually slow**:
1. Close other applications
2. Ensure you have 4+ GB available RAM
3. Try breaking upload into smaller files
4. Check antivirus isn't scanning files

---

## FAQ

### General Questions

**Q: Is my data sent anywhere?**

A: **No.** This tool runs 100% locally on your machine. No external network calls except when using the optional offline collector to gather data from your APIC.

**Q: Do I need a database?**

A: **No.** Everything is file-based. Data is stored in the `fabrics/` directory as JSON files.

**Q: Can I run this on a shared server?**

A: Yes, but there's **no authentication**. It's designed for single-user local use. For shared environments, consider adding authentication or running in Docker with network isolation.

**Q: What Python version do I need?**

A: **Python 3.8 or higher.** Tested on 3.8, 3.9, 3.10, 3.11.

**Q: Can I analyze multiple fabrics at once?**

A: **Yes!** Create multiple fabrics and switch between them. You can also compare them in the "What-If Scenarios" section.

**Q: Does this modify my ACI fabric?**

A: **No.** This tool is read-only. It analyzes exported data but never connects to or modifies your live fabric.

### Data Questions

**Q: What ACI versions are supported?**

A: Tested with **APIC 3.x, 4.x, and 5.x**. The tool works with standard ACI object exports, which are consistent across versions.

**Q: Can I upload partial data?**

A: Yes. The tool will analyze whatever you provide. Some analyses require specific objects (e.g., EPG analysis needs fvAEPg and fvRsPathAtt objects).

**Q: How much data can it handle?**

A: Tested up to **110 leafs, 316 FEX, 4,000+ objects** (1.2 MB JSON). Performance: 5-8 seconds for full analysis.

**Q: Can I analyze non-FEX fabrics?**

A: Yes. The tool works with leaf-only fabrics too. Some FEX-specific analyses will be skipped.

**Q: Does it support vPC?**

A: **Yes.** The tool detects vPC configurations and validates symmetry.

### Mode-Specific Questions

**Q: What's the difference between Offboard and EVPN Migration?**

A:
- **Offboard**: Stay in ACI, consolidate FEX
- **EVPN Migration**: Leave ACI entirely, move to standards-based EVPN

**Q: Can I use Offboard and EVPN together?**

A: **Yes!** Common workflow:
1. Use **Offboard** to consolidate first (reduce complexity)
2. Then use **EVPN Migration** to plan your exit

**Q: Do the generated EVPN configs work out-of-the-box?**

A: They're **90% ready**. You'll need to customize:
- IP addresses (loopbacks, p2p links)
- BGP AS numbers
- Route reflector IPs
- Underlay IGP (OSPF/IS-IS) configuration

**Q: What's a good consolidation score?**

A:
- **80-100**: Excellent candidate (low risk, high reward)
- **60-79**: Good candidate (review specifics)
- **40-59**: Moderate candidate (higher complexity)
- **0-39**: Poor candidate (high risk or already optimized)

**Q: How accurate are the ROI calculations?**

A: Conservative estimates based on:
- FEX hardware: $5,000/unit
- Power: $0.12/kWh (adjust for your region)
- Labor: $100/hour
- Update values in the code for your specific costs

### Technical Questions

**Q: Can I customize the analysis logic?**

A: **Yes!** All analysis code is in `analysis/` directory. Modify as needed.

**Q: Can I export raw data?**

A: **Yes.** Reports include CSV export with all analysis results.

**Q: Does it support multi-tenancy?**

A: **Yes.** The tool analyzes all tenants simultaneously and flags multi-tenant complexity in EVPN migrations.

**Q: Can I add my own platforms to EVPN config generation?**

A: **Yes!** Edit `analysis/evpn_migration.py` and add a new `_generate_<platform>_config()` method.

**Q: How do I backup my analysis?**

A: Copy the `fabrics/` directory. It contains all uploaded data and analysis state.

---

## Performance

### Expected Performance

| Fabric Size | Upload | Analysis | Visualization | Report Gen |
|-------------|--------|----------|---------------|------------|
| Small (10 leafs, 20 FEX) | <1s | <1s | <1s | 1-2s |
| Medium (50 leafs, 100 FEX) | 1-2s | 2-3s | 1-2s | 3-4s |
| Large (110 leafs, 316 FEX) | 2-3s | 3-5s | 2-3s | 5-8s |
| Very Large (200+ leafs) | 3-5s | 5-10s | 3-5s | 10-15s |

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| CPU | 2 cores | 4 cores |
| RAM | 2 GB | 4 GB |
| Disk | 200 MB | 1 GB |
| Python | 3.8 | 3.10+ |

### Optimization Tips

1. **Large Fabrics**: Upload data once, then switch modes without re-uploading
2. **Multiple Analyses**: Keep the browser tab open to avoid re-parsing
3. **CMDB Data**: Only upload if you need rack-level analysis
4. **Legacy Configs**: Optional - skip if not needed

---

## Contributing

### Reporting Issues

Found a bug or have a feature request?

1. Check existing issues: https://github.com/sartios-source/acimig/issues
2. Create new issue with:
   - Detailed description
   - Steps to reproduce
   - Expected vs actual behavior
   - Screenshots if applicable

### Suggesting Features

We welcome feature suggestions! Consider:
- What problem does it solve?
- How does it fit into existing workflows?
- Is it generalizable or specific to your environment?

### Code Contributions

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## Directory Structure

```
aciv2/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── analysis/             # Analysis engine
│   ├── __init__.py
│   ├── parsers.py        # Data parsers (JSON/XML/CSV/legacy)
│   ├── engine.py         # Core analysis logic
│   ├── fabric_manager.py # Multi-fabric management
│   ├── planning.py       # Consolidation/onboard planning
│   ├── reporting.py      # Report generation
│   └── evpn_migration.py # EVPN migration engine
├── templates/            # HTML templates
│   ├── base.html
│   ├── index.html
│   ├── analyze.html
│   ├── visualize.html
│   ├── plan.html
│   ├── report.html
│   ├── evpn_migration.html
│   └── help.html
├── static/               # CSS, JS, assets
│   ├── styles.css
│   ├── app.js
│   └── logo.svg
├── scripts/              # Utility scripts
│   ├── win-setup.ps1
│   ├── unix-setup.sh
│   └── generate_large_scale_sample.py
├── data/                 # Data directory
│   └── samples/          # Sample data files
│       ├── sample_aci.json
│       ├── sample_aci.xml
│       ├── sample_nxos.txt
│       ├── sample_cmdb.csv
│       ├── sample_large_scale.json
│       └── sample_large_scale_cmdb.csv
├── docs/                 # Documentation
│   └── LARGE_SCALE_EXAMPLE.md
├── fabrics/              # Per-fabric storage (created at runtime)
├── cmdb/                 # CMDB uploads (created at runtime)
├── output/               # Generated reports (created at runtime)
└── offline_collector.py  # APIC data collector
```

---

## Security Notes

### Data Privacy

- ✅ All data stays local (no cloud/external services)
- ✅ No telemetry or analytics
- ✅ No authentication required (single-user tool)
- ⚠️ Not designed for multi-user/shared environments
- ⚠️ No encryption at rest (store on encrypted drives if needed)

### Best Practices

1. **Run on trusted machines only**
2. **Don't expose to public networks**
3. **Use VPN if accessing remote APICss**
4. **Backup fabrics/ directory securely**
5. **Clear sensitive data**: Delete fabrics when done
6. **Review generated configs**: Don't blindly apply to production

---

## License

**Internal Use Only**

This tool is provided for internal use within your organization. Redistribution, modification, or commercial use requires permission.

---

## Acknowledgments

Built with:
- **Flask** - Web framework
- **Python 3** - Core language
- **Jinja2** - Template engine
- **Pandas** - Data analysis (optional)

Inspired by the need for better ACI visibility and migration planning tools.

---

## Support

### Getting Help

1. **Check this README** - Most questions answered here
2. **Review Help Page** - In-app documentation (http://127.0.0.1:5000/help)
3. **Check FAQ section** - Common issues covered
4. **GitHub Issues** - Report bugs or request features

### Quick Links

- **Repository**: https://github.com/sartios-source/acimig
- **Issues**: https://github.com/sartios-source/acimig/issues
- **Large-Scale Example**: [docs/LARGE_SCALE_EXAMPLE.md](docs/LARGE_SCALE_EXAMPLE.md)

---

## What's Next?

1. ✅ **Start the app**: `python app.py`
2. ✅ **Create a fabric**: "Test-Fabric"
3. ✅ **Upload sample data**: `data/samples/sample_aci.json`
4. ✅ **Explore the three modes**: Offboard, Onboard, EVPN
5. ✅ **Generate a report**: Download HTML/Markdown/CSV
6. ✅ **Try EVPN migration**: See auto-generated configs
7. ✅ **Test at scale**: Upload `sample_large_scale.json`

**Happy analyzing! 🚀**

---

*Last updated: 2024-11-10*
*Version: 2.0.0*
