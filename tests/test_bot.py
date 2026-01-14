"""Tests for bot.py - message handling."""
import pytest
import sys
from unittest.mock import MagicMock

# Mock external modules before importing bot
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['claude_agent_sdk'] = MagicMock()

from bot import is_duplicate_message, clear_message_hashes


class TestDeduplication:
    """Test message deduplication."""

    def setup_method(self):
        """Clear hashes before each test."""
        clear_message_hashes()

    def test_first_message_not_duplicate(self):
        """First message should not be duplicate."""
        assert is_duplicate_message("hello", 1234567890) is False

    def test_same_message_is_duplicate(self):
        """Same message within window is duplicate."""
        is_duplicate_message("hello", 1234567890)
        assert is_duplicate_message("hello", 1234567890) is True

    def test_different_message_not_duplicate(self):
        """Different message is not duplicate."""
        is_duplicate_message("hello", 1234567890)
        assert is_duplicate_message("world", 1234567891) is False

    def test_same_content_different_time_not_duplicate(self):
        """Same content but different timestamp is not duplicate."""
        is_duplicate_message("hello", 1234567890)
        assert is_duplicate_message("hello", 1234567900) is False

    def test_clear_message_hashes_works(self):
        """clear_message_hashes should reset state."""
        is_duplicate_message("hello", 1234567890)
        clear_message_hashes()
        # After clearing, same message should not be duplicate
        assert is_duplicate_message("hello", 1234567890) is False
