#!/usr/bin/env python3
"""
Enhanced Reporting Module for DMARC Monitor - Phase 2
Provides smart alerting and issue-focused reporting with non-technical explanations
"""

from datetime import datetime
from typing import Dict, List, Optional
import logging
from non_technical_formatter import NonTechnicalFormatter

logger = logging.getLogger(__name__)

class EnhancedReporter:
    def __init__(self, config: Dict, database):
        """Initialize enhanced reporter with config and database"""
        self.config = config
        self.db = database
        self.thresholds = config.get('thresholds', {})
        self.formatter = NonTechnicalFormatter()
    
    def generate_smart_report(self, analyzed_reports: List[Dict]) -> Dict:
        """Generate intelligent report based on issues and thresholds"""
        if not analyzed_reports:
            return self._create_no_reports_summary()
        
        # Categorize reports
        reports_with_issues = []
        clean_reports = []
        
        for report in analyzed_reports:
            # Check if report has issues (database storage handled in main script)
            if self._has_significant_issues(report):
                reports_with_issues.append(report)
            else:
                clean_reports.append(report)
        
        # Generate appropriate report
        if reports_with_issues:
            return self._create_issues_report(reports_with_issues, clean_reports)
        elif self.config['notifications'].get('send_clean_status', True):
            return self._create_clean_status_report(clean_reports)
        else:
            return None  # No report needed
    
    def _has_significant_issues(self, report: Dict) -> bool:
        """Check if a report has significant issues worth alerting about"""
        raw_data = report['raw_data']
        claude_analysis = report['claude_analysis']
        
        # Calculate authentication success rate
        total_messages = sum(record['count'] for record in raw_data['records'])
        if total_messages < self.thresholds.get('minimum_messages_for_alert', 10):
            return False  # Skip reports with very few messages
        
        successful_messages = sum(
            record['count'] for record in raw_data['records']
            if record['dkim'] == 'pass' and record['spf'] == 'pass'
        )
        auth_success_rate = (successful_messages / total_messages) * 100 if total_messages > 0 else 100
        
        # Check thresholds
        if auth_success_rate < self.thresholds.get('auth_success_rate_min', 95.0):
            return True
        
        # Check for historical decline
        domain = raw_data['policy']['domain']
        historical_comparison = self.db.compare_with_historical(domain, auth_success_rate)
        if abs(historical_comparison['change']) >= self.thresholds.get('auth_rate_drop_threshold', 5.0):
            return True
        
        # Check for new/suspicious sources
        new_sources = len(set(record['source_ip'] for record in raw_data['records']))
        historical_data = self.db.get_historical_data(domain, days_back=7)
        if historical_data:
            avg_sources = sum(r['new_sources_detected'] for r in historical_data) / len(historical_data)
            if new_sources > avg_sources + self.thresholds.get('new_sources_threshold', 3):
                return True
        
        # Check Claude analysis for issue indicators with better context
        issue_keywords = ['issue', 'problem', 'fail', 'suspicious', 'error', 'warning', '⚠️', '❌']
        positive_keywords = ['none detected', 'no issues', 'perfect', 'healthy', 'working well', 'no problems', 
                           'perfect scores', 'all clear', 'success', 'passing', 'legitimate']

        analysis_lower = claude_analysis.lower()

        # Don't flag as issue if positive indicators are present
        if any(positive in analysis_lower for positive in positive_keywords):
            return False

        # Only flag if issue keywords are present without positive context
        if any(keyword in analysis_lower for keyword in issue_keywords):
            return True
        
        return False
    
    def _create_issues_report(self, issues_reports: List[Dict], clean_reports: List[Dict]) -> Dict:
        """Create detailed report focusing on issues with hybrid format"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_reports = len(issues_reports) + len(clean_reports)
        
        # Get summary stats
        summary_stats = self.db.get_summary_stats()
        
        # Calculate overall risk level
        avg_auth_rate = summary_stats['avg_auth_rate']
        risk_level, risk_icon, risk_desc = self.formatter.get_risk_level(float(avg_auth_rate))
        
        subject = f"{self.config['notifications']['email_subject_prefix']} {risk_icon} {risk_level} Risk - {len(issues_reports)} domains need attention"
        
        body = f"""
🚨 DMARC SECURITY REPORT - {timestamp}
{'=' * 60}

{risk_icon} OVERALL RISK LEVEL: {risk_level}
{risk_desc}

QUICK SUMMARY FOR BUSINESS OWNER
{'=' * 60}
📊 Checked: {total_reports} domain reports ({summary_stats['total_messages']:,} emails)
⚠️ Problems Found: {len(issues_reports)} domains with issues
✅ Working Well: {len(clean_reports)} domains without issues
📈 Overall Security Score: {summary_stats['avg_auth_rate']}%

