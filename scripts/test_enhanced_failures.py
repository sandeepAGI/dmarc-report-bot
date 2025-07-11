#!/usr/bin/env python3
"""
Unit tests for enhanced failure details functionality
Tests the new database methods and reporting enhancements
"""

import os
import sys
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import DMARCDatabase
from enhanced_reporting import EnhancedReporter

class TestEnhancedFailures(unittest.TestCase):
    def setUp(self):
        """Set up test database and mock config"""
        # Create temporary database for testing
        self.test_db_fd, self.test_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.test_db_fd)
        
        self.db = DMARCDatabase(self.test_db_path)
        
        # Mock config
        self.config = {
            'thresholds': {
                'auth_success_rate_min': 95.0,
                'auth_rate_drop_threshold': 5.0,
                'new_sources_threshold': 3,
                'minimum_messages_for_alert': 10
            },
            'notifications': {
                'send_clean_status': True,
                'email_subject_prefix': '[DMARC Test]'
            }
        }
        
        self.reporter = EnhancedReporter(self.config, self.db)
        
        # Sample test data
        self.sample_report_with_failures = {
            'metadata': {
                'org_name': 'Test Outlook',
                'report_id': 'test-report-123',
                'date_range': {
                    'begin': '1750032000',
                    'end': '1750118400'
                }
            },
            'policy': {
                'domain': 'test-domain.com',
                'p': 'none',
                'sp': 'none',
                'pct': '100'
            },
            'records': [
                {
                    'source_ip': '50.63.9.60',
                    'count': 1,
                    'disposition': 'none',
                    'dkim': 'fail',
                    'spf': 'fail'
                },
                {
                    'source_ip': '50.63.11.59',
                    'count': 2,
                    'disposition': 'none',
                    'dkim': 'fail',
                    'spf': 'pass'
                },
                {
                    'source_ip': '40.107.236.93',
                    'count': 10,
                    'disposition': 'none',
                    'dkim': 'pass',
                    'spf': 'pass'
                }
            ]
        }
        
        self.sample_report_clean = {
            'metadata': {
                'org_name': 'Test Outlook',
                'report_id': 'test-report-clean',
                'date_range': {
                    'begin': '1750118400',
                    'end': '1750204800'
                }
            },
            'policy': {
                'domain': 'test-domain.com',
                'p': 'none',
                'sp': 'none',
                'pct': '100'
            },
            'records': [
                {
                    'source_ip': '40.107.236.93',
                    'count': 15,
                    'disposition': 'none',
                    'dkim': 'pass',
                    'spf': 'pass'
                }
            ]
        }
    
    def tearDown(self):
        """Clean up test database"""
        if os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)
    
    def test_database_failure_methods(self):
        """Test new database methods for failure details"""
        # Store a report with failures
        claude_analysis = "Test analysis with authentication failures detected"
        report_id = self.db.store_report(self.sample_report_with_failures, claude_analysis)
        
        self.assertIsNotNone(report_id)
        
        # Test get_failure_details
        failure_details = self.db.get_failure_details('test-domain.com', report_id)
        
        # Should return 2 records (the ones with failures)
        self.assertEqual(len(failure_details), 2)
        
        # Check that we get the correct failure records
        failed_ips = [detail['source_ip'] for detail in failure_details]
        self.assertIn('50.63.9.60', failed_ips)
        self.assertIn('50.63.11.59', failed_ips)
        self.assertNotIn('40.107.236.93', failed_ips)  # This one passed
        
        # Test get_last_failure_date
        last_failure = self.db.get_last_failure_date('test-domain.com')
        self.assertIsNotNone(last_failure)
        self.assertIsInstance(last_failure, str)
        
        # Test with domain that has no failures
        no_failure = self.db.get_last_failure_date('no-failures.com')
        self.assertIsNone(no_failure)
    
    def test_ip_intelligence(self):
        """Test IP intelligence functionality"""
        # Test Microsoft IP
        microsoft_intel = self.db.get_ip_intelligence('40.107.236.93')
        self.assertEqual(microsoft_intel['organization'], 'Microsoft Corporation (Office 365)')
        self.assertFalse(microsoft_intel['is_suspicious'])
        
        # Test Google IP
        google_intel = self.db.get_ip_intelligence('209.85.128.1')
        self.assertEqual(google_intel['organization'], 'Google LLC (Gmail)')
        self.assertFalse(google_intel['is_suspicious'])
        
        # Test suspicious IP
        suspicious_intel = self.db.get_ip_intelligence('50.63.9.60')
        self.assertEqual(suspicious_intel['organization'], 'Unknown Provider (50.63.x.x range)')
        self.assertTrue(suspicious_intel['is_suspicious'])
        
        # Test unknown IP
        unknown_intel = self.db.get_ip_intelligence('192.168.1.1')
        self.assertEqual(unknown_intel['organization'], 'Unknown Provider')
        self.assertFalse(unknown_intel['is_suspicious'])
    
    def test_detailed_failure_analysis(self):
        """Test detailed failure analysis generation"""
        # Store report with failures
        claude_analysis = "Authentication failures detected in multiple sources"
        report_id = self.db.store_report(self.sample_report_with_failures, claude_analysis)
        
        # Create mock report structure
        mock_report = {
            'raw_data': self.sample_report_with_failures,
            'claude_analysis': claude_analysis,
            'db_report_id': report_id
        }
        
        # Test detailed failure analysis
        failure_analysis = self.reporter._get_detailed_failure_analysis(mock_report)
        
        self.assertIn("DETAILED FAILURE ANALYSIS", failure_analysis)
        self.assertIn("50.63.9.60", failure_analysis)
        self.assertIn("50.63.11.59", failure_analysis)
        self.assertIn("DKIM ❌ FAIL", failure_analysis)
        self.assertIn("RECOMMENDED ACTIONS", failure_analysis)
        self.assertIn("dig TXT test-domain.com", failure_analysis)
        self.assertIn("⚠️ INVESTIGATE", failure_analysis)  # Should flag suspicious IPs
    
    def test_clean_report_with_historical_context(self):
        """Test clean reports include historical failure context"""
        # First store a report with failures
        claude_analysis_fail = "Authentication failures detected"
        fail_report_id = self.db.store_report(self.sample_report_with_failures, claude_analysis_fail)
        
        # Then store a clean report
        claude_analysis_clean = "All authentication checks passed"
        clean_report_id = self.db.store_report(self.sample_report_clean, claude_analysis_clean)
        
        # Create clean report
        clean_reports = [{
            'raw_data': self.sample_report_clean,
            'claude_analysis': claude_analysis_clean,
            'db_report_id': clean_report_id
        }]
        
        report_data = self.reporter._create_clean_status_report(clean_reports)
        
        # Should include "No failures detected since" with a date
        self.assertIn("No failures detected since", report_data['body'])
        self.assertIn("2025-", report_data['body'])  # Should have a date
    
    def test_issues_report_with_detailed_failures(self):
        """Test that issues reports include detailed failure analysis"""
        # Store report with failures
        claude_analysis = "Multiple authentication failures detected across different sources"
        report_id = self.db.store_report(self.sample_report_with_failures, claude_analysis)
        
        # Create issues report
        issues_reports = [{
            'raw_data': self.sample_report_with_failures,
            'claude_analysis': claude_analysis,
            'db_report_id': report_id
        }]
        
        report_data = self.reporter._create_issues_report(issues_reports, [])
        
        # Should include detailed failure analysis
        self.assertIn("DETAILED FAILURE ANALYSIS", report_data['body'])
        self.assertIn("Failed Authentication Details", report_data['body'])
        self.assertIn("50.63.9.60", report_data['body'])
        self.assertIn("RECOMMENDED ACTIONS", report_data['body'])
        self.assertIn("⚠️ INVESTIGATE", report_data['body'])
    
    def test_no_failures_no_detailed_analysis(self):
        """Test that reports with no failures don't include detailed analysis"""
        # Store clean report
        claude_analysis = "All authentication successful"
        report_id = self.db.store_report(self.sample_report_clean, claude_analysis)
        
        mock_report = {
            'raw_data': self.sample_report_clean,
            'claude_analysis': claude_analysis,
            'db_report_id': report_id
        }
        
        # Should return empty string for detailed analysis
        failure_analysis = self.reporter._get_detailed_failure_analysis(mock_report)
        self.assertEqual(failure_analysis, "")
    
    def test_missing_db_report_id(self):
        """Test handling of missing database report ID"""
        mock_report = {
            'raw_data': self.sample_report_with_failures,
            'claude_analysis': "Some analysis"
            # No db_report_id
        }
        
        # Should handle gracefully and return empty string
        failure_analysis = self.reporter._get_detailed_failure_analysis(mock_report)
        self.assertEqual(failure_analysis, "")

