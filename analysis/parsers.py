"""Data Parsers for ACI, Legacy Network Configs, and CMDB CSV"""
import json
import csv
import re
from io import StringIO
from typing import Dict, List, Any

# Use defusedxml to prevent XXE attacks
try:
    import defusedxml.ElementTree as ET
except ImportError:
    # Fallback to standard library with warning
    import xml.etree.ElementTree as ET
    import warnings
    warnings.warn(
        "defusedxml not installed. Using standard XML parser which may be vulnerable to XXE attacks. "
        "Install defusedxml: pip install defusedxml",
        SecurityWarning
    )

def parse_aci(content: str, file_format: str) -> Dict[str, Any]:
    if file_format == 'json':
        return parse_aci_json(content)
    elif file_format == 'xml':
        return parse_aci_xml(content)
    else:
        raise ValueError(f"Unsupported ACI format: {file_format}")

def parse_aci_json(content: str) -> Dict[str, Any]:
    """Parse ACI JSON export with error handling."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Invalid JSON format at line {e.lineno}, column {e.colno}: {e.msg}"
        )

    objects = []
    if 'imdata' in data:
        for item in data['imdata']:
            for obj_type, obj_data in item.items():
                attributes = obj_data.get('attributes', {})
                objects.append({
                    'type': obj_type,
                    'attributes': attributes,
                    'dn': attributes.get('dn', ''),
                })

    if not objects:
        raise ValueError("No valid ACI objects found in JSON file. Expected 'imdata' array.")

    return {'format': 'aci_json', 'objects': objects, 'count': len(objects)}

def parse_aci_xml(content: str) -> Dict[str, Any]:
    """Parse ACI XML export with security and error handling."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        raise ValueError(f"Invalid XML format: {str(e)}")
    except Exception as e:
        raise ValueError(f"XML parsing error: {str(e)}")

    objects = []
    for child in root:
        obj_type = child.tag
        attributes = dict(child.attrib)
        objects.append({
            'type': obj_type,
            'attributes': attributes,
            'dn': attributes.get('dn', ''),
        })

    if not objects:
        raise ValueError("No valid ACI objects found in XML file.")

    return {'format': 'aci_xml', 'objects': objects, 'count': len(objects)}

def parse_legacy_config(content: str) -> Dict[str, Any]:
    lines = content.splitlines()
    platform = 'nxos' if 'nxos' in content.lower() else 'ios'
    return {
        'platform': platform,
        'interfaces': [],
        'vlans': [],
        'port_channels': [],
        'vpcs': [],
    }

def parse_cmdb_csv(content: str) -> List[Dict[str, Any]]:
    """Parse CMDB CSV file with error handling."""
    try:
        reader = csv.DictReader(StringIO(content))
        records = []

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
            try:
                serial = row.get('SerialNumber', row.get('Serial', '')).strip()
                if serial:
                    records.append({
                        'serial_number': serial,
                        'rack': row.get('Rack', ''),
                        'building': row.get('Building', ''),
                        'hall': row.get('Hall', ''),
                        'site': row.get('Site', ''),
                    })
            except Exception as e:
                # Log warning but continue processing
                import warnings
                warnings.warn(f"Error parsing CSV row {row_num}: {str(e)}")

        if not records:
            raise ValueError(
                "No valid records found in CMDB CSV. Expected columns: "
                "SerialNumber (or Serial), Rack, Building, Hall, Site"
            )

        return records

    except csv.Error as e:
        raise ValueError(f"Invalid CSV format: {str(e)}")

def extract_vlan_list(vlan_string: str) -> List[int]:
    vlans = []
    match = re.search(r'vlan\s+([\d,\-]+)', vlan_string)
    if match:
        for part in match.group(1).split(','):
            if '-' in part:
                start, end = part.split('-')
                vlans.extend(range(int(start), int(end) + 1))
            else:
                try:
                    vlans.append(int(part))
                except ValueError:
                    pass
    return vlans
