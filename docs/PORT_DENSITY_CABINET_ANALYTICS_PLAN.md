# Port Density & Cabinet Analytics - Implementation Plan

## Overview

Comprehensive port density and cabinet-level analytics to provide physical topology insights, optimize rack space utilization, and support data center consolidation/expansion planning.

---

## Business Value

### Offboard Mode
- Identify underutilized cabinets for consolidation
- Calculate power savings from decommissioned devices
- Optimize cabinet/rack space utilization
- Plan physical moves and re-stacking

### Onboard Mode
- Find cabinets with available capacity
- Plan new device placement
- Optimize port density for new deployments
- Balance power and cooling across cabinets

### EVPN Migration Mode
- Group migrations by physical location
- Minimize cable moves during migration
- Understand physical dependencies
- Plan migration waves by cabinet/row/datacenter

---

## Data Requirements

### Required Data

#### 1. CMDB Data (Enhanced)
Current CMDB fields:
```csv
device_name, serial_number, model, location, rack, status
```

**Enhanced CMDB fields needed**:
```csv
device_name,serial_number,model,device_type,location,datacenter,room,row,cabinet,rack_unit_start,rack_unit_height,power_consumption_watts,port_count,ports_connected,management_ip,notes
```

**Example**:
```csv
leaf-101,SAL1234567,N9K-C93180YC-EX,leaf,NYC-DC1,NYC,Room-A,Row-3,Cab-15,10,2,350,48,32,10.1.1.101,Production leaf
fex-201,FCH1234567,N2K-C2348TQ-10GE,fex,NYC-DC1,NYC,Room-A,Row-3,Cab-15,15,1,75,48,28,10.1.1.201,Connected to leaf-101
```

#### 2. ACI Fabric Data
- eqptFex - FEX devices with port counts
- fabricNode - Leaf switches
- ethpmPhysIf - Physical interfaces with operational status
- fvRsPathAtt - EPG path attachments for port utilization

### Optional Data
- Power consumption data (from DCIM systems)
- Temperature/cooling data
- Cable plant documentation
- Physical port labels

---

## Analysis Components

### 1. Port Density Analysis

#### Metrics to Calculate

**Per Device**:
```python
{
    'device_id': 'fex-201',
    'device_name': 'FEX-201-NYC',
    'model': 'N2K-C2348TQ-10GE',
    'total_ports': 48,
    'connected_ports': 28,
    'active_ports': 24,      # Ports with active traffic
    'available_ports': 20,    # Total - connected
    'port_utilization': 58.3, # (connected / total) * 100
    'port_efficiency': 85.7,  # (active / connected) * 100
    'density_score': 49.9     # Composite score for optimization
}
```

**Per Cabinet/Rack**:
```python
{
    'cabinet_id': 'Cab-15',
    'location': 'NYC-DC1/Room-A/Row-3/Cab-15',
    'total_devices': 8,
    'device_breakdown': {
        'leafs': 2,
        'fexes': 6,
        'other': 0
    },
    'total_ports': 336,        # Sum of all device ports
    'connected_ports': 187,
    'active_ports': 156,
    'available_ports': 149,
    'port_utilization': 55.7,
    'rack_units_used': 18,     # Physical rack space
    'rack_units_available': 24, # 42U rack
    'rack_utilization': 42.9,
    'power_consumption': 1850,  # Watts
    'power_capacity': 5000,     # Watts per cabinet
    'power_utilization': 37.0,
    'consolidation_opportunity': 'HIGH'  # Based on low utilization
}
```

**Per Datacenter/Room/Row**:
```python
{
    'datacenter': 'NYC-DC1',
    'room': 'Room-A',
    'row': 'Row-3',
    'total_cabinets': 12,
    'total_devices': 96,
    'total_ports': 4032,
    'avg_port_utilization': 62.4,
    'underutilized_cabinets': 5,  # < 40% port utilization
    'fully_utilized_cabinets': 2,  # > 90% port utilization
    'available_capacity_ports': 1518,
    'consolidation_savings': {
        'devices_to_remove': 18,
        'ports_freed': 864,
        'power_savings_watts': 1350,
        'rack_units_freed': 22
    }
}
```

