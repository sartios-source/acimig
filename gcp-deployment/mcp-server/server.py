#!/usr/bin/env python3
"""
MCP Server for ACI Migrator
Queries ACI Simulator and provides data via MCP protocol
"""

import json
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
import aiohttp
from aiohttp import web
import ssl

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ACIClient:
    """Client for querying ACI APIC"""

    def __init__(self, apic_url: str, username: str, password: str):
        self.apic_url = apic_url.rstrip('/')
        self.username = username
        self.password = password
        self.token = None
        self.session = None

    async def __aenter__(self):
        """Async context manager entry"""
        # Create SSL context that doesn't verify certificates (for mock APIC)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(connector=connector)
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()

    async def login(self):
        """Authenticate to APIC"""
        login_data = {
            "aaaUser": {
                "attributes": {
                    "name": self.username,
                    "pwd": self.password
                }
            }
        }

        try:
            async with self.session.post(
                f"{self.apic_url}/api/aaaLogin.json",
                json=login_data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    raise Exception(f"Login failed: {response.status}")

                data = await response.json()
                self.token = data['imdata'][0]['aaaLogin']['attributes']['token']
                logger.info(f"Successfully authenticated to APIC as {self.username}")

        except Exception as e:
            logger.error(f"Failed to authenticate to APIC: {e}")
            raise

    async def query_class(self, class_name: str, params: Optional[Dict] = None) -> List[Dict]:
        """Query ACI class"""
        if not self.token:
            await self.login()

        url = f"{self.apic_url}/api/class/{class_name}.json"

        headers = {
            'Cookie': f'APIC-cookie={self.token}'
        }

        try:
            async with self.session.get(
                url,
                headers=headers,
                params=params or {},
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    logger.error(f"Query failed for {class_name}: {response.status}")
                    return []

                data = await response.json()
                objects = []

                for item in data.get('imdata', []):
                    if class_name in item:
                        objects.append(item[class_name]['attributes'])

                logger.info(f"Retrieved {len(objects)} {class_name} objects")
                return objects

        except Exception as e:
            logger.error(f"Failed to query {class_name}: {e}")
            return []

    async def get_all_fabric_data(self) -> Dict[str, Any]:
        """Retrieve all fabric data"""
        logger.info("Starting full fabric data retrieval...")

        data = {
            "timestamp": datetime.utcnow().isoformat(),
            "fabric": {},
            "nodes": [],
            "tenants": [],
            "vrfs": [],
            "bridge_domains": [],
            "application_profiles": [],
            "epgs": [],
            "epg_paths": [],
            "contracts": [],
            "filters": [],
            "l3outs": []
        }

        # Query system info
        system_info = await self.query_class('topSystem')
        if system_info:
            data['fabric'] = {
                'name': 'ACI Fabric',
                'version': system_info[0].get('version', 'unknown'),
                'node_count': len(system_info)
            }

        # Query all classes in parallel
        results = await asyncio.gather(
            self.query_class('fabricNode'),
            self.query_class('fvTenant'),
            self.query_class('fvCtx'),
            self.query_class('fvBD'),
            self.query_class('fvAp'),
            self.query_class('fvAEPg'),
            self.query_class('fvRsPathAtt'),
            self.query_class('vzBrCP'),
            self.query_class('vzFilter'),
            self.query_class('l3extOut'),
            return_exceptions=True
        )

        # Assign results
        data['nodes'] = results[0] if not isinstance(results[0], Exception) else []
        data['tenants'] = results[1] if not isinstance(results[1], Exception) else []
        data['vrfs'] = results[2] if not isinstance(results[2], Exception) else []
        data['bridge_domains'] = results[3] if not isinstance(results[3], Exception) else []
        data['application_profiles'] = results[4] if not isinstance(results[4], Exception) else []
        data['epgs'] = results[5] if not isinstance(results[5], Exception) else []
        data['epg_paths'] = results[6] if not isinstance(results[6], Exception) else []
        data['contracts'] = results[7] if not isinstance(results[7], Exception) else []
        data['filters'] = results[8] if not isinstance(results[8], Exception) else []
        data['l3outs'] = results[9] if not isinstance(results[9], Exception) else []

        logger.info("Completed fabric data retrieval")
        logger.info(f"Summary: {len(data['nodes'])} nodes, {len(data['tenants'])} tenants, "
                   f"{len(data['epgs'])} EPGs, {len(data['epg_paths'])} paths")

        return data


class DataTransformer:
    """Transform ACI data for ACI Migrator"""

    @staticmethod
    def extract_node_id(dn: str) -> Optional[str]:
        """Extract node ID from DN"""
        try:
            if '/node-' in dn:
                return dn.split('/node-')[1].split('/')[0]
        except:
            pass
        return None

    @staticmethod
    def extract_fex_id(dn: str) -> Optional[str]:
        """Extract FEX ID from path DN"""
        try:
            if '/extpaths-' in dn:
                return dn.split('/extpaths-')[1].split('/')[0]
        except:
            pass
        return None

    @staticmethod
    def parse_path_dn(path_dn: str) -> Dict[str, Any]:
        """Parse path DN to extract components"""
        result = {
            'leaf_id': None,
            'fex_id': None,
            'interface': None,
            'path_type': 'unknown'
        }

        try:
            # Extract leaf ID
            if '/paths-' in path_dn:
                result['leaf_id'] = path_dn.split('/paths-')[1].split('/')[0]

            # Check for FEX
            if '/extpaths-' in path_dn:
                result['fex_id'] = path_dn.split('/extpaths-')[1].split('/')[0]
                result['path_type'] = 'fex'
            else:
                result['path_type'] = 'leaf'

            # Extract interface
            if '/pathep-[' in path_dn:
                result['interface'] = path_dn.split('/pathep-[')[1].rstrip(']')

        except Exception as e:
            logger.warning(f"Failed to parse path DN {path_dn}: {e}")

        return result

    @staticmethod
    def transform_for_migrator(aci_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform ACI data to ACI Migrator format"""
        logger.info("Transforming data for ACI Migrator...")

        migrator_data = {
            "fabric_name": aci_data['fabric'].get('name', 'Unknown'),
            "import_timestamp": datetime.utcnow().isoformat(),
            "statistics": {
                "total_nodes": len(aci_data['nodes']),
                "total_tenants": len(aci_data['tenants']),
                "total_epgs": len(aci_data['epgs']),
                "total_paths": len(aci_data['epg_paths'])
            },
            "devices": [],
            "epg_mappings": []
        }

        # Build device list
        devices = {}
        fex_devices = {}

        # Process nodes
        for node in aci_data['nodes']:
            node_id = node.get('id')
            role = node.get('role', '')

            if role in ['leaf', 'spine']:
                devices[node_id] = {
                    'device_id': node_id,
                    'device_name': node.get('name', f"node-{node_id}"),
                    'device_type': role,
                    'model': node.get('model', 'unknown'),
                    'serial': node.get('serial', 'unknown'),
                    'ports': []
                }

        # Process EPG paths to build port mappings
        epg_path_map = {}

        for path in aci_data['epg_paths']:
            path_dn = path.get('tDn', '')
            encap = path.get('encap', '')
            vlan = encap.replace('vlan-', '') if encap.startswith('vlan-') else None

            # Parse path DN
            path_info = DataTransformer.parse_path_dn(path_dn)

            leaf_id = path_info['leaf_id']
            fex_id = path_info['fex_id']
            interface = path_info['interface']

            # Determine device ID (FEX takes precedence)
            if fex_id:
                device_id = fex_id
                device_type = 'fex'
                parent_leaf = leaf_id

                # Create FEX device if not exists
                if fex_id not in fex_devices:
                    fex_devices[fex_id] = {
                        'device_id': fex_id,
                        'device_name': f"FEX-{fex_id}",
                        'device_type': 'fex',
                        'model': 'N2K-C2248TP',
                        'parent_leaf': parent_leaf,
                        'ports': []
                    }
            else:
                device_id = leaf_id
                device_type = 'leaf'

            # Extract EPG info from path DN
            epg_dn = path.get('dn', '').split('/rspathAtt-')[0]

            if epg_dn not in epg_path_map:
                epg_path_map[epg_dn] = []

            epg_path_map[epg_dn].append({
                'device_id': device_id,
                'device_type': device_type,
                'interface': interface,
                'vlan': vlan,
                'leaf_id': leaf_id,
                'fex_id': fex_id
            })

        # Build EPG mappings
        for epg in aci_data['epgs']:
            epg_dn = epg.get('dn', '')
            epg_name = epg.get('name', '')

            # Extract tenant and AP from DN
            dn_parts = epg_dn.split('/')
            tenant = None
            ap = None

            for part in dn_parts:
                if part.startswith('tn-'):
                    tenant = part[3:]
                elif part.startswith('ap-'):
                    ap = part[3:]

            # Get paths for this EPG
            paths = epg_path_map.get(epg_dn, [])

            # Get unique VLANs
            vlans = sorted(set(p['vlan'] for p in paths if p['vlan']))

            # Get unique devices
            devices_used = set(p['device_id'] for p in paths)

            # Calculate utilization metrics
            total_ports = len(paths)

            migrator_data['epg_mappings'].append({
                'tenant': tenant,
                'application_profile': ap,
                'epg': epg_name,
                'vlans': vlans,
                'devices': list(devices_used),
                'total_ports': total_ports,
                'paths': paths
            })

        # Add all devices to migrator data
        migrator_data['devices'] = list(devices.values()) + list(fex_devices.values())

        logger.info(f"Transformation complete: {len(migrator_data['devices'])} devices, "
                   f"{len(migrator_data['epg_mappings'])} EPG mappings")

        return migrator_data


class MCPServer:
    """MCP Server for ACI Migrator"""

    def __init__(self, apic_url: str, username: str, password: str, port: int = 5000):
        self.apic_url = apic_url
        self.username = username
        self.password = password
        self.port = port
        self.app = web.Application()
        self.setup_routes()
        self.cached_data = None
        self.last_refresh = None

    def setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_get('/health', self.health)
        self.app.router.add_get('/api/fabric/data', self.get_fabric_data)
        self.app.router.add_get('/api/fabric/refresh', self.refresh_fabric_data)
        self.app.router.add_get('/api/migrator/data', self.get_migrator_data)
        self.app.router.add_post('/api/migrator/analyze', self.analyze_fabric)

    async def health(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'service': 'ACI MCP Server',
            'version': '1.0.0',
            'apic_url': self.apic_url,
            'last_refresh': self.last_refresh.isoformat() if self.last_refresh else None
        })

    async def get_fabric_data(self, request):
        """Get raw fabric data from ACI"""
        try:
            async with ACIClient(self.apic_url, self.username, self.password) as client:
                data = await client.get_all_fabric_data()
                self.cached_data = data
                self.last_refresh = datetime.utcnow()
                return web.json_response(data)
        except Exception as e:
            logger.error(f"Failed to get fabric data: {e}")
            return web.json_response({
                'error': str(e)
            }, status=500)

    async def refresh_fabric_data(self, request):
        """Force refresh of fabric data"""
        try:
            async with ACIClient(self.apic_url, self.username, self.password) as client:
                data = await client.get_all_fabric_data()
                self.cached_data = data
                self.last_refresh = datetime.utcnow()
                return web.json_response({
                    'status': 'refreshed',
                    'timestamp': self.last_refresh.isoformat(),
                    'statistics': data.get('statistics', {})
                })
        except Exception as e:
            logger.error(f"Failed to refresh fabric data: {e}")
            return web.json_response({
                'error': str(e)
            }, status=500)

    async def get_migrator_data(self, request):
        """Get data transformed for ACI Migrator"""
        try:
            # Use cached data if available and fresh (< 5 minutes)
            if self.cached_data and self.last_refresh:
                age = (datetime.utcnow() - self.last_refresh).total_seconds()
                if age < 300:  # 5 minutes
                    logger.info("Using cached fabric data")
                    data = self.cached_data
                else:
                    async with ACIClient(self.apic_url, self.username, self.password) as client:
                        data = await client.get_all_fabric_data()
                        self.cached_data = data
                        self.last_refresh = datetime.utcnow()
            else:
                async with ACIClient(self.apic_url, self.username, self.password) as client:
                    data = await client.get_all_fabric_data()
                    self.cached_data = data
                    self.last_refresh = datetime.utcnow()

            # Transform data
            migrator_data = DataTransformer.transform_for_migrator(data)
            return web.json_response(migrator_data)

        except Exception as e:
            logger.error(f"Failed to get migrator data: {e}")
            return web.json_response({
                'error': str(e)
            }, status=500)

    async def analyze_fabric(self, request):
        """Analyze fabric and return recommendations"""
        try:
            # Get migrator data
            async with ACIClient(self.apic_url, self.username, self.password) as client:
                data = await client.get_all_fabric_data()

            migrator_data = DataTransformer.transform_for_migrator(data)

            # Simple analysis
            analysis = {
                'timestamp': datetime.utcnow().isoformat(),
                'summary': {
                    'total_epgs': len(migrator_data['epg_mappings']),
                    'total_devices': len(migrator_data['devices']),
                    'fex_count': sum(1 for d in migrator_data['devices'] if d['device_type'] == 'fex')
                },
                'recommendations': []
            }

            # Check for EPGs spanning multiple devices (coupling)
            for epg_mapping in migrator_data['epg_mappings']:
                if len(epg_mapping['devices']) > 1:
                    analysis['recommendations'].append({
                        'type': 'high_coupling',
                        'severity': 'medium',
                        'epg': f"{epg_mapping['tenant']}/{epg_mapping['application_profile']}/{epg_mapping['epg']}",
                        'devices': epg_mapping['devices'],
                        'message': f"EPG spans {len(epg_mapping['devices'])} devices"
                    })

            return web.json_response(analysis)

        except Exception as e:
            logger.error(f"Failed to analyze fabric: {e}")
            return web.json_response({
                'error': str(e)
            }, status=500)

    def run(self):
        """Run the MCP server"""
        logger.info(f"Starting MCP Server on port {self.port}")
        logger.info(f"APIC URL: {self.apic_url}")
        web.run_app(self.app, host='0.0.0.0', port=self.port)


if __name__ == '__main__':
    import os

    # Get configuration from environment
    apic_url = os.getenv('APIC_URL', 'https://localhost')
    username = os.getenv('APIC_USERNAME', 'admin')
    password = os.getenv('APIC_PASSWORD', 'C1sco12345')
    port = int(os.getenv('MCP_PORT', '5000'))

    # Start server
    server = MCPServer(apic_url, username, password, port)
    server.run()
