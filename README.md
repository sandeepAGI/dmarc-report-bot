# DMARC Report Monitor

Automatically monitors Outlook for DMARC reports and analyzes them using Claude AI with intelligent scheduling, consolidated reporting, and robust error handling.

## Features

### ✅ Phase 1 (Implemented)
- **Smart Email Processing** - Only analyzes emails since last successful run (no duplicates)
- **Consolidated Reporting** - Single email with executive summary + individual domain analyses  
- **Intelligent Scheduling** - 10AM Mon-Fri with 5PM retry if morning job fails
- **Error Handling** - Email notifications when script fails + automatic retry logic
- **Quiet Mode** - No spam emails when no new reports found
- **Secure Configuration** - All secrets stored locally, never committed to git

### ✅ Phase 2 (Implemented)
- **SQLite Database Storage** - Historical data persistence with automatic migration
- **Intelligent Alerting** - Smart thresholds only send alerts when issues exceed configurable limits
- **Historical Analysis** - Compare current vs previous reports with trend detection
- **Enhanced Reporting** - Issue-focused reports with executive summaries and actionable recommendations
- **Clean Status Emails** - Confirmation emails when no issues are detected
- **Automatic Issue Detection** - Identifies authentication failures, suspicious IPs, and policy violations
- **Context-Aware Analysis** - Improved keyword detection prevents false positives for domains with perfect scores
- **Detailed Failure Analysis** - Specific IP addresses, message counts, and failure types with actionable recommendations
- **IP Intelligence** - Identifies legitimate email providers vs. suspicious sources requiring investigation
- **Historical Failure Context** - Clean reports show "No failures since X" for confidence building
- **🆕 Non-Technical Reporting (Aug 2025)** - Plain English explanations designed for small businesses without IT staff
- **🆕 Risk-Based Priority System** - CRITICAL/HIGH/MODERATE/LOW risk levels with color coding
- **🆕 Enhanced IP Investigation** - Claude AI identifies each IP (Google, Microsoft, AWS, etc.) with specific fix instructions
- **🆕 DIY Action Steps** - Step-by-step instructions for fixing issues yourself (DNS changes, email settings)
- **🆕 Business Impact Analysis** - Clear explanations of what failures mean for your business operations
- **🆕 API Retry Logic** - Automatic retry (3 attempts with exponential backoff) when Claude API fails
- **🆕 Fallback Analysis** - Basic analysis still provided when AI is completely unavailable
- **🆕 Improved Reliability** - Increased timeout (30s→45s) and better error handling
- **🔧 Automatic Email Organization (Nov 2025)** - Processed reports automatically moved to "DMARC Processed" folder
- **🔧 Multi-Mailbox Support (Nov 2025)** - Configure which mailbox to monitor via `mailbox_account` setting
- **🔧 Full Pagination Support (Nov 2025)** - Retrieves all messages regardless of volume (not limited to 10)
- **🔧 Extended Lookback (Nov 2025)** - 72-hour default lookback covers weekends for Monday runs

### 🚀 Phase 3 (Future Enhancements)
- **Web Dashboard** - Visual trends and historical data with charts and graphs
- **REST API** - External integrations and monitoring system connections
- **Advanced ML Analytics** - Machine learning-based anomaly detection
- **Multi-Tenant Support** - MSP and enterprise multi-domain management
- **SIEM Integration** - Export to Splunk, ELK, and other security platforms
- **Slack/Teams Integration** - Send alerts to team channels
- **Advanced Filtering** - Domain-specific rules and custom analysis prompts
- **Automated Response** - Auto-remediation for common DMARC issues

## Prerequisites