#### Density Scoring Algorithm

```python
def calculate_density_score(device_data):
    """
    Calculate port density optimization score (0-100).
    Lower score = better consolidation candidate
    Higher score = efficiently utilized
    """

    # Factor 1: Port utilization (40% weight)
    port_util = (device_data['connected_ports'] / device_data['total_ports']) * 100
    port_score = port_util * 0.4

    # Factor 2: Port efficiency (30% weight)
    # Active vs connected ports
    port_efficiency = (device_data['active_ports'] / device_data['connected_ports']) * 100 if device_data['connected_ports'] > 0 else 0
    efficiency_score = port_efficiency * 0.3

    # Factor 3: Operational status (20% weight)
    status_score = 20 if device_data['operational_status'] == 'up' else 0

    # Factor 4: Strategic importance (10% weight)
    # Based on tenant criticality, EPG types
    strategic_score = calculate_strategic_importance(device_data) * 0.1

    total_score = port_score + efficiency_score + status_score + strategic_score

    return round(total_score, 2)
```

---

### 2. Cabinet Analytics

#### Cabinet View Hierarchy

```
Datacenter
├── Room
│   ├── Row
│   │   ├── Cabinet
│   │   │   ├── Device 1 (RU 10-12)
│   │   │   │   ├── Port utilization
│   │   │   │   ├── EPG distribution
│   │   │   │   └── Power consumption
│   │   │   ├── Device 2 (RU 15)
│   │   │   └── Device 3 (RU 20-21)
│   │   ├── Cabinet 2
│   │   └── ...
│   ├── Row 2
│   └── ...
└── Room B
```

#### Cabinet Heatmap

Visual representation of port utilization across cabinets:

```
NYC-DC1 / Room-A / Row-3

Cab-13  Cab-14  Cab-15  Cab-16  Cab-17  Cab-18
┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐
│ 92%│  │ 45%│  │ 38%│  │ 78%│  │ 15%│  │ 88%│
│████│  │██░░│  │█░░░│  │███░│  │░░░░│  │████│
│████│  │██░░│  │█░░░│  │███░│  │░░░░│  │████│
└────┘  └────┘  └────┘  └────┘  └────┘  └────┘
 HIGH    MED     LOW     HIGH    LOW     HIGH

Legend:
  ████ >80% - Fully Utilized (Green)
  ███░ 60-80% - Well Utilized (Blue)
  ██░░ 40-60% - Moderate (Yellow)
  █░░░ <40% - Underutilized (Orange)
  ░░░░ <20% - Candidate for Consolidation (Red)
```

#### Cabinet Physical Layout

```
Cabinet: Cab-15 (NYC-DC1/Room-A/Row-3)
42U Rack

RU  Device           Model             Ports  Util   Power
──────────────────────────────────────────────────────────
42  ▒▒▒▒▒▒▒▒▒▒▒▒▒                                  0W
40  ▒▒▒▒▒▒▒▒▒▒▒▒▒                                  0W
38  ▒▒▒▒▒▒▒▒▒▒▒▒▒                                  0W
...
22  Leaf-102        N9K-C93180       48/48  100%   350W
20  ────────────                                     ─
18  FEX-206         N2K-C2348TQ      32/48   67%    75W
16  ▒▒▒▒▒▒▒▒▒▒▒▒▒                                  0W
15  FEX-205         N2K-C2348TQ      18/48   38%    75W
14  ▒▒▒▒▒▒▒▒▒▒▒▒▒                                  0W
12  FEX-204         N2K-C2348TQ      28/48   58%    75W
10  Leaf-101        N9K-C93180       48/48  100%   350W
08  ────────────                                     ─
06  FEX-203         N2K-C2348TQ      12/48   25%    75W
04  ▒▒▒▒▒▒▒▒▒▒▒▒▒                                  0W
02  FEX-202         N2K-C2348TQ       8/48   17%    75W
01  ▒▒▒▒▒▒▒▒▒▒▒▒▒                                  0W

Summary:
  Devices: 6 (2 leafs, 4 FEX)
  RU Used: 18 / 42 (43%)
  Ports: 146 / 336 (43%)
  Power: 1,075W / 5,000W (22%)

Recommendations:
  ⚠ 3 FEX devices with <40% utilization
  💡 Consolidate FEX-202, FEX-203, FEX-205 → 1 FEX
  💰 Save 150W power, free 3 RU
```

