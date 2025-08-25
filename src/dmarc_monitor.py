#!/usr/bin/env python3
"""
DMARC Report Monitor - Phase 2 Enhanced Version
Monitors Outlook mailbox for DMARC reports with intelligent alerting and historical analysis
"""

import os
import json
import gzip
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import requests
import logging
import time
from database import DMARCDatabase
from enhanced_reporting import EnhancedReporter

def load_config():
    """Load configuration from config file"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    config_path = os.path.join(project_root, 'config', 'config.json')
    
    if not os.path.exists(config_path):
        print(f"ERROR: Configuration file not found: {config_path}")
        print("Please copy config.json.template to config.json and fill in your credentials")
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Validate required fields
        required_fields = [
            ('microsoft', 'client_id'),
            ('microsoft', 'client_secret'),
            ('microsoft', 'tenant_id'),
            ('claude', 'api_key')
        ]
        
        for section, field in required_fields:
            if section not in config or field not in config[section]:
                raise ValueError(f"Missing required configuration: {section}.{field}")
            
            value = config[section][field]
            if not value or (isinstance(value, str) and value.startswith('YOUR_')):
                raise ValueError(f"Please configure {section}.{field} in {config_path}")
        
        print("Configuration loaded successfully")
        return config
        
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in configuration file: {e}")
        raise
    except Exception as e:
        print(f"ERROR: Error loading configuration: {e}")
        raise

# Load configuration first
CONFIG = load_config()

# Setup logging
def setup_logging(config):
    """Setup logging configuration"""
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO').upper())
    log_file = log_config.get('file', 'logs/dmarc_monitor.log')
    
    # Ensure log directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging(CONFIG)

class OutlookClient:
    def __init__(self, config):
        self.config = config
        self.access_token = None
        self.token_file = 'outlook_token.json'
        
    def get_access_token(self):
        """Get or refresh access token"""
        if os.path.exists(self.token_file):
            with open(self.token_file, 'r') as f:
                token_data = json.load(f)
                
            # Check if token is still valid (with 5-minute buffer)
            expires_at = datetime.fromisoformat(token_data.get('expires_at', '2000-01-01'))
            if datetime.now() < expires_at - timedelta(minutes=5):
                self.access_token = token_data['access_token']
                return True
                
            # Try to refresh token
            if 'refresh_token' in token_data:
                if self._refresh_token(token_data['refresh_token']):
                    return True
        
        # Need to get new token
        return self._get_new_token()
    
    def _get_new_token(self):
        """Get new access token via authorization code flow"""
        import webbrowser
        import urllib.parse
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import threading
        
        # Authorization URL
        auth_url = f"https://login.microsoftonline.com/{self.config['tenant_id']}/oauth2/v2.0/authorize"
        params = {
            'client_id': self.config['client_id'],
            'response_type': 'code',
            'redirect_uri': self.config['redirect_uri'],
            'scope': 'https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send offline_access',
            'response_mode': 'query'
        }
        
        auth_url_with_params = f"{auth_url}?{urllib.parse.urlencode(params)}"
        
        # Set up local server to receive callback
        authorization_code = None
        server_error = None
        
        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                nonlocal authorization_code, server_error
                
                if self.path.startswith('/callback'):
                    query = urllib.parse.urlparse(self.path).query
                    params = urllib.parse.parse_qs(query)
                    
                    if 'code' in params:
                        authorization_code = params['code'][0]
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(b'''
                        <html><body>
                        <h2>Authorization successful!</h2>
                        <p>You can close this window and return to the terminal.</p>
                        </body></html>
                        ''')
                    else:
                        server_error = params.get('error_description', ['Unknown error'])[0]
                        self.send_response(400)
                        self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        self.wfile.write(f'<html><body><h2>Error: {server_error}</h2></body></html>'.encode())
                
            def log_message(self, format, *args):
                pass  # Suppress log messages
        
        # Start local server
        server = HTTPServer(('localhost', 8080), CallbackHandler)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        print(f"\nOpening browser for authentication...")
        print(f"If the browser doesn't open automatically, go to:")
        print(f"{auth_url_with_params}")
        print("Waiting for authorization...")
        
        # Open browser
        webbrowser.open(auth_url_with_params)
        
        # Wait for callback
        import time
        timeout = 300  # 5 minutes
        start_time = time.time()
        
        while authorization_code is None and server_error is None:
            if time.time() - start_time > timeout:
                server.shutdown()
                logger.error("Authentication timeout")
                return False
            time.sleep(1)
        
        server.shutdown()
        
        if server_error:
            logger.error(f"Authentication error: {server_error}")
            return False
        
        if not authorization_code:
            logger.error("No authorization code received")
            return False
        
        # Exchange code for token (confidential client)
        token_url = f"https://login.microsoftonline.com/{self.config['tenant_id']}/oauth2/v2.0/token"
        token_data = {
            'grant_type': 'authorization_code',
            'client_id': self.config['client_id'],
            'client_secret': self.config['client_secret'],  # Include client_secret for confidential client
            'code': authorization_code,
            'redirect_uri': self.config['redirect_uri'],
            'scope': 'https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send offline_access'
        }
        
        response = requests.post(token_url, data=token_data)
        
        if response.status_code == 200:
            token_info = response.json()
            # Save token
            token_info['expires_at'] = (datetime.now() + timedelta(seconds=token_info['expires_in'])).isoformat()
            with open(self.token_file, 'w') as f:
                json.dump(token_info, f)
            
            self.access_token = token_info['access_token']
            logger.info("Successfully authenticated with Microsoft Graph")
            return True
        else:
            logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
            return False
    
    def _refresh_token(self, refresh_token):
        """Refresh access token (confidential client)"""
        token_url = f"https://login.microsoftonline.com/{self.config['tenant_id']}/oauth2/v2.0/token"
        
        data = {
            'grant_type': 'refresh_token',
            'client_id': self.config['client_id'],
            'client_secret': self.config['client_secret'],
            'refresh_token': refresh_token
        }
        
        response = requests.post(token_url, data=data)
        
        if response.status_code == 200:
            token_data = response.json()
            token_data['expires_at'] = (datetime.now() + timedelta(seconds=token_data['expires_in'])).isoformat()
            
            with open(self.token_file, 'w') as f:
                json.dump(token_data, f)
            
            self.access_token = token_data['access_token']
            return True
        
        return False
    
    def get_messages(self, folder_name, hours_back=24):
        """Get messages from specified folder"""
        if not self.access_token:
            raise Exception("Not authenticated")
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        
        # Get folder ID
        folders_url = "https://graph.microsoft.com/v1.0/me/mailFolders"
        folders_response = requests.get(folders_url, headers=headers)
        
        folder_id = None
        for folder in folders_response.json().get('value', []):
            if folder['displayName'] == folder_name:
                folder_id = folder['id']
                break
        
        if not folder_id:
            logger.warning(f"Folder '{folder_name}' not found")
            return []
        
        # Get messages from last N hours
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        filter_query = f"receivedDateTime ge {cutoff_time.isoformat()}Z"
        
        messages_url = f"https://graph.microsoft.com/v1.0/me/mailFolders/{folder_id}/messages"
        params = {
            '$filter': filter_query,
            '$select': 'id,subject,receivedDateTime,hasAttachments,from',
            '$orderby': 'receivedDateTime desc'
        }
        
        response = requests.get(messages_url, headers=headers, params=params)
        return response.json().get('value', [])
    
    def get_attachments(self, message_id):
        """Get attachments from a message"""
        if not self.access_token:
            raise Exception("Not authenticated")
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        attachments_url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments"
        
        response = requests.get(attachments_url, headers=headers)
        return response.json().get('value', [])

    def send_email(self, to_email, subject, body):
        """Send email via Microsoft Graph API"""
        if not self.access_token:
            raise Exception("Not authenticated")
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        email_data = {
            'message': {
                'subject': subject,
                'body': {
                    'contentType': 'Text',
                    'content': body
                },
                'toRecipients': [
                    {
                        'emailAddress': {
                            'address': to_email
                        }
                    }
                ]
            }
        }
        
        send_url = "https://graph.microsoft.com/v1.0/me/sendMail"
        response = requests.post(send_url, headers=headers, json=email_data)
        
        if response.status_code == 202:
            logger.info("Email sent successfully via Outlook")
            return True
        else:
            logger.error(f"Failed to send email: {response.status_code} - {response.text}")
            return False

class DMARCParser:
    @staticmethod
    def parse_xml_content(xml_content):
        """Parse DMARC XML report"""
        try:
            root = ET.fromstring(xml_content)
            
            # Extract metadata
            metadata = {
                'org_name': root.find('.//org_name').text if root.find('.//org_name') is not None else 'Unknown',
                'email': root.find('.//email').text if root.find('.//email') is not None else 'Unknown',
                'report_id': root.find('.//report_id').text if root.find('.//report_id') is not None else 'Unknown',
                'date_range': {
                    'begin': root.find('.//date_range/begin').text if root.find('.//date_range/begin') is not None else 'Unknown',
                    'end': root.find('.//date_range/end').text if root.find('.//date_range/end') is not None else 'Unknown'
                }
            }
            
            # Extract policy
            policy = {
                'domain': root.find('.//policy_published/domain').text if root.find('.//policy_published/domain') is not None else 'Unknown',
                'p': root.find('.//policy_published/p').text if root.find('.//policy_published/p') is not None else 'none',
                'sp': root.find('.//policy_published/sp').text if root.find('.//policy_published/sp') is not None else 'none',
                'pct': root.find('.//policy_published/pct').text if root.find('.//policy_published/pct') is not None else '100'
            }
            
            # Extract records
            records = []
            for record in root.findall('.//record'):
                source_ip = record.find('.//source_ip').text if record.find('.//source_ip') is not None else 'Unknown'
                count = record.find('.//count').text if record.find('.//count') is not None else '0'
                
                # Policy evaluation
                disposition = record.find('.//disposition').text if record.find('.//disposition') is not None else 'none'
                dkim_result = record.find('.//dkim').text if record.find('.//dkim') is not None else 'unknown'
                spf_result = record.find('.//spf').text if record.find('.//spf') is not None else 'unknown'
                
                records.append({
                    'source_ip': source_ip,
                    'count': int(count),
                    'disposition': disposition,
                    'dkim': dkim_result,
                    'spf': spf_result
                })
            
            return {
                'metadata': metadata,
                'policy': policy,
                'records': records
            }
            
        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing DMARC report: {e}")
            return None

class ClaudeAnalyzer:
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model
        
    def analyze_dmarc_report(self, parsed_report):
        """Send DMARC report to Claude for analysis"""
        prompt = f"""
