"""Data Parsers for ACI, Legacy Network Configs, and CMDB CSV"""
import json
import xml.etree.ElementTree as ET
import csv
import re
from io import StringIO
from typing import Dict, List, Any

def parse_aci(content: str, file_format: str) -> Dict[str, Any]:
    if file_format == 'json':
        return parse_aci_json(content)
    elif file_format == 'xml':
        return parse_aci_xml(content)
    else:
        raise ValueError(f"Unsupported ACI format: {file_format}")

def parse_aci_json(content: str) -> Dict[str, Any]:
    data = json.loads(content)
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
    return {'format': 'aci_json', 'objects': objects, 'count': len(objects)}

def parse_aci_xml(content: str) -> Dict[str, Any]:
    root = ET.fromstring(content)
    objects = []
    for child in root:
        obj_type = child.tag
        attributes = dict(child.attrib)
        objects.append({
            'type': obj_type,
            'attributes': attributes,
            'dn': attributes.get('dn', ''),
        })
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
    reader = csv.DictReader(StringIO(content))
    records = []
    for row in reader:
        serial = row.get('SerialNumber', row.get('Serial', '')).strip()
        if serial:
            records.append({
                'serial_number': serial,
                'rack': row.get('Rack', ''),
                'building': row.get('Building', ''),
                'hall': row.get('Hall', ''),
                'site': row.get('Site', ''),
            })
    return records

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
