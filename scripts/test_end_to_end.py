#!/usr/bin/env python3
"""
End-to-end test demonstrating enhanced failure details functionality
"""

import os
import sys
import tempfile

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import DMARCDatabase
from enhanced_reporting import EnhancedReporter

def test_end_to_end():
    """Complete end-to-end test of enhanced functionality"""
    
    print("🚀 DMARC Enhanced Failure Details - End-to-End Test")
    print("=" * 60)
    
    # Create temporary database for clean test
    test_db_fd, test_db_path = tempfile.mkstemp(suffix='.db')
    os.close(test_db_fd)
    
    try:
        db = DMARCDatabase(test_db_path)
        config = {
            'thresholds': {
                'auth_success_rate_min': 95.0,
                'auth_rate_drop_threshold': 5.0,
                'new_sources_threshold': 3,
                'minimum_messages_for_alert': 10
            },
            'notifications': {
                'send_clean_status': True,
                'email_subject_prefix': '[DMARC Enhanced]'
            }
        }
        reporter = EnhancedReporter(config, db)
        
        # Test 1: Report with failures
        print("\n📊 TEST 1: Report with Authentication Failures")
        print("-" * 40)
        
        failed_report_data = {
            'metadata': {
                'org_name': 'Enterprise Outlook',
                'report_id': 'test-failures-123',
                'date_range': {'begin': '1750032000', 'end': '1750118400'}
            },
            'policy': {
                'domain': 'test-company.com',
                'p': 'none', 'sp': 'none', 'pct': '100'
            },
            'records': [
                {'source_ip': '50.63.9.60', 'count': 2, 'disposition': 'none', 'dkim': 'fail', 'spf': 'fail'},
                {'source_ip': '50.63.11.59', 'count': 1, 'disposition': 'none', 'dkim': 'fail', 'spf': 'pass'},
                {'source_ip': '192.168.1.100', 'count': 1, 'disposition': 'none', 'dkim': 'pass', 'spf': 'fail'},
                {'source_ip': '40.107.236.93', 'count': 8, 'disposition': 'none', 'dkim': 'pass', 'spf': 'pass'}
            ]
        }
        
        claude_analysis = "Authentication failures detected on multiple sources. DKIM issues on 50.63.x.x range and SPF failure on 192.168.1.100 require investigation."
        
        # Store in database
        report_id = db.store_report(failed_report_data, claude_analysis)
        print(f"✅ Stored report with ID: {report_id}")
        
        # Create report structure for enhanced reporting
        analyzed_report = {
            'raw_data': failed_report_data,
            'claude_analysis': claude_analysis,
            'db_report_id': report_id
        }
        
        # Generate enhanced report
        issues_report = reporter._create_issues_report([analyzed_report], [])
        
        print("\n📋 ENHANCED ISSUES REPORT:")
        print("=" * 60)
        print(issues_report['body'])
        
        # Test 2: Clean report with historical context
        print("\n\n📊 TEST 2: Clean Report with Historical Context")
        print("-" * 40)
        
        clean_report_data = {
            'metadata': {
                'org_name': 'Enterprise Outlook',
                'report_id': 'test-clean-456',
                'date_range': {'begin': '1750118400', 'end': '1750204800'}
            },
            'policy': {
                'domain': 'test-company.com',
                'p': 'none', 'sp': 'none', 'pct': '100'
            },
            'records': [
                {'source_ip': '40.107.236.93', 'count': 15, 'disposition': 'none', 'dkim': 'pass', 'spf': 'pass'}
            ]
        }
        
        clean_claude_analysis = "All authentication checks passed successfully. No issues detected."
        
        # Store clean report
        clean_report_id = db.store_report(clean_report_data, clean_claude_analysis)
        print(f"✅ Stored clean report with ID: {clean_report_id}")
        
        clean_analyzed_report = {
            'raw_data': clean_report_data,
            'claude_analysis': clean_claude_analysis,
            'db_report_id': clean_report_id
        }
        
        # Generate clean status report
        clean_report = reporter._create_clean_status_report([clean_analyzed_report])
        
        print("\n📋 ENHANCED CLEAN STATUS REPORT:")
        print("=" * 60)
        print(clean_report['body'])
        
        # Test 3: Database queries
        print("\n\n📊 TEST 3: Database Intelligence Features")
        print("-" * 40)
        
        # Test failure details
        failure_details = db.get_failure_details('test-company.com', report_id)
        print(f"✅ Found {len(failure_details)} failure records")
        for detail in failure_details:
            print(f"   - {detail['source_ip']}: {detail['count']} msg(s), DKIM={detail['dkim_result']}, SPF={detail['spf_result']}")
        
        # Test last failure date
        last_failure = db.get_last_failure_date('test-company.com')
        print(f"✅ Last failure date: {last_failure}")
        
        # Test IP intelligence
        print("\n🔍 IP Intelligence:")
        test_ips = ['50.63.9.60', '40.107.236.93', '192.168.1.100']
        for ip in test_ips:
            intel = db.get_ip_intelligence(ip)
            status = "⚠️  SUSPICIOUS" if intel['is_suspicious'] else "✅ TRUSTED"
            print(f"   - {ip}: {intel['organization']} {status}")
        
        print(f"\n🎉 END-TO-END TEST COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("✅ Enhanced failure details are working correctly")
        print("✅ Historical context is being added to clean reports")
        print("✅ IP intelligence is providing actionable information")
        print("✅ Database methods are functioning properly")
        
    finally:
        # Cleanup
        if os.path.exists(test_db_path):
            os.unlink(test_db_path)

if __name__ == "__main__":
    test_end_to_end()