- **Python 3.7+** installed
- **Microsoft 365 account** with Outlook access
- **Claude API key** from Anthropic ([Get one here](https://console.anthropic.com))
- **Azure app registration** (for Outlook API access)

## Project Structure

```
~/utilities/dmarc-monitor/
├── .gitignore                  # Protects secrets from git
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── .vscode/                    # VSCode configuration
│   ├── settings.json
│   └── launch.json
├── config/
│   ├── config.json.template    # Safe template (committed)
│   └── config.json             # Your secrets (gitignored)
├── src/
│   ├── dmarc_monitor.py        # Main application (enhanced with IP investigation)
│   ├── database.py             # SQLite database management (Phase 2)
│   ├── enhanced_reporting.py   # Intelligent reporting system (with hybrid format)
│   └── non_technical_formatter.py # Plain English formatter for small businesses (NEW)
├── scripts/
│   ├── setup.py                         # Configuration setup
│   ├── retry_if_failed.py               # Retry logic for cron
│   ├── test_phase2.py                   # Phase 2 test suite
│   ├── test_enhanced_failures.py        # Enhanced failure details unit tests
│   ├── test_enhanced_reporting.py       # Non-technical reporting test suite
│   ├── test_retry_logic.py              # API retry and fallback test suite
│   ├── test_end_to_end.py               # End-to-end integration test
│   ├── test_fixed_authentication.py     # Verify correct mailbox authentication (NEW)
│   ├── catchup_backlog.py               # Process historical backlog with safety checks (NEW)
│   ├── move_processed_emails.py         # Bulk move processed emails to archive folder (NEW)
│   ├── generate_historical_report.py    # Query database for historical analysis (NEW)
│   └── database_maintenance.py          # Database maintenance utility
├── logs/                       # Execution logs
│   └── dmarc_monitor.log
└── data/                       # Analysis results & tracking
    ├── last_successful_run.txt
    ├── migration_completed.txt  # Phase 2 migration status
    ├── dmarc_monitor.db         # SQLite database (Phase 2)
    └── dmarc_analysis_*.txt     # Individual analysis files
```

## Quick Start

### 1. Clone/Download Project
```bash
# Download and run the project setup script in ~/utilities/
cd ~/utilities
# Save setup_dmarc_project.sh and run:
chmod +x setup_dmarc_project.sh
./setup_dmarc_project.sh
```

### 2. Install Dependencies
```bash
cd ~/utilities/dmarc-monitor
pip install -r requirements.txt
```

### 3. Create Azure App Registration
1. Go to [Azure Portal](https://portal.azure.com) → **Azure Active Directory** → **App registrations**
2. Click **New registration**:
   - **Name**: "DMARC Monitor"
   - **Supported account types**: "Accounts in this organizational directory only"
   - **Redirect URI**: Leave blank for now
3. Note down: **Application (client) ID** and **Directory (tenant) ID**
4. Go to **Certificates & secrets** → **New client secret** → Save the **Value**
5. Go to **Authentication** → **Add a platform** → **Web** → Add `http://localhost:8080/callback`
6. Go to **API permissions** → **Add permission** → **Microsoft Graph** → **Delegated**:
   - Add: `Mail.ReadWrite`, `Mail.Send`, `offline_access`
   - Click **Grant admin consent**

### 4. Get Claude API Key
1. Go to [Anthropic Console](https://console.anthropic.com)
2. Create account/login → **API Keys** → **Create Key**
3. Copy the key (starts with `sk-ant-api03-`)

### 5. Configure Secrets
```bash
cd ~/utilities/dmarc-monitor
python scripts/setup.py  # Creates config/config.json from template
```

Edit `config/config.json` with your credentials:
```json
{
  "microsoft": {
    "client_id": "your-azure-app-id",
    "client_secret": "your-azure-client-secret",
    "tenant_id": "your-azure-tenant-id",
    "redirect_uri": "http://localhost:8080/callback"
  },
  "claude": {
    "api_key": "your-claude-api-key",
    "model": "claude-sonnet-4-20250514"
  },
  "email": {
    "mailbox_account": "email@domain.com",      // ⚠️ IMPORTANT: Mailbox where DMARC reports are delivered
    "folder_name": "DMARC Reports",
    "processed_folder": "DMARC Processed",      // Processed reports moved here automatically
    "lookback_hours": 72,                       // Covers weekends for Monday runs
    "max_lookback_hours": 168                   // 7 days for extended outages
  },
  "notifications": {
    "email_results": true,
    "email_to": "your-email@domain.com",
    "email_subject_prefix": "[DMARC Analysis]",
    "quiet_mode": true
  }
}
```

**Important Configuration Notes:**
- `mailbox_account`: Must be the email address where DMARC reports are delivered (may differ from notification email)
- `processed_folder`: Reports automatically moved here after processing (keeps inbox clean)
- `lookback_hours`: 72h default covers weekends; system calculates actual time since last run
- `max_lookback_hours`: Maximum lookback period for extended outages

### 6. Set Up Outlook Folders
1. Open Outlook → Create folders:
   - **"DMARC Reports"** - Incoming reports land here
   - **"DMARC Processed"** - Processed reports automatically moved here
2. Set up email rule to move DMARC reports to "DMARC Reports" folder:
   - **Condition**: Subject contains "DMARC" OR from domain contains your domain
   - **Action**: Move to "DMARC Reports" folder

**Note**: The system will automatically move processed reports from "DMARC Reports" to "DMARC Processed" after analysis, keeping your inbox organized.

### 7. First Run & Authentication
```bash
python src/dmarc_monitor.py
```
- Browser will open for Microsoft authentication
- Sign in and grant permissions
- Script will analyze any existing reports

## Scheduling (Automated Operation)

### Set Up Cron Jobs
```bash
crontab -e
```

Add these lines:
```bash
# Main run: 10AM Monday-Friday
0 10 * * 1-5 cd ~/myworkspace/Utilities/dmarc-monitor && /opt/anaconda3/bin/python3 src/dmarc_monitor.py >> logs/cron.log 2>&1

# Retry run: 5PM Monday-Friday (only if morning failed)
0 17 * * 1-5 cd ~/myworkspace/Utilities/dmarc-monitor && /opt/anaconda3/bin/python3 scripts/retry_if_failed.py >> logs/cron.log 2>&1
```

### How Scheduling Works
- **10AM Mon-Fri**: Main analysis run
  - Checks emails since last successful run (no duplicates)
  - Sends consolidated report if new DMARC reports found
  - Quiet mode: no email if no new reports
- **5PM Mon-Fri**: Intelligent retry
  - Only runs if 10AM job failed or didn't run
  - Automatic error detection and recovery

### Monitoring Cron Jobs
```bash
# Check scheduled jobs
crontab -l

# View execution logs  
tail -f ~/utilities/dmarc-monitor/logs/cron.log

# Check last run status
cat ~/utilities/dmarc-monitor/data/last_successful_run.txt
```

## Configuration Reference

### Core Settings (`config/config.json`)
```json
{
  "microsoft": {
    "client_id": "azure-app-id",
    "client_secret": "azure-client-secret",
    "tenant_id": "azure-tenant-id", 
    "redirect_uri": "http://localhost:8080/callback"
  },
  "claude": {
    "api_key": "claude-api-key",
    "model": "claude-sonnet-4-20250514"
  },
  "email": {
    "mailbox_account": "member@domain.com",
    "folder_name": "DMARC Reports",
    "processed_folder": "DMARC Processed",
    "lookback_hours": 72,
    "max_lookback_hours": 168
  },
  "notifications": {
    "email_results": true,
    "email_to": "your-email@domain.com", 
    "email_subject_prefix": "[DMARC Analysis]",
    "quiet_mode": true,
    "send_clean_status": true
  },
  "thresholds": {
    "auth_success_rate_min": 95.0,
    "auth_rate_drop_threshold": 5.0,
    "new_sources_threshold": 3,
    "minimum_messages_for_alert": 10
  },
  "logging": {
    "level": "INFO",
    "file": "logs/dmarc_monitor.log"
  }
}
```

### Key Settings Explained

#### Core Settings
- **`mailbox_account`**: Email address where DMARC reports are delivered (forces authentication to correct mailbox)
- **`processed_folder`**: Folder where processed reports are automatically moved after analysis
- **`quiet_mode`**: `true` = no email when no reports found, `false` = always send status email
- **`send_clean_status`**: `true` = send confirmation email when no issues detected
- **`lookback_hours`**: Default hours to check on first run (72 hours recommended to cover weekends)
- **`max_lookback_hours`**: Maximum lookback to prevent overwhelming (168 = 7 days)
- **`model`**: Claude model to use (`claude-sonnet-4-20250514` recommended)

#### Phase 2 Alert Thresholds
- **`auth_success_rate_min`**: Minimum authentication success rate (%) before triggering alert (default: 95.0)
- **`auth_rate_drop_threshold`**: Alert if authentication rate drops by this percentage vs historical average (default: 5.0)
- **`new_sources_threshold`**: Alert if number of new IP sources exceeds this number vs recent history (default: 3)
- **`minimum_messages_for_alert`**: Minimum email messages in report before considering for alerts (default: 10)

#### Database Management
- **`retention_days`**: Number of days to keep historical data (default: 30)
- **`auto_purge`**: Automatically purge old data when database grows large (default: true)
- **`purge_on_startup`**: Force purge check on every startup (default: false)

## Maintenance Utilities

### Process Historical Backlog

If reports have been accumulating unprocessed, use the catch-up script:

```bash
python scripts/catchup_backlog.py
```

This script will:
- Safely backup your `last_successful_run.txt` timestamp
- Process ALL reports in the "DMARC Reports" folder
- Generate a consolidated report
- Store all results in the database
- Restore normal operations

**Safety Features:**
- Asks for confirmation before proceeding
- Backs up state before processing
- Can be interrupted with Ctrl+C (will restore backup)
- Provides detailed progress output

### Clean Up Processed Emails

To move processed emails from "DMARC Reports" to "DMARC Processed":

```bash
python scripts/move_processed_emails.py
```

**Note:** The main script now does this automatically after each run. This utility is only needed for one-time cleanup of historical processed reports.

### Generate Historical Analysis

To view a consolidated report from your database:

```bash
python scripts/generate_historical_report.py
```

This generates a report showing:
- Total reports processed and date range
- Summary by domain
- Authentication success rates
- Reports with issues
- Top failing IP addresses
- Current DMARC policy analysis

### Verify Authentication

To test that authentication is working correctly:

```bash
python scripts/test_fixed_authentication.py
```

This will:
- Confirm authentication to the correct mailbox (`mailbox_account`)
- List accessible folders
- Verify "DMARC Reports" and "DMARC Processed" folders are visible

## Team Setup Instructions

Since `config/config.json` is gitignored (for security), new team members need to:

### For New Team Members
1. **Clone the repository**:
   ```bash
   git clone your-repo-url
   cd dmarc-monitor
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Create config from template**:
   ```bash
   python scripts/setup.py
   ```

4. **Get credentials from team admin**:
   - Azure app registration details (client_id, client_secret, tenant_id)
   - Claude API key (or create your own)
   - Target email address for notifications

5. **Update config file**:
   ```bash
   # Edit config/config.json with provided credentials
   code config/config.json
   ```

6. **Test setup**:
   ```bash
   python src/dmarc_monitor.py
   ```

### For Team Admins
1. **Share Azure app details** (from original setup):
   - Client ID, Client Secret, Tenant ID
   - Or create separate Azure app for team member

2. **Provide Claude API access**:
   - Share organization API key, OR
   - Have team member create personal API key at [console.anthropic.com](https://console.anthropic.com)

3. **Document team-specific settings**:
   - Which Outlook folders to monitor
   - Target email addresses for notifications
   - Any custom analysis requirements

## Manual Operations

### One-Time Analysis
```bash
# Analyze all reports from last 48 hours
python src/dmarc_monitor.py
```

### Test Retry Logic
```bash
# Check if retry would run (without actually running)
python scripts/retry_if_failed.py
```

### Force Re-analysis
```bash
# Delete tracking files to reprocess recent reports
rm data/last_successful_run.txt
python src/dmarc_monitor.py
```

## Output Examples

### Phase 2 Enhanced Reports (Now with Non-Technical Format)

#### NEW: Enhanced Report with Plain English (Aug 2025)

```text
🚨 DMARC SECURITY REPORT - 2025-08-25 10:15:23
============================================================

🟠 OVERALL RISK LEVEL: HIGH
Action needed this week - Significant security gaps

QUICK SUMMARY FOR BUSINESS OWNER
============================================================
📊 Checked: 2 domain reports (81 emails)
⚠️ Problems Found: 1 domain with issues
✅ Working Well: 1 domain without issues
📈 Overall Security Score: 73.3%

WHAT THIS MEANS FOR YOUR BUSINESS
============================================================
⚠️ HIGH: 22 emails (27%) at risk of spam filtering
📧 Important emails may end up in spam folders
🔍 Recipients becoming suspicious of legitimate emails
📉 Declining email reputation affecting deliverability

1. training.aileron-group.com 🟠 HIGH RISK
--------------------------------------------------

🔍 PLAIN ENGLISH EXPLANATION
----------------------------------------
🎉 Analyzed 81 emails sent using your company name
⚠️ 73.3% passed security verification
🔍 22 emails couldn't be verified as legitimate
📍 Found 4 different sources of concern

🔎 WHO'S SENDING FAILED EMAILS?
----------------------------------------
📍 Google Gmail Server (209.85.220.41)
   Status: Legitimate Google server but not authorized in your SPF
   Action: ADD to SPF: "include:_spf.google.com" in your DNS records
   Confidence: 95% legitimate - Google's official servers

📍 Amazon AWS Server (35.174.145.124)
   Status: Could be legitimate service OR suspicious
   Action: CHECK: Do you use MailChimp, SendGrid, or similar?
   If YES → Add their SPF records
   If NO → Monitor for spoofing attempts

🛠️ HOW TO FIX THESE ISSUES
----------------------------------------
📝 FIX YOUR SPF RECORD (Authorized Senders List):
   1. Log into your domain registrar (GoDaddy, Namecheap, etc.)
   2. Go to DNS Management / DNS Settings
   3. Find the TXT record that starts with "v=spf1"
   4. Add: "include:_spf.google.com" for Gmail
   5. Save changes (may take 1-24 hours to take effect)

🎯 ACTION SUMMARY - WHAT TO DO NOW
============================================================
1. Review each domain's risk level above
2. For HIGH risks: Take action TODAY
3. Follow the step-by-step DIY instructions provided
4. Save this report for your records
```

#### Legacy Technical Report Format (still included below plain English)

```text
🚨 DMARC ISSUES DETECTED - 2025-07-11 10:15:23
============================================================

EXECUTIVE SUMMARY
• Total Reports Analyzed: 3
• Reports with Issues: 2
• Clean Reports: 1
• Total Email Messages: 1,247
• Average Authentication Rate: 87.3%

DOMAINS REQUIRING ATTENTION
============================================================

1. example.com (reported by Google)
--------------------------------------------------
📊 Authentication Rate: 76.2% (952/1,247 messages)
📈 Historical Trend: Declined (-12.5% vs 30-day avg)
⏰ Report Period: 1634140800 to 1634227200

🔍 DETAILED FAILURE ANALYSIS:

  Failed Authentication Details:
  • 3 IP(s) with 295 failed message(s)

  • 50.63.9.60: 150 message(s) - DKIM ❌ FAIL, SPF ❌ FAIL
    └─ Unknown Provider (50.63.x.x range) ⚠️ INVESTIGATE
  • 192.168.1.100: 100 message(s) - DKIM ✅ PASS, SPF ❌ FAIL
    └─ Unknown Provider
  • 203.0.113.45: 45 message(s) - DKIM ❌ FAIL, SPF ✅ PASS
    └─ Example ISP

  📋 RECOMMENDED ACTIONS:
  1. **Investigate IP range 50.63.x.x:** All failures from same subnet
  2. **DKIM Issues:** 2 IP(s) failing DKIM - check signing configuration
  3. **SPF Issues:** 2 IP(s) failing SPF - verify authorized senders
  4. **Verification Steps:**
     - Check SPF record: dig TXT example.com | grep spf
     - Verify these IPs are legitimate senders for example.com
     - If legitimate: update SPF record and configure DKIM
     - If malicious: consider abuse reporting

🔍 ANALYSIS & RECOMMENDATIONS:
  • Update DKIM keys for newsletter platform
  • Review SPF record for new IP 192.168.1.100
  • Investigate 23.8% authentication failures

✅ CLEAN DOMAINS (1 domains)
============================================================
The following domains showed no significant issues:
• aileron-group.com: 295 messages processed successfully
```

#### Clean Status Report (when no issues found)
```
✅ ALL SYSTEMS HEALTHY - 2025-07-11 10:15:23
============================================================

EXECUTIVE SUMMARY
• Total Reports Analyzed: 2
• All domains performing well
• Total Email Messages: 1,542
• Average Authentication Rate: 98.7%

DOMAIN STATUS
============================================================

✅ aileron-group.com (reported by Google)
   📊 Authentication Rate: 99.1% (1,528/1,542 messages)
   📈 Trend: Stable (+0.3% vs 30-day avg)
   🛡️ No failures detected since 2025-07-09

✅ example.com (reported by Microsoft)
   📊 Authentication Rate: 98.2% (491/500 messages)
   📊 Trend: Stable (-0.1% vs 30-day avg)
   🛡️ No failures detected in monitoring history

============================================================
🛡️  All DMARC policies are working effectively
🎯 No action required at this time
```

### Legacy Consolidated Email Report (Phase 1)
```
DMARC Analysis Report - 2025-06-07 10:15:23
==================================================

EXECUTIVE SUMMARY  
• Reports Analyzed: 3
• Domains Covered: 2
• Total Email Messages: 1,247
• Domains: aileron-group.com, example.com

DETAILED ANALYSIS
==================================================

1. aileron-group.com (reported by Google)
   Overall Status: ✅ 98.5% authentication success
   Authentication Results: DKIM passing, SPF aligned
   Source Analysis: All sources recognized, no new IPs
   Issues Found: 1.5% failures from legacy system
   Recommendations: Update legacy system SPF record

2. example.com (reported by Microsoft)
   Overall Status: ⚠️ 87% authentication success  
   Authentication Results: DKIM failing for newsletter system
   Source Analysis: New IP 192.168.1.100 detected
   Issues Found: Newsletter system DKIM signature invalid
   Recommendations: Update DKIM keys for newsletter platform
```

### Retry Script Behavior

```bash
# If morning job succeeded:
✅ Morning job completed successfully at 10:15

# If morning job failed:
❌ Morning job failed at 10:05
🔄 Retrying failed morning job

# If no morning job detected:
❓ No morning job detected today
🚀 Running DMARC monitor retry...
```

### API Reliability Features (NEW Aug 2025)

The system now includes robust error handling for Claude API failures:

#### Automatic Retry Logic
- **3 retry attempts** with exponential backoff (2s, 4s, 8s delays)
- **Handles timeouts** - Increased timeout from 30s to 45s
- **Rate limit handling** - Automatically backs off when rate limited
- **Clear logging** - Shows retry attempts and reasons in logs

#### Fallback Analysis
When Claude API is completely unavailable after all retries:
- **Basic analysis provided** - Authentication rates, pass/fail status
- **IP identification** - Basic detection of Google/Microsoft/AWS servers
- **DIY recommendations** - Still provides actionable steps based on failures
- **Clear notification** - Report indicates AI analysis was unavailable

Example log output with retry:
```
2025-08-25 12:32:37 - WARNING - Claude API timeout, retrying in 2 seconds (attempt 2/3)...
2025-08-25 12:32:41 - WARNING - Claude API timeout, retrying in 4 seconds (attempt 3/3)...
2025-08-25 12:32:47 - ERROR - Claude API timeout after 3 attempts
2025-08-25 12:32:47 - INFO - Using fallback analysis due to Claude API unavailability
```

## How It Works

### Smart Processing Flow
1. **Check Last Run**: Reads `data/last_successful_run.txt` to determine lookback time
2. **Email Retrieval**: Gets emails from "DMARC Reports" folder since last successful run
3. **Report Parsing**: Extracts and parses XML from .gz, .zip, or .xml attachments
4. **Claude Analysis**: Sends structured data to Claude for intelligent analysis
5. **Consolidated Reporting**: Combines all analyses into single email with executive summary
6. **Timestamp Tracking**: Saves successful run time to prevent duplicate processing

### Error Handling
- **Authentication Failures**: Emails admin with error details
- **API Errors**: Logs errors and marks run as failed for retry system
- **Script Crashes**: Catches exceptions and sends error notifications
- **Retry Logic**: 5PM job automatically retries if 10AM job failed

### Security Features
- **Local Credential Storage**: All secrets stored in gitignored config file
- **Token Management**: OAuth tokens cached locally with automatic refresh
- **No External Dependencies**: Runs entirely on your infrastructure
- **Audit Trail**: Comprehensive logging of all operations

## Testing the Complete System

### Phase 2 Feature Testing
```bash
# Test Phase 2 database and reporting features
python scripts/test_phase2.py

# Test enhanced failure details functionality
python scripts/test_enhanced_failures.py

# Run comprehensive end-to-end test
python scripts/test_end_to_end.py

# Test specific components
python -c "from scripts.test_phase2 import test_database; test_database()"
python -c "from scripts.test_phase2 import test_enhanced_reporting; test_enhanced_reporting()"
```

### End-to-End Test
```bash
# 1. Delete tracking files to start fresh
rm -f data/last_successful_run.txt data/last_failed_run.txt

# 2. Run main script (should work)
python src/dmarc_monitor.py

# 3. Test retry logic (should skip)
python scripts/retry_if_failed.py

# 4. Simulate failure
echo "$(date --iso-8601=seconds)" > data/last_failed_run.txt

# 5. Test retry after failure (should execute)
python scripts/retry_if_failed.py
```

### Verify Cron Setup
```bash
# Test exact cron command manually
cd ~/utilities/dmarc-monitor && /usr/bin/python3 src/dmarc_monitor.py >> logs/cron.log 2>&1

# Check results
cat logs/cron.log
```

## Troubleshooting

### Authentication Issues
```bash
# Test Claude API key
python -c "
import requests
headers = {'x-api-key': 'your-key', 'anthropic-version': '2023-06-01', 'content-type': 'application/json'}
response = requests.post('https://api.anthropic.com/v1/messages', 
    headers=headers, 
    json={'model': 'claude-sonnet-4-20250514', 'max_tokens': 10, 'messages': [{'role': 'user', 'content': 'Hi'}]})
print(response.status_code, response.text)
"

# Re-authenticate with Outlook  
rm outlook_token.json
python src/dmarc_monitor.py
```

### Cron Job Issues
```bash
# Check cron service status
service cron status  # Linux
launchctl list | grep cron  # macOS

# Test cron command manually
cd ~/utilities/dmarc-monitor && /usr/bin/python3 src/dmarc_monitor.py

# Check cron logs
tail -f /var/log/cron  # Linux  
log show --predicate 'process == "cron"' --last 1h  # macOS
```

### Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| 401 Authentication Error | Invalid/expired Claude API key | Regenerate API key in Anthropic Console |
| No messages found | Wrong folder name or no DMARC reports | Check folder name in config, verify email rules |
| Cron jobs not running | Cron service not running | Start cron service, check crontab syntax |
| Wrong email address | Old email in config | Update `notifications.email_to` in config |
| Token expired | Outlook token expired | Delete `outlook_token.json` and re-authenticate |

### Email Issues
- **Wrong email address**: Check `notifications.email_to` in config
- **No emails sent**: Verify `notifications.email_results` is `true`
- **Error emails**: Check `outlook_token.json` exists and is valid

## Monitoring & Maintenance

### Regular Monitoring
```bash
# Check system health
tail -f logs/dmarc_monitor.log

# View recent cron activity
tail -20 logs/cron.log

# Check last successful run
cat data/last_successful_run.txt
```

### Maintenance Tasks
- **Monthly**: Review logs for any recurring errors
- **Quarterly**: Rotate API keys for security
- **Annually**: Review Azure app permissions and access

### Log Management
```bash
# Archive old logs (if they get large)
gzip logs/dmarc_monitor.log
mv logs/dmarc_monitor.log.gz logs/archive/

# Clean old analysis files (keep last 30 days)
find data/ -name "dmarc_analysis_*.txt" -mtime +30 -delete
```

## Performance & Scaling

### Current Capacity
- **Email Volume**: Handles 10-50 DMARC reports per run efficiently
- **Processing Time**: ~10-15 seconds per report (Claude analysis)
- **Storage**: Minimal (logs + small analysis files)

### Scaling Considerations
- **High Volume**: For >50 reports/day, consider Phase 2 SQLite storage
- **Multiple Domains**: Current setup handles unlimited domains automatically
- **Team Usage**: Each team member can run their own instance

## Security Considerations

### Data Protection
- **Secrets Management**: All credentials stored locally, never committed
- **Email Content**: DMARC reports may contain sensitive IP/domain info
- **Token Security**: OAuth tokens auto-refresh, stored locally
- **Log Security**: Logs may contain email metadata - treat as confidential

### Best Practices
- **API Key Rotation**: Change Claude API keys quarterly
- **Access Review**: Periodically review Azure app permissions
- **Local Security**: Protect the config.json file with appropriate file permissions
- **Network Security**: Ensure HTTPS connections for all API calls

## Cost Estimates

### Monthly Costs (Typical Organization)
- **Microsoft Graph API**: Free for reasonable usage
- **Claude API**: $0.01-0.05 per DMARC report analysis  
- **Infrastructure**: $0 (runs on your existing hardware)

### Example Cost Calculations
- **2 reports/day**: ~$3/month
- **10 reports/day**: ~$15/month  
- **50 reports/day**: ~$75/month

*Costs may vary based on report complexity and Claude model used*

## Phase 2 Benefits & Migration

### What's New in Phase 2

#### Intelligent Alerting
- **Reduced Alert Fatigue**: Only get notified about real problems
- **Smart Thresholds**: Configurable limits for authentication rates and trends
- **Historical Context**: Compare current performance vs. past averages
- **Clean Status Confirmations**: Know when everything is working well
- **Context-Aware Detection**: Enhanced keyword analysis prevents false positives when domains have perfect authentication scores

#### Enhanced Data Management
- **SQLite Database**: Persistent storage for trend analysis
- **Automatic Migration**: Seamlessly upgrades from Phase 1
- **Historical Analysis**: Track authentication rates over time
- **Performance Metrics**: Detailed insights into email security

#### Better Reporting
- **Issue-Focused Reports**: Highlights problems requiring attention
- **Executive Summaries**: High-level overview with key metrics
- **Actionable Recommendations**: Specific steps to resolve issues
- **Trend Indicators**: Visual status (📈 📊 📉) for performance changes

### Migration from Phase 1

Phase 2 is fully backwards compatible. On first run, the system will:

1. **Automatic Database Setup**: Creates SQLite database structure
2. **Data Migration**: Processes existing analysis files (if any)
3. **Configuration Enhancement**: Works with existing config.json
4. **Seamless Operation**: No changes to cron jobs or authentication

### Testing Your Upgrade

```bash
# Backup current setup
cp -r ~/myworkspace/Utilities/dmarc-monitor ~/myworkspace/Utilities/dmarc-monitor-backup

# Test Phase 2 features (includes false positive fix validation)
python scripts/test_phase2.py

# Run with existing data
python src/dmarc_monitor.py
```

### Issue Detection Improvements
The system now uses enhanced context-aware analysis to distinguish between actual issues and perfect performance:

- **Perfect Scores**: Domains with 100% authentication rates and "NONE DETECTED" status correctly generate "✅ All Clear" reports
- **Actual Issues**: Domains with authentication failures, policy violations, or suspicious activity still trigger appropriate "⚠️ Issues Detected" alerts
- **Reduced False Positives**: Improved keyword detection prevents misleading headlines for healthy domains

### Database Features

The new SQLite database provides:
- **Historical Tracking**: Store all DMARC reports with full context
- **Trend Analysis**: Compare current vs. historical performance
- **Alert History**: Track when and why alerts were sent
- **Performance Queries**: Fast retrieval of historical data
- **Automatic Maintenance**: Rolling 30-day data retention with configurable purging

### Database Maintenance

The system includes automatic data purging to prevent unlimited database growth:

#### Automatic Purging
- **Default Retention**: 30 days (configurable)
- **Smart Triggers**: Purges when database > 10MB or > 100 reports
- **VACUUM Operation**: Reclaims disk space after purging
- **Logging**: Full audit trail of maintenance operations

#### Manual Maintenance
```bash
# View database statistics
python scripts/database_maintenance.py stats

# Preview what would be purged (dry run)
python scripts/database_maintenance.py purge --days 30 --dry-run

# Actually purge data older than 30 days
python scripts/database_maintenance.py purge --days 30 --confirm

# Export database info to JSON
python scripts/database_maintenance.py export --output db_info.json
```

#### Configuration Options
```json
{
  "database": {
    "retention_days": 30,        // Keep data for 30 days
    "auto_purge": true,          // Enable automatic purging
    "purge_on_startup": false    // Don't force purge on every startup
  }
}
```

#### Enhanced Database Features

The database now includes advanced querying capabilities for detailed failure analysis:

```python
# Example usage of new database methods
from database import DMARCDatabase

db = DMARCDatabase()

# Get detailed failure information for a specific report
failure_details = db.get_failure_details('example.com', report_id)
# Returns: [{'source_ip': '50.63.9.60', 'count': 2, 'dkim_result': 'fail', 'spf_result': 'fail'}, ...]

# Get the last date when failures occurred for a domain
last_failure = db.get_last_failure_date('example.com')
# Returns: '2025-07-09' or None if no failures found

# Get intelligence about an IP address
ip_intel = db.get_ip_intelligence('50.63.9.60')
# Returns: {'organization': 'Unknown Provider', 'is_suspicious': True, ...}
```

### New Files Created

- `src/database.py` - Database management system with auto-purging and enhanced failure analysis
- `src/enhanced_reporting.py` - Intelligent reporting engine with detailed failure breakdown and non-technical format
- `src/non_technical_formatter.py` - Plain English formatter for small businesses (Aug 2025)
- `scripts/test_phase2.py` - Comprehensive test suite for Phase 2 features
- `scripts/test_enhanced_failures.py` - Unit tests for enhanced failure details functionality
- `scripts/test_enhanced_reporting.py` - Test suite for non-technical reporting features (Aug 2025)
- `scripts/test_retry_logic.py` - Test suite for API retry and fallback analysis (Aug 2025)
- `scripts/test_end_to_end.py` - End-to-end integration test demonstrating new features
- `scripts/database_maintenance.py` - Database maintenance utility
- `data/dmarc_monitor.db` - SQLite database (auto-created)
- `data/migration_completed.txt` - Migration status tracker

### Recent Improvements

#### Non-Technical Reporting & API Reliability (August 2025)
- **Plain English Reports**: All technical terms explained for small business owners
- **Risk-Based Priority System**: CRITICAL/HIGH/MODERATE/LOW risk levels with clear business impact
- **Enhanced IP Investigation**: Claude AI identifies each IP (Google, Microsoft, AWS, etc.) with specific actions
- **DIY Action Steps**: Step-by-step DNS and email configuration instructions
- **API Retry Logic**: 3 retry attempts with exponential backoff when Claude API fails
- **Fallback Analysis**: Basic analysis provided when AI is completely unavailable
- **Improved Reliability**: Increased timeout (30s→45s) and comprehensive error handling

#### Enhanced Failure Details (July 2025)
- **Detailed Failure Analysis**: Reports now include specific IP addresses, message counts, and failure types (DKIM/SPF) for actionable troubleshooting
- **IP Intelligence**: Automatic categorization of IP sources (Microsoft/Google vs. suspicious ranges) with investigation flags
- **Historical Context**: Clean reports show "No failures detected since [date]" for confidence building
- **Actionable Recommendations**: Specific DNS verification commands and step-by-step investigation guidance

#### Previous Improvements
- **Fixed False Positive Alerts** (June 2025): Enhanced keyword detection logic prevents domains with perfect authentication scores from being incorrectly flagged as having issues
- **Improved Context Analysis**: System now recognizes positive indicators like "NONE DETECTED" and "PERFECT SCORES" to avoid misleading alert headlines

## Getting Help

### Documentation
- **Config Issues**: Check Configuration Reference section
- **Cron Problems**: See Scheduling section and troubleshooting
- **API Errors**: Review authentication setup steps

### Log Analysis
```bash
# Find recent errors
grep -i error logs/dmarc_monitor.log | tail -10

# Check authentication flow
grep -i "auth" logs/dmarc_monitor.log | tail -5

# View processing summary
grep -i "completed processing" logs/dmarc_monitor.log | tail -5
```

### Support Resources
- **Azure Documentation**: [Microsoft Graph API docs](https://docs.microsoft.com/en-us/graph/)
- **Claude API**: [Anthropic API documentation](https://docs.anthropic.com/)
- **Cron Help**: Check your OS documentation for crontab syntax

---

## Quick Reference

### Essential Commands
```bash
# Run analysis manually
python src/dmarc_monitor.py

# Test retry logic
python scripts/retry_if_failed.py

# View logs
tail -f logs/dmarc_monitor.log

# Check cron schedule
crontab -l

# Edit configuration
code config/config.json
```

### Important File Locations
- **Main script**: `src/dmarc_monitor.py`
- **Configuration**: `config/config.json`
- **Logs**: `logs/dmarc_monitor.log`
- **Tracking**: `data/last_successful_run.txt`
- **Auth tokens**: `outlook_token.json`

Built with ❤️ for automated DMARC monitoring and analysis.