WHAT THIS MEANS FOR YOUR BUSINESS
{'=' * 60}
{self.formatter.get_business_impact(float(avg_auth_rate), summary_stats['total_messages'])}

DOMAINS REQUIRING YOUR ATTENTION
{'=' * 60}
"""
        
        # Add detailed analysis for problematic domains
        for i, report in enumerate(issues_reports, 1):
            domain = report['raw_data']['policy']['domain']
            org_name = report['raw_data']['metadata']['org_name']
            
            # Get historical comparison
            total_messages = sum(record['count'] for record in report['raw_data']['records'])
            successful_messages = sum(
                record['count'] for record in report['raw_data']['records']
                if record['dkim'] == 'pass' and record['spf'] == 'pass'
            )
            auth_rate = (successful_messages / total_messages) * 100 if total_messages > 0 else 100
            
            historical_comparison = self.db.compare_with_historical(domain, auth_rate)
            
            # Get risk level for this specific domain
            domain_risk_level, domain_risk_icon, domain_risk_desc = self.formatter.get_risk_level(auth_rate)
            
            body += f"""
{i}. {domain} (reported by {org_name}) {domain_risk_icon} {domain_risk_level} RISK
{'-' * 50}

📊 QUICK STATS:
• Security Score: {auth_rate:.1f}% ({successful_messages:,} passed / {total_messages:,} total emails)
• Trend: {historical_comparison['trend'].title()} ({historical_comparison['change']:+.1f}% vs last month)
• Period: {report['raw_data']['metadata']['date_range']['begin']} to {report['raw_data']['metadata']['date_range']['end']}
"""
            
            # Add hybrid analysis section
            db_report_id = report.get('db_report_id')
            if db_report_id:
                failure_details = self.db.get_failure_details(domain, db_report_id)
                if failure_details:
                    # Add enhanced failure details with IP intelligence
                    for detail in failure_details:
                        # Enhance with organization info
                        ip_intel = self.db.get_ip_intelligence(detail['source_ip'])
                        detail['org_info'] = ip_intel['organization']
                    
                    hybrid_section = self.formatter.create_hybrid_report_section(
                        domain, 
                        report['raw_data'],
                        failure_details
                    )
                    body += f"\n{hybrid_section}\n"
            
            # Add Claude's enhanced analysis
            body += f"""

📋 TECHNICAL ANALYSIS FROM AI:
{'-' * 40}
{self._extract_enhanced_recommendations(report['claude_analysis'])}

"""
        
        # Add clean domains summary
        if clean_reports:
            body += f"""
✅ DOMAINS WORKING WELL ({len(clean_reports)} domains)
{'=' * 60}
The following domains showed no significant issues:
"""
            for report in clean_reports:
                domain = report['raw_data']['policy']['domain']
                total_messages = sum(record['count'] for record in report['raw_data']['records'])
                body += f"• {domain}: {total_messages:,} messages processed successfully\n"
        
        # Add action summary
        body += f"""

🎯 ACTION SUMMARY - WHAT TO DO NOW
{'=' * 60}
1. Review each domain's risk level above
2. For HIGH/CRITICAL risks: Take action TODAY
3. For MODERATE risks: Schedule fixes this week
4. Follow the step-by-step DIY instructions provided
5. Save this report for your records

Need help? Options:
• Follow the DIY steps above (most issues can be self-resolved)
• Contact your domain registrar's support (GoDaddy, Namecheap, etc.)
• Forward to a tech-savvy friend or consultant
• Search online for: "[Your email provider] DKIM SPF setup guide"

