#!/usr/bin/env python3
"""
TDD test suite for Q&A Responder feature.
Tests are written before implementation per plan requirements.
Run with: python3 scripts/test_qa_responder.py
"""

import os
import sys
import unittest
from unittest.mock import MagicMock

# Add scripts dir to path so we can import qa_responder once implemented
sys.path.insert(0, os.path.dirname(__file__))
# Add src dir to path for database imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from qa_responder import QAResponder


def make_responder(**kwargs):
    """Helper: create a QAResponder with sensible defaults"""
    config = kwargs.pop('config', {
        'email': {'processed_folder': 'DMARC Processed'},
        'notifications': {'email_to': 'admin@example.com'},
    })
    return QAResponder(
        config=config,
        database=kwargs.pop('database', MagicMock()),
        outlook_client=kwargs.pop('outlook_client', MagicMock()),
        claude_analyzer=kwargs.pop('claude_analyzer', MagicMock()),
    )


# ---------------------------------------------------------------------------
# Subject detection tests
# ---------------------------------------------------------------------------

class TestSubjectDetection(unittest.TestCase):

    def setUp(self):
        self.r = make_responder()

    def test_detect_issue_reply(self):
        subject = "Re: \u26a0\ufe0f  DMARC Report \u2014 connect.aileron-group.com \u2014 ACTION NEEDED"
        self.assertTrue(self.r.is_dmarc_reply(subject))
        self.assertEqual(self.r.extract_domain(subject), "connect.aileron-group.com")

    def test_detect_clean_reply(self):
        subject = "Re: \u2705 DMARC Report \u2014 aileron-group.com"
        self.assertTrue(self.r.is_dmarc_reply(subject))
        self.assertEqual(self.r.extract_domain(subject), "aileron-group.com")

    def test_ignore_non_dmarc_email(self):
        subject = "Re: Meeting notes"
        self.assertFalse(self.r.is_dmarc_reply(subject))

    def test_ignore_original_report(self):
        """Subjects without 'Re:' prefix (our sent reports) must be ignored"""
        subject = "\u26a0\ufe0f  DMARC Report \u2014 connect.aileron-group.com \u2014 ACTION NEEDED"
        self.assertFalse(self.r.is_dmarc_reply(subject))


# ---------------------------------------------------------------------------
# Question extraction tests
# ---------------------------------------------------------------------------

class TestQuestionExtraction(unittest.TestCase):

    def setUp(self):
        self.r = make_responder()

    def test_extract_question_plain_body(self):
        body = "Is Amazon AWS actually a threat to our email system?"
        result = self.r.extract_question(body)
        self.assertEqual(result, "Is Amazon AWS actually a threat to our email system?")

    def test_extract_question_strips_outlook_quote(self):
        body = (
            "What should I fix first?\n\n"
            "From: DMARC Monitor <monitor@aileron-group.com>\n"
            "Sent: Tuesday, March 14, 2026 10:00 AM\n"
            "To: admin@example.com\n"
            "Subject: DMARC Report\n\n"
            "Original report content here"
        )
        result = self.r.extract_question(body)
        self.assertIsNotNone(result)
        self.assertIn("What should I fix first?", result)
        self.assertNotIn("From: DMARC Monitor", result)

    def test_extract_question_strips_angle_quote(self):
        body = "Is this suspicious?\n> DMARC Report content\n> More quoted text"
        result = self.r.extract_question(body)
        self.assertEqual(result, "Is this suspicious?")

    def test_extract_question_empty_after_strip(self):
        body = "> This is all quoted\n> Nothing else here"
        result = self.r.extract_question(body)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Answer email formatting tests
# ---------------------------------------------------------------------------

class TestAnswerEmailFormatting(unittest.TestCase):

    def setUp(self):
        self.r = make_responder()

    def test_format_answer_email(self):
        domain = "connect.aileron-group.com"
        question = "Is Amazon AWS a threat?"
        answer = "Based on your report, the Amazon AWS IP is sending on behalf of your connected services."

        result = self.r.format_answer_email(domain, question, answer)

        self.assertIn("subject", result)
        self.assertIn("body", result)
        self.assertIn(domain, result["subject"])
        self.assertIn(question, result["body"])
        self.assertIn(answer, result["body"])


# ---------------------------------------------------------------------------
# End-to-end integration test (all external calls mocked)
# ---------------------------------------------------------------------------

class TestEndToEndWithMocks(unittest.TestCase):

    def setUp(self):
        self.config = {
            'email': {'processed_folder': 'DMARC Processed'},
            'notifications': {'email_to': 'admin@example.com'},
        }
        self.mock_db = MagicMock()
        self.mock_outlook = MagicMock()
        self.mock_claude = MagicMock()

        self.r = QAResponder(
            config=self.config,
            database=self.mock_db,
            outlook_client=self.mock_outlook,
            claude_analyzer=self.mock_claude,
        )

    def test_end_to_end_with_mocks(self):
        fake_message = {
            'id': 'msg_abc123',
            'subject': 'Re: \u26a0\ufe0f  DMARC Report \u2014 connect.aileron-group.com \u2014 ACTION NEEDED',
        }

        self.mock_outlook.get_message_body.return_value = (
            "Is Amazon AWS a real threat to our domain?"
        )

        self.mock_db.get_latest_report.return_value = {
            'domain': 'connect.aileron-group.com',
            'date_begin': 1741996800,
            'date_end': 1742083200,
            'policy_p': 'none',
            'total_messages': 26,
            'auth_success_rate': 88.5,
            'claude_analysis': (
                'FAILURES:\n'
                'IP: 35.174.145.124\n'
                'Company: Amazon AWS\n'
                'Risk: INVESTIGATE\n\n'
                'RECOMMENDATIONS:\n'
                '1. Upgrade DMARC policy.'
            ),
        }

        self.mock_claude.ask_question.return_value = (
            "Amazon AWS is sending emails on behalf of your connected services. "
            "You should investigate."
        )

        self.mock_outlook.send_email.return_value = True
        self.mock_outlook.move_message.return_value = True

        result = self.r.process_reply(fake_message)

        self.assertTrue(result)
        self.mock_outlook.get_message_body.assert_called_once_with('msg_abc123')
        self.mock_db.get_latest_report.assert_called_once_with('connect.aileron-group.com')
        self.mock_claude.ask_question.assert_called_once()
        self.mock_outlook.send_email.assert_called_once()
        self.mock_outlook.move_message.assert_called_once_with('msg_abc123', 'DMARC Processed')

    def test_process_reply_skips_non_dmarc_email(self):
        fake_message = {'id': 'msg_xyz', 'subject': 'Re: Meeting notes'}
        result = self.r.process_reply(fake_message)
        self.assertFalse(result)
        self.mock_outlook.get_message_body.assert_not_called()

    def test_process_reply_moves_when_no_question(self):
        """When body is only quoted text, reply is moved but no email sent"""
        fake_message = {
            'id': 'msg_noquestion',
            'subject': 'Re: \u2705 DMARC Report \u2014 aileron-group.com',
        }
        self.mock_outlook.get_message_body.return_value = "> All quoted text here"

        self.r.process_reply(fake_message)

        self.mock_outlook.send_email.assert_not_called()
        self.mock_outlook.move_message.assert_called_once_with('msg_noquestion', 'DMARC Processed')


if __name__ == '__main__':
    unittest.main(verbosity=2)
