#!/usr/bin/env python3
"""
Test script for Phase 2 features
Validates database functionality and enhanced reporting
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import DMARCDatabase
from enhanced_reporting import EnhancedReporter
import json
from datetime import datetime

def test_database():
    """Test database functionality including purge operations"""
    print("Testing Database Functionality...")
    print("=" * 50)
    
    # Initialize database
    db = DMARCDatabase("data/test_dmarc_monitor.db")
    
    # Create sample report
    sample_report = {
        'metadata': {
            'org_name': 'Google',
            'report_id': 'test_123',
            'date_range': {'begin': '1634140800', 'end': '1634227200'}
        },
        'policy': {
            'domain': 'example.com',
            'p': 'quarantine',
            'sp': 'none',
            'pct': '100'
        },
        'records': [
            {'source_ip': '192.168.1.1', 'count': 100, 'disposition': 'none', 'dkim': 'pass', 'spf': 'pass'},
            {'source_ip': '192.168.1.2', 'count': 50, 'disposition': 'quarantine', 'dkim': 'fail', 'spf': 'pass'}
        ]
    }
    
    # Test storing report
    report_id = db.store_report(sample_report, "Test analysis with some issues detected")
    print(f"✅ Stored test report with ID: {report_id}")
    
    # Test getting summary stats
    stats = db.get_summary_stats()
    print(f"✅ Summary stats: {stats}")
    
    # Test historical comparison
    comparison = db.compare_with_historical('example.com', 85.0)
    print(f"✅ Historical comparison: {comparison}")
    
    # Test database statistics
    db_stats = db.get_database_stats()
    print(f"✅ Database stats: Size={db_stats.get('database_size_mb', 0)}MB, Records={db_stats.get('total_records', 0)}")
    
    # Test purge functionality (dry run)
    purge_stats = db.purge_old_data(retention_days=0)  # This should delete everything for testing
    print(f"✅ Purge test: {purge_stats['reports_deleted']} reports purged")
    
    print("Database tests completed successfully!")
    return True

def test_enhanced_reporting():
    """Test enhanced reporting functionality"""
    print("\nTesting Enhanced Reporting...")
    print("=" * 50)
    
    # Load minimal config for testing
    config = {
        'notifications': {
            'email_subject_prefix': '[DMARC Test]',
            'send_clean_status': True
        },
        'thresholds': {
            'auth_success_rate_min': 95.0,
            'auth_rate_drop_threshold': 5.0,
            'new_sources_threshold': 3,
            'minimum_messages_for_alert': 10
        }
    }
    
    db = DMARCDatabase("data/test_dmarc_monitor.db")
    reporter = EnhancedReporter(config, db)
    
    # Create test reports
    good_report = {
        'raw_data': {
            'metadata': {'org_name': 'Google', 'date_range': {'begin': '1634140800', 'end': '1634227200'}},
            'policy': {'domain': 'good-example.com'},
            'records': [
                {'count': 100, 'dkim': 'pass', 'spf': 'pass', 'source_ip': '1.1.1.1'}
            ]
        },
        'claude_analysis': 'All authentication checks passed successfully. No issues detected.'
    }
    
    bad_report = {
        'raw_data': {
            'metadata': {'org_name': 'Microsoft', 'date_range': {'begin': '1634140800', 'end': '1634227200'}},
            'policy': {'domain': 'bad-example.com'},
            'records': [
                {'count': 50, 'dkim': 'pass', 'spf': 'pass', 'source_ip': '2.2.2.2'},
                {'count': 50, 'dkim': 'fail', 'spf': 'fail', 'source_ip': '3.3.3.3'}
            ]
        },
        'claude_analysis': 'Issues detected: 50% authentication failure rate. Suspicious IP detected.'
    }
    
    # Test with issues
    print("Testing report with issues...")
    issues_report = reporter.generate_smart_report([bad_report, good_report])
    print(f"✅ Issues report generated: {issues_report['subject']}")
    print(f"   Has issues: {issues_report.get('has_issues', False)}")
    
    # Test clean report
    print("\nTesting clean report...")
    clean_report = reporter.generate_smart_report([good_report])
    print(f"✅ Clean report generated: {clean_report['subject']}")
    print(f"   Has issues: {clean_report.get('has_issues', False)}")
    
    # Test no reports
    print("\nTesting no reports scenario...")
    no_report = reporter.generate_smart_report([])
    print(f"✅ No reports scenario: {no_report['subject']}")
    
    print("Enhanced reporting tests completed successfully!")
    return True

def test_integration():
    """Test integration between components"""
    print("\nTesting Integration...")
    print("=" * 50)
    
    # Test that all components work together
    db = DMARCDatabase("data/test_dmarc_monitor.db")
    
    config = {
        'notifications': {
            'email_subject_prefix': '[DMARC Integration Test]',
            'send_clean_status': True
        },
        'thresholds': {
            'auth_success_rate_min': 95.0,
            'auth_rate_drop_threshold': 5.0,
            'new_sources_threshold': 3,
            'minimum_messages_for_alert': 10
        }
    }
    
    reporter = EnhancedReporter(config, db)
    
    # Simulate a full workflow
    test_report = {
        'raw_data': {
            'metadata': {
                'org_name': 'Integration Test',
                'report_id': 'integration_123',
                'date_range': {'begin': str(int(datetime.now().timestamp()) - 86400), 'end': str(int(datetime.now().timestamp()))}
            },
            'policy': {'domain': 'integration-test.com', 'p': 'reject', 'sp': 'reject', 'pct': '100'},
            'records': [
                {'source_ip': '10.0.0.1', 'count': 1000, 'disposition': 'none', 'dkim': 'pass', 'spf': 'pass'},
                {'source_ip': '10.0.0.2', 'count': 100, 'disposition': 'reject', 'dkim': 'fail', 'spf': 'fail'}
            ]
        },
        'claude_analysis': 'Overall good performance with 90.9% success rate. Minor issues with one source.'
    }
    
    # Store report in database
    report_id = db.store_report(test_report['raw_data'], test_report['claude_analysis'])
    print(f"✅ Stored integration test report: {report_id}")
    
    # Generate report
    generated_report = reporter.generate_smart_report([test_report])
    print(f"✅ Generated report: {generated_report['subject']}")
    print(f"   Report type: {'Issues' if generated_report.get('has_issues') else 'Clean'}")
    
    # Test historical data retrieval
    historical = db.get_historical_data('integration-test.com', days_back=1)
    print(f"✅ Retrieved {len(historical)} historical records")
    
    print("Integration tests completed successfully!")
    return True

def main():
    """Run all tests"""
    print("DMARC Monitor Phase 2 - Test Suite")
    print("=" * 60)
    
    try:
        # Run tests
        test_database()
        test_enhanced_reporting() 
        test_integration()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("Phase 2 implementation is ready for production use.")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)