{'=' * 60}
📧 Report generated by DMARC Monitor at {timestamp}
🤖 Enhanced analysis with plain English explanations
💡 Designed for small businesses without IT departments
"""
        
        return {
            'subject': subject,
            'body': body,
            'has_issues': True,
            'issue_count': len(issues_reports)
        }
    
    def _create_clean_status_report(self, clean_reports: List[Dict]) -> Dict:
        """Create clean status report when no issues are found"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        summary_stats = self.db.get_summary_stats()
        
        subject = f"{self.config['notifications']['email_subject_prefix']} ✅ All Clear - Email Security Working Well"
        
        body = f"""
✅ GOOD NEWS - YOUR EMAIL SECURITY IS WORKING! - {timestamp}
{'=' * 60}

PLAIN ENGLISH SUMMARY
{'=' * 60}
🎉 Great news! Your email security passed all checks.
📧 We verified {summary_stats['total_messages']:,} emails from your domain(s)
✅ {summary_stats['avg_auth_rate']}% passed authentication (excellent!)
🛡️ Your emails are being delivered properly and protected from spoofing

WHAT THIS MEANS FOR YOUR BUSINESS
{'=' * 60}
• ✅ Your legitimate emails are reaching customers
• ✅ Your domain is protected from email spoofing
• ✅ Email providers (Gmail, Outlook) trust your domain
• ✅ No immediate action required

YOUR DOMAINS - ALL PERFORMING WELL
{'=' * 60}
"""
        
        for report in clean_reports:
            domain = report['raw_data']['policy']['domain']
            org_name = report['raw_data']['metadata']['org_name']
            total_messages = sum(record['count'] for record in report['raw_data']['records'])
            successful_messages = sum(
                record['count'] for record in report['raw_data']['records']
                if record['dkim'] == 'pass' and record['spf'] == 'pass'
            )
            auth_rate = (successful_messages / total_messages) * 100 if total_messages > 0 else 100
            
            # Get trend info
            historical_comparison = self.db.compare_with_historical(domain, auth_rate)
            trend_emoji = "📈" if historical_comparison['trend'] == 'improved' else "📊" if historical_comparison['trend'] == 'stable' else "📉"
            
            # Get last failure date for historical context
            last_failure_date = self.db.get_last_failure_date(domain)
            failure_context = f"   🛡️ No failures detected since {last_failure_date}" if last_failure_date else "   🛡️ No failures detected in monitoring history"
            
            body += f"""
✅ {domain} (reported by {org_name})
   📊 Authentication Rate: {auth_rate:.1f}% ({successful_messages:,}/{total_messages:,} messages)
   {trend_emoji} Trend: {historical_comparison['trend'].title()} ({historical_comparison['change']:+.1f}% vs 30-day avg)
{failure_context}

"""
        
        body += f"""

RECOMMENDATIONS FOR CONTINUED SUCCESS
{'=' * 60}
Even though everything looks good, here are best practices:

1. 📅 Keep monitoring these reports weekly
2. 📝 Document any new email services you start using
3. 🔄 If you add new email tools (marketing, CRM), update your SPF record
4. 💾 Save these reports for your records
5. 📈 Consider strengthening your DMARC policy from 'none' to 'quarantine' 
   (This provides even better protection - consult documentation when ready)

{'=' * 60}
📧 Report generated by DMARC Monitor at {timestamp}
🤖 Enhanced analysis for small businesses
💚 Your email security is in good shape!

Next scheduled check: Tomorrow at 10 AM (or as configured)
"""
        
        return {
            'subject': subject,
            'body': body,
            'has_issues': False,
            'clean_count': len(clean_reports)
        }
    
    def _create_no_reports_summary(self) -> Dict:
        """Create summary when no DMARC reports were found"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        subject = f"{self.config['notifications']['email_subject_prefix']} 📭 No New DMARC Reports"
        
        body = f"""
📭 NO NEW REPORTS - {timestamp}
{'=' * 60}

STATUS
• No new DMARC reports found since last check
• System is monitoring normally
• All configured email folders checked

RECENT ACTIVITY
{'=' * 60}
"""
        
        # Get recent summary from database
        recent_issues = self.db.get_recent_issues(hours_back=72)  # Last 3 days
        if recent_issues:
            body += f"Recent issues (last 3 days): {len(recent_issues)} domains had issues\n"
        else:
            body += "No issues detected in the last 3 days\n"
        
        body += f"""

