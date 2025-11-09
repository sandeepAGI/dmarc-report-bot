Please start with reviewing the README.md and the code base

## CRITICAL FIXES & IMPROVEMENTS (2025-11-08)

The DMARC monitoring system had stopped processing reports for ~2-3 weeks (456 backlogged reports). Root cause analysis and comprehensive fixes were implemented:

### Issues Fixed:

1. **Authentication to Wrong Mailbox** (CRITICAL FIX)
   - **Problem**: System was authenticating as `sandeep@aileron-group.com` instead of `member@aileron-group.com` where DMARC reports actually land
   - **Impact**: "DMARC Reports" folder appeared empty, 456 reports went unprocessed for weeks
   - **Solution**: Added `mailbox_account` config parameter and `login_hint` OAuth parameter to force correct account authentication
   - **Files Modified**: `src/dmarc_monitor.py:130-158`, `config/config.json:13`

2. **Missing Pagination in Email Retrieval** (HIGH PRIORITY FIX)
   - **Problem**: Graph API only returned first page (10 messages) instead of all messages due to missing pagination
   - **Impact**: Only 5-10 reports processed per run instead of all available
   - **Solution**: Implemented `@odata.nextLink` pagination loop to retrieve all messages
   - **Files Modified**: `src/dmarc_monitor.py:289-305`

3. **No Email Auto-Move Functionality** (NEW FEATURE)
   - **Problem**: Processed emails remained in "DMARC Reports" folder, causing clutter
   - **Impact**: 457+ processed reports sitting in inbox folder
   - **Solution**: Implemented automatic move to "DMARC Processed" folder after successful processing
   - **Files Added**: `scripts/move_processed_emails.py`
   - **Files Modified**: `src/dmarc_monitor.py:355-397, 898-989`

4. **Configuration Improvements**
   - **Lookback Hours**: Changed from 24h to 72h to properly cover weekends for Monday runs
   - **Max Lookback**: Set to 168h (7 days) for extended outages
   - **Dynamic Lookback**: System already calculates based on last successful run, but defaults improved for safety

### New Functionality:

1. **Automatic Email Organization**:
   - Processed reports automatically moved from "DMARC Reports" → "DMARC Processed"
   - Keeps inbox clean while preserving audit trail
   - Added `get_folder_id()` and `move_message()` methods to OutlookClient class

2. **Backlog Catch-Up Script**:
   - `scripts/catchup_backlog.py` - One-time script to process all historical reports
   - Safely backs up and restores `last_successful_run.txt`
   - User confirmation before processing
   - Successfully processed all 456 backlogged reports (May 31 - Nov 8, 2025)

3. **Historical Reporting**:
   - `scripts/generate_historical_report.py` - Query database for consolidated historical analysis
   - Shows authentication trends, failing IPs, security alerts
   - Useful for post-catch-up analysis

### Configuration Changes:

```json
{
  "email": {
    "mailbox_account": "member@aileron-group.com",  // NEW: Forces correct account auth
    "folder_name": "DMARC Reports",
    "processed_folder": "DMARC Processed",
    "lookback_hours": 72,      // CHANGED: from 24 to cover weekends
    "max_lookback_hours": 168  // CHANGED: from 4320 to 7 days
  }
}
```

### Test Scripts Added:

- `scripts/test_fixed_authentication.py` - Verify correct mailbox authentication
- `scripts/move_processed_emails.py` - One-time cleanup of 457 backlogged emails
- `scripts/catchup_backlog.py` - Process all historical reports with safety checks

### Results from Catch-Up:

- **456 reports processed** (Oct 10 - Nov 8, 2025; some older purged by 30-day retention)
- **81 reports retained** in database (last 30 days)
- **104 reports had authentication issues** (< 100% success rate)
- **30 unique failing IP addresses** identified
- **Average authentication rates**: aileron-group.com (89.6%), training.aileron-group.com (92.3%)

### Key Insights from Historical Analysis:

1. **Google SPF Failures are Normal**: DKIM passes but SPF fails on Google IPs (209.85.220.x) - this is expected email forwarding behavior, not a security issue
2. **SPF Records Already Correct**: Both domains have `include:_spf.google.com` properly configured
3. **DMARC Policy Recommendation**: Safe to upgrade from `p=none` to `p=quarantine` since DKIM alignment will protect forwarded emails

### How It Works Now:

1. Cron job runs Mon-Fri at 10 AM (with 5 PM retry)
2. Authenticates to **member@aileron-group.com** (correct mailbox)
3. Retrieves **all messages** from last run via pagination
4. Processes each DMARC report (parse, analyze, store in DB)
5. **Automatically moves processed emails** to "DMARC Processed" folder
6. Sends consolidated email report
7. Updates `last_successful_run.txt` for next dynamic lookback calculation

