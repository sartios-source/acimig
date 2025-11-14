# ACI Migrator v1.01 - Technical Documentation

> Comprehensive technical documentation for developers and system administrators

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Installation Guide](#installation-guide)
4. [User Guide](#user-guide)
5. [API Reference](#api-reference)
6. [Configuration](#configuration)
7. [Security](#security)
8. [Troubleshooting](#troubleshooting)
9. [Development Guide](#development-guide)

---

## Overview

### What is ACI Migrator?

ACI Migrator v1.01 is a professional web-based analysis and migration planning tool for Cisco ACI (Application Centric Infrastructure) environments. It provides comprehensive analysis, visualization, and automated configuration generation for:

- **EVPN/VXLAN Migration**: Migrate from ACI to standards-based EVPN fabric
- **Onboard Planning**: Plan new FEX/leaf deployments and capacity
- **Network Analysis**: Deep inspection of ACI configuration and topology
- **Multi-Fabric Management**: Manage multiple data centers and environments

### Key Features

- Multi-format data ingestion (JSON, XML, CSV, legacy configs)
- Advanced analysis engine with 15+ analysis methods
- Interactive visualizations and dashboards
- Automated EVPN/VXLAN configuration generation
- Multi-platform support (Cisco NX-OS, Arista EOS, Juniper Junos)
- Comprehensive reporting (HTML, Markdown, CSV)
- Fabric management with isolation and multi-tenancy
- Security hardening and rate limiting

### Technology Stack

**Backend:**
- Python 3.8+
- Flask 3.0+ (Web framework)
- Jinja2 (Template engine)
- WTForms (Form validation)
- Flask-Limiter (Rate limiting)

**Frontend:**
- Tailwind CSS (Utility-first CSS)
- Vanilla JavaScript (No frameworks)
- Chart.js (Data visualization)
- Mermaid.js (Flowcharts)

**Storage:**
- File-based storage (JSON)
- No database required

---

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
│  (Tailwind CSS, JavaScript, Responsive Design)          │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  Flask Application                       │
│  - Routing & View Logic                                 │
│  - Session Management                                    │
│  - Security Middleware (CSRF, Rate Limiting)            │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│               Analysis Engine Layer                      │
│  ┌─────────────┬──────────────┬──────────────┐         │
│  │   Parsers   │   Analyzer   │   Planning   │         │
│  │             │              │              │         │
│  │ - JSON/XML  │ - ACIAnalyzer│ - ACIPlanner │         │
│  │ - CSV       │ - Metrics    │ - EVPN Gen   │         │
│  │ - Legacy    │ - Topology   │ - Reporting  │         │
│  └─────────────┴──────────────┴──────────────┘         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                Fabric Manager Layer                      │
│  - Multi-fabric isolation                                │
│  - Dataset management                                    │
│  - Metadata tracking                                     │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│                  Storage Layer                           │
│  fabrics/                                                │
│    ├── fabric1/                                          │
│    │   ├── manifest.json                                 │
│    │   ├── data1.json                                    │
│    │   └── data2.xml                                     │
│    └── fabric2/                                          │
│        └── ...                                           │
└─────────────────────────────────────────────────────────┘
```

### Component Architecture

**1. Web Layer (Flask + Templates)**
- `app.py`: Main application entry point
- `templates/`: Jinja2 HTML templates
- `static/`: JavaScript, CSS assets

**2. Analysis Layer**
- `analysis/parsers.py`: Data ingestion and parsing
- `analysis/engine.py`: Core analysis logic
- `analysis/planning.py`: Migration planning
- `analysis/evpn_migration.py`: EVPN config generation
- `analysis/reporting.py`: Report generation

**3. Fabric Management**
- `analysis/fabric_manager.py`: Multi-fabric CRUD operations

**4. Configuration**
- `config.py`: Environment-based configuration
- `.env`: Environment variables

### Data Flow

```
Upload → Parse → Validate → Categorize → Store → Analyze → Visualize → Report
```

**Step-by-Step:**

1. **Upload**: User uploads ACI JSON/XML or CMDB CSV
2. **Parse**: Appropriate parser extracts data
3. **Validate**: Schema validation and completeness check
4. **Categorize**: Objects sorted by type (EPG, FEX, BD, etc.)
5. **Store**: Data saved to fabric directory
6. **Analyze**: Analysis engine processes data
7. **Visualize**: Results rendered in dashboards
8. **Report**: Export in multiple formats

---

## Installation Guide

### System Requirements

**Minimum:**
- Python 3.8 or higher
- 2GB RAM
- 1GB disk space
- Modern web browser (Chrome, Firefox, Safari, Edge)

**Recommended:**
- Python 3.10+
- 4GB+ RAM
- 5GB disk space (for large datasets)
- High-speed network for large file uploads

### Installation Steps

#### 1. Clone Repository

```bash
git clone <repository-url>
cd ACI Migrator
```

#### 2. Create Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

#### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

#### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# (Use your preferred text editor)
```

#### 5. Verify Installation

```bash
python app.py
```

Expected output:
```
======================================================================
ACI Migrator v1.0.0 - Professional ACI Migration Tool
======================================================================
Data directory: C:\Users\...\aciv2\data
Fabrics directory: C:\Users\...\aciv2\fabrics
Output directory: C:\Users\...\aciv2\output
======================================================================
Access the application at: http://127.0.0.1:5000
======================================================================
```

#### 6. Access Application

Open browser to: `http://127.0.0.1:5000`

### Docker Installation (Optional)

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["python", "app.py"]
```

```bash
# Build and run
docker build -t ACI Migrator:1.0 .
docker run -p 5000:5000 -v $(pwd)/fabrics:/app/fabrics ACI Migrator:1.0
```

---

## User Guide

### Getting Started

#### 1. Create Your First Fabric

1. Open the application in your browser
2. Click "Fabric Manager" in the left sidebar
3. Click "Create Fabric" button
4. Enter a descriptive name (e.g., "prod-dc1")
5. Click "Create Fabric"

**Fabric Naming Best Practices:**
- Use environment prefixes: `prod-`, `dev-`, `staging-`
- Include location: `dc1-`, `aws-us-east-1-`
- Keep it short but descriptive
- Avoid spaces and special characters

#### 2. Upload ACI Configuration Data

**Option A: ACI JSON/XML Export**

1. Navigate to "Upload" page
2. Drag and drop your ACI export files
3. Supported formats: `.json`, `.xml`
4. Wait for parsing to complete

**Option B: CMDB CSV Import**

1. Prepare CSV with columns:
   - `device_name`
   - `serial_number`
   - `model`
   - `location`
   - `rack`
2. Upload via "Upload" page

**Option C: Legacy Config Import**

1. Export legacy switch configs
2. Supported formats: `.txt`, `.cfg`, `.conf`
3. Upload via "Upload" page

#### 3. Analyze Your Data

1. Navigate to "Analyze" page
2. Review data completeness validation
3. Explore categorized tables:
   - **FEX Devices**: Fabric Extenders
   - **Leaf Switches**: Leaf nodes
   - **EPGs**: Endpoint Groups
   - **Bridge Domains**: Layer 2 segments
   - **VRFs**: Routing instances
   - **Contracts**: Policy rules
4. Use search and filters to focus analysis

#### 4. Visualize Network Topology

1. Navigate to "Visualize" page
2. Explore interactive charts:
   - **Port Utilization**: Identify underutilized devices
   - **VLAN Distribution**: Namespace conflicts
   - **EPG Complexity**: Migration difficulty
   - **VPC Symmetry**: Configuration consistency
3. Drill down into specific devices

#### 5. Generate Migration Plan

1. Navigate to "Plan" page
2. Select mode:
   - **EVPN**: Migration to standards-based fabric
   - **Onboard**: New deployment planning
3. Review recommendations:
   - Priority ranking
   - Time estimates
   - Risk assessment
4. Download configurations

#### 6. Export Reports

1. Navigate to "Report" page
2. Choose format:
   - **HTML**: Interactive browser report
   - **Markdown**: Documentation-friendly
   - **CSV**: Data analysis in Excel
3. Click "Download Report"

### Fabric Management

**Switch Fabrics:**
1. Click "Fabric Manager" in sidebar
2. Select fabric from dropdown
3. Page will reload with new fabric context

**Delete Fabric:**
1. Ensure fabric is selected
2. Click "Delete Fabric" button
3. Confirm deletion (cannot be undone)

**View Current Fabric:**
- Current fabric name is always displayed in sidebar
- Also shown in top navigation bar

### Advanced Features

#### Multi-Mode Operation

**EVPN Migration Mode:**
- Analyze VPC configurations
- Map contracts to ACLs
- Document L3Out connectivity
- Generate EVPN configs (spine, leaf, border)

**Onboard Mode:**
- Calculate port capacity
- Identify available resources
- Generate policy scaffolding
- Plan new deployments

#### API Analysis

Use REST API for programmatic access:

```bash
# Get fabric list
curl http://localhost:5000/fabrics

# Analyze VPC configuration
curl http://localhost:5000/api/analyze/vpc/fabric_name

# Migration assessment
curl http://localhost:5000/api/migration-assessment/fabric_name
```

---

## API Reference

### Authentication

Currently, ACI Migrator v1.0 does not require authentication. For production deployment, implement authentication middleware or use reverse proxy with authentication.

### Endpoints

#### Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-11-13T10:00:00",
  "version": "1.0.0",
  "app_name": "ACI Migrator",
  "fabrics_dir_exists": true,
  "output_dir_exists": true
}
```

#### Fabric Management

**List Fabrics**
```
GET /fabrics
```

**Create Fabric**
```
POST /fabrics
Content-Type: application/json

{
  "name": "production-dc1"
}
```

**Delete Fabric**
```
DELETE /fabrics/{fabric_name}
```

**Select Fabric**
```
POST /fabrics/{fabric_name}/select
```

#### Data Upload

**Upload File**
```
POST /upload
Content-Type: multipart/form-data

file: <binary data>
```

#### Analysis APIs

**VPC Analysis**
```
GET /api/analyze/vpc/{fabric_id}
```

**Contract Analysis**
```
GET /api/analyze/contracts/{fabric_id}
```

**L3Out Analysis**
```
GET /api/analyze/l3out/{fabric_id}
```

**VLAN Analysis**
```
GET /api/analyze/vlans/{fabric_id}
```

**Physical Connectivity**
```
GET /api/analyze/physical/{fabric_id}
```

**Migration Assessment**
```
GET /api/migration-assessment/{fabric_id}
```

**Generic Analysis**
```
GET /api/analysis/{analysis_type}
```

Supported `analysis_type` values:
- `port_utilization`
- `leaf_fex_mapping`
- `rack_grouping`
- `bd_epg_mapping`
- `vlan_distribution`
- `epg_complexity`
- `vpc_symmetry`
- `pdom_analysis`
- `migration_flags`
- `contract_scope`
- `vlan_spread`
- `cmdb_correlation`

#### Report Generation

**Download Report**
```
GET /download/report/{format}
```

Formats: `html`, `markdown`, `csv`

**Download EVPN Config**
```
GET /download/evpn_config/{device_role}?platform={platform}
```

Device roles: `spine`, `leaf`, `border_leaf`
Platforms: `nxos`, `eos`, `junos`

---

## Configuration

### Environment Variables

Create `.env` file:

```bash
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key-here-change-in-production

# Data Directories
DATA_DIR=./data
FABRICS_DIR=./fabrics
OUTPUT_DIR=./output
CMDB_DIR=./cmdb

# Security
MAX_CONTENT_LENGTH=1073741824  # 1GB
ALLOWED_EXTENSIONS=json,xml,csv,txt,cfg,conf

# Rate Limiting
API_RATE_LIMIT=100 per hour

# Logging
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log
LOG_MAX_BYTES=10485760  # 10MB
LOG_BACKUP_COUNT=5
```

### Configuration Classes

**Development Configuration:**
```python
DEBUG = True
TESTING = False
LOG_LEVEL = logging.DEBUG
```

**Production Configuration:**
```python
DEBUG = False
TESTING = False
LOG_LEVEL = logging.INFO
# Stricter security settings
```

**Testing Configuration:**
```python
TESTING = True
# Use temporary directories
```

### Directory Structure

```
ACI Migrator/
├── fabrics/          # Fabric data storage
│   ├── fabric1/
│   │   ├── manifest.json
│   │   └── *.json, *.xml
│   └── fabric2/
├── output/           # Generated reports
├── logs/             # Application logs
├── data/             # Temporary data
└── cmdb/             # CMDB data
```

---

## Security

### Built-in Security Features

1. **CSRF Protection**: Enabled for all POST/PUT/DELETE requests
2. **Rate Limiting**: API endpoints limited to prevent abuse
3. **File Upload Validation**:
   - Extension whitelist
   - Content-type checking
   - Size limits (1GB default)
4. **Path Traversal Prevention**: Filename sanitization
5. **Input Validation**: All user input validated
6. **Secure Fabric Names**: Alphanumeric and dash/underscore only

### Security Best Practices

1. **Change Secret Key**: Use strong random key in production
2. **Use HTTPS**: Deploy behind reverse proxy with SSL
3. **Limit Access**: Use firewall rules or authentication proxy
4. **Regular Updates**: Keep dependencies updated
5. **Audit Logs**: Review logs regularly for anomalies
6. **Backup Data**: Regular backups of fabrics directory

### Production Deployment

**Using Nginx as Reverse Proxy:**

```nginx
server {
    listen 443 ssl;
    server_name ACI Migrator.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=ACI Migrator:10m rate=10r/s;
    limit_req zone=ACI Migrator burst=20;
}
```

---

## Troubleshooting

### Common Issues

#### Application Won't Start

**Symptom:** Error on startup

**Solutions:**
```bash
# Check Python version (3.8+ required)
python --version

# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Check for port conflicts
netstat -an | grep 5000  # Linux/macOS
netstat -an | findstr 5000  # Windows
```

#### File Upload Fails

**Symptom:** "Upload failed" error

**Solutions:**
- Check file size (max 1GB by default)
- Verify file extension is allowed
- Ensure fabric is selected
- Check disk space
- Review logs: `tail -f logs/app.log`

#### Parse Errors

**Symptom:** "Invalid JSON" or "Parse error"

**Solutions:**
```bash
# Validate JSON
python -m json.tool < your_file.json

# Check for BOM (Byte Order Mark)
file your_file.json

# Try different encoding
iconv -f UTF-16 -t UTF-8 input.json > output.json
```

#### Dashboards Not Loading

**Symptom:** Blank visualizations

**Solutions:**
- Ensure fabric has uploaded data
- Check browser console for JavaScript errors (F12)
- Clear browser cache
- Verify data completeness in Analyze page

#### No Objects Found

**Symptom:** Analysis shows 0 objects

**Solutions:**
- Verify JSON structure contains "imdata" array
- Check object class names match ACI format
- Ensure file parsed successfully (check Upload page)
- Review logs for parsing errors

### Debug Mode

Enable detailed logging:

```bash
# Windows
set FLASK_ENV=development
set LOG_LEVEL=DEBUG
python app.py

# Linux/macOS
export FLASK_ENV=development
export LOG_LEVEL=DEBUG
python app.py
```

### Reset Application

Clear all data:

```bash
# Backup first!
cp -r fabrics fabrics.backup

# Remove all data
rm -rf fabrics/* output/* logs/*

# Restart application
python app.py
```

---

## Development Guide

### Development Setup

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Enable debug mode
export FLASK_ENV=development

# Run application
python app.py
```

### Code Structure

```
ACI Migrator/
├── app.py                 # Main Flask app
├── config.py              # Configuration classes
├── requirements.txt       # Dependencies
│
├── analysis/             # Analysis modules
│   ├── __init__.py
│   ├── parsers.py        # Data parsers
│   ├── engine.py         # Analysis engine
│   ├── planning.py       # Migration planning
│   ├── reporting.py      # Report generation
│   ├── evpn_migration.py # EVPN config gen
│   └── fabric_manager.py # Fabric management
│
├── templates/            # Jinja2 templates
│   ├── base.html         # Base template
│   ├── index.html        # Home page
│   ├── upload.html       # Upload interface
│   ├── analyze.html      # Analysis dashboard
│   ├── visualize.html    # Visualizations
│   ├── plan.html         # Planning page
│   ├── report.html       # Reports page
│   ├── evpn_migration.html
│   └── help.html         # Documentation
│
├── static/               # Static assets
│   ├── app.js            # Core JavaScript
│   ├── upload.js         # Upload handling
│   └── styles.css        # Custom CSS
│
└── tests/                # Test suite
    ├── test_analysis_engine.py
    ├── test_parsers.py
    └── test_fabric_manager.py
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python test_analysis_engine.py

# Run with coverage
python -m pytest --cov=analysis --cov-report=html
```

### Code Style

```bash
# Format code
black app.py analysis/

# Lint code
flake8 app.py analysis/

# Type checking
mypy app.py
```

### Adding New Analysis Methods

1. Add method to `analysis/engine.py`:

```python
def analyze_custom_metric(self):
    """Your custom analysis."""
    results = []
    # Analysis logic here
    return results
```

2. Register in analysis methods dict:

```python
analysis_methods = {
    'custom_metric': analyzer.analyze_custom_metric
}
```

3. Add API endpoint in `app.py`:

```python
@app.route('/api/analysis/custom_metric')
def get_custom_metric():
    # API logic
    pass
```

### Contributing

1. Fork repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes and add tests
4. Ensure tests pass: `pytest`
5. Commit: `git commit -m "Add my feature"`
6. Push: `git push origin feature/my-feature`
7. Create pull request

---

## Appendix

### Glossary

- **ACI**: Application Centric Infrastructure (Cisco)
- **EPG**: Endpoint Group
- **BD**: Bridge Domain
- **VRF**: Virtual Routing and Forwarding
- **FEX**: Fabric Extender
- **VPC**: Virtual Port Channel
- **EVPN**: Ethernet VPN
- **VXLAN**: Virtual Extensible LAN
- **L3Out**: Layer 3 Outside Connection
- **VTEP**: VXLAN Tunnel Endpoint

### Further Reading

- [Cisco ACI Documentation](https://www.cisco.com/c/en/us/support/cloud-systems-management/application-policy-infrastructure-controller-apic/tsd-products-support-series-home.html)
- [EVPN/VXLAN RFC 7432](https://datatracker.ietf.org/doc/html/rfc7432)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)

### Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

**ACI Migrator v1.0** - Professional ACI to EVPN/VXLAN Migration Analysis Tool

Copyright 2025 - All Rights Reserved
