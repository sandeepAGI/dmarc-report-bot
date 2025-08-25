#!/usr/bin/env python3
"""
Non-Technical Report Formatter for DMARC Monitor
Provides plain English explanations and actionable guidance for small businesses
"""

from typing import Dict, List, Tuple
import re

class NonTechnicalFormatter:
    """Formats DMARC report data in plain English for non-technical users"""
    
    def __init__(self):
        self.risk_thresholds = {
            'critical': 70,  # Below 70% authentication
            'high': 80,      # 70-80% authentication  
            'moderate': 90,  # 80-90% authentication
            'low': 95        # 90-95% authentication
        }
    
    def get_risk_level(self, auth_rate: float) -> Tuple[str, str, str]:
        """Determine risk level based on authentication rate"""
        if auth_rate < self.risk_thresholds['critical']:
            return ('CRITICAL', '🔴', 'Immediate action required - Major email security issues')
        elif auth_rate < self.risk_thresholds['high']:
            return ('HIGH', '🟠', 'Action needed this week - Significant security gaps')
        elif auth_rate < self.risk_thresholds['moderate']:
            return ('MODERATE', '🟡', 'Schedule fixes soon - Some security issues')
        elif auth_rate < self.risk_thresholds['low']:
            return ('LOW', '🟢', 'Minor issues - Monitor and fix when convenient')
        else:
            return ('GOOD', '✅', 'Excellent - Email security working well')
    
    def explain_authentication_failure(self, dkim_fail: bool, spf_fail: bool) -> str:
        """Provide plain English explanation of authentication failures"""
        if dkim_fail and spf_fail:
            return "Email completely failed verification - likely spam or phishing using your domain name"
        elif dkim_fail:
            return "Email signature invalid - message may have been tampered with or sent from unauthorized service"
        elif spf_fail:
            return "Sender not on your approved list - email sent from unauthorized server"
        else:
            return "Email passed basic checks"
    
    def get_business_impact(self, auth_rate: float, total_messages: int) -> str:
        """Explain business impact of authentication failures"""
        failed_rate = 100 - auth_rate
        failed_count = int(total_messages * (failed_rate / 100))
        
        impacts = []
        
        if auth_rate < 70:
            impacts.append(f"⚠️ SEVERE: {failed_count} emails ({failed_rate:.0f}%) may be blocked or sent to spam")
            impacts.append("📧 Customer emails, invoices, and quotes might not be delivered")
            impacts.append("🚫 Major email providers (Gmail, Outlook) may block your domain entirely")
            impacts.append("💸 Potential loss of business due to undelivered communications")
        elif auth_rate < 85:
            impacts.append(f"⚠️ HIGH: {failed_count} emails ({failed_rate:.0f}%) at risk of spam filtering")
            impacts.append("📧 Important emails may end up in spam folders")
            impacts.append("🔍 Recipients becoming suspicious of legitimate emails")
            impacts.append("📉 Declining email reputation affecting deliverability")
        elif auth_rate < 95:
            impacts.append(f"⚠️ MODERATE: {failed_count} emails ({failed_rate:.0f}%) failed verification")
            impacts.append("📧 Some emails may be delayed or filtered")
            impacts.append("🔍 Email reputation needs improvement")
        else:
            impacts.append(f"✅ MINIMAL: Only {failed_count} emails ({failed_rate:.0f}%) had issues")
            impacts.append("📧 Email delivery working well overall")
            impacts.append("🛡️ Good protection against email spoofing")
        
        return '\n'.join(impacts)
    
    def analyze_ip_address(self, ip: str, org_info: str, dkim_result: str, spf_result: str, count: int) -> Dict:
        """Provide detailed analysis of an IP address with actionable guidance"""
        analysis = {
            'ip': ip,
            'summary': '',
            'legitimacy': '',
            'action': '',
            'confidence': '',
            'technical_note': f"DKIM: {dkim_result}, SPF: {spf_result}"
        }
        
        # Identify common email services
        if 'google' in org_info.lower() or 'gmail' in org_info.lower():
            analysis['summary'] = f"Google/Gmail Server - {count} email(s)"
            if spf_result != 'pass':
                analysis['legitimacy'] = "Legitimate Google server but not authorized in your SPF"
                analysis['action'] = 'ADD to SPF: "include:_spf.google.com" in your DNS records'
                analysis['confidence'] = "95% legitimate - Google's official servers"
            else:
                analysis['legitimacy'] = "Authorized Google server"
                analysis['action'] = "No action needed for this IP"
                analysis['confidence'] = "100% legitimate"
                
        elif 'microsoft' in org_info.lower() or 'outlook' in org_info.lower():
            analysis['summary'] = f"Microsoft/Office 365 Server - {count} email(s)"
            if spf_result != 'pass':
                analysis['legitimacy'] = "Microsoft server not properly authorized"
                analysis['action'] = 'ADD to SPF: "include:spf.protection.outlook.com" in your DNS'
                analysis['confidence'] = "95% legitimate - Microsoft's official servers"
            else:
                analysis['legitimacy'] = "Authorized Microsoft server"
                analysis['action'] = "No action needed"
                analysis['confidence'] = "100% legitimate"
                
        elif 'amazon' in org_info.lower() or 'aws' in org_info.lower():
            analysis['summary'] = f"Amazon AWS Server - {count} email(s)"
            analysis['legitimacy'] = "Could be legitimate (if you use email services) OR suspicious"
            analysis['action'] = """CHECK: Do you use any of these services?
   • Email marketing (MailChimp, SendGrid, Constant Contact)
   • CRM systems (Salesforce, HubSpot)
   • E-commerce platforms (Shopify, WooCommerce)
   If YES → Add their SPF records
   If NO → This is likely spam/phishing - monitor closely"""
            analysis['confidence'] = "Requires verification"
            
        elif self._is_suspicious_ip(ip, org_info):
            analysis['summary'] = f"⚠️ SUSPICIOUS SOURCE - {count} email(s)"
            analysis['legitimacy'] = "High probability of spam or phishing attempt"
            analysis['action'] = """INVESTIGATE IMMEDIATELY:
   1. Check if any accounts were compromised
   2. Review recent email activity
   3. Consider reporting to abuse@[your-email-provider]
   4. Monitor for continued attempts"""
            analysis['confidence'] = "90% suspicious - take action"
            
        else:
            analysis['summary'] = f"Unknown Server ({org_info}) - {count} email(s)"
            analysis['legitimacy'] = "Cannot determine - requires investigation"
            analysis['action'] = """INVESTIGATE:
   1. Check if this matches any services you use
   2. Review the time period - did you send emails then?
   3. If unrecognized, treat as suspicious"""
            analysis['confidence'] = "Needs verification"
        
        return analysis
    
    def _is_suspicious_ip(self, ip: str, org_info: str) -> bool:
        """Check if IP appears suspicious based on patterns"""
        suspicious_patterns = [
            'digital ocean', 'digitalocean', 'linode', 'vultr',
            'ovh', 'hetzner', 'residential', 'broadband',
            'cable', 'dsl', 'dynamic'
        ]
        
        org_lower = org_info.lower()
        
        # Check for residential/dynamic IPs
        if any(pattern in org_lower for pattern in suspicious_patterns):
            return True
            
        # Check for IPs from certain countries often associated with spam
        # This is a simplified check - you might want to use a proper geolocation service
        suspicious_ranges = [
            '185.',  # Often Eastern Europe  
            '195.',  # Often Eastern Europe
            '91.',   # Often Asia
            '103.',  # Often Asia-Pacific
        ]
        
        if any(ip.startswith(range_prefix) for range_prefix in suspicious_ranges):
            return True
            
        return False
    
    def format_diy_action_steps(self, domain: str, failures: List[Dict]) -> str:
        """Create step-by-step DIY instructions for fixing issues"""
        steps = []
        
        # Analyze what needs fixing
        needs_spf = any(f['spf_result'] != 'pass' for f in failures)
        needs_dkim = any(f['dkim_result'] != 'pass' for f in failures)
        has_suspicious = any(self._is_suspicious_ip(f['source_ip'], f.get('org_info', '')) for f in failures)
        
        if needs_spf:
            steps.append("""
📝 FIX YOUR SPF RECORD (Authorized Senders List):
   
   1. Log into your domain registrar (GoDaddy, Namecheap, etc.)
   2. Go to DNS Management / DNS Settings
   3. Find the TXT record that starts with "v=spf1"
   4. Based on the failed IPs above, add the needed includes:
      • For Google: add "include:_spf.google.com"
      • For Microsoft: add "include:spf.protection.outlook.com"
      • For email marketing: check your provider's SPF requirements
   5. Save changes (may take 1-24 hours to take effect)
   
   Example SPF record:
   "v=spf1 include:spf.protection.outlook.com include:_spf.google.com -all"
""")
        
        if needs_dkim:
            steps.append("""
🔐 FIX DKIM SIGNING (Email Signatures):
   
   1. Log into your email service (Office 365, Google Workspace)
   2. Go to Admin Center → Security → DKIM
   3. Enable DKIM signing for your domain
   4. Copy the DKIM records provided
   5. Add these as TXT records in your DNS (same place as SPF)
   6. Return to email service and verify DKIM
   
   Need help? Search: "[Your Email Provider] enable DKIM"
""")
        
        if has_suspicious:
            steps.append("""
🚨 HANDLE SUSPICIOUS SENDERS:
   
   IMMEDIATE ACTIONS:
   1. Change passwords for all email accounts
   2. Enable two-factor authentication
   3. Check sent folders for unauthorized emails
   4. Review email forwarding rules
   
   ONGOING MONITORING:
   • Watch for bounce-back messages you didn't send
   • Check if customers mention strange emails from you
   • Consider upgrading DMARC policy to 'quarantine' after fixes
""")
        
        if not needs_spf and not needs_dkim and not has_suspicious:
            steps.append("""
✅ MINOR TWEAKS NEEDED:
   
   Your email security is mostly working. Consider:
   1. Monitoring these reports weekly
   2. Documenting all legitimate email services you use
   3. Setting calendar reminder to review quarterly
""")
        
        return '\n'.join(steps)
    
    def format_plain_english_summary(self, auth_rate: float, total_messages: int, 
                                    failed_messages: int, unique_failures: int) -> str:
        """Create a plain English summary of the report"""
        risk_level, risk_icon, risk_desc = self.get_risk_level(auth_rate)
        
        if auth_rate >= 95:
            tone = "good news"
            action = "minor maintenance"
        elif auth_rate >= 85:
            tone = "attention needed"
            action = "some fixes required"
        else:
            tone = "urgent attention required"
            action = "immediate action needed"
        
        summary = f"""
{risk_icon} RISK LEVEL: {risk_level}
{'=' * 60}

WHAT WE CHECKED:
✉️ Analyzed {total_messages} emails sent using your company name
{'✅' if auth_rate >= 95 else '⚠️'} {auth_rate:.1f}% passed security verification
{'🔍' if failed_messages > 0 else '✅'} {failed_messages} emails couldn't be verified as legitimate
{'📍' if unique_failures > 0 else '✅'} Found {unique_failures} different sources of concern

THE {tone.upper()}:
{risk_desc}

Time needed to fix: {'15-30 minutes' if auth_rate >= 85 else '30-60 minutes'}
Technical difficulty: {'Low' if auth_rate >= 90 else 'Medium'} (follow our step-by-step guide)
Business priority: {risk_level}
"""
        
        return summary
    
    def create_hybrid_report_section(self, domain: str, report_data: Dict, 
                                    failure_details: List[Dict]) -> str:
        """Create a hybrid report section with both plain English and technical details"""
        total_messages = sum(record['count'] for record in report_data['records'])
        failed_messages = sum(d['count'] for d in failure_details)
        auth_rate = ((total_messages - failed_messages) / total_messages * 100) if total_messages > 0 else 100
        
        # Plain English section
        section = "🔍 PLAIN ENGLISH EXPLANATION\n"
        section += "-" * 40 + "\n"
        section += self.format_plain_english_summary(auth_rate, total_messages, 
                                                     failed_messages, len(failure_details))
        
        # Business Impact
        section += "\n📊 BUSINESS IMPACT\n"
        section += "-" * 40 + "\n"
        section += self.get_business_impact(auth_rate, total_messages)
        
        # Detailed IP Analysis
        if failure_details:
            section += "\n\n🔎 WHO'S SENDING FAILED EMAILS?\n"
            section += "-" * 40 + "\n"
            
            for detail in failure_details:
                ip_analysis = self.analyze_ip_address(
                    detail['source_ip'],
                    detail.get('org_info', 'Unknown'),
                    detail['dkim_result'],
                    detail['spf_result'],
                    detail['count']
                )
                
                section += f"\n📍 {ip_analysis['summary']}\n"
                section += f"   Status: {ip_analysis['legitimacy']}\n"
                section += f"   Action: {ip_analysis['action']}\n"
                section += f"   Confidence: {ip_analysis['confidence']}\n"
                section += f"   Technical: {ip_analysis['technical_note']}\n"
        
        # DIY Action Steps
        section += "\n\n🛠️ HOW TO FIX THESE ISSUES\n"
        section += "-" * 40
        section += self.format_diy_action_steps(domain, failure_details)
        
        return section