{'=' * 60}
🔍 DMARC Monitor is actively checking for new reports
📧 Report generated at {timestamp}
"""
        
        return {
            'subject': subject,
            'body': body,
            'has_issues': False,
            'no_reports': True
        }
    
    def _get_detailed_failure_analysis(self, report: Dict) -> str:
        """Generate detailed failure analysis for reports with authentication issues"""
        domain = report['raw_data']['policy']['domain']
        db_report_id = report.get('db_report_id')
        
        if not db_report_id:
            return ""
        
        # Get failure details from database
        failure_details = self.db.get_failure_details(domain, db_report_id)
        
        if not failure_details:
            return ""
        
        failure_analysis = "🔍 DETAILED FAILURE ANALYSIS:\n\n"
        failure_analysis += "  Failed Authentication Details:\n"
        
        total_failed_messages = sum(detail['count'] for detail in failure_details)
        failure_analysis += f"  • {len(failure_details)} IP(s) with {total_failed_messages} failed message(s)\n\n"
        
        # Group failures and add IP intelligence
        for detail in failure_details:
            ip = detail['source_ip']
            count = detail['count']
            dkim_status = "❌ FAIL" if detail['dkim_result'] != 'pass' else "✅ PASS"
            spf_status = "❌ FAIL" if detail['spf_result'] != 'pass' else "✅ PASS"
            
            # Get IP intelligence
            ip_intel = self.db.get_ip_intelligence(ip)
            org_info = ip_intel['organization']
            
            # Add warning for suspicious IPs
            warning = " ⚠️ INVESTIGATE" if ip_intel['is_suspicious'] else ""
            
            failure_analysis += f"  • {ip}: {count} message(s) - DKIM {dkim_status}, SPF {spf_status}\n"
            failure_analysis += f"    └─ {org_info}{warning}\n"
        
        # Add actionable recommendations based on failure patterns
        failure_analysis += "\n  📋 RECOMMENDED ACTIONS:\n"
        
        # Check if all failures are from same IP range
        ip_prefixes = set('.'.join(detail['source_ip'].split('.')[0:2]) for detail in failure_details)
        if len(ip_prefixes) == 1:
            prefix = list(ip_prefixes)[0] + ".x.x"
            failure_analysis += f"  1. **Investigate IP range {prefix}:** All failures from same subnet\n"
        else:
            failure_analysis += f"  1. **Investigate {len(failure_details)} different IP sources:** Multiple failure points detected\n"
        
        # Check failure types
        dkim_failures = [d for d in failure_details if d['dkim_result'] != 'pass']
        spf_failures = [d for d in failure_details if d['spf_result'] != 'pass']
        
        if dkim_failures:
            failure_analysis += f"  2. **DKIM Issues:** {len(dkim_failures)} IP(s) failing DKIM - check signing configuration\n"
        if spf_failures:
            failure_analysis += f"  3. **SPF Issues:** {len(spf_failures)} IP(s) failing SPF - verify authorized senders\n"
        
        # Add specific investigation steps
        failure_analysis += f"  4. **Verification Steps:**\n"
        failure_analysis += f"     - Check SPF record: dig TXT {domain} | grep spf\n"
        failure_analysis += f"     - Verify these IPs are legitimate senders for {domain}\n"
        failure_analysis += f"     - If legitimate: update SPF record and configure DKIM\n"
        failure_analysis += f"     - If malicious: consider abuse reporting\n"
        
        return failure_analysis
    
    def _extract_recommendations(self, claude_analysis: str) -> str:
        """Extract and format recommendations from Claude analysis"""
        lines = claude_analysis.split('\n')
        recommendations = []
        in_recommendations = False
        
        for line in lines:
            line = line.strip()
            if 'recommendation' in line.lower() or 'action' in line.lower():
                in_recommendations = True
                continue
            
            if in_recommendations and line:
                if line.startswith(('•', '-', '*', '1.', '2.', '3.')):
                    recommendations.append(f"  {line}")
                elif line.startswith(('Overall', 'Authentication', 'Source', 'Issues')):
                    break  # End of recommendations section
                else:
                    recommendations.append(f"  • {line}")
        
        if recommendations:
            return '\n'.join(recommendations)
        
        # Fallback: return key insights from analysis
        key_lines = [line.strip() for line in lines if any(keyword in line.lower() 
                    for keyword in ['pass', 'fail', 'issue', 'recommend', 'should', 'update'])]
        return '\n'.join(f"  • {line}" for line in key_lines[-3:]) if key_lines else "See detailed analysis above."
    
    def _extract_enhanced_recommendations(self, claude_analysis: str) -> str:
        """Extract and format Claude's enhanced analysis with IP investigations"""
        # Claude's analysis should now include IP investigations and DIY steps
        # Just format it nicely for display
        lines = claude_analysis.split('\n')
        formatted_lines = []
        
        for line in lines:
            line = line.strip()
            if line:
                # Keep headers as-is
                if line.startswith('**') and line.endswith('**'):
                    formatted_lines.append(line)
                # Format list items
                elif line.startswith(('•', '-', '*', '1.', '2.', '3.', '4.', '5.')):
                    formatted_lines.append(f"  {line}")
                # Regular lines
                else:
                    formatted_lines.append(line)
        
        return '\n'.join(formatted_lines) if formatted_lines else claude_analysis
    
    def should_send_report(self, report_data: Optional[Dict]) -> bool:
        """Determine if a report should be sent based on configuration"""
        if not report_data:
            return False
        
        # Always send if there are issues
        if report_data.get('has_issues', False):
            return True
        
        # Send clean status if configured
        if self.config['notifications'].get('send_clean_status', True):
            return True
        
        # Send no-reports notification if not in quiet mode
        if report_data.get('no_reports', False) and not self.config['notifications'].get('quiet_mode', True):
            return True
        
        return False