---

### 3. Consolidation Analysis

#### Consolidation Opportunities

**Per Cabinet**:
```python
{
    'cabinet_id': 'Cab-15',
    'current_state': {
        'devices': 6,
        'ports_total': 336,
        'ports_connected': 146,
        'power_watts': 1075,
        'rack_units': 18
    },
    'consolidation_scenario': {
        'devices_to_remove': ['FEX-202', 'FEX-203', 'FEX-205'],
        'devices_to_keep': ['Leaf-101', 'Leaf-102', 'FEX-204', 'FEX-206'],
        'ports_migrated': 38,  # Ports from removed FEX
        'target_devices': ['FEX-204'],  # Migrate to these devices
        'target_ports_available': 20  # Sufficient capacity
    },
    'post_consolidation': {
        'devices': 4,
        'ports_total': 240,
        'ports_connected': 146,
        'power_watts': 850,
        'rack_units': 12
    },
    'savings': {
        'devices_removed': 2,
        'power_saved_watts': 225,
        'power_saved_annual_kwh': 1971,
        'power_saved_annual_cost': 197,  # @$0.10/kWh
        'rack_units_freed': 6,
        'ports_freed': 96
    },
    'risk_level': 'LOW',  # Based on coupling analysis
    'estimated_effort_hours': 8
}
```

#### Multi-Cabinet Consolidation

Identify opportunities to consolidate entire cabinets:

```python
{
    'scenario': 'Consolidate Row-3 cabinets',
    'current_cabinets': ['Cab-15', 'Cab-16', 'Cab-17'],
    'target_cabinets': ['Cab-15', 'Cab-16'],  # Consolidate into 2
    'cabinet_to_empty': 'Cab-17',
    'devices_to_relocate': [
        {'device': 'FEX-301', 'from': 'Cab-17', 'to': 'Cab-15'},
        {'device': 'FEX-302', 'from': 'Cab-17', 'to': 'Cab-16'}
    ],
    'savings': {
        'cabinets_freed': 1,
        'power_saved_watts': 450,
        'annual_cost_savings': 394,
        'floor_space_freed_sqft': 4
    },
    'implementation_plan': {
        'phase_1': 'Migrate EPGs from FEX-301 and FEX-302',
        'phase_2': 'Physical relocation during maintenance window',
        'phase_3': 'Cable cleanup and verification',
        'total_downtime_hours': 4,
        'maintenance_windows_required': 1
    }
}
```

---

### 4. Capacity Planning

#### Available Capacity by Location

```python
{
    'datacenter': 'NYC-DC1',
    'capacity_summary': {
        'total_cabinets': 120,
        'cabinets_with_capacity': 68,
        'total_available_ports': 5420,
        'total_available_rack_units': 386,
        'total_available_power_kw': 145
    },
    'capacity_by_room': [
        {
            'room': 'Room-A',
            'available_ports': 1240,
            'available_rack_units': 86,
            'available_power_kw': 32,
            'recommended_for_expansion': True,
            'notes': 'High availability, good cooling'
        },
        {
            'room': 'Room-B',
            'available_ports': 2180,
            'available_rack_units': 124,
            'available_power_kw': 48,
            'recommended_for_expansion': True,
            'notes': 'New infrastructure, optimal for growth'
        }
    ],
    'onboard_scenarios': [
        {
            'scenario': 'Add 10 new FEX (480 ports)',
            'recommended_cabinets': ['Cab-B12', 'Cab-B13', 'Cab-B14'],
            'power_required': 750,
            'cooling_required': 2560,  # BTU/hr
            'estimated_cost': 15000,
            'deployment_time_days': 3
        }
    ]
}
```

---

## Visualization Components