### Files Modified Summary:

- **config/config.json**: Added `mailbox_account`, adjusted lookback hours
- **src/dmarc_monitor.py**: Fixed auth (login_hint), pagination, added auto-move functionality
- **scripts/catchup_backlog.py**: NEW - Backlog processing with safety checks
- **scripts/move_processed_emails.py**: NEW - Bulk email mover for cleanup
- **scripts/generate_historical_report.py**: NEW - Database reporting tool
- **scripts/test_fixed_authentication.py**: NEW - Auth verification test

### System Status:

✅ Authentication fixed - using correct mailbox
✅ Pagination implemented - retrieves all messages
✅ Auto-move implemented - keeps folders organized
✅ All 456 historical reports processed and stored in database
✅ Folders cleaned up - 457 emails moved to "DMARC Processed"
✅ Configuration optimized for Mon-Fri cron schedule
✅ Ready for normal operations

---

## RECENT IMPROVEMENTS (2025-08-25)

The DMARC monitoring system has been enhanced with non-technical user friendly reporting:

### New Features Implemented:

1. **Plain English Explanations**: All technical terms (DKIM, SPF, authentication) now have clear business explanations
2. **Risk-Based Priority System**: Reports show CRITICAL/HIGH/MODERATE/LOW risk levels with color coding
3. **Enhanced IP Investigation**: Claude now investigates each IP to identify if it's Google, Microsoft, AWS, or suspicious
4. **DIY Action Steps**: Step-by-step instructions for fixing issues without IT support
5. **Business Impact Analysis**: Clear explanation of what failures mean for your business
6. **Hybrid Report Format**: Every report includes both plain English and technical details
7. **API Retry Logic**: Automatic retry with exponential backoff (2s, 4s, 8s) when Claude API fails
8. **Fallback Analysis**: Basic analysis provided when Claude is completely unavailable
9. **Improved Timeout**: Increased from 30s to 45s for better reliability

### Files Added/Modified:

- `src/non_technical_formatter.py` - New module for plain English formatting
- `src/enhanced_reporting.py` - Updated to use hybrid format
- `src/dmarc_monitor.py` - Enhanced Claude prompt for better IP investigation + retry logic
- `scripts/test_enhanced_reporting.py` - Test suite for new features
- `scripts/test_retry_logic.py` - Test suite for retry and fallback logic

### How It Works:
- Your existing cron job continues to work exactly the same
- Reports are now automatically enhanced with plain English explanations
- No configuration changes needed - improvements are automatic

I would like us to review a few of the emails that I get.

Example 1:
"🚨 DMARC ISSUES DETECTED - 2025-08-25 10:02:32
============================================================

EXECUTIVE SUMMARY
• Total Reports Analyzed: 10
• Reports with Issues: 4
• Clean Reports: 6
• Total Email Messages: 81
• Average Authentication Rate: 91.8%

DOMAINS REQUIRING ATTENTION
============================================================

1. training.aileron-group.com (reported by Enterprise Outlook)
--------------------------------------------------
📊 Authentication Rate: 93.8% (15/16 messages)
📈 Historical Trend: Improved (+5.4% vs 30-day avg)
⏰ Report Period: 1755820800 to 1755907200

🔍 DETAILED FAILURE ANALYSIS:

  Failed Authentication Details:
  • 1 IP(s) with 1 failed message(s)

  • 35.174.145.124: 1 message(s) - DKIM ❌ FAIL, SPF ❌ FAIL
    └─ Unknown Provider

  📋 RECOMMENDED ACTIONS:
  1. **Investigate IP range 35.174.x.x:** All failures from same subnet
  2. **DKIM Issues:** 1 IP(s) failing DKIM - check signing configuration
  3. **SPF Issues:** 1 IP(s) failing SPF - verify authorized senders
  4. **Verification Steps:**
     - Check SPF record: dig TXT training.aileron-group.com | grep spf
     - Verify these IPs are legitimate senders for training.aileron-group.com
     - If legitimate: update SPF record and configure DKIM
     - If malicious: consider abuse reporting


🔍 ANALYSIS & RECOMMENDATIONS:
  1. **Investigate AWS IP**: Check if 35.174.145.124 is a legitimate service you use
  - If legitimate: Add to SPF record and configure DKIM
  - If unauthorized: Monitor for additional attempts
  2. **Review Email Sources**: Verify all authorized senders are properly configured
  • ### Medium-term Improvements
  3. **Strengthen DMARC Policy**: Consider upgrading from `p=none` to `p=quarantine` after confirming all legitimate sources pass authentication
  • 4. **Monitor Trends**: Continue tracking this IP and similar authentication failures
  • ### Current Security Posture
  • Your email authentication is working well for legitimate Microsoft 365 traffic, but the AWS failure indicates potential unauthorized use of your domain that requires investigation.


