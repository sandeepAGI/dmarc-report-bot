#!/usr/bin/env python3
"""
Enhanced Reporting Module for DMARC Monitor - Phase 3
Clean, jargon-free reports with per-domain emails and structured Claude output parsing.
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class EnhancedReporter:
    def __init__(self, config: Dict, database):
        self.config = config
        self.db = database
        self.thresholds = config.get('thresholds', {})

    # ─────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────

    def generate_smart_report(self, analyzed_reports: List[Dict]) -> Dict:
        """Generate report for one exact domain's batch of DMARC report files."""
        if not analyzed_reports:
            return self._create_no_reports_summary()

        reports_with_issues = []
        clean_reports = []
        for report in analyzed_reports:
            if self._has_significant_issues(report):
                reports_with_issues.append(report)
            else:
                clean_reports.append(report)

        if reports_with_issues:
            return self._create_issues_report(reports_with_issues, clean_reports)
        elif self.config['notifications'].get('send_clean_status', True):
            return self._create_clean_status_report(clean_reports)
        return None

    def should_send_report(self, report_data: Optional[Dict]) -> bool:
        if not report_data:
            return False
        if report_data.get('has_issues', False):
            return True
        if self.config['notifications'].get('send_clean_status', True):
            return True
        if report_data.get('no_reports', False) and not self.config['notifications'].get('quiet_mode', True):
            return True
        return False

    # ─────────────────────────────────────────────────────────────
    # Issue detection — data-driven only, no Claude text scanning
    # ─────────────────────────────────────────────────────────────

    def _has_significant_issues(self, report: Dict) -> bool:
        """A report has issues only when at least one email was quarantined or rejected."""
        return any(
            r['disposition'] != 'none'
            for r in report['raw_data']['records']
        )

    # ─────────────────────────────────────────────────────────────
    # Helpers — stats and formatting
    # ─────────────────────────────────────────────────────────────

    def _format_timestamp(self, ts) -> str:
        try:
            return datetime.fromtimestamp(int(ts)).strftime('%b %d, %Y')
        except (ValueError, TypeError):
            return str(ts)

    def _get_date_range(self, reports: List[Dict]) -> str:
        """Return human-readable date range across all report files."""
        begins, ends = [], []
        for report in reports:
            dr = report['raw_data']['metadata']['date_range']
            try:
                begins.append(int(dr['begin']))
                ends.append(int(dr['end']))
            except (ValueError, TypeError, KeyError):
                pass
        if not begins:
            return datetime.now().strftime('%b %d, %Y')
        start = datetime.fromtimestamp(min(begins))
        end = datetime.fromtimestamp(max(ends))
        if start.year == end.year and start.month == end.month:
            return f"{start.strftime('%b %d')}–{end.strftime('%d, %Y')}"
        elif start.year == end.year:
            return f"{start.strftime('%b %d')} – {end.strftime('%b %d, %Y')}"
        return f"{start.strftime('%b %d, %Y')} – {end.strftime('%b %d, %Y')}"

    def _get_batch_stats(self, reports: List[Dict]) -> Dict:
        """Aggregate totals from current report batch (not DB history)."""
        total = successful = 0
        reporters = set()
        for report in reports:
            for r in report['raw_data']['records']:
                total += r['count']
                if r['disposition'] == 'none':
                    successful += r['count']
            org = report['raw_data']['metadata'].get('org_name', '')
            if org:
                reporters.add(org)
        auth_rate = (successful / total * 100) if total > 0 else 100.0
        return {
            'total': total,
            'successful': successful,
            'failed': total - successful,
            'auth_rate': auth_rate,
            'reporters': sorted(reporters),
        }

    def _get_passing_summary(self, reports: List[Dict], sources: Dict[str, str] = None) -> Dict[str, int]:
        """Map organization name → count of passing emails using Claude's provider names."""
        if sources is None:
            sources = {}
        by_org: Dict[str, int] = {}
        for report in reports:
            for r in report['raw_data']['records']:
                if r['disposition'] == 'none':
                    org = sources.get(r['source_ip'], 'Unknown Provider')
                    by_org[org] = by_org.get(org, 0) + r['count']
        return by_org

    # ─────────────────────────────────────────────────────────────
    # Claude output parsing
    # ─────────────────────────────────────────────────────────────

    def _parse_claude_sources(self, claude_analysis: str) -> Dict[str, str]:
        """Parse SOURCES section → {ip: company_name}."""
        sources: Dict[str, str] = {}
        # Extract text between SOURCES: and FAILURES:
        m = re.search(r'SOURCES:\s*\n(.*?)(?=\nFAILURES:)', claude_analysis, re.DOTALL | re.IGNORECASE)
        if not m:
            return sources
        for line in m.group(1).strip().split('\n'):
            # Format: IP: x.x.x.x | Company: Name
            ip_match = re.match(r'IP:\s*(\S+)\s*\|\s*Company:\s*(.+)', line, re.IGNORECASE)
            if ip_match:
                sources[ip_match.group(1).strip()] = ip_match.group(2).strip()
        return sources

    def _parse_claude_notes(self, claude_analysis: str) -> List[str]:
        """Parse NOTES section → list of informational note strings."""
        m = re.search(r'\nNOTES:\s*\n(.*?)(?=\nRECOMMENDATIONS:)', claude_analysis, re.DOTALL | re.IGNORECASE)
        if not m:
            return []
        text = m.group(1).strip()
        if text.lower().rstrip('.') in ('none', 'n/a'):
            return []
        return [line.strip() for line in text.split('\n') if line.strip()]

    def _parse_claude_failures(self, claude_analysis: str) -> List[Dict]:
        """Parse the structured FAILURES: section from Claude's output."""
        failures = []
        # Extract text between FAILURES: and NOTES: (or RECOMMENDATIONS: for backward compat)
        m = re.search(r'\nFAILURES:\s*\n(.*?)(?=\n(?:NOTES|RECOMMENDATIONS):)', claude_analysis, re.DOTALL | re.IGNORECASE)
        if m:
            failures_text = m.group(1).strip()
        else:
            # Fallback: old two-section format
            parts = re.split(r'\nRECOMMENDATIONS:', claude_analysis, flags=re.IGNORECASE)
            failures_text = re.sub(r'^FAILURES:\s*\n?', '', parts[0], flags=re.IGNORECASE).strip()

        if not failures_text or failures_text.lower().rstrip('.') in ('none', 'n/a'):
            return failures

        # Each IP block starts with "IP:"
        blocks = re.split(r'\n(?=IP:)', failures_text)
        for block in blocks:
            block = block.strip()
            if not block:
                continue
            parsed: Dict = {}
            current_key: Optional[str] = None
            current_lines: List[str] = []

            for line in block.split('\n'):
                field_match = re.match(
                    r'^(IP|Company|Emails|Risk|What happened|What to do):\s*(.*)',
                    line, re.IGNORECASE
                )
                if field_match:
                    if current_key:
                        parsed[current_key] = '\n'.join(current_lines).strip()
                    current_key = field_match.group(1).lower().replace(' ', '_')
                    current_lines = [field_match.group(2)]
                elif current_key:
                    current_lines.append(line)

            if current_key:
                parsed[current_key] = '\n'.join(current_lines).strip()

            if 'ip' in parsed:
                failures.append(parsed)

        return failures

    def _parse_claude_recommendations(self, claude_analysis: str) -> List[str]:
        """Parse the structured RECOMMENDATIONS: section from Claude's output."""
        parts = re.split(r'\nRECOMMENDATIONS:', claude_analysis, flags=re.IGNORECASE)
        if len(parts) < 2:
            return []
        rec_text = parts[1].strip()
        if rec_text.lower().rstrip('.') in ('none at this time', 'none', 'n/a'):
            return []

        recommendations: List[str] = []
        current: List[str] = []
        for line in rec_text.split('\n'):
            line_s = line.strip()
            if not line_s:
                if current:
                    recommendations.append('\n'.join(current))
                    current = []
                continue
            if re.match(r'^\d+\.', line_s):
                if current:
                    recommendations.append('\n'.join(current))
                current = [line_s]
            elif current:
                current.append(line_s)
        if current:
            recommendations.append('\n'.join(current))
        return recommendations

    def _collect_sources(self, reports: List[Dict]) -> Dict[str, str]:
        """Merge SOURCES sections across all report files → {ip: company}."""
        merged: Dict[str, str] = {}
        for report in reports:
            merged.update(self._parse_claude_sources(report.get('claude_analysis', '')))
        return merged

    def _get_recommendations_section(self, reports: List[Dict]) -> List[str]:
        """Collect and deduplicate recommendations across all report files."""
        all_recs: List[str] = []
        seen: set = set()
        for report in reports:
            for rec in self._parse_claude_recommendations(report.get('claude_analysis', '')):
                key = re.sub(r'\s+', ' ', rec.lower().strip())[:100]
                if key not in seen:
                    seen.add(key)
                    all_recs.append(rec)
        return all_recs

    # ─────────────────────────────────────────────────────────────
    # Report builders
    # ─────────────────────────────────────────────────────────────

    _DIV = '─' * 61

    def _recommendations_block(self, reports: List[Dict]) -> str:
        recs = self._get_recommendations_section(reports)
        if not recs:
            return ''
        lines = [f"{self._DIV}\nRECOMMENDATIONS\n{self._DIV}"]
        for i, rec in enumerate(recs, 1):
            rec_lines = rec.split('\n')
            # Strip any leading number Claude may have included (e.g. "1. Upgrade...")
            first_line = re.sub(r'^\d+\.\s*', '', rec_lines[0])
            lines.append(f"{i}. {first_line}")
            for extra in rec_lines[1:]:
                lines.append(f"   {extra}")
        lines.append(self._DIV)
        return '\n'.join(lines) + '\n'

    def _create_clean_status_report(self, clean_reports: List[Dict]) -> Dict:
        domain = clean_reports[0]['raw_data']['policy']['domain']
        date_range = self._get_date_range(clean_reports)
        stats = self._get_batch_stats(clean_reports)
        sources = self._collect_sources(clean_reports)
        reporter_list = ', '.join(stats['reporters']) if stats['reporters'] else 'various sources'

        subject = f"✅ DMARC Report — {domain} — All Clear"

        body = (
            f"✅ DMARC Report — {domain}\n"
            f"{date_range}\n\n"
            f"Good news — all emails verified successfully this period.\n\n"
            f"EMAILS VERIFIED\n"
            f"{self._DIV}\n"
            f"  {stats['total']} total emails, {stats['auth_rate']:.0f}% verified ✅\n"
            f"  Reported by: {reporter_list}\n"
            f"{self._DIV}\n\n"
        )

        # Passing summary with Claude-sourced provider names
        passing_by_org = self._get_passing_summary(clean_reports, sources)
        if passing_by_org:
            body += f"EMAILS BY PROVIDER\n{self._DIV}\n"
            for org, count in sorted(passing_by_org.items(), key=lambda x: -x[1]):
                body += f"  • {org}: {count} emails ✅\n"
            body += f"{self._DIV}\n\n"

        # NOTES section (informational findings like SPF-only failures saved by DKIM)
        all_notes: List[str] = []
        for report in clean_reports:
            all_notes.extend(self._parse_claude_notes(report.get('claude_analysis', '')))
        if all_notes:
            body += f"NOTES\n{self._DIV}\n"
            for note in all_notes:
                body += f"  {note}\n"
            body += f"{self._DIV}\n\n"

        body += self._recommendations_block(clean_reports)
        body += f"\n─\nReport generated {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"

        return {'subject': subject, 'body': body, 'has_issues': False, 'clean_count': len(clean_reports)}

    def _create_issues_report(self, issues_reports: List[Dict], clean_reports: List[Dict]) -> Dict:
        all_reports = issues_reports + clean_reports
        domain = all_reports[0]['raw_data']['policy']['domain']
        date_range = self._get_date_range(all_reports)
        stats = self._get_batch_stats(all_reports)
        sources = self._collect_sources(all_reports)

        subject = f"⚠️ ACTION NEEDED — DMARC Report — {domain}"

        body = (
            f"⚠️  DMARC Report — {domain} — ACTION NEEDED\n"
            f"{date_range}\n\n"
            f"WHAT HAPPENED\n"
            f"{stats['failed']} out of {stats['total']} emails from {domain} could not be\n"
            f"verified as coming from you.\n\n"
        )

        # Collect and deduplicate Claude-parsed failure blocks
        seen_ips: set = set()
        all_failures: List[Dict] = []
        for report in issues_reports:
            for f in self._parse_claude_failures(report.get('claude_analysis', '')):
                if f.get('ip') not in seen_ips:
                    seen_ips.add(f.get('ip'))
                    all_failures.append(f)

        # Fallback: build failure blocks from raw records if Claude parsing yielded nothing
        if not all_failures:
            for report in issues_reports:
                for r in report['raw_data']['records']:
                    if r['disposition'] != 'none':
                        ip = r['source_ip']
                        if ip not in seen_ips:
                            seen_ips.add(ip)
                            company = sources.get(ip, 'Unknown Provider')
                            all_failures.append({
                                'ip': ip,
                                'company': company,
                                'emails': r['count'],
                                'risk': 'INVESTIGATE',
                                'what_happened': f"{r['count']} emails came from this server but could not be verified.",
                                'what_to_do': 'Contact your IT provider or email service to investigate this IP address.',
                            })

        # Only show FAILED EMAILS section if there are failures to render
        if all_failures:
            body += (
                f"{self._DIV}\n"
                f"FAILED EMAILS — WHAT TO DO\n"
                f"{self._DIV}\n"
            )

            for failure in all_failures:
                ip = failure.get('ip', 'Unknown IP')
                company = failure.get('company', 'Unknown')
                emails = failure.get('emails', '?')
                risk = (failure.get('risk') or 'INVESTIGATE').upper()
                what_happened = failure.get('what_happened', '')
                what_to_do = failure.get('what_to_do', '')

                risk_icon = '🚨' if risk == 'SUSPICIOUS' else '⚠️'
                body += f"\n{risk_icon} {company} ({ip}) — {emails} emails — {risk}\n"
                if what_happened:
                    for line in what_happened.split('\n'):
                        body += f"   {line}\n"
                if what_to_do:
                    body += "\n"
                    for line in what_to_do.split('\n'):
                        body += f"   {line}\n"

        # Passing summary with Claude-sourced provider names
        passing_by_org = self._get_passing_summary(all_reports, sources)
        if passing_by_org:
            body += f"\n{self._DIV}\nEMAILS THAT PASSED\n{self._DIV}\n"
            for org, count in sorted(passing_by_org.items(), key=lambda x: -x[1]):
                body += f"  • {org}: {count} emails ✅\n"
            body += "\n"

        body += self._recommendations_block(all_reports)
        body += f"\n─\nReport generated {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"

        return {'subject': subject, 'body': body, 'has_issues': True, 'issue_count': len(issues_reports)}

    def _create_no_reports_summary(self) -> Dict:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = f"{self.config['notifications']['email_subject_prefix']} 📭 No New DMARC Reports"
        body = (
            f"📭 NO NEW REPORTS — {timestamp}\n\n"
            f"STATUS\n"
            f"• No new DMARC reports found since last check\n"
            f"• System is monitoring normally\n"
            f"• All configured email folders checked\n\n"
            f"─\nDMARC Monitor is actively checking for new reports\n"
        )
        return {'subject': subject, 'body': body, 'has_issues': False, 'no_reports': True}