### 1. Port Density Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│ 📊 Port Density & Cabinet Analytics                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Datacenter: [NYC-DC1 ▼]     Room: [All Rooms ▼]              │
│  Row: [All Rows ▼]          View: [●Cabinet ○Device ○Port]    │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Summary Metrics                                                │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ 4,032       │  │ 62.4%       │  │ 1,518       │           │
│  │ Total Ports │  │ Utilization │  │ Available   │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐           │
│  │ 96          │  │ 22          │  │ $2,340      │           │
│  │ Devices     │  │ RU Free     │  │ Annual Save │           │
│  └─────────────┘  └─────────────┘  └─────────────┘           │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Cabinet Heatmap - Room A, Row 3                                │
│                                                                 │
│  Cab-13   Cab-14   Cab-15   Cab-16   Cab-17   Cab-18          │
│  ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐  ┌────┐             │
│  │ 92%│  │ 45%│  │ 38%│  │ 78%│  │ 15%│  │ 88%│             │
│  │ H  │  │ M  │  │ L  │  │ H  │  │ L  │  │ H  │             │
│  └────┘  └────┘  └────┘  └────┘  └────┘  └────┘             │
│  [View]   [View]  [View]  [View]  [View]  [View]              │
│                                                                 │
│  Legend: H=High (>80%) M=Medium (40-80%) L=Low (<40%)          │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Top Consolidation Opportunities                                │
│                                                                 │
│  Rank  Cabinet     Location        Util   Savings    Risk      │
│  ──────────────────────────────────────────────────────────────│
│   1    Cab-17      Row-3          15%    $450/yr    LOW       │
│   2    Cab-15      Row-3          38%    $225/yr    LOW       │
│   3    Cab-22      Row-4          28%    $340/yr    MEDIUM    │
│   4    Cab-08      Row-1          35%    $280/yr    LOW       │
│   5    Cab-19      Row-3          42%    $190/yr    LOW       │
│                                                                 │
│   [Generate Consolidation Plan]   [Export Report]              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Cabinet Detail View

```
┌─────────────────────────────────────────────────────────────────┐
│ 🗄️ Cabinet Detail: Cab-15                                       │
│ Location: NYC-DC1 / Room-A / Row-3 / Position-15               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Cabinet Metrics                                                │
│                                                                 │
│  Port Utilization:  [███░░░░░░░] 43% (146/336)                 │
│  Rack Utilization:  [███░░░░░░░] 43% (18/42 RU)                │
│  Power Utilization: [██░░░░░░░░] 22% (1075/5000 W)             │
│                                                                 │
│  Devices: 6  |  Ports: 336  |  Power: 1.1 kW                   │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Physical Layout (42U Rack)                                     │
│                                                                 │
│  RU │ Device      │ Model        │ Ports │ Util  │ Power │    │
│  ───┼─────────────┼──────────────┼───────┼───────┼───────┤    │
│  42 │ [Empty]     │              │       │       │       │    │
│  ... │            │              │       │       │       │    │
│  22 │ Leaf-102    │ N9K-C93180   │ 48/48 │ 100%  │ 350W  │ ←  │
│  20 │ ────────    │              │       │       │       │    │
│  18 │ FEX-206     │ N2K-C2348TQ  │ 32/48 │  67%  │  75W  │ ←  │
│  16 │ [Empty]     │              │       │       │       │    │
│  15 │ FEX-205     │ N2K-C2348TQ  │ 18/48 │  38%  │  75W  │ ⚠  │
│  14 │ [Empty]     │              │       │       │       │    │
│  12 │ FEX-204     │ N2K-C2348TQ  │ 28/48 │  58%  │  75W  │ ←  │
│  10 │ Leaf-101    │ N9K-C93180   │ 48/48 │ 100%  │ 350W  │ ←  │
│  08 │ ────────    │              │       │       │       │    │
│  06 │ FEX-203     │ N2K-C2348TQ  │ 12/48 │  25%  │  75W  │ ⚠  │
│  04 │ [Empty]     │              │       │       │       │    │
│  02 │ FEX-202     │ N2K-C2348TQ  │  8/48 │  17%  │  75W  │ ⚠  │
│  01 │ [Empty]     │              │       │       │       │    │
│                                                                 │
│  Legend: ← Well Utilized | ⚠ Underutilized                     │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  💡 Consolidation Recommendations                               │
│                                                                 │
│  Scenario 1: Consolidate 3 underutilized FEX                   │
│                                                                 │
│  Remove: FEX-202, FEX-203, FEX-205                             │
│  Migrate 38 ports → FEX-204 (has 20 ports available)           │
│                                                                 │
│  Savings:                                                       │
│    • Power: 225W → $197/year                                   │
│    • Rack Space: 3 RU                                          │
│    • Maintenance: 3 fewer devices                              │
│                                                                 │
│  Risk: LOW (no multi-tenant coupling detected)                 │
│  Effort: 8 hours                                               │
│                                                                 │
│  [View Detailed Plan]  [Export to PDF]  [Create Work Order]    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Port Density Treemap

Interactive treemap showing port utilization hierarchy:

```
┌─────────────────────────────────────────────────────────────────┐
│ Port Utilization Treemap                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ NYC-DC1 ─────────────────────────────────────────────────┐ │
│  │                                                             │ │
│  │  ┌─ Room-A ──────────────┐  ┌─ Room-B ──────────────────┐ │ │
│  │  │                        │  │                            │ │ │
│  │  │ ┌─Row-1─┐ ┌─Row-2───┐ │  │ ┌─Row-1────┐ ┌─Row-2────┐ │ │ │
│  │  │ │ 82%   │ │ 65%     │ │  │ │ 45%      │ │ 72%      │ │ │ │
│  │  │ │ Cab15 │ │ Cab18   │ │  │ │ Cab01    │ │ Cab08    │ │ │ │
│  │  │ └───────┘ └─────────┘ │  │ └──────────┘ └──────────┘ │ │ │
│  │  │                        │  │                            │ │ │
│  │  └────────────────────────┘  └────────────────────────────┘ │ │
│  │                                                             │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  Size = Total Ports | Color = Utilization % | Click to drill   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

