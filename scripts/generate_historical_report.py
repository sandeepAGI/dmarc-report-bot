#!/usr/bin/env python3
"""
Generate a consolidated report from the database for all processed reports
"""

import os
import sys
import sqlite3
from datetime import datetime
from collections import defaultdict

# Add src directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, os.path.join(project_root, 'src'))

def main():
    db_path = os.path.join(project_root, 'data', 'dmarc_monitor.db')

    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return 1

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("=" * 80)
    print("CONSOLIDATED DMARC REPORT - HISTORICAL ANALYSIS")
    print("=" * 80)

    # Get database statistics
    cursor.execute("SELECT COUNT(*) FROM dmarc_reports")
    total_reports = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM dmarc_records")
    total_records = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM dmarc_analyses")
    total_analyses = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM dmarc_alerts")
    total_alerts = cursor.fetchone()[0]

    # Get date range
    cursor.execute("""
        SELECT
            MIN(date_begin) as earliest,
            MAX(date_end) as latest
        FROM dmarc_reports
    """)
    date_range = cursor.fetchone()

    print(f"\n📊 DATABASE STATISTICS")
    print(f"   Total Reports: {total_reports}")
    print(f"   Total Records: {total_records}")
    print(f"   Total Analyses: {total_analyses}")
    print(f"   Total Alerts: {total_alerts}")

    if date_range['earliest'] and date_range['latest']:
        earliest = datetime.fromtimestamp(int(date_range['earliest']))
        latest = datetime.fromtimestamp(int(date_range['latest']))
        print(f"   Date Range: {earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')}")

    # Get summary by domain
    print(f"\n" + "=" * 80)
    print("SUMMARY BY DOMAIN")
    print("=" * 80)

    cursor.execute("""
        SELECT
            domain,
            COUNT(*) as report_count,
            SUM(CAST(json_extract(report_metadata, '$.messages_received') AS INTEGER)) as total_messages
        FROM dmarc_reports
        GROUP BY domain
        ORDER BY report_count DESC
    """)

    domain_summary = cursor.fetchall()
    for row in domain_summary:
        print(f"\n{row['domain']}:")
        print(f"   Reports: {row['report_count']}")
        print(f"   Messages: {row['total_messages'] if row['total_messages'] else 'N/A'}")

    # Get all alerts (security issues)
    print(f"\n" + "=" * 80)
    print("SECURITY ALERTS & ISSUES DETECTED")
    print("=" * 80)

    cursor.execute("""
        SELECT
            a.domain,
            a.alert_type,
            a.severity,
            a.description,
            a.created_at,
            a.details
        FROM dmarc_alerts a
        ORDER BY a.created_at DESC
    """)

    alerts = cursor.fetchall()

    if alerts:
        print(f"\n⚠️  Found {len(alerts)} security alerts:")

        # Group by severity
        critical_alerts = [a for a in alerts if a['severity'] == 'critical']
        high_alerts = [a for a in alerts if a['severity'] == 'high']
        medium_alerts = [a for a in alerts if a['severity'] == 'medium']
        low_alerts = [a for a in alerts if a['severity'] == 'low']

        if critical_alerts:
            print(f"\n🔴 CRITICAL ({len(critical_alerts)} alerts):")
            for alert in critical_alerts[:10]:  # Show first 10
                print(f"   • {alert['domain']}: {alert['description']}")

        if high_alerts:
            print(f"\n🟠 HIGH ({len(high_alerts)} alerts):")
            for alert in high_alerts[:10]:
                print(f"   • {alert['domain']}: {alert['description']}")

        if medium_alerts:
            print(f"\n🟡 MEDIUM ({len(medium_alerts)} alerts):")
            for alert in medium_alerts[:10]:
                print(f"   • {alert['domain']}: {alert['description']}")

        if low_alerts:
            print(f"\n🟢 LOW ({len(low_alerts)} alerts):")
            for alert in low_alerts[:5]:
                print(f"   • {alert['domain']}: {alert['description']}")
    else:
        print("\n✅ No security alerts found - all reports passed authentication!")

    # Get analysis summaries with issues
    print(f"\n" + "=" * 80)
    print("DETAILED ANALYSIS - REPORTS WITH ISSUES")
    print("=" * 80)

    cursor.execute("""
        SELECT
            r.domain,
            r.org_name,
            r.report_id,
            r.date_begin,
            r.date_end,
            a.analysis_result,
            a.authentication_rate,
            a.created_at
        FROM dmarc_reports r
        JOIN dmarc_analyses a ON r.id = a.report_id
        WHERE a.authentication_rate < 100
        ORDER BY a.authentication_rate ASC, r.date_begin DESC
        LIMIT 50
    """)

    problematic_reports = cursor.fetchall()

    if problematic_reports:
        print(f"\n⚠️  Found {len(problematic_reports)} reports with authentication issues:\n")

        for i, report in enumerate(problematic_reports, 1):
            date_begin = datetime.fromtimestamp(int(report['date_begin'])).strftime('%Y-%m-%d')
            date_end = datetime.fromtimestamp(int(report['date_end'])).strftime('%Y-%m-%d')

            print(f"{i}. {report['domain']} (reported by {report['org_name']})")
            print(f"   Period: {date_begin} to {date_end}")
            print(f"   Authentication Rate: {report['authentication_rate']:.1f}%")

            # Try to parse analysis result for key issues
            analysis = report['analysis_result']
            if analysis and len(analysis) < 500:  # Show brief analysis
                print(f"   Analysis: {analysis[:200]}...")
            print()
    else:
        print("\n✅ All reports had 100% authentication rate!")

    # Get top failing IPs
    print(f"\n" + "=" * 80)
    print("TOP FAILING IP ADDRESSES")
    print("=" * 80)

    cursor.execute("""
        SELECT
            source_ip,
            COUNT(*) as failure_count,
            GROUP_CONCAT(DISTINCT domain) as affected_domains
        FROM dmarc_records
        WHERE dkim_result = 'fail' OR spf_result = 'fail'
        GROUP BY source_ip
        ORDER BY failure_count DESC
        LIMIT 20
    """)

    failing_ips = cursor.fetchall()

    if failing_ips:
        print(f"\n⚠️  Top {len(failing_ips)} IP addresses with authentication failures:\n")

        for i, ip_record in enumerate(failing_ips, 1):
            domains = ip_record['affected_domains'].split(',') if ip_record['affected_domains'] else []
            domains_str = ', '.join(set(domains)[:3])  # Show first 3 unique domains
            if len(set(domains)) > 3:
                domains_str += f" (+{len(set(domains)) - 3} more)"

            print(f"{i}. {ip_record['source_ip']}")
            print(f"   Failures: {ip_record['failure_count']}")
            print(f"   Affected domains: {domains_str}")
            print()
    else:
        print("\n✅ No authentication failures detected!")

    # Get policy recommendations
    print(f"\n" + "=" * 80)
    print("DMARC POLICY ANALYSIS")
    print("=" * 80)

    cursor.execute("""
        SELECT
            domain,
            policy_domain,
            policy_adkim,
            policy_aspf,
            policy_p,
            policy_sp,
            COUNT(*) as report_count
        FROM dmarc_reports
        GROUP BY domain, policy_p
        ORDER BY domain, report_count DESC
    """)

    policies = cursor.fetchall()

    if policies:
        print(f"\n📋 Current DMARC policies:\n")

        for policy in policies:
            print(f"{policy['domain']}:")
            print(f"   Policy: {policy['policy_p'] or 'none'}")
            print(f"   Subdomain Policy: {policy['policy_sp'] or 'same as domain'}")
            print(f"   DKIM Alignment: {policy['policy_adkim'] or 'relaxed'}")
            print(f"   SPF Alignment: {policy['policy_aspf'] or 'relaxed'}")
            print(f"   Reports analyzed: {policy['report_count']}")

            # Recommendation
            if policy['policy_p'] == 'none':
                print(f"   ⚠️  RECOMMENDATION: Consider upgrading to 'quarantine' or 'reject' for better protection")
            elif policy['policy_p'] == 'quarantine':
                print(f"   ✅ Good! Consider upgrading to 'reject' after monitoring")
            elif policy['policy_p'] == 'reject':
                print(f"   ✅ Excellent! Maximum DMARC protection enabled")
            print()

    print("=" * 80)
    print("END OF REPORT")
    print("=" * 80)

    conn.close()
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
