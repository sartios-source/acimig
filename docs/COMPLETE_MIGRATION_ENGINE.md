# Complete Migration Engine

This document describes the ACI migration analysis engine used by ACI Migrator v2.0.

## Goals

- Provide a unified readiness assessment for migrating off ACI
- Surface dependencies across VPC, contracts, L3Out, VLAN pools, and physical connectivity
- Produce actionable recommendations with effort estimates

## Core Modules

1. VPC/Port-Channel Analysis (`analysis/vpc_analysis.py`)
2. Contract-to-ACL Translation (`analysis/contract_translation.py`)
3. L3Out Connectivity Analysis (`analysis/l3out_analysis.py`)
4. VLAN Pool Analysis (`analysis/vlan_pool_analysis.py`)
5. Physical Connectivity Analysis (`analysis/physical_connectivity.py`)

## Outputs

- Migration readiness score (0-100)
- Wave planning and sequencing suggestions
- Risk inventory and dependency notes
- Report exports (PDF, Excel, HTML, CSV, JSON)

## Data Inputs

- ACI JSON/XML exports
- CMDB CSV datasets (optional)
- Legacy configs (optional)

## API Entry Points

```
GET /api/analyze/vpc/<fabric_id>
GET /api/analyze/contracts/<fabric_id>
GET /api/analyze/l3out/<fabric_id>
GET /api/analyze/vlans/<fabric_id>
GET /api/analyze/physical/<fabric_id>
GET /api/migration-assessment/<fabric_id>
```
