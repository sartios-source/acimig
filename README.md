# ACI Analysis Tool v2

A professional, local-only tool for analyzing Cisco ACI fabrics with support for **Onboarding**, **Offboarding**, and **EVPN Migration** workflows.

## Features

- **Triple Mode**: Toggle between Onboard, Offboard, and EVPN Migration workflows
- **Multi-Fabric Analysis**: Manage and analyze 20+ fabrics simultaneously
- **Multiple Data Sources**:
  - ACI JSON/XML exports
  - Legacy network configs (IOS, CatOS, NX-OS, Arista EOS)
  - CMDB CSV data
- **Deep Analysis Engine**: 12+ analysis types including port utilization, VLAN distribution, EPG complexity, vPC symmetry, and more
- **EVPN Migration Engine**: Complete ACI-to-EVPN migration planning with config generation for Cisco NX-OS, Arista EOS, and Juniper Junos
- **Interactive Visualizations**: Topology diagrams, density charts, rack layouts
- **Comprehensive Planning**: Consolidation recommendations, migration steps, risk analysis
- **Professional Reports**: Export to Markdown, CSV, and HTML
- **Configuration Generation**: Auto-generate EVPN configs for leaf, spine, and border devices

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

## EVPN Migration Workflow

The tool now includes a comprehensive **ACI to EVPN migration** feature - your off-ramp from ACI to standards-based EVPN/VXLAN fabrics.

### Features

- **Automatic Object Mapping**: Maps ACI constructs to EVPN equivalents
  - VRFs → L3 VNIs + VRF
  - Bridge Domains → L2 VNIs + VLANs
  - EPGs → VLANs + access ports
  - Contracts → ACLs/Route-maps/Zone-based policies

- **Multi-Platform Support**: Generate configs for:
  - Cisco NX-OS (with NVE interface, BGP EVPN, anycast gateway)
  - Arista EOS (with Vxlan1 interface, vEOS-style config)
  - Juniper Junos (set-style configuration)

- **Migration Complexity Assessment**: Automatic scoring based on:
  - Tenant count and multi-tenancy complexity
  - Contract policy complexity
  - Service graph usage
  - L3Out complexity
  - EPG-to-BD ratio

- **7-Phase Migration Plan**:
  1. Pre-Migration: Documentation and design
  2. Pre-Migration: Build parallel EVPN fabric
  3. Pre-Migration: Fabric validation
  4. Migration: Pilot workload migration
  5. Migration: Security policy translation
  6. Migration: Production workload migration
  7. Post-Migration: ACI decommission

- **Configuration Generation**: Download ready-to-use configs for:
  - Leaf switches (VTEP configuration)
  - Spine switches (Route Reflector configuration)
  - Border leaf switches (external connectivity)

- **Validation Checklist**: Post-migration validation for:
  - Underlay (IGP, reachability)
  - BGP EVPN control plane
  - Data plane (MAC learning, ARP, connectivity)
  - Policy enforcement

### Usage

1. Select **EVPN Migration** mode from the home page
2. Upload ACI data (same as Offboard mode)
3. Choose target platform (NX-OS, EOS, or Junos)
4. Review:
   - Migration complexity assessment
   - ACI-to-EVPN object mappings
   - 7-phase migration plan with risks and timelines
5. Download platform-specific configurations
6. Use validation checklist during migration

### Example Mapping

| ACI Object | EVPN Equivalent | Details |
|------------|-----------------|---------|
| fvCtx (VRF) | L3 VNI 50000+ | VRF with BGP EVPN RT |
| fvBD (Bridge Domain) | L2 VNI 10000+ | VLAN + L2 VNI mapping |
| fvAEPg (EPG) | VLAN | Access port configuration |
| vzBrCP (Contract) | ACL/Route-map | Translated to permit/deny rules |

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