### Phase 1: Data Model & Collection (Week 1-2)

**Tasks**:
1. ✅ Enhance CMDB CSV format specification
2. ✅ Create sample enhanced CMDB data
3. ✅ Update parsers to handle extended CMDB fields
4. ✅ Add validation for location hierarchy
5. ✅ Create data structures for cabinet analytics

**Deliverables**:
- Enhanced CMDB template with all required fields
- Parser updates to handle cabinet/rack data
- Validation logic for location hierarchy

### Phase 2: Analysis Engine (Week 3-4)

**Tasks**:
1. ✅ Implement port density calculation methods
2. ✅ Create cabinet-level aggregation
3. ✅ Build consolidation scoring algorithm
4. ✅ Implement capacity planning calculations
5. ✅ Add multi-level rollup (device → cabinet → row → room → DC)

**New Methods**:
```python
class ACIAnalyzer:
    def analyze_port_density(self) -> Dict[str, Any]
    def analyze_cabinet_utilization(self) -> Dict[str, Any]
    def analyze_consolidation_opportunities(self) -> Dict[str, Any]
    def analyze_capacity_by_location(self) -> Dict[str, Any]
    def generate_cabinet_layout(self, cabinet_id: str) -> Dict[str, Any]
```

**Deliverables**:
- 5 new analysis methods in engine.py
- Comprehensive test suite
- Documentation

### Phase 3: Visualization UI (Week 5-6)

**Tasks**:
1. ✅ Create port density dashboard page
2. ✅ Build cabinet heatmap visualization (D3.js)
3. ✅ Implement cabinet detail view
4. ✅ Add interactive treemap
5. ✅ Create consolidation scenario builder

**New Templates**:
- `templates/port_density.html` - Main dashboard
- `templates/cabinet_detail.html` - Cabinet drill-down
- `static/cabinet_viz.js` - Visualization logic

**Deliverables**:
- Interactive dashboards
- Drill-down capability
- Export functionality

### Phase 4: Reports & Export (Week 7-8)

**Tasks**:
1. ✅ Create consolidation plan PDF export
2. ✅ Add cabinet inventory report
3. ✅ Generate capacity planning report
4. ✅ Create work order templates
5. ✅ Add email notifications for reports

