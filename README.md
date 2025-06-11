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

### 🔄 Phase 2 (Planned)
- **Historical Analysis** - Compare current vs previous reports ("Auth rate dropped 10% vs last week")
- **Alert Thresholds** - Only email for reports with issues/changes above threshold
- **SQLite Storage** - Better data persistence and trend analysis
- **Multi-folder Monitoring** - Check both "DMARC Reports" and "Inbox"

### 🚀 Phase 3 (Future)
- **Web Dashboard** - Visual trends and historical data
- **API Integration** - REST API for external monitoring systems  
- **Advanced Filtering** - Domain-specific rules and custom analysis prompts
- **Slack/Teams Integration** - Send reports to team channels

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
│   └── dmarc_monitor.py        # Main application
├── scripts/
│   ├── setup.py                # Configuration setup
│   └── retry_if_failed.py      # Retry logic for cron
├── logs/                       # Execution logs
│   └── dmarc_monitor.log
└── data/                       # Analysis results & tracking
    ├── last_successful_run.txt
    └── dmarc_analysis_*.txt
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
    "tenant_id": "your-azure-tenant-id"
  },
  "claude": {
    "api_key": "your-claude-api-key"
  },
  "notifications": {
    "email_to": "your-email@domain.com"
  }
}
```

### 6. Set Up Outlook Folders
1. Open Outlook → Create folder **"DMARC Reports"**
2. Set up email rule to move DMARC reports to this folder:
   - **Condition**: Subject contains "DMARC" OR from domain contains your domain
   - **Action**: Move to "DMARC Reports" folder

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
    "folder_name": "DMARC Reports",
    "lookback_hours": 24,
    "max_lookback_hours": 168
  },
  "notifications": {
    "email_results": true,
    "email_to": "your-email@domain.com", 
    "email_subject_prefix": "[DMARC Analysis]",
    "quiet_mode": true
  },
  "logging": {
    "level": "INFO",
    "file": "logs/dmarc_monitor.log"
  }
}
```

### Key Settings Explained
- **`quiet_mode`**: `true` = no email when no reports found, `false` = always send status email
- **`lookback_hours`**: Default hours to check on first run (24 hours)
- **`max_lookback_hours`**: Maximum lookback to prevent overwhelming (168 = 7 days)
- **`model`**: Claude model to use (`claude-sonnet-4-20250514` recommended)

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

### Consolidated Email Report
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