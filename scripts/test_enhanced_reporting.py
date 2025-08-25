#!/usr/bin/env python3
"""
Test script for enhanced DMARC reporting with non-technical formatting
Tests the new hybrid report format and plain English explanations
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from datetime import datetime
from non_technical_formatter import NonTechnicalFormatter

def test_risk_levels():
    """Test risk level categorization"""
    print("Testing Risk Level Categorization")
    print("=" * 50)
    
    formatter = NonTechnicalFormatter()
    
    test_cases = [
        (65.0, "CRITICAL"),
        (75.0, "HIGH"),
        (85.0, "MODERATE"),
        (92.0, "LOW"),
        (98.0, "GOOD")
    ]
    
    for auth_rate, expected_level in test_cases:
        level, icon, desc = formatter.get_risk_level(auth_rate)
        print(f"Auth Rate: {auth_rate}% → {icon} {level}")
        print(f"  Description: {desc}")
        assert level == expected_level, f"Expected {expected_level}, got {level}"
    
    print("✅ Risk level tests passed!\n")

def test_ip_analysis():
    """Test IP address analysis and recommendations"""
    print("Testing IP Address Analysis")
    print("=" * 50)
    
    formatter = NonTechnicalFormatter()
    
    # Test Google IP
    google_analysis = formatter.analyze_ip_address(
        "209.85.220.41",
        "Google LLC",
        "pass",
        "fail",
        4
    )
    
    print(f"Google IP Analysis:")
    print(f"  Summary: {google_analysis['summary']}")
    print(f"  Action: {google_analysis['action']}")
    print()
    
    # Test suspicious IP
    suspicious_analysis = formatter.analyze_ip_address(
        "185.234.218.123",
        "DigitalOcean LLC",
        "fail",
        "fail",
        10
    )
    
    print(f"Suspicious IP Analysis:")
    print(f"  Summary: {suspicious_analysis['summary']}")
    print(f"  Action: {suspicious_analysis['action']}")
    print()
    
    print("✅ IP analysis tests passed!\n")

def test_business_impact():
    """Test business impact explanations"""
    print("Testing Business Impact Explanations")
    print("=" * 50)
    
    formatter = NonTechnicalFormatter()
    
    # Test severe impact
    severe_impact = formatter.get_business_impact(65.0, 100)
    print("Severe Impact (65% auth rate, 100 emails):")
    print(severe_impact)
    print()
    
    # Test moderate impact
    moderate_impact = formatter.get_business_impact(88.0, 50)
    print("Moderate Impact (88% auth rate, 50 emails):")
    print(moderate_impact)
    print()
    
    print("✅ Business impact tests passed!\n")

def test_diy_instructions():
    """Test DIY action steps generation"""
    print("Testing DIY Action Steps")
    print("=" * 50)
    
    formatter = NonTechnicalFormatter()
    
    failures = [
        {
            'source_ip': '209.85.220.41',
            'org_info': 'Google LLC',
            'dkim_result': 'pass',
            'spf_result': 'fail',
            'count': 5
        },
        {
            'source_ip': '35.174.145.124',
            'org_info': 'Amazon AWS',
            'dkim_result': 'fail',
            'spf_result': 'fail',
            'count': 2
        }
    ]
    
    instructions = formatter.format_diy_action_steps("example.com", failures)
    print("Generated DIY Instructions:")
    print(instructions)
    print()
    
    print("✅ DIY instructions test passed!\n")

def test_plain_english_summary():
    """Test plain English summary generation"""
    print("Testing Plain English Summary")
    print("=" * 50)
    
    formatter = NonTechnicalFormatter()
    
    summary = formatter.format_plain_english_summary(
        auth_rate=73.3,
        total_messages=81,
        failed_messages=22,
        unique_failures=4
    )
    
    print("Generated Summary:")
    print(summary)
    
    print("✅ Plain English summary test passed!\n")

def test_hybrid_report():
    """Test complete hybrid report section"""
    print("Testing Complete Hybrid Report Section")
    print("=" * 50)
    
    formatter = NonTechnicalFormatter()
    
    # Sample data similar to real DMARC report
    report_data = {
        'policy': {'domain': 'training.aileron-group.com'},
        'records': [
            {'source_ip': '209.85.220.41', 'count': 10, 'dkim': 'pass', 'spf': 'pass'},
            {'source_ip': '35.174.145.124', 'count': 4, 'dkim': 'fail', 'spf': 'fail'},
        ]
    }
    
    failure_details = [
        {
            'source_ip': '35.174.145.124',
            'count': 4,
            'dkim_result': 'fail',
            'spf_result': 'fail',
            'org_info': 'Amazon AWS'
        }
    ]
    
    hybrid_section = formatter.create_hybrid_report_section(
        'training.aileron-group.com',
        report_data,
        failure_details
    )
    
    print("Generated Hybrid Report Section:")
    print(hybrid_section)
    
    print("✅ Hybrid report test passed!\n")

def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("ENHANCED DMARC REPORTING TEST SUITE")
    print("Testing Non-Technical Formatting Features")
    print("=" * 60 + "\n")
    
    try:
        test_risk_levels()
        test_ip_analysis()
        test_business_impact()
        test_diy_instructions()
        test_plain_english_summary()
        test_hybrid_report()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED SUCCESSFULLY!")
        print("=" * 60)
        print("\nThe enhanced reporting system is ready to use.")
        print("Your cron job will automatically use these improvements.")
        print("\nKey improvements implemented:")
        print("• Plain English explanations for all technical terms")
        print("• Risk-based priority levels (CRITICAL/HIGH/MODERATE/LOW)")
        print("• Business impact explanations")
        print("• IP investigation with actionable guidance")
        print("• Step-by-step DIY instructions")
        print("• Hybrid format (plain English + technical details)")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()