Please analyze this DMARC report and provide a clear, actionable summary for a small business owner without IT staff:

REPORT METADATA:
- Organization: {parsed_report['metadata']['org_name']}
- Report ID: {parsed_report['metadata']['report_id']}
- Date Range: {parsed_report['metadata']['date_range']['begin']} to {parsed_report['metadata']['date_range']['end']}

POLICY:
- Domain: {parsed_report['policy']['domain']}
- Policy: {parsed_report['policy']['p']}
- Subdomain Policy: {parsed_report['policy']['sp']}
- Percentage: {parsed_report['policy']['pct']}%

RECORDS:
{json.dumps(parsed_report['records'], indent=2)}

Please provide:
1. **Overall Status**: Pass/fail summary and key metrics
2. **Authentication Results**: DKIM and SPF performance 
3. **IP Investigation**: For each IP address, identify:
   - Who owns it (Google, Microsoft, AWS, suspicious sources, etc.)
   - Whether it's likely legitimate or suspicious
   - If it's a known email service (Gmail, Office 365, MailChimp, SendGrid, etc.)
   - Specific action needed (add to SPF, investigate further, block, etc.)
4. **Issues Found**: Any authentication failures or policy violations IN PLAIN ENGLISH
5. **DIY Recommendations**: Step-by-step actions the business owner can take themselves:
   - Specific DNS records to add/modify
   - Which service providers to contact
   - What settings to check in their email service
   - Red flags that require immediate attention

