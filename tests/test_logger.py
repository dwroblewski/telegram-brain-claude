"""Tests for logger.py - structured logging."""
import pytest
import json
from logger import _scrub_pii, log_event


class TestPIIScrubbing:
    """Test PII scrubbing."""

    def test_truncates_long_content(self):
        """Long content should be truncated."""
        data = {"content": "a" * 200}
        scrubbed = _scrub_pii(data, max_content_len=100)
        assert len(scrubbed["content"]) == 103  # 100 + "..."
        assert scrubbed["content"].endswith("...")

    def test_redacts_sensitive_fields(self):
        """Sensitive fields should be redacted."""
        data = {"api_key": "sk-1234", "token": "abc"}
        scrubbed = _scrub_pii(data)
        assert scrubbed["api_key"] == "[REDACTED]"
        assert scrubbed["token"] == "[REDACTED]"

    def test_preserves_short_content(self):
        """Short content should not be modified."""
        data = {"content": "short text"}
        scrubbed = _scrub_pii(data)
        assert scrubbed["content"] == "short text"
