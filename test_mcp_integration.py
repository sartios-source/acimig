"""
Test Suite for MCP Integration
Tests the MCP client and server integration functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_client import MCPClient, MCPDataValidator, test_mcp_connection as mcp_test_connection, fetch_and_validate_data


class TestMCPClient(unittest.TestCase):
    """Test MCP Client functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mcp_url = "http://test-mcp-server:5000"
        self.client = MCPClient(self.mcp_url)

    def test_client_initialization(self):
        """Test MCP client can be initialized."""
        self.assertEqual(self.client.server_url, self.mcp_url)
        self.assertEqual(self.client.timeout, 30)

    def test_client_custom_timeout(self):
        """Test MCP client with custom timeout."""
        custom_client = MCPClient(self.mcp_url, timeout=60)
        self.assertEqual(custom_client.timeout, 60)

    @patch('mcp_client.requests.get')
    def test_health_check_success(self, mock_get):
        """Test successful health check."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'status': 'healthy',
            'service': 'MCP Server',
            'version': '1.0.0'
        }
        mock_get.return_value = mock_response

        result = self.client.health_check()

        self.assertEqual(result['status'], 'healthy')
        self.assertEqual(result['service'], 'MCP Server')
        self.assertIsNotNone(self.client.last_health_check)

    @patch('mcp_client.requests.get')
    def test_health_check_failure(self, mock_get):
        """Test health check failure."""
        mock_get.side_effect = Exception("Connection refused")

        with self.assertRaises(Exception) as context:
            self.client.health_check()

        self.assertIn('Failed to connect', str(context.exception))

    @patch('mcp_client.requests.get')
    def test_get_fabric_data_success(self, mock_get):
        """Test successful fabric data retrieval."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'nodes': [{'id': '101', 'name': 'leaf-101'}],
            'epgs': [{'name': 'web-epg'}]
        }
        mock_get.return_value = mock_response

        result = self.client.get_fabric_data()

        self.assertIn('nodes', result)
        self.assertIn('epgs', result)
        self.assertEqual(len(result['nodes']), 1)

    @patch('mcp_client.requests.get')
    def test_get_migrator_data_success(self, mock_get):
        """Test successful migrator data retrieval."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'fabric_name': 'test-fabric',
            'devices': [{'device_id': '101', 'device_name': 'leaf-101', 'device_type': 'leaf'}],
            'epg_mappings': [{'tenant': 'prod', 'epg': 'web', 'vlans': [100], 'devices': ['101']}],
            'statistics': {'total_devices': 1, 'total_epgs': 1}
        }
        mock_get.return_value = mock_response

        result = self.client.get_migrator_data()

        self.assertEqual(result['fabric_name'], 'test-fabric')
        self.assertEqual(len(result['devices']), 1)
        self.assertEqual(len(result['epg_mappings']), 1)


class TestMCPDataValidator(unittest.TestCase):
    """Test MCP Data Validator."""

    def setUp(self):
        """Set up test data."""
        self.valid_data = {
            'fabric_name': 'test-fabric',
            'devices': [
                {
                    'device_id': '101',
                    'device_name': 'leaf-101',
                    'device_type': 'leaf',
                    'model': 'N9K-C93180YC-FX'
                }
            ],
            'epg_mappings': [
                {
                    'tenant': 'production',
                    'epg': 'web-epg',
                    'vlans': [100, 101],
                    'devices': ['101']
                }
            ],
            'statistics': {
                'total_devices': 1,
                'total_epgs': 1
            }
        }

    def test_validate_valid_data(self):
        """Test validation of valid data."""
        errors = MCPDataValidator.validate_migrator_data(self.valid_data)
        self.assertEqual(len(errors), 0)

    def test_validate_missing_required_key(self):
        """Test validation with missing required key."""
        invalid_data = self.valid_data.copy()
        del invalid_data['fabric_name']

        errors = MCPDataValidator.validate_migrator_data(invalid_data)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any('fabric_name' in err for err in errors))

    def test_validate_invalid_device_type(self):
        """Test validation with invalid device type."""
        invalid_data = self.valid_data.copy()
        invalid_data['devices'] = [{
            'device_id': '101',
            'device_name': 'test',
            'device_type': 'invalid_type'
        }]

        errors = MCPDataValidator.validate_migrator_data(invalid_data)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any('invalid_type' in err for err in errors))

    def test_validate_missing_device_fields(self):
        """Test validation with missing device fields."""
        invalid_data = self.valid_data.copy()
        invalid_data['devices'] = [{
            'device_id': '101'
            # Missing device_name and device_type
        }]

        errors = MCPDataValidator.validate_migrator_data(invalid_data)
        self.assertGreater(len(errors), 0)

    def test_validate_invalid_vlans_format(self):
        """Test validation with invalid VLANs format."""
        invalid_data = self.valid_data.copy()
        invalid_data['epg_mappings'] = [{
            'tenant': 'prod',
            'epg': 'web',
            'vlans': 'should_be_list',  # Wrong type
            'devices': ['101']
        }]

        errors = MCPDataValidator.validate_migrator_data(invalid_data)
        self.assertGreater(len(errors), 0)

    def test_validate_devices_not_list(self):
        """Test validation when devices is not a list."""
        invalid_data = self.valid_data.copy()
        invalid_data['devices'] = "not_a_list"

        errors = MCPDataValidator.validate_migrator_data(invalid_data)
        self.assertGreater(len(errors), 0)
        self.assertTrue(any('must be a list' in err for err in errors))


class TestMCPHelperFunctions(unittest.TestCase):
    """Test MCP helper functions."""

    @patch('mcp_client.MCPClient')
    def test_test_mcp_connection_success(self, mock_client_class):
        """Test successful connection test."""
        mock_client = MagicMock()
        mock_client.health_check.return_value = {
            'status': 'healthy',
            'service': 'MCP Server',
            'version': '1.0.0'
        }
        mock_client_class.return_value = mock_client

        result = mcp_test_connection("http://test:5000")

        self.assertTrue(result['success'])
        self.assertEqual(result['status'], 'healthy')

    @patch('mcp_client.MCPClient')
    def test_test_mcp_connection_failure(self, mock_client_class):
        """Test failed connection test."""
        mock_client = MagicMock()
        mock_client.health_check.side_effect = Exception("Connection failed")
        mock_client_class.return_value = mock_client

        result = mcp_test_connection("http://test:5000")

        self.assertFalse(result['success'])
        self.assertIn('error', result)

    @patch('mcp_client.MCPClient')
    def test_fetch_and_validate_success(self, mock_client_class):
        """Test successful fetch and validation."""
        mock_client = MagicMock()
        mock_client.get_migrator_data.return_value = {
            'fabric_name': 'test',
            'devices': [{'device_id': '1', 'device_name': 'test', 'device_type': 'leaf'}],
            'epg_mappings': [{'tenant': 't', 'epg': 'e', 'vlans': [], 'devices': []}],
            'statistics': {}
        }
        mock_client_class.return_value = mock_client

        result = fetch_and_validate_data("http://test:5000")

        self.assertTrue(result['success'])
        self.assertIn('data', result)
        self.assertIn('statistics', result)

    @patch('mcp_client.MCPClient')
    def test_fetch_and_validate_validation_errors(self, mock_client_class):
        """Test fetch with validation errors."""
        mock_client = MagicMock()
        mock_client.get_migrator_data.return_value = {
            # Missing required fields
            'devices': []
        }
        mock_client_class.return_value = mock_client

        result = fetch_and_validate_data("http://test:5000")

        self.assertFalse(result['success'])
        self.assertGreater(len(result['errors']), 0)


if __name__ == '__main__':
    print("=" * 80)
    print("Testing MCP Integration")
    print("=" * 80)

    unittest.main(verbosity=2)
