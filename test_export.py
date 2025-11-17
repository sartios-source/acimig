"""
Test Suite for PDF and Excel Export Functionality
Tests the new report generation capabilities.
"""

import unittest
from pathlib import Path
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analysis.export import PDFReportGenerator, ExcelReportGenerator, generate_pdf_report, generate_excel_report


class TestExportFunctionality(unittest.TestCase):
    """Test PDF and Excel export functions."""

    def setUp(self):
        """Set up test data."""
        self.test_data = {
            'fabric_name': 'test-fabric',
            'mode': 'evpn',
            'total_devices': 50,
            'total_leafs': 10,
            'total_spines': 2,
            'total_fex': 38,
            'total_epgs': 150,
            'total_bridge_domains': 50,
            'total_vrfs': 10,
            'total_contracts': 75,
            'devices': [
                {
                    'device_id': '101',
                    'device_name': 'leaf-101',
                    'device_type': 'leaf',
                    'model': 'N9K-C93180YC-FX',
                    'port_count': 48
                },
                {
                    'device_id': '102',
                    'device_name': 'fex-102',
                    'device_type': 'fex',
                    'model': 'N2K-C2248TP',
                    'parent_leaf': 'leaf-101',
                    'port_count': 48
                }
            ],
            'epgs': [
                {
                    'tenant': 'production',
                    'application_profile': 'web-app',
                    'epg': 'web-tier',
                    'vlan_count': 2,
                    'device_count': 5,
                    'path_count': 10,
                    'complexity': 'low'
                },
                {
                    'tenant': 'production',
                    'application_profile': 'web-app',
                    'epg': 'app-tier',
                    'vlan_count': 3,
                    'device_count': 8,
                    'path_count': 20,
                    'complexity': 'medium'
                }
            ],
            'recommendations': [
                {
                    'priority': 'high',
                    'category': 'planning',
                    'title': 'Review Migration Waves',
                    'description': 'Analyze recommended migration wave order',
                    'action': 'Start with standalone EPGs',
                    'estimated_hours': 4
                },
                {
                    'priority': 'medium',
                    'category': 'vpc',
                    'title': 'VPC Configuration Review',
                    'description': 'Ensure VPC pairs are symmetric',
                    'action': 'Review VPC analysis',
                    'estimated_hours': 2
                }
            ],
            'migration_assessment': {
                'overall_readiness': {
                    'score': 75,
                    'ready_for_migration': True,
                    'critical_issues': 0
                },
                'component_scores': {
                    'vpc_configuration': 85,
                    'contract_complexity': 70,
                    'vlan_management': 65
                }
            },
            'migration_waves': [
                {
                    'wave': 'Wave 1 - Standalone',
                    'epg_count': 50,
                    'complexity': 'low',
                    'estimated_days': 5,
                    'start_week': 0,
                    'duration_weeks': 1
                },
                {
                    'wave': 'Wave 2 - Low Complexity',
                    'epg_count': 60,
                    'complexity': 'low',
                    'estimated_days': 7,
                    'start_week': 1,
                    'duration_weeks': 2
                }
            ]
        }

    def test_pdf_generator_initialization(self):
        """Test PDF generator can be initialized."""
        generator = PDFReportGenerator()
        self.assertIsNotNone(generator)
        self.assertIsNotNone(generator.styles)

    def test_pdf_report_generation(self):
        """Test PDF report can be generated."""
        pdf_bytes = generate_pdf_report(self.test_data)
        self.assertIsNotNone(pdf_bytes)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertGreater(len(pdf_bytes), 1000)  # Should be substantial
        # PDF files start with %PDF
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_excel_generator_initialization(self):
        """Test Excel generator can be initialized."""
        generator = ExcelReportGenerator()
        self.assertIsNotNone(generator)
        self.assertIsNotNone(generator.wb)

    def test_excel_report_generation(self):
        """Test Excel report can be generated."""
        excel_bytes = generate_excel_report(self.test_data)
        self.assertIsNotNone(excel_bytes)
        self.assertIsInstance(excel_bytes, bytes)
        self.assertGreater(len(excel_bytes), 1000)  # Should be substantial
        # Excel files start with PK (ZIP format)
        self.assertTrue(excel_bytes.startswith(b'PK'))

    def test_pdf_with_minimal_data(self):
        """Test PDF generation with minimal data."""
        minimal_data = {
            'fabric_name': 'minimal-test',
            'mode': 'evpn',
            'total_devices': 0,
            'total_leafs': 0,
            'total_spines': 0,
            'total_fex': 0,
            'total_epgs': 0,
            'devices': [],
            'epgs': [],
            'recommendations': []
        }
        pdf_bytes = generate_pdf_report(minimal_data)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))

    def test_excel_with_minimal_data(self):
        """Test Excel generation with minimal data."""
        minimal_data = {
            'fabric_name': 'minimal-test',
            'mode': 'evpn',
            'total_devices': 0,
            'total_leafs': 0,
            'total_spines': 0,
            'total_fex': 0,
            'total_epgs': 0,
            'devices': [],
            'epgs': [],
            'recommendations': [],
            'migration_waves': []
        }
        excel_bytes = generate_excel_report(minimal_data)
        self.assertIsNotNone(excel_bytes)
        self.assertTrue(excel_bytes.startswith(b'PK'))

    def test_pdf_file_save(self):
        """Test PDF can be saved to file."""
        output_path = Path('output/test_report.pdf')
        output_path.parent.mkdir(exist_ok=True, parents=True)

        pdf_bytes = generate_pdf_report(self.test_data)
        output_path.write_bytes(pdf_bytes)

        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 1000)

        # Cleanup
        if output_path.exists():
            output_path.unlink()

    def test_excel_file_save(self):
        """Test Excel can be saved to file."""
        output_path = Path('output/test_report.xlsx')
        output_path.parent.mkdir(exist_ok=True, parents=True)

        excel_bytes = generate_excel_report(self.test_data)
        output_path.write_bytes(excel_bytes)

        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 1000)

        # Cleanup
        if output_path.exists():
            output_path.unlink()


if __name__ == '__main__':
    print("=" * 80)
    print("Testing PDF and Excel Export Functionality")
    print("=" * 80)

    unittest.main(verbosity=2)