2. training.aileron-group.com (reported by Enterprise Outlook)
--------------------------------------------------
📊 Authentication Rate: 100.0% (11/11 messages)
📈 Historical Trend: Improved (+11.7% vs 30-day avg)
⏰ Report Period: 1755734400 to 1755820800

🔍 ANALYSIS & RECOMMENDATIONS:
  • ### Strategic Improvements:
  1. **Upgrade DMARC Policy**:
  - Current: `p=none` (monitoring only)
  - **Recommended**: Gradually move to `p=quarantine` then `p=reject` for stronger protection
  2. **Monitor Trends**: Continue monitoring future reports to establish baseline traffic patterns
  3. **Document Baseline**: Record these legitimate Microsoft IPs as authorized senders for future reference
  • ### Next Steps:
  - **Week 1-2**: Review additional reports to confirm consistent authentication success
  - **Week 3-4**: Consider testing `p=quarantine` policy if patterns remain stable
  - **Month 2+**: Evaluate upgrade to `p=reject` for maximum protection
  **Status**: Your email authentication is working excellently. Focus on policy strengthening when ready.


3. training.aileron-group.com (reported by google.com)
--------------------------------------------------
📊 Authentication Rate: 71.4% (10/14 messages)
📈 Historical Trend: Declined (-16.9% vs 30-day avg)
⏰ Report Period: 1755820800 to 1755907199

🔍 DETAILED FAILURE ANALYSIS:

  Failed Authentication Details:
  • 4 IP(s) with 4 failed message(s)

  • 209.85.220.41: 1 message(s) - DKIM ✅ PASS, SPF ❌ FAIL
    └─ Google LLC (Gmail)
  • 209.85.220.41: 1 message(s) - DKIM ✅ PASS, SPF ❌ FAIL
    └─ Google LLC (Gmail)
  • 209.85.220.41: 1 message(s) - DKIM ✅ PASS, SPF ❌ FAIL
    └─ Google LLC (Gmail)
  • 209.85.220.69: 1 message(s) - DKIM ✅ PASS, SPF ❌ FAIL
    └─ Google LLC (Gmail)

  📋 RECOMMENDED ACTIONS:
  1. **Investigate IP range 209.85.x.x:** All failures from same subnet
  3. **SPF Issues:** 4 IP(s) failing SPF - verify authorized senders
  4. **Verification Steps:**
     - Check SPF record: dig TXT training.aileron-group.com | grep spf
     - Verify these IPs are legitimate senders for training.aileron-group.com
     - If legitimate: update SPF record and configure DKIM
     - If malicious: consider abuse reporting


🔍 ANALYSIS & RECOMMENDATIONS:
  1. **Investigate SPF Record**: Review your SPF record to ensure it includes the failing IP `209.85.220.41`
  2. **Verify Email Sources**: Confirm if `209.85.220.41` is an authorized sender for your domain
  • ### Next Steps
  3. **Update SPF Record**: Add missing authorized IPs to your SPF record
  • 4. **Monitor Results**: Wait 1-2 weeks to confirm SPF failures are resolved
  • 5. **Strengthen Policy**: Once SPF issues are fixed, consider upgrading DMARC policy to `quarantine` then `reject`
  • ### Policy Progression Path
  • ```
  • Current: p=none → Target: p=quarantine → Goal: p=reject
  • ```
  **Priority Level**: 🟡 **MEDIUM** - Address SPF issues before enforcing stricter DMARC policies.


4. training.aileron-group.com (reported by Enterprise Outlook)
--------------------------------------------------
📊 Authentication Rate: 83.3% (15/18 messages)
📈 Historical Trend: Declined (-5.0% vs 30-day avg)
⏰ Report Period: 1755648000 to 1755734400

🔍 DETAILED FAILURE ANALYSIS:

  Failed Authentication Details:
  • 3 IP(s) with 3 failed message(s)

  • 2a01:111:f403:2009::70e: 1 message(s) - DKIM ❌ FAIL, SPF ✅ PASS
    └─ Unknown Provider
  • 2a01:111:f403:200a::722: 1 message(s) - DKIM ❌ FAIL, SPF ✅ PASS
    └─ Unknown Provider
  • 35.174.145.124: 1 message(s) - DKIM ❌ FAIL, SPF ❌ FAIL
    └─ Unknown Provider

  📋 RECOMMENDED ACTIONS:
  1. **Investigate 3 different IP sources:** Multiple failure points detected
  2. **DKIM Issues:** 3 IP(s) failing DKIM - check signing configuration
  3. **SPF Issues:** 1 IP(s) failing SPF - verify authorized senders
  4. **Verification Steps:**
     - Check SPF record: dig TXT training.aileron-group.com | grep spf
     - Verify these IPs are legitimate senders for training.aileron-group.com
     - If legitimate: update SPF record and configure DKIM
     - If malicious: consider abuse reporting