**Deliverables**:
- PDF report templates
- CSV export for cabinet data
- Work order generation

---

## Data Collection Guide

### Enhanced CMDB CSV Format

**Template**:
```csv
device_name,serial_number,model,device_type,datacenter,room,row,cabinet,rack_unit_start,rack_unit_height,total_ports,management_ip,power_watts,status,notes

leaf-101,SAL1928374,N9K-C93180YC-EX,leaf,NYC-DC1,Room-A,Row-3,Cab-15,10,2,48,10.1.1.101,350,active,Production leaf
fex-201,FCH9283746,N2K-C2348TQ-10GE,fex,NYC-DC1,Room-A,Row-3,Cab-15,15,1,48,10.1.1.201,75,active,Connected to leaf-101
```

**Required Fields**:
- `device_name` - Hostname/identifier
- `serial_number` - For ACI correlation
- `model` - Device model
- `device_type` - leaf, fex, spine, apic
- `datacenter` - Top-level location
- `room` - Room identifier
- `row` - Row identifier
- `cabinet` - Cabinet/rack identifier
- `rack_unit_start` - Bottom RU position
- `rack_unit_height` - Height in RU

**Optional Fields**:
- `total_ports` - Port count (if not in ACI data)
- `management_ip` - For reference
- `power_watts` - Power consumption
- `status` - active, maintenance, decommissioned
- `notes` - Free-form notes

### Data Collection Script

```bash
#!/bin/bash
# collect_cabinet_data.sh

# 1. Export ACI fabric data
moquery -c eqptFex -o json > fex_devices.json
moquery -c fabricNode -o json > fabric_nodes.json
moquery -c ethpmPhysIf -o json > physical_interfaces.json
moquery -c fvRsPathAtt -o json > path_attachments.json

# 2. Prepare CMDB export
# Export from DCIM system (NetBox, Device42, etc.) with enhanced fields
# Or manually create CSV following template

# 3. Upload to ACI Analysis Tool
# Use enhanced upload interface with both files
```

---

## API Endpoints

### New API Routes

```python
@app.route('/api/port-density')
def get_port_density():
    """Get port density metrics for all devices"""

@app.route('/api/cabinet/<cabinet_id>')
def get_cabinet_details(cabinet_id):
    """Get detailed cabinet information"""

@app.route('/api/consolidation-scenarios')
def get_consolidation_scenarios():
    """Get consolidation opportunities"""

@app.route('/api/capacity/<location>')
def get_capacity_by_location(location):
    """Get available capacity for a location"""

@app.route('/api/cabinet-heatmap')
def get_cabinet_heatmap():
    """Get data for cabinet heatmap visualization"""
```

---

## Success Metrics

### Business Metrics
- **Cost Savings**: Track annual power/cooling savings from consolidation
- **Space Efficiency**: Measure rack unit utilization improvement
- **Time to Deploy**: Reduce new device deployment time by identifying available capacity
- **Consolidation Rate**: Track devices consolidated per quarter

### Technical Metrics
- **Port Utilization**: Overall average >70%
- **Cabinet Utilization**: Target 60-80% (sweet spot)
- **Data Accuracy**: >95% CMDB correlation rate
- **Report Generation**: <5 seconds for full datacenter analysis

---

## Example Use Cases

### Use Case 1: Offboard - Consolidate Underutilized Cabinets

**Scenario**: NYC-DC1 has 12 cabinets in Row-3, several with low port utilization

**Steps**:
1. Navigate to Port Density dashboard
2. Filter to NYC-DC1 / Room-A / Row-3
3. View cabinet heatmap - identify Cab-15 and Cab-17 with <40% utilization
4. Click "Consolidate" → System generates plan to empty Cab-17
5. Review migration plan showing device relocations and cable requirements
6. Export PDF work order for implementation team
7. Track progress and validate post-consolidation utilization

**Result**:
- 1 cabinet freed (4 sq ft floor space)
- 450W power savings ($394/year)
- 18 devices consolidated to 15
- 6 RU freed for future expansion