Focus on actionable insights a non-technical person can understand and implement.
For each failed IP, explain WHO it likely is and WHAT to do about it.
"""

        headers = {
            'Content-Type': 'application/json',
            'x-api-key': self.api_key,
            'anthropic-version': '2023-06-01'
        }
        
        data = {
            'model': self.model,
            'max_tokens': 1000,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt
                }
            ]
        }
        
        # Retry logic with exponential backoff
        max_retries = 3
        retry_delays = [2, 4, 8]  # seconds
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    'https://api.anthropic.com/v1/messages',
                    headers=headers,
                    json=data,
                    timeout=45  # Increased timeout to 45 seconds
                )
                
                if response.status_code == 200:
                    return response.json()['content'][0]['text']
                elif response.status_code == 429:  # Rate limit
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        logger.warning(f"Rate limited by Claude API, retrying in {delay} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        logger.error(f"Claude API rate limit exceeded after {max_retries} attempts")
                        return self._get_fallback_analysis(parsed_report)
                else:
                    logger.error(f"Claude API error: {response.status_code} - {response.text}")
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        logger.info(f"Retrying Claude API call in {delay} seconds (attempt {attempt + 2}/{max_retries})...")
                        time.sleep(delay)
                        continue
                    else:
                        return self._get_fallback_analysis(parsed_report)
                        
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.warning(f"Claude API timeout, retrying in {delay} seconds (attempt {attempt + 2}/{max_retries})...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Claude API timeout after {max_retries} attempts")
                    return self._get_fallback_analysis(parsed_report)
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    delay = retry_delays[attempt]
                    logger.warning(f"Error calling Claude API: {e}, retrying in {delay} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    logger.error(f"Error calling Claude API after {max_retries} attempts: {e}")
                    return self._get_fallback_analysis(parsed_report)
        
        # Should not reach here, but just in case
        return self._get_fallback_analysis(parsed_report)
    
    def _get_fallback_analysis(self, parsed_report):
        """Provide basic analysis when Claude API is unavailable"""
        logger.info("Using fallback analysis due to Claude API unavailability")
        
        domain = parsed_report['policy']['domain']
        total_messages = sum(record['count'] for record in parsed_report['records'])
        failed_messages = sum(
            record['count'] for record in parsed_report['records']
            if record['dkim'] != 'pass' or record['spf'] != 'pass'
        )
        auth_rate = ((total_messages - failed_messages) / total_messages * 100) if total_messages > 0 else 100
        
        # Identify failed IPs
        failed_ips = []
        for record in parsed_report['records']:
            if record['dkim'] != 'pass' or record['spf'] != 'pass':
                failed_ips.append({
                    'ip': record['source_ip'],
                    'count': record['count'],
                    'dkim': record['dkim'],
                    'spf': record['spf']
                })
        
        # Build fallback analysis
        analysis = f"""
