#!/usr/bin/env python3
"""
Enhanced Reporting Module for DMARC Monitor - Phase 2
Provides smart alerting and issue-focused reporting
"""

from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class EnhancedReporter:
    def __init__(self, config: Dict, database):
        """Initialize enhanced reporter with config and database"""
        self.config = config
        self.db = database
        self.thresholds = config.get('thresholds', {})
    
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
        """Create detailed report focusing on issues"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        total_reports = len(issues_reports) + len(clean_reports)
        
        # Get summary stats
        summary_stats = self.db.get_summary_stats()
        
        subject = f"{self.config['notifications']['email_subject_prefix']} ⚠️ Issues Detected - {len(issues_reports)} domains need attention"
        
        body = f"""
🚨 DMARC ISSUES DETECTED - {timestamp}
{'=' * 60}

EXECUTIVE SUMMARY
• Total Reports Analyzed: {total_reports}
• Reports with Issues: {len(issues_reports)}
• Clean Reports: {len(clean_reports)}
• Total Email Messages: {summary_stats['total_messages']:,}
• Average Authentication Rate: {summary_stats['avg_auth_rate']}%

DOMAINS REQUIRING ATTENTION
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
            
            body += f"""
{i}. {domain} (reported by {org_name})
{'-' * 50}
📊 Authentication Rate: {auth_rate:.1f}% ({successful_messages:,}/{total_messages:,} messages)
📈 Historical Trend: {historical_comparison['trend'].title()} ({historical_comparison['change']:+.1f}% vs 30-day avg)
⏰ Report Period: {report['raw_data']['metadata']['date_range']['begin']} to {report['raw_data']['metadata']['date_range']['end']}

🔍 ANALYSIS & RECOMMENDATIONS:
{self._extract_recommendations(report['claude_analysis'])}

"""
        
        # Add clean domains summary
        if clean_reports:
            body += f"""
✅ CLEAN DOMAINS ({len(clean_reports)} domains)
{'=' * 60}
The following domains showed no significant issues:
"""
            for report in clean_reports:
                domain = report['raw_data']['policy']['domain']
                total_messages = sum(record['count'] for record in report['raw_data']['records'])
                body += f"• {domain}: {total_messages:,} messages processed successfully\n"
        
        body += f"""

{'=' * 60}
📧 Report generated by DMARC Monitor at {timestamp}
🤖 Analysis powered by Claude AI with intelligent thresholds
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
        
        subject = f"{self.config['notifications']['email_subject_prefix']} ✅ All Clear - No Issues Detected"
        
        body = f"""
✅ ALL SYSTEMS HEALTHY - {timestamp}
{'=' * 60}

EXECUTIVE SUMMARY
• Total Reports Analyzed: {len(clean_reports)}
• All domains performing well
• Total Email Messages: {summary_stats['total_messages']:,}
• Average Authentication Rate: {summary_stats['avg_auth_rate']}%

DOMAIN STATUS
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
            
            body += f"""
✅ {domain} (reported by {org_name})
   📊 Authentication Rate: {auth_rate:.1f}% ({successful_messages:,}/{total_messages:,} messages)
   {trend_emoji} Trend: {historical_comparison['trend'].title()} ({historical_comparison['change']:+.1f}% vs 30-day avg)

"""
        
        body += f"""
{'=' * 60}
🛡️  All DMARC policies are working effectively
🎯 No action required at this time
📧 Report generated by DMARC Monitor at {timestamp}

Next scheduled check: As per your cron configuration
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