class TestDatabaseIntegration(unittest.TestCase):
    """Integration tests for database functionality"""
    
    def setUp(self):
        self.test_db_fd, self.test_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.test_db_fd)
        self.db = DMARCDatabase(self.test_db_path)
    
    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.unlink(self.test_db_path)
    
    def test_failure_tracking_over_time(self):
        """Test tracking failures across multiple reports"""
        domain = 'tracking-test.com'
        
        # Create reports with different timestamps
        base_timestamp = int(datetime.now().timestamp())
        
        # Report 1: Has failures (7 days ago)
        old_report = {
            'metadata': {
                'org_name': 'Test Provider',
                'report_id': 'old-report',
                'date_range': {
                    'begin': str(base_timestamp - 7*24*3600),
                    'end': str(base_timestamp - 6*24*3600)
                }
            },
            'policy': {'domain': domain, 'p': 'none', 'sp': 'none', 'pct': '100'},
            'records': [{
                'source_ip': '192.168.1.100',
                'count': 1,
                'disposition': 'none',
                'dkim': 'fail',
                'spf': 'fail'
            }]
        }
        
        # Report 2: Clean (today)
        new_report = {
            'metadata': {
                'org_name': 'Test Provider',
                'report_id': 'new-report',
                'date_range': {
                    'begin': str(base_timestamp - 3600),
                    'end': str(base_timestamp)
                }
            },
            'policy': {'domain': domain, 'p': 'none', 'sp': 'none', 'pct': '100'},
            'records': [{
                'source_ip': '40.107.236.93',
                'count': 5,
                'disposition': 'none',
                'dkim': 'pass',
                'spf': 'pass'
            }]
        }
        
        # Store both reports
        old_id = self.db.store_report(old_report, "Old report with failures")
        new_id = self.db.store_report(new_report, "New clean report")
        
        # Test that we can get the last failure date
        last_failure = self.db.get_last_failure_date(domain)
        self.assertIsNotNone(last_failure)
        
        # Test that failure details work for the old report
        failures = self.db.get_failure_details(domain, old_id)
        self.assertEqual(len(failures), 1)
        self.assertEqual(failures[0]['source_ip'], '192.168.1.100')
        
        # Test that no failures for new report
        no_failures = self.db.get_failure_details(domain, new_id)
        self.assertEqual(len(no_failures), 0)

def run_tests():
    """Run all tests and return results"""
    print("🧪 Running Enhanced Failure Details Tests...")
    print("=" * 60)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(unittest.makeSuite(TestEnhancedFailures))
    suite.addTest(unittest.makeSuite(TestDatabaseIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.failures:
        print("\nFAILURES:")
        for test, traceback in result.failures:
            print(f"- {test}: {traceback}")
    
    if result.errors:
        print("\nERRORS:")
        for test, traceback in result.errors:
            print(f"- {test}: {traceback}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    print(f"\n{'✅ ALL TESTS PASSED' if success else '❌ SOME TESTS FAILED'}")
    
    return success

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)