**Overall Status**: {'✅ PASS' if auth_rate >= 95 else '⚠️ NEEDS ATTENTION' if auth_rate >= 80 else '❌ CRITICAL'}
- Authentication Rate: {auth_rate:.1f}% ({total_messages - failed_messages}/{total_messages} messages)
- Domain: {domain}
- Report Period: {parsed_report['metadata']['date_range']['begin']} to {parsed_report['metadata']['date_range']['end']}

**Authentication Results**:
- Total Messages: {total_messages}
- Passed: {total_messages - failed_messages}
- Failed: {failed_messages}
"""
        
        if failed_ips:
            analysis += "\n**IP Investigation**: (AI analysis unavailable - showing raw data)\n"
            for ip_info in failed_ips[:5]:  # Show top 5 failed IPs
                analysis += f"- {ip_info['ip']}: {ip_info['count']} messages"
                analysis += f" (DKIM: {ip_info['dkim']}, SPF: {ip_info['spf']})\n"
                
                # Basic IP identification
                if '209.85.' in ip_info['ip'] or '172.217.' in ip_info['ip']:
                    analysis += "  → Likely Google/Gmail server\n"
                elif '40.107.' in ip_info['ip'] or '52.96.' in ip_info['ip']:
                    analysis += "  → Likely Microsoft/Office 365 server\n"
                elif '35.' in ip_info['ip'] or '52.' in ip_info['ip'] or '54.' in ip_info['ip']:
                    analysis += "  → Likely AWS server (check if you use email services)\n"
                else:
                    analysis += "  → Unknown provider (investigate further)\n"
        
        analysis += """
**Issues Found**: """ + ('None detected' if auth_rate >= 95 else f'{failed_messages} messages failed authentication')
        
        analysis += """

**DIY Recommendations**:
"""
        if auth_rate < 95:
            if any(ip['spf'] != 'pass' for ip in failed_ips):
                analysis += """1. Fix SPF Record:
   - Log into your domain registrar
   - Add missing senders to your SPF record
   - For Google: add "include:_spf.google.com"
   - For Microsoft: add "include:spf.protection.outlook.com"
"""
            if any(ip['dkim'] != 'pass' for ip in failed_ips):
                analysis += """2. Fix DKIM Signing:
   - Check your email service admin panel
   - Enable DKIM signing for your domain
   - Add DKIM records to your DNS
"""
        else:
            analysis += "- Your email authentication is working well\n- Continue monitoring for any changes"
        
        analysis += "\n\n⚠️ Note: AI-powered analysis was unavailable for this report. Showing basic analysis only."
        
        return analysis

def get_last_run_time():
    """Get the timestamp of the last successful run"""
    last_run_file = "data/last_successful_run.txt"
    if os.path.exists(last_run_file):
        try:
            with open(last_run_file, 'r') as f:
                return datetime.fromisoformat(f.read().strip())
        except Exception as e:
            logger.warning(f"Could not read last run time: {e}")
    return None

def save_last_run_time():
    """Save the current time as the last successful run"""
    last_run_file = "data/last_successful_run.txt"
    os.makedirs(os.path.dirname(last_run_file), exist_ok=True)
    
    with open(last_run_file, 'w') as f:
        f.write(datetime.now().isoformat())
    logger.info("Saved last successful run timestamp")

def calculate_lookback_hours():
    """Calculate how far back to look for emails based on last run"""
    last_run = get_last_run_time()
    
    if last_run is None:
        # First run - use configured default
        lookback_hours = CONFIG['email'].get('lookback_hours', 24)
        logger.info(f"First run - using default lookback of {lookback_hours} hours")
        return lookback_hours
    
    # Calculate time since last run
    time_since_last_run = datetime.now() - last_run
    hours_since_last_run = time_since_last_run.total_seconds() / 3600
    
    # Cap at maximum lookback to avoid overwhelming (default 7 days)
    max_lookback_hours = CONFIG['email'].get('max_lookback_hours', 168)  # 7 days
    
    if hours_since_last_run > max_lookback_hours:
        logger.warning(f"Time since last run ({hours_since_last_run:.1f}h) exceeds maximum lookback ({max_lookback_hours}h)")
        hours_since_last_run = max_lookback_hours
    
    logger.info(f"Checking emails from the last {hours_since_last_run:.1f} hours (since last run)")
    return hours_since_last_run

def extract_xml_from_attachment(attachment_data, filename):
    """Extract XML content from compressed attachment"""
    try:
        import base64
        content = base64.b64decode(attachment_data)
        
        # Handle gzip files
        if filename.endswith('.gz'):
            return gzip.decompress(content).decode('utf-8')
        
        # Handle zip files
        elif filename.endswith('.zip'):
            import io
            with zipfile.ZipFile(io.BytesIO(content)) as zf:
                # Get the first XML file in the zip
                for name in zf.namelist():
                    if name.endswith('.xml'):
                        return zf.read(name).decode('utf-8')
        
        # Handle plain XML
        elif filename.endswith('.xml'):
            return content.decode('utf-8')
        
        # Try to decode as text anyway
        else:
            return content.decode('utf-8')
            
    except Exception as e:
        logger.error(f"Error extracting XML from {filename}: {e}")
        return None

def send_error_notification(error_message, config, outlook_client):
    """Send email notification when script fails"""
    if not config['notifications'].get('email_results', True):
        return
    
    try:
        subject = f"{config['notifications']['email_subject_prefix']} Script Error"
        body = f"""
DMARC Monitor Script Error
=========================

The DMARC monitoring script encountered an error and was unable to complete successfully.

Error Details:
{error_message}

Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Please check the logs for more details and resolve the issue.

This is an automated error notification from the DMARC Monitor.
"""
        
        success = outlook_client.send_email(
            config['notifications']['email_to'],
            subject,
            body
        )
        
        if success:
            logger.info("Error notification email sent")
        else:
            logger.error("Failed to send error notification email")
            
    except Exception as e:
        logger.error(f"Error sending error notification: {e}")

def create_consolidated_report(analyzed_reports):
    """Create a consolidated email report from multiple DMARC analyses"""
    if not analyzed_reports:
        return None
    
    # Create summary statistics
    total_reports = len(analyzed_reports)
    domains_analyzed = list(set(report['domain'] for report in analyzed_reports))
    total_messages = sum(sum(record['count'] for record in report['raw_data']['records']) 
                        for report in analyzed_reports)
    
    # Build consolidated report
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    report = f"""
DMARC Analysis Report - {timestamp}
{'=' * 50}

EXECUTIVE SUMMARY
• Reports Analyzed: {total_reports}
• Domains Covered: {len(domains_analyzed)}
• Total Email Messages: {total_messages:,}
• Domains: {', '.join(sorted(domains_analyzed))}

DETAILED ANALYSIS
{'=' * 50}
"""
    
    # Add individual domain analyses
    for i, analysis in enumerate(analyzed_reports, 1):
        domain = analysis['domain']
        report_org = analysis['raw_data']['metadata']['org_name']
        date_range = analysis['raw_data']['metadata']['date_range']
        
        report += f"""

{i}. {domain} (reported by {report_org})
{'-' * 60}
Date Range: {date_range['begin']} to {date_range['end']}

{analysis['claude_analysis']}