### Use Case 2: Onboard - Plan New FEX Deployment

**Scenario**: Need to add 5 new FEX devices (240 ports) for application expansion

**Steps**:
1. Navigate to Capacity Planning view
2. Filter to target datacenter (NYC-DC1)
3. View available capacity by room/row/cabinet
4. System recommends Room-B / Row-2 / Cabinets B-08 through B-10
5. Review power and cooling availability
6. Generate deployment plan with exact rack positions
7. Export device placement diagram and port allocation

**Result**:
- Optimal placement identified in 2 minutes
- Power and cooling verified sufficient
- Rack positions allocated (RU 15-16 in each cabinet)
- Deployment plan includes cable requirements

### Use Case 3: EVPN Migration - Physical Wave Planning

**Scenario**: Migrating 500 EPGs from ACI to EVPN, want to minimize cable moves

**Steps**:
1. Run coupling analysis to understand EPG dependencies
2. Navigate to Cabinet Analytics
3. Group EPGs by physical location (cabinet-level)
4. System suggests migration waves based on physical proximity
5. Wave 1: All EPGs in Cab-15 (minimal cable changes)
6. Wave 2: All EPGs in Cab-16 (same row, coordinated)
7. Export physical migration plan with cabinet diagrams

**Result**:
- Migration waves aligned with physical topology
- Cable move requirements minimized by 60%
- Maintenance windows optimized by location
- Rollback strategy considers physical dependencies

---

## Integration Points

### DCIM Systems
- **NetBox**: REST API for cabinet/device location data
- **Device42**: Export enhanced CMDB with location hierarchy
- **Sunbird DCIM**: Power and cooling data integration

### Monitoring Systems
- **Prometheus**: Port utilization metrics over time
- **Grafana**: Historical port density dashboards
- **SNMP**: Real-time interface statistics

### Ticketing Systems
- **ServiceNow**: Generate work orders for consolidation
- **Jira**: Track migration tasks by cabinet/location
- **Email**: Automated consolidation opportunity alerts

---

## Testing Plan

### Unit Tests
- Port density calculation accuracy
- Cabinet aggregation logic
- Consolidation scoring algorithm
- Capacity calculation correctness

### Integration Tests
- CMDB parsing with location hierarchy
- End-to-end cabinet analysis
- Report generation
- API endpoint responses

### Performance Tests
- Large datacenter (500+ cabinets)
- 10,000+ devices
- Real-time heatmap rendering
- Report export speed

### User Acceptance Tests
- Cabinet visualization clarity
- Consolidation recommendations actionability
- Work order completeness
- Mobile responsiveness

---

## Documentation Deliverables

1. **User Guide**: Port Density & Cabinet Analytics
2. **CMDB Format Specification**: Enhanced CSV template
3. **API Documentation**: All new endpoints
4. **Administrator Guide**: Data collection procedures
5. **Best Practices**: Cabinet optimization strategies

---

## Future Enhancements

### Phase 5: Advanced Features (Future)
- **3D Cabinet Visualization**: Interactive 3D rack views
- **Power Trending**: Historical power consumption analysis
- **Cooling Optimization**: Temperature-based placement recommendations
- **Cable Management**: Cable plant tracking and optimization
- **Automated Consolidation**: ML-based consolidation recommendations
- **What-If Scenarios**: Simulate different consolidation approaches
- **Mobile App**: Cabinet inspection and verification
- **AR Integration**: Augmented reality for physical deployment

---

## Conclusion

Port density and cabinet analytics provide critical physical topology insights for data center optimization. By combining logical (ACI) and physical (CMDB) data, the tool enables:

- **Smart consolidation** based on actual port utilization
- **Capacity planning** with available rack space visibility
- **Cost optimization** through power and space savings
- **Migration planning** aligned with physical topology

**Next Steps**:
1. Review and approve enhanced CMDB format
2. Collect sample data from production environment
3. Begin Phase 1 implementation (Data Model & Collection)
4. Iterate based on user feedback

**Timeline**: 8 weeks for full implementation (Phases 1-4)
**Resources Required**: 1 backend developer, 1 frontend developer, 1 QA engineer

