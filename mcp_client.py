"""
MCP Client for ACI Migrator
Connects to MCP server and imports ACI data into the application
"""

import requests
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for connecting to MCP server and retrieving ACI data"""

    def __init__(self, mcp_server_url: str, timeout: int = 30):
        """
        Initialize MCP client

        Args:
            mcp_server_url: URL of the MCP server (e.g., http://IP:5000)
            timeout: Request timeout in seconds
        """
        self.server_url = mcp_server_url.rstrip('/')
        self.timeout = timeout
        self.last_health_check = None

    def health_check(self) -> Dict[str, Any]:
        """
        Check MCP server health

        Returns:
            Health status dictionary
        """
        try:
            response = requests.get(
                f"{self.server_url}/health",
                timeout=self.timeout
            )
            response.raise_for_status()

            self.last_health_check = datetime.utcnow()
            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"MCP health check failed: {e}")
            raise Exception(f"Failed to connect to MCP server: {e}")

    def get_fabric_data(self) -> Dict[str, Any]:
        """
        Get raw fabric data from ACI

        Returns:
            Raw fabric data dictionary
        """
        try:
            response = requests.get(
                f"{self.server_url}/api/fabric/data",
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"Retrieved fabric data: {len(data.get('nodes', []))} nodes, "
                       f"{len(data.get('epgs', []))} EPGs")

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get fabric data: {e}")
            raise Exception(f"Failed to retrieve fabric data: {e}")

    def get_migrator_data(self) -> Dict[str, Any]:
        """
        Get data transformed for ACI Migrator

        Returns:
            Migrator-formatted data dictionary
        """
        try:
            response = requests.get(
                f"{self.server_url}/api/migrator/data",
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            logger.info(f"Retrieved migrator data: {len(data.get('devices', []))} devices, "
                       f"{len(data.get('epg_mappings', []))} EPG mappings")

            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get migrator data: {e}")
            raise Exception(f"Failed to retrieve migrator data: {e}")

    def refresh_fabric_data(self) -> Dict[str, Any]:
        """
        Force refresh of fabric data on MCP server

        Returns:
            Refresh status dictionary
        """
        try:
            response = requests.get(
                f"{self.server_url}/api/fabric/refresh",
                timeout=self.timeout * 2  # Refresh takes longer
            )
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to refresh fabric data: {e}")
            raise Exception(f"Failed to refresh fabric data: {e}")

    def analyze_fabric(self) -> Dict[str, Any]:
        """
        Run analysis on fabric

        Returns:
            Analysis results dictionary
        """
        try:
            response = requests.post(
                f"{self.server_url}/api/migrator/analyze",
                timeout=self.timeout
            )
            response.raise_for_status()

            return response.json()

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to analyze fabric: {e}")
            raise Exception(f"Failed to analyze fabric: {e}")

    def import_to_fabric(self, fabric_name: str, db_session: Any) -> Dict[str, Any]:
        """
        Import MCP data directly to ACI Migrator database

        Args:
            fabric_name: Name for the imported fabric
            db_session: SQLAlchemy database session

        Returns:
            Import statistics
        """
        from models import Fabric, Device, EPG  # Import locally to avoid circular deps

        try:
            # Get data from MCP server
            logger.info(f"Fetching data from MCP server for fabric '{fabric_name}'...")
            migrator_data = self.get_migrator_data()

            # Create fabric
            fabric = Fabric(
                name=fabric_name,
                description=f"Imported from MCP server at {datetime.utcnow().isoformat()}",
                created_at=datetime.utcnow()
            )
            db_session.add(fabric)
            db_session.flush()  # Get fabric ID

            stats = {
                'fabric_name': fabric_name,
                'devices_imported': 0,
                'epgs_imported': 0,
                'paths_imported': 0,
                'errors': []
            }

            # Import devices
            logger.info("Importing devices...")
            device_map = {}  # Map device_id to Device object

            for device_data in migrator_data.get('devices', []):
                try:
                    device = Device(
                        fabric_id=fabric.id,
                        device_id=device_data['device_id'],
                        device_name=device_data['device_name'],
                        device_type=device_data['device_type'],
                        model=device_data.get('model', 'Unknown'),
                        parent_leaf=device_data.get('parent_leaf')
                    )
                    db_session.add(device)
                    device_map[device_data['device_id']] = device
                    stats['devices_imported'] += 1

                except Exception as e:
                    error_msg = f"Failed to import device {device_data.get('device_id')}: {e}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)

            db_session.flush()  # Commit devices to get IDs

            # Import EPG mappings
            logger.info("Importing EPG mappings...")

            for epg_data in migrator_data.get('epg_mappings', []):
                try:
                    # Create EPG
                    epg = EPG(
                        fabric_id=fabric.id,
                        tenant=epg_data['tenant'],
                        application_profile=epg_data.get('application_profile', ''),
                        epg=epg_data['epg'],
                        vlans=','.join(map(str, epg_data.get('vlans', []))),
                        total_ports=epg_data.get('total_ports', 0)
                    )
                    db_session.add(epg)
                    stats['epgs_imported'] += 1

                    # Link EPG to devices
                    for device_id in epg_data.get('devices', []):
                        if device_id in device_map:
                            epg.devices.append(device_map[device_id])

                    # Count paths
                    stats['paths_imported'] += epg_data.get('total_paths', 0)

                except Exception as e:
                    error_msg = f"Failed to import EPG {epg_data.get('epg')}: {e}"
                    logger.error(error_msg)
                    stats['errors'].append(error_msg)

            # Commit all changes
            db_session.commit()

            logger.info(f"Import complete: {stats['devices_imported']} devices, "
                       f"{stats['epgs_imported']} EPGs imported")

            return stats

        except Exception as e:
            db_session.rollback()
            logger.error(f"Import failed: {e}")
            raise Exception(f"Failed to import fabric: {e}")


class MCPDataValidator:
    """Validator for MCP data format"""

    @staticmethod
    def validate_migrator_data(data: Dict[str, Any]) -> List[str]:
        """
        Validate migrator data format

        Args:
            data: Migrator data dictionary

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required top-level keys
        required_keys = ['fabric_name', 'devices', 'epg_mappings', 'statistics']
        for key in required_keys:
            if key not in data:
                errors.append(f"Missing required key: {key}")

        # Validate devices
        if 'devices' in data:
            if not isinstance(data['devices'], list):
                errors.append("'devices' must be a list")
            else:
                for i, device in enumerate(data['devices']):
                    required_device_keys = ['device_id', 'device_name', 'device_type']
                    for key in required_device_keys:
                        if key not in device:
                            errors.append(f"Device {i} missing required key: {key}")

                    # Validate device_type
                    if 'device_type' in device and device['device_type'] not in ['leaf', 'spine', 'fex']:
                        errors.append(f"Device {i} has invalid device_type: {device['device_type']}")

        # Validate EPG mappings
        if 'epg_mappings' in data:
            if not isinstance(data['epg_mappings'], list):
                errors.append("'epg_mappings' must be a list")
            else:
                for i, epg in enumerate(data['epg_mappings']):
                    required_epg_keys = ['tenant', 'epg', 'vlans', 'devices']
                    for key in required_epg_keys:
                        if key not in epg:
                            errors.append(f"EPG {i} missing required key: {key}")

                    # Validate VLANs
                    if 'vlans' in epg and not isinstance(epg['vlans'], list):
                        errors.append(f"EPG {i} 'vlans' must be a list")

                    # Validate devices
                    if 'devices' in epg and not isinstance(epg['devices'], list):
                        errors.append(f"EPG {i} 'devices' must be a list")

        return errors


# Helper functions for Flask routes
def test_mcp_connection(mcp_url: str) -> Dict[str, Any]:
    """
    Test MCP server connection

    Args:
        mcp_url: MCP server URL

    Returns:
        Connection test results
    """
    try:
        client = MCPClient(mcp_url)
        health = client.health_check()

        return {
            'success': True,
            'status': health.get('status'),
            'service': health.get('service'),
            'version': health.get('version'),
            'last_refresh': health.get('last_refresh')
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def fetch_and_validate_data(mcp_url: str) -> Dict[str, Any]:
    """
    Fetch and validate MCP data

    Args:
        mcp_url: MCP server URL

    Returns:
        Validation results
    """
    try:
        client = MCPClient(mcp_url)
        data = client.get_migrator_data()

        # Validate
        errors = MCPDataValidator.validate_migrator_data(data)

        return {
            'success': len(errors) == 0,
            'data': data if len(errors) == 0 else None,
            'errors': errors,
            'statistics': data.get('statistics', {})
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'errors': [str(e)]
        }
