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

    class SecurityWarning(UserWarning):
        """Warning for insecure XML parsing fallback."""
        pass

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

    def _extract_children(children, objects_list):
        for child in children or []:
            if not isinstance(child, dict):
                continue
            for child_type, child_data in child.items():
                child_attrs = child_data.get('attributes', {}) if isinstance(child_data, dict) else {}
                objects_list.append({
                    'type': child_type,
                    'attributes': child_attrs,
                    'dn': child_attrs.get('dn', ''),
                })
                if isinstance(child_data, dict) and child_data.get('children'):
                    _extract_children(child_data.get('children', []), objects_list)

    objects = []
    if isinstance(data, list):
        data = {'imdata': data}
    if 'imdata' in data:
        for item in data['imdata']:
            for obj_type, obj_data in item.items():
                attributes = obj_data.get('attributes', {})
                objects.append({
                    'type': obj_type,
                    'attributes': attributes,
                    'dn': attributes.get('dn', ''),
                })
                if isinstance(obj_data, dict) and obj_data.get('children'):
                    _extract_children(obj_data.get('children', []), objects)

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

def _normalize_cmdb_value(value: Any) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def parse_cmdb_csv(content: str) -> List[Dict[str, Any]]:
    """Parse CMDB CSV file with error handling and normalized field names."""
    try:
        reader = csv.DictReader(StringIO(content))
        if not reader.fieldnames:
            raise ValueError("CMDB CSV missing header row")

        header_aliases = {
            'serialnumber': ['serialnumber', 'serial', 'serialno', 'serialnum', 'serial_number', 'serial number'],
            'rack': ['rack', 'rackid'],
            'building': ['building', 'bldg'],
            'hall': ['hall'],
            'site': ['site', 'dc', 'datacenter'],
            'unitlocation': ['unitlocation', 'unit location', 'position', 'u', 'u_location'],
            'devicetype': ['devicetype', 'device type', 'type'],
            'deviceid': ['deviceid', 'device id', 'assetid', 'asset id'],
            'modelname': ['modelname', 'model', 'hwmodel'],
            'name': ['name', 'hostname', 'device', 'devicename']
        }

        def normalize_header(name: str) -> str:
            return re.sub(r'[\s_\-]+', '', name.strip().lstrip('\ufeff').lower())

        normalized_headers = {normalize_header(h): h for h in reader.fieldnames if h}
        header_map = {}
        for canonical, aliases in header_aliases.items():
            for alias in aliases:
                key = normalize_header(alias)
                if key in normalized_headers:
                    header_map[canonical] = normalized_headers[key]
                    break

        records = []

        for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
            try:
                # Build per-row normalized lookup to tolerate messy headers
                row_lookup = {normalize_header(k): v for k, v in row.items() if k}
                def _get(canonical_key: str) -> str:
                    header_key = header_map.get(canonical_key)
                    if header_key and header_key in row:
                        return row.get(header_key, '')
                    for alias in header_aliases.get(canonical_key, []):
                        alias_key = normalize_header(alias)
                        if alias_key in row_lookup:
                            return row_lookup.get(alias_key, '')
                    return ''

                serial = _normalize_cmdb_value(_get('serialnumber'))
                if serial:
                    serial = serial.upper()
                if serial:
                    model_name = _normalize_cmdb_value(_get('modelname'))
                    name = _normalize_cmdb_value(_get('name'))
                    rack = _normalize_cmdb_value(_get('rack'))
                    building = _normalize_cmdb_value(_get('building'))
                    hall = _normalize_cmdb_value(_get('hall'))
                    site = _normalize_cmdb_value(_get('site'))
                    unit_location = _normalize_cmdb_value(_get('unitlocation'))
                    device_type = _normalize_cmdb_value(_get('devicetype'))
                    device_id = _normalize_cmdb_value(_get('deviceid'))

                    records.append({
                        'SerialNumber': serial,
                        'Name': name,
                        'ModelName': model_name,
                        'DeviceType': device_type,
                        'DeviceID': device_id,
                        'Site': site,
                        'Building': building,
                        'Hall': hall,
                        'Rack': rack,
                        'UnitLocation': unit_location,
                        # Backwards compatible keys
                        'serial_number': serial,
                        'name': name,
                        'model_name': model_name,
                        'model': model_name,
                        'device_type': device_type,
                        'device_id': device_id,
                        'site': site,
                        'building': building,
                        'hall': hall,
                        'rack': rack,
                        'unit_location': unit_location,
                        'unitlocation': unit_location
                    })
            except Exception as e:
                # Log warning but continue processing
                import warnings
                warnings.warn(f"Error parsing CSV row {row_num}: {str(e)}")

        if not records:
            raise ValueError(
                "No valid records found in CMDB CSV. Expected columns: "
                "SerialNumber, Rack, Building, Hall, Site, UnitLocation, Name, ModelName"
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
