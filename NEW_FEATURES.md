# New Features - ACI Migrator v2.1

**Release Date**: 2026-01-28
**Version**: 2.1
**Previous Version**: 2.0

---

## Overview

ACI Migrator v2.1 shifts Visualize to a table-first experience, introduces VLAN coupling as the primary migration difficulty signal, and replaces readiness charts with actionable Migration Units.

---

## Highlights

- VLAN Coupling Explorer (coupling + blast radius)
- Migration Units with Easy/Medium/Hard/Blocked buckets
- Data Explorer component across Visualize tabs
- Utilization shown as Unknown/N/A when signal is missing
- CMDB join on SerialNumber with expanded location fields

---

## Notable Changes

- Visualize dashboards rebuilt around tables (charts are secondary)
- Port utilization uses data-quality checks to avoid false 0% values
- VLAN coupling score now drives migration difficulty and readiness

---

## Upgrade Notes

1. Regenerate documentation screenshots using the v2.1 UI.
2. Ensure CMDB CSV uses SerialNumber and ModelName columns.
3. Re-validate migration planning outputs against coupling-driven readiness.
