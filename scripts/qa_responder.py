#!/usr/bin/env python3
"""
Q&A Responder for DMARC Monitor

Polls the inbox of member@aileron-group.com for reply emails to DMARC reports
and answers follow-up questions using Claude AI.

Cron schedule (Mon-Fri 8AM-8PM):
    0 8-20 * * 1-5 cd ~/myworkspace/Utilities/dmarc-monitor && \
        /opt/anaconda3/bin/python3 scripts/qa_responder.py >> logs/cron.log 2>&1
"""

import os
import sys
import re
import json
import logging
import time
from datetime import datetime
from typing import Optional

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from dmarc_monitor import OutlookClient, ClaudeAnalyzer, load_config
from database import DMARCDatabase

logger = logging.getLogger(__name__)


class QAResponder:
    REPLY_SUBJECT_PATTERN = re.compile(
        r'^Re:.*DMARC Report.*?[\u2014\u2013-]\s*([a-zA-Z0-9][a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        re.IGNORECASE,
    )
    QUOTE_MARKERS = [
        '\nFrom:',
        '\n-----Original Message-----',
        '\n________________________________',
    ]

    def __init__(self, config: dict, database, outlook_client, claude_analyzer):
        self.config = config
        self.database = database
        self.outlook_client = outlook_client
        self.claude_analyzer = claude_analyzer
        self.processed_folder = config.get('email', {}).get('processed_folder', 'DMARC Processed')
        self.email_to = config.get('notifications', {}).get('email_to', '')

    # ------------------------------------------------------------------
    # Subject parsing
    # ------------------------------------------------------------------

    def is_dmarc_reply(self, subject: str) -> bool:
        """Return True if the subject is a reply to one of our DMARC report emails."""
        return bool(self.REPLY_SUBJECT_PATTERN.search(subject))

    def extract_domain(self, subject: str) -> Optional[str]:
        """Extract the domain from a DMARC reply subject line."""
        match = self.REPLY_SUBJECT_PATTERN.search(subject)
        return match.group(1) if match else None

    # ------------------------------------------------------------------
    # Body parsing
    # ------------------------------------------------------------------

    def extract_question(self, body: str) -> Optional[str]:
        """
        Strip quoted reply content and return the user's plain-text question.
        Returns None when nothing remains after stripping.
        """
        # Remove Outlook / mail-client quote blocks
        for marker in self.QUOTE_MARKERS:
            if marker in body:
                body = body[:body.index(marker)]

        # Remove angle-quoted lines ("> text")
        lines = [line for line in body.split('\n') if not line.startswith('>')]

        result = '\n'.join(lines).strip()
        return result if result else None

    # ------------------------------------------------------------------
    # Claude interaction
    # ------------------------------------------------------------------

    def ask_claude(self, question: str, report_context: dict) -> str:
        """Build a context-aware prompt and call claude_analyzer.ask_question()."""
        domain = report_context.get('domain', 'unknown')
        date_begin = report_context.get('date_begin', 0)
        date_end = report_context.get('date_end', 0)
        auth_rate = report_context.get('auth_success_rate', 0)
        policy = report_context.get('policy_p', 'none')
        total_messages = report_context.get('total_messages', 0)
        claude_analysis = report_context.get('claude_analysis', '')

        try:
            begin_str = datetime.fromtimestamp(int(date_begin)).strftime('%b %d, %Y')
            end_str = datetime.fromtimestamp(int(date_end)).strftime('%b %d, %Y')
            date_range = f"{begin_str} \u2013 {end_str}"
        except (ValueError, TypeError):
            date_range = "unknown period"

        failures_summary = (
            "No failures"
            if claude_analysis.startswith("FAILURES:\nNone")
            else f"{total_messages} total emails, {auth_rate:.1f}% auth rate"
        )

        context = {
            'domain': domain,
            'date_range': date_range,
            'auth_rate': f"{auth_rate:.1f}",
            'policy': policy,
            'failures_summary': failures_summary,
            'claude_analysis': claude_analysis,
        }

        return self.claude_analyzer.ask_question(question, context)

    # ------------------------------------------------------------------
    # Email formatting
    # ------------------------------------------------------------------

    def format_answer_email(self, domain: str, question: str, answer: str) -> dict:
        """Return a dict with 'subject' and 'body' for the answer email."""
        subject = f"Re: DMARC Question \u2014 {domain}"
        sep = "\u2500" * 61
        body = (
            f"YOUR QUESTION\n"
            f"{sep}\n"
            f"{question}\n"
            f"{sep}\n\n"
            f"ANSWER\n"
            f"{sep}\n"
            f"{answer}\n"
            f"{sep}\n\n"
            f"Based on your most recent DMARC report for {domain}.\n"
            f"Reply again with any follow-up questions.\n\n"
            f"\u2500\n"
            f"DMARC Monitor \u2014 automated reply"
        )
        return {'subject': subject, 'body': body}

    # ------------------------------------------------------------------
    # Core processing
    # ------------------------------------------------------------------

    def process_reply(self, message: dict) -> bool:
        """
        Process a single inbox message.
        Returns True if an answer email was sent successfully.
        """
        message_id = message['id']
        subject = message.get('subject', '')

        if not self.is_dmarc_reply(subject):
            return False

        domain = self.extract_domain(subject)
        if not domain:
            logger.warning(f"Could not extract domain from subject: {subject}")
            return False

        # Fetch message body
        body = self.outlook_client.get_message_body(message_id)
        if not body:
            logger.warning(f"Empty body for message {message_id} — moving without reply")
            self.outlook_client.move_message(message_id, self.processed_folder)
            return False

        # Extract question (strip quoted text)
        question = self.extract_question(body)
        if not question:
            logger.info(
                f"No question found in reply for {domain} (only quoted text) — moving without reply"
            )
            self.outlook_client.move_message(message_id, self.processed_folder)
            return False

        # Get most recent report context from DB
        report_context = self.database.get_latest_report(domain)
        if not report_context:
            logger.info(f"No DB records for {domain} — answering without historical context")
            report_context = {'domain': domain, 'claude_analysis': ''}

        # Call Claude
        try:
            answer = self.ask_claude(question, report_context)
        except Exception as exc:
            logger.error(f"Claude API error for domain {domain}: {exc}")
            answer = (
                "I was unable to generate an answer at this time. "
                "Please try again later or contact your IT administrator."
            )

        # Send answer
        email = self.format_answer_email(domain, question, answer)
        sent = self.outlook_client.send_email(self.email_to, email['subject'], email['body'])
        if sent:
            logger.info(f"Sent Q&A reply for {domain} to {self.email_to}")
        else:
            logger.error(f"Failed to send Q&A reply for {domain}")

        # Always move the reply to DMARC Processed to prevent re-processing
        self.outlook_client.move_message(message_id, self.processed_folder)
        return sent

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Fetch inbox messages for the last ~65 minutes and process DMARC replies."""
        logger.info("Q&A Responder: checking inbox for DMARC reply emails")
        try:
            messages = self.outlook_client.get_messages('Inbox', hours_back=1.1)
        except Exception as exc:
            logger.error(f"Failed to fetch inbox messages: {exc}")
            return

        dmarc_replies = [m for m in messages if self.is_dmarc_reply(m.get('subject', ''))]
        logger.info(f"Found {len(dmarc_replies)} DMARC reply email(s) to process")

        for message in dmarc_replies:
            try:
                self.process_reply(message)
            except Exception as exc:
                logger.error(f"Error processing reply {message.get('id')}: {exc}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def _setup_logging():
    log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(log_dir, 'dmarc_monitor.log')),
        ],
    )


def main():
    _setup_logging()

    try:
        config = load_config()
    except Exception as exc:
        logger.error(f"Failed to load config: {exc}")
        sys.exit(1)

    db_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'dmarc_monitor.db')
    database = DMARCDatabase(db_path)

    outlook_client = OutlookClient(config['microsoft'], config.get('email', {}))
    if not outlook_client.get_access_token():
        logger.error("Failed to authenticate with Microsoft")
        sys.exit(1)

    claude_analyzer = ClaudeAnalyzer(config['claude']['api_key'], config['claude']['model'])

    responder = QAResponder(config, database, outlook_client, claude_analyzer)
    responder.run()


if __name__ == '__main__':
    main()
