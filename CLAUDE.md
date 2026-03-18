Please start with reviewing the README.md and the code base

## Commands & Setup

```bash
# Run the monitor (fetches emails since last run, sends report emails)
cd ~/myworkspace/Utilities/dmarc-monitor && python3 src/dmarc_monitor.py

# Force a wider lookback (e.g. 3 days) — temporarily back-date last run
echo "2026-03-14T10:00:00" > data/last_successful_run.txt
python3 src/dmarc_monitor.py

# Run end-to-end test (no real emails — uses temp DB, prints report to stdout)
python3 scripts/test_end_to_end.py

# Process historical backlog (prompts for confirmation)
python3 scripts/catchup_backlog.py

# View historical analysis from DB
python3 scripts/generate_historical_report.py

# Database maintenance
python3 scripts/database_maintenance.py stats
python3 scripts/database_maintenance.py purge --days 30 --dry-run
```

**Required files (not in git):**
- `config/config.json` — copy from `config/config.json.template`, fill in credentials
- `outlook_token.json` — auto-created on first run via browser OAuth flow

**Cron schedule:** Mon–Fri 10 AM main run, 5 PM retry if morning failed.

---

## Architecture

```
src/dmarc_monitor.py        # Entry point: auth, fetch emails, parse XML, call Claude, send emails
src/enhanced_reporting.py   # Builds clean/issue report emails; parses Claude's structured output
src/database.py             # SQLite storage, IP intelligence, historical trend queries
src/non_technical_formatter.py  # IP lookup helpers used by database.py (not used by enhanced_reporting)
config/config.json          # Credentials + thresholds (gitignored)
data/last_successful_run.txt  # Dynamic lookback anchor — delete to reprocess
data/dmarc_monitor.db       # SQLite DB (30-day rolling retention)
```

**Flow:** fetch emails → parse DMARC XML → Claude analysis (structured) → store in DB → group by exact domain → send one email per domain.

---

## PHASE 3: REPORT REDESIGN (2026-03-17)

Complete rewrite of `src/enhanced_reporting.py` and targeted changes to `src/dmarc_monitor.py`.

### Bug Fixed: Domain Grouping

`connect.aileron-group.com` was being silently merged with `aileron-group.com` because the old `get_root_domain()` function stripped both to the same two-part key. Fix: removed `get_root_domain()` entirely. Reports now group by the **exact domain string** from the DMARC XML. One email is sent per exact domain.

### New Report Formats

**Clean report** — no AI analysis body, just summary + human-readable date + recommendations from Claude:
```
✅ DMARC Report — aileron-group.com
Mar 14–15, 2026

Good news — all emails verified successfully this period.

EMAILS VERIFIED
─────────────────────────────────────────────────────────────
  30 total emails, 100% verified ✅
  Reported by: Google
─────────────────────────────────────────────────────────────

RECOMMENDATIONS
─────────────────────────────────────────────────────────────
1. Upgrade your DMARC policy from p=none to p=quarantine...
─────────────────────────────────────────────────────────────
```

**Issue report** — plain-English "what happened" + per-IP step-by-step fix blocks (from Claude) + passing email summary + recommendations:
```
⚠️  DMARC Report — connect.aileron-group.com — ACTION NEEDED
Mar 14–15, 2026

WHAT HAPPENED
3 out of 26 emails from connect.aileron-group.com could not be
verified as coming from you.

─────────────────────────────────────────────────────────────
FAILED EMAILS — WHAT TO DO
─────────────────────────────────────────────────────────────
⚠️ Amazon AWS (35.174.145.124) — 3 emails — INVESTIGATE
   [plain-English explanation + numbered fix steps]

─────────────────────────────────────────────────────────────
EMAILS THAT PASSED
─────────────────────────────────────────────────────────────
  • Microsoft Office 365: 18 emails ✅

─────────────────────────────────────────────────────────────
RECOMMENDATIONS
─────────────────────────────────────────────────────────────
1. Upgrade DMARC policy from p=none to p=quarantine...
─────────────────────────────────────────────────────────────
```

### Key Design Decisions

- **Issue detection is data-driven only**: `_has_significant_issues()` checks auth rate < 95%, historical decline > 5%, and new-source spikes. The old Claude-text keyword scan (which was fragile and inconsistent) is gone.
- **p=none is a recommendation, not an issue**: Shown in every report's RECOMMENDATIONS section — it never triggers an "issue" email on its own.
- **All recommendations come from Claude**: No hardcoded policy-upgrade logic in the code. Claude's structured output drives the RECOMMENDATIONS section.
- **Timestamps are human-readable**: Unix integers (e.g. `1755820800`) converted to `Aug 21, 2025` everywhere.
- **`non_technical_formatter.py` is no longer used by enhanced_reporting.py**: The new design gets plain English directly from Claude's structured prompt output. The file remains on disk but is not imported.

### New Claude Prompt Structure

Claude now outputs exactly two sections (parseable by `enhanced_reporting.py`):
```
FAILURES:
IP: [address]
Company: [who owns it]
Emails: [count]
Risk: SUSPICIOUS / INVESTIGATE / LIKELY OK
What happened: [1-2 plain-English sentences]
What to do: [numbered step-by-step instructions]

RECOMMENDATIONS:
1. [improvement — plain-English reason + exact change needed]
```

If Claude API is unavailable, `_get_fallback_analysis()` generates the **same structured format** so the parsing code works identically in both paths.

### Files Changed

- **`src/dmarc_monitor.py`**: New structured Claude prompt, removed `get_root_domain()`, removed subject prefix injection, updated fallback to produce structured format
- **`src/enhanced_reporting.py`**: Full rewrite — new `_has_significant_issues()` (data-driven), `_format_timestamp()`, `_get_date_range()`, `_get_batch_stats()`, `_get_passing_summary()`, `_parse_claude_failures()`, `_parse_claude_recommendations()`, `_get_recommendations_section()`, `_create_clean_status_report()`, `_create_issues_report()`

---

## CRITICAL FIXES (2025-11-08)

The system had stopped processing reports for ~2-3 weeks (456 backlogged reports). Key fixes:

1. **Wrong mailbox authenticated** — was using `sandeep@aileron-group.com` instead of `member@aileron-group.com`. Fixed via `mailbox_account` config key + `login_hint` OAuth param.
2. **Missing pagination** — Graph API returned only first 10 messages. Fixed with `@odata.nextLink` loop.
3. **No auto-move** — processed emails stayed in "DMARC Reports". Fixed: auto-moved to "DMARC Processed" after each run.

**Key config added:**
```json
{
  "email": {
    "mailbox_account": "member@aileron-group.com",
    "processed_folder": "DMARC Processed",
    "lookback_hours": 72,
    "max_lookback_hours": 168
  }
}
```

**Key insight:** Google SPF failures on `209.85.220.x` are normal (email forwarding behaviour) — DKIM passes, so DMARC alignment holds. Not a security issue.

---

## RECENT IMPROVEMENTS (2025-08-25)

Added plain-English reporting (`non_technical_formatter.py`), Claude API retry logic (3 attempts, exponential backoff 2s/4s/8s), 45s timeout, and fallback analysis when Claude is unavailable.

*(Note: The hybrid report format from this period was superseded by the Phase 3 redesign above.)*
