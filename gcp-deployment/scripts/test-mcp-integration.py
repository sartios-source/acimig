#!/usr/bin/env python3
"""
Test MCP Integration with ACI Migrator
Validates MCP server functionality and data retrieval
"""

import sys
import json
import requests
import argparse
from typing import Dict, Any
from datetime import datetime

# Disable SSL warnings for self-signed certificates
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class Colors:
    """ANSI color codes"""
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    NC = '\033[0m'  # No Color


def log_info(msg):
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")


def log_success(msg):
    print(f"{Colors.GREEN}[SUCCESS]{Colors.NC} {msg}")


def log_warning(msg):
    print(f"{Colors.YELLOW}[WARNING]{Colors.NC} {msg}")


def log_error(msg):
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}")


class MCPIntegrationTester:
    """Test MCP integration"""

    def __init__(self, mcp_url: str, apic_url: str, skip_apic: bool = False):
        self.mcp_url = mcp_url.rstrip('/')
        self.apic_url = apic_url.rstrip('/')
        self.skip_apic = skip_apic
        self.test_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'tests': [],
            'passed': 0,
            'failed': 0
        }

    def add_result(self, test_name: str, passed: bool, message: str, details: Any = None):
        """Add test result"""
        self.test_results['tests'].append({
            'name': test_name,
            'passed': passed,
            'message': message,
            'details': details
        })
        if passed:
            self.test_results['passed'] += 1
        else:
            self.test_results['failed'] += 1

    def test_apic_health(self) -> bool:
        """Test APIC health endpoint"""
        log_info("Testing APIC health endpoint...")
        try:
            response = requests.get(
                f"{self.apic_url}/health",
                verify=False,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    log_success("APIC health check passed")
                    self.add_result(
                        'APIC Health Check',
                        True,
                        'APIC is healthy',
                        data
                    )
                    return True

            log_error(f"APIC health check failed: {response.status_code}")
            self.add_result(
                'APIC Health Check',
                False,
                f'Health check returned {response.status_code}'
            )
            return False

        except Exception as e:
            log_error(f"APIC health check failed: {e}")
            self.add_result(
                'APIC Health Check',
                False,
                str(e)
            )
            return False

    def test_apic_login(self, username: str = 'admin', password: str = 'C1sco12345') -> bool:
        """Test APIC login"""
        log_info("Testing APIC login...")
        try:
            login_data = {
                "aaaUser": {
                    "attributes": {
                        "name": username,
                        "pwd": password
                    }
                }
            }

            response = requests.post(
                f"{self.apic_url}/api/aaaLogin.json",
                json=login_data,
                verify=False,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if 'imdata' in data and len(data['imdata']) > 0:
                    token = data['imdata'][0]['aaaLogin']['attributes'].get('token')
                    if token:
                        log_success("APIC login successful")
                        self.add_result(
                            'APIC Login',
                            True,
                            'Successfully authenticated',
                            {'token_length': len(token)}
                        )
                        return True

            log_error(f"APIC login failed: {response.status_code}")
            self.add_result(
                'APIC Login',
                False,
                f'Login returned {response.status_code}'
            )
            return False

        except Exception as e:
            log_error(f"APIC login failed: {e}")
            self.add_result(
                'APIC Login',
                False,
                str(e)
            )
            return False

    def test_mcp_health(self) -> bool:
        """Test MCP server health"""
        log_info("Testing MCP server health...")
        try:
            response = requests.get(
                f"{self.mcp_url}/health",
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'healthy':
                    log_success("MCP server health check passed")
                    self.add_result(
                        'MCP Health Check',
                        True,
                        'MCP server is healthy',
                        data
                    )
                    return True

            log_error(f"MCP health check failed: {response.status_code}")
            self.add_result(
                'MCP Health Check',
                False,
                f'Health check returned {response.status_code}'
            )
            return False

        except Exception as e:
            log_error(f"MCP health check failed: {e}")
            self.add_result(
                'MCP Health Check',
                False,
                str(e)
            )
            return False

    def test_mcp_fabric_data(self) -> bool:
        """Test MCP fabric data retrieval"""
        log_info("Testing MCP fabric data retrieval...")
        try:
            response = requests.get(
                f"{self.mcp_url}/api/fabric/data",
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                # Validate data structure
                required_keys = ['nodes', 'tenants', 'epgs', 'epg_paths']
                missing_keys = [k for k in required_keys if k not in data]

                if missing_keys:
                    log_error(f"Missing keys in fabric data: {missing_keys}")
                    self.add_result(
                        'MCP Fabric Data',
                        False,
                        f'Missing keys: {missing_keys}'
                    )
                    return False

                # Log statistics
                stats = {
                    'nodes': len(data.get('nodes', [])),
                    'tenants': len(data.get('tenants', [])),
                    'epgs': len(data.get('epgs', [])),
                    'epg_paths': len(data.get('epg_paths', []))
                }

                log_success(f"Fabric data retrieved: {stats}")
                self.add_result(
                    'MCP Fabric Data',
                    True,
                    'Successfully retrieved fabric data',
                    stats
                )
                return True

            log_error(f"Fabric data retrieval failed: {response.status_code}")
            self.add_result(
                'MCP Fabric Data',
                False,
                f'Request returned {response.status_code}'
            )
            return False

        except Exception as e:
            log_error(f"Fabric data retrieval failed: {e}")
            self.add_result(
                'MCP Fabric Data',
                False,
                str(e)
            )
            return False

    def test_mcp_migrator_data(self) -> bool:
        """Test MCP migrator data transformation"""
        log_info("Testing MCP migrator data transformation...")
        try:
            response = requests.get(
                f"{self.mcp_url}/api/migrator/data",
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                # Validate data structure
                required_keys = ['fabric_name', 'devices', 'epg_mappings', 'statistics']
                missing_keys = [k for k in required_keys if k not in data]

                if missing_keys:
                    log_error(f"Missing keys in migrator data: {missing_keys}")
                    self.add_result(
                        'MCP Migrator Data',
                        False,
                        f'Missing keys: {missing_keys}'
                    )
                    return False

                # Validate devices have required fields
                if data['devices']:
                    device = data['devices'][0]
                    required_device_keys = ['device_id', 'device_name', 'device_type']
                    missing_device_keys = [k for k in required_device_keys if k not in device]

                    if missing_device_keys:
                        log_error(f"Device missing keys: {missing_device_keys}")
                        self.add_result(
                            'MCP Migrator Data',
                            False,
                            f'Device missing keys: {missing_device_keys}'
                        )
                        return False

                # Validate EPG mappings
                if data['epg_mappings']:
                    epg = data['epg_mappings'][0]
                    required_epg_keys = ['tenant', 'epg', 'vlans', 'devices']
                    missing_epg_keys = [k for k in required_epg_keys if k not in epg]

                    if missing_epg_keys:
                        log_error(f"EPG mapping missing keys: {missing_epg_keys}")
                        self.add_result(
                            'MCP Migrator Data',
                            False,
                            f'EPG mapping missing keys: {missing_epg_keys}'
                        )
                        return False

                stats = data.get('statistics', {})
                log_success(f"Migrator data validated: {stats}")
                self.add_result(
                    'MCP Migrator Data',
                    True,
                    'Successfully validated migrator data format',
                    stats
                )
                return True

            log_error(f"Migrator data retrieval failed: {response.status_code}")
            self.add_result(
                'MCP Migrator Data',
                False,
                f'Request returned {response.status_code}'
            )
            return False

        except Exception as e:
            log_error(f"Migrator data retrieval failed: {e}")
            self.add_result(
                'MCP Migrator Data',
                False,
                str(e)
            )
            return False

    def test_mcp_analysis(self) -> bool:
        """Test MCP analysis endpoint"""
        log_info("Testing MCP analysis endpoint...")
        try:
            response = requests.post(
                f"{self.mcp_url}/api/migrator/analyze",
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()

                if 'summary' in data and 'recommendations' in data:
                    summary = data['summary']
                    rec_count = len(data['recommendations'])

                    log_success(f"Analysis complete: {summary}, {rec_count} recommendations")
                    self.add_result(
                        'MCP Analysis',
                        True,
                        f'Analysis generated {rec_count} recommendations',
                        summary
                    )
                    return True

            log_error(f"Analysis failed: {response.status_code}")
            self.add_result(
                'MCP Analysis',
                False,
                f'Request returned {response.status_code}'
            )
            return False

        except Exception as e:
            log_error(f"Analysis failed: {e}")
            self.add_result(
                'MCP Analysis',
                False,
                str(e)
            )
            return False

    def run_all_tests(self):
        """Run all tests"""
        print(f"\n{Colors.BLUE}========================================")
        print("MCP Integration Test Suite")
        print(f"========================================{Colors.NC}\n")

        # Run tests
        if not self.skip_apic:
            self.test_apic_health()
            self.test_apic_login()
        self.test_mcp_health()
        self.test_mcp_fabric_data()
        self.test_mcp_migrator_data()
        self.test_mcp_analysis()

        # Display results
        self.display_results()

    def display_results(self):
        """Display test results"""
        print(f"\n{Colors.BLUE}========================================")
        print("Test Results")
        print(f"========================================{Colors.NC}\n")

        for test in self.test_results['tests']:
            status = f"{Colors.GREEN}PASS{Colors.NC}" if test['passed'] else f"{Colors.RED}FAIL{Colors.NC}"
            print(f"[{status}] {test['name']}: {test['message']}")

        print(f"\n{Colors.BLUE}Summary:{Colors.NC}")
        print(f"  Passed: {Colors.GREEN}{self.test_results['passed']}{Colors.NC}")
        print(f"  Failed: {Colors.RED}{self.test_results['failed']}{Colors.NC}")
        print(f"  Total:  {self.test_results['passed'] + self.test_results['failed']}")

        # Overall status
        if self.test_results['failed'] == 0:
            print(f"\n{Colors.GREEN}All tests passed!{Colors.NC}\n")
            return 0
        else:
            print(f"\n{Colors.RED}Some tests failed!{Colors.NC}\n")
            return 1

    def save_results(self, filename: str):
        """Save results to JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.test_results, f, indent=2)
        log_info(f"Results saved to {filename}")


def main():
    parser = argparse.ArgumentParser(description='Test MCP Integration')
    parser.add_argument('--mcp-url', required=True, help='MCP server URL')
    parser.add_argument('--apic-url', default='http://127.0.0.1', help='APIC URL')
    parser.add_argument('--skip-apic', action='store_true', help='Skip APIC connectivity checks')
    parser.add_argument('--output', default='test-results.json', help='Output file for results')

    args = parser.parse_args()

    tester = MCPIntegrationTester(args.mcp_url, args.apic_url, skip_apic=args.skip_apic)
    tester.run_all_tests()
    tester.save_results(args.output)

    sys.exit(tester.display_results())


if __name__ == '__main__':
    main()