🔍 ANALYSIS & RECOMMENDATIONS:
  1. **Investigate AWS source**: Block or authorize `35.174.145.124` - verify if this is a legitimate service
  2. **Review DKIM configuration**: Check for recent key rotations or configuration changes
  3. **Monitor trend**: Watch for recurring failures from the same sources
  1. **Consider policy upgrade**: Move from `p=none` to `p=quarantine` after resolving current issues
  2. **Implement stricter monitoring**: Set up alerts for authentication failure rates >10%
  3. **Document legitimate senders**: Maintain a whitelist of authorized IP ranges
  • ### Priority Level: **MEDIUM**
  • While most traffic is legitimate Microsoft infrastructure, the AWS source requires immediate investigation to prevent potential spoofing attacks.


✅ CLEAN DOMAINS (6 domains)
============================================================
The following domains showed no significant issues:
• training.aileron-group.com: 6 messages processed successfully
• aileron-group.com: 3 messages processed successfully
• training.aileron-group.com: 1 messages processed successfully
• aileron-group.com: 4 messages processed successfully
• aileron-group.com: 7 messages processed successfully
• aileron-group.com: 1 messages processed successfully


============================================================
📧 Report generated by DMARC Monitor at 2025-08-25 10:02:32
🤖 Analysis powered by Claude AI with intelligent thresholds"

Example 2:
"🚨 DMARC ISSUES DETECTED - 2025-08-21 10:08:20
============================================================

EXECUTIVE SUMMARY
• Total Reports Analyzed: 6
• Reports with Issues: 1
• Clean Reports: 5
• Total Email Messages: 30
• Average Authentication Rate: 84.8%

DOMAINS REQUIRING ATTENTION
============================================================

1. training.aileron-group.com (reported by Enterprise Outlook)
--------------------------------------------------
📊 Authentication Rate: 73.3% (11/15 messages)
📈 Historical Trend: Stable (+0.9% vs 30-day avg)
⏰ Report Period: 1755475200 to 1755561600

🔍 DETAILED FAILURE ANALYSIS:

  Failed Authentication Details:
  • 4 IP(s) with 4 failed message(s)

  • 128.24.22.83: 1 message(s) - DKIM ✅ PASS, SPF ❌ FAIL
    └─ Unknown Provider
  • 35.174.145.124: 1 message(s) - DKIM ❌ FAIL, SPF ❌ FAIL
    └─ Unknown Provider
  • 35.174.145.124: 1 message(s) - DKIM ❌ FAIL, SPF ❌ FAIL
    └─ Unknown Provider
  • 40.107.237.126: 1 message(s) - DKIM ❌ FAIL, SPF ✅ PASS
    └─ Microsoft Corporation (Office 365)

  📋 RECOMMENDED ACTIONS:
  1. **Investigate 4 different IP sources:** Multiple failure points detected
  2. **DKIM Issues:** 3 IP(s) failing DKIM - check signing configuration
  3. **SPF Issues:** 3 IP(s) failing SPF - verify authorized senders
  4. **Verification Steps:**
     - Check SPF record: dig TXT training.aileron-group.com | grep spf
     - Verify these IPs are legitimate senders for training.aileron-group.com
     - If legitimate: update SPF record and configure DKIM
     - If malicious: consider abuse reporting


🔍 ANALYSIS & RECOMMENDATIONS:
See detailed analysis above.


✅ CLEAN DOMAINS (5 domains)
============================================================
The following domains showed no significant issues:
• aileron-group.com: 3 messages processed successfully
• training.aileron-group.com: 7 messages processed successfully
• aileron-group.com: 5 messages processed successfully
• aileron-group.com: 6 messages processed successfully
• training.aileron-group.com: 8 messages processed successfully


============================================================
📧 Report generated by DMARC Monitor at 2025-08-21 10:08:20
🤖 Analysis powered by Claude AI with intelligent thresholds"

Because I am not very technical and do not know what a DKIM fail vs. SPF fail vs what does authentication mean, these reports are not being very helpful.

Ideally, I need to have clear understanding of implications (if any) and what I need to do

Please propose improvements so that this is more helpful for me.