"""
    
    report += f"""
{'=' * 50}
Report generated by DMARC Monitor at {timestamp}
This is an automated analysis using Claude AI.
"""
    
    return report

def mark_run_as_failed():
    """Mark the current run as failed (don't update last_successful_run)"""
    failed_run_file = "data/last_failed_run.txt"
    os.makedirs(os.path.dirname(failed_run_file), exist_ok=True)
    
    with open(failed_run_file, 'w') as f:
        f.write(datetime.now().isoformat())

def main():
    """Main execution function with Phase 2 enhancements"""
    logger.info("Starting DMARC report monitor (Phase 2)")
    
    analyzed_reports = []
    
    try:
        # Initialize clients and database
        outlook_client = OutlookClient(CONFIG['microsoft'])
        claude_analyzer = ClaudeAnalyzer(CONFIG['claude']['api_key'], CONFIG['claude']['model'])
        dmarc_parser = DMARCParser()
        database = DMARCDatabase()
        enhanced_reporter = EnhancedReporter(CONFIG, database)
        
        # Check if this is first run with Phase 2 and migrate existing data
        if not os.path.exists("data/migration_completed.txt"):
            logger.info("Performing one-time migration of existing data to database...")
            migrated_count = database.migrate_existing_data()
            with open("data/migration_completed.txt", "w") as f:
                f.write(f"Migration completed at {datetime.now().isoformat()}\nFiles processed: {migrated_count}")
            logger.info(f"Migration completed: {migrated_count} files processed")
        
        # Perform database maintenance if configured
        db_config = CONFIG.get('database', {})
        if db_config.get('auto_purge', True):
            retention_days = db_config.get('retention_days', 30)
            purge_on_startup = db_config.get('purge_on_startup', False)
            
            # Get database stats before purge
            db_stats = database.get_database_stats()
            
            # Only purge if database has grown significantly or if explicitly configured
            should_purge = (
                purge_on_startup or 
                db_stats.get('database_size_mb', 0) > 10 or  # > 10MB
                db_stats.get('total_reports', 0) > 100       # > 100 reports
            )
            
            if should_purge:
                logger.info(f"Database size: {db_stats.get('database_size_mb', 0)}MB, "
                          f"Total reports: {db_stats.get('total_reports', 0)}")
                purge_stats = database.purge_old_data(retention_days)
                
                if purge_stats['reports_deleted'] > 0:
                    logger.info(f"Database maintenance completed: Purged {purge_stats['reports_deleted']} "
                              f"reports older than {retention_days} days")
                    
                    # Log final size
                    final_stats = database.get_database_stats()
                    logger.info(f"Database size after purge: {final_stats.get('database_size_mb', 0)}MB")
                else:
                    logger.info(f"No data older than {retention_days} days found to purge")
        
        # Authenticate with Outlook
        if not outlook_client.get_access_token():
            error_msg = "Failed to authenticate with Microsoft Graph"
            logger.error(error_msg)
            send_error_notification(error_msg, CONFIG, outlook_client)
            mark_run_as_failed()
            return False
        
        # Calculate dynamic lookback time
        lookback_hours = calculate_lookback_hours()
        
        # Get recent messages
        messages = outlook_client.get_messages(
            CONFIG['email']['folder_name'], 
            lookback_hours
        )
        
        logger.info(f"Found {len(messages)} messages in the last {lookback_hours:.1f} hours")
        
        # Process each message
        for message in messages:
            if not message.get('hasAttachments'):
                continue
                
            logger.info(f"Processing message: {message['subject']}")
            
            # Get attachments
            attachments = outlook_client.get_attachments(message['id'])
            
            for attachment in attachments:
                if attachment.get('@odata.type') != '#microsoft.graph.fileAttachment':
                    continue
                
                filename = attachment.get('name', '')
                if not any(filename.endswith(ext) for ext in ['.xml', '.gz', '.zip']):
                    continue
                
                logger.info(f"Processing attachment: {filename}")
                
                # Extract XML content
                xml_content = extract_xml_from_attachment(
                    attachment.get('contentBytes'), 
                    filename
                )
                
                if not xml_content:
                    continue
                
                # Parse DMARC report
                parsed_report = dmarc_parser.parse_xml_content(xml_content)
                if not parsed_report:
                    continue
                
                # Analyze with Claude
                analysis = claude_analyzer.analyze_dmarc_report(parsed_report)
                
                # Store in database for historical tracking
                db_report_id = database.store_report(parsed_report, analysis)
                
                # Store for consolidated report
                analyzed_reports.append({
                    'domain': parsed_report['policy']['domain'],
                    'claude_analysis': analysis,
                    'raw_data': parsed_report,
                    'message_subject': message['subject'],
                    'received_time': message['receivedDateTime'],
                    'db_report_id': db_report_id
                })
                
                # Save analysis locally in data directory
                os.makedirs('data', exist_ok=True)
                analysis_file = f"data/dmarc_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{parsed_report['policy']['domain']}.txt"
                
                individual_summary = f"""
DMARC Report Analysis - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Domain: {parsed_report['policy']['domain']}
Report From: {parsed_report['metadata']['org_name']}
Date Range: {parsed_report['metadata']['date_range']['begin']} to {parsed_report['metadata']['date_range']['end']}

{analysis}

---
Raw Report Summary:
- Total Records: {len(parsed_report['records'])}
- Total Messages: {sum(record['count'] for record in parsed_report['records'])}
"""
                
                with open(analysis_file, 'w') as f:
                    f.write(individual_summary)
                
                logger.info(f"Successfully analyzed report for {parsed_report['policy']['domain']}")
        
        # Generate intelligent report using Phase 2 enhanced reporting
        report_data = enhanced_reporter.generate_smart_report(analyzed_reports)
        
        # Send report if needed
        if enhanced_reporter.should_send_report(report_data):
            success = outlook_client.send_email(
                CONFIG['notifications']['email_to'],
                report_data['subject'],
                report_data['body']
            )
            
            if success:
                if report_data.get('has_issues', False):
                    logger.info(f"Issue alert sent successfully ({report_data.get('issue_count', 0)} domains with issues)")
                    # Log alert to database
                    for report in analyzed_reports:
                        if enhanced_reporter._has_significant_issues(report):
                            database.log_alert(
                                report['raw_data']['policy']['domain'],
                                'authentication_issues',
                                'Multiple thresholds exceeded',
                                sent=True
                            )
                else:
                    logger.info(f"Clean status report sent successfully ({report_data.get('clean_count', 0)} domains)")
            else:
                logger.error("Failed to send enhanced report")
        else:
            logger.info("No report needed based on current configuration and analysis results")
        
        # Mark run as successful
        save_last_run_time()
        logger.info(f"Completed processing. Analyzed {len(analyzed_reports)} reports.")
        return True
        
    except Exception as e:
        error_msg = f"Unexpected error in main execution: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Try to send error notification
        try:
            outlook_client = OutlookClient(CONFIG['microsoft'])
            if outlook_client.get_access_token():
                send_error_notification(error_msg, CONFIG, outlook_client)
        except:
            logger.error("Could not send error notification")
        
        mark_run_as_failed()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
