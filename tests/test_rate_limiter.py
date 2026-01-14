"""Tests for rate_limiter.py - rate limiting and budget tracking."""
import pytest
import time
from unittest.mock import patch
from rate_limiter import RateLimiter


class TestRateLimiter:
    """Test rate limiting functionality."""

    def test_first_query_allowed(self):
        """First query should always be allowed."""
        limiter = RateLimiter(cooldown_seconds=30)
        allowed, msg = limiter.check_rate_limit(user_id=123)
        assert allowed is True
        assert msg is None

    def test_immediate_second_query_blocked(self):
        """Query within cooldown should be blocked."""
        limiter = RateLimiter(cooldown_seconds=30)
        limiter.check_rate_limit(user_id=123)
        allowed, msg = limiter.check_rate_limit(user_id=123)
        assert allowed is False
        assert "wait" in msg.lower()

    def test_query_after_cooldown_allowed(self):
        """Query after cooldown should be allowed."""
        limiter = RateLimiter(cooldown_seconds=1)
        limiter.check_rate_limit(user_id=123)
        time.sleep(1.1)
        allowed, msg = limiter.check_rate_limit(user_id=123)
        assert allowed is True

    def test_different_users_independent(self):
        """Different users should have independent rate limits."""
        limiter = RateLimiter(cooldown_seconds=30)
        limiter.check_rate_limit(user_id=123)
        allowed, msg = limiter.check_rate_limit(user_id=456)
        assert allowed is True


class TestBudgetTracking:
    """Test daily budget tracking."""

    def test_under_budget_allowed(self):
        """Queries under budget should be allowed."""
        limiter = RateLimiter(daily_budget_usd=1.00)
        allowed, msg = limiter.check_budget(user_id=123)
        assert allowed is True

    def test_record_spend_tracks_cost(self):
        """Recording spend should update daily total."""
        limiter = RateLimiter(daily_budget_usd=1.00)
        limiter.record_spend(user_id=123, cost_usd=0.50)
        assert limiter.get_daily_spend(user_id=123) == 0.50

    def test_over_budget_blocked(self):
        """Queries over budget should be blocked."""
        limiter = RateLimiter(daily_budget_usd=0.10)
        limiter.record_spend(user_id=123, cost_usd=0.10)
        allowed, msg = limiter.check_budget(user_id=123)
        assert allowed is False
        assert "budget" in msg.lower()

    def test_budget_resets_daily(self):
        """Budget should reset at midnight."""
        limiter = RateLimiter(daily_budget_usd=0.10)
        limiter.record_spend(user_id=123, cost_usd=0.10)
        # Simulate day change
        limiter._spend_dates[123] = "2026-01-13"
        allowed, msg = limiter.check_budget(user_id=123)
        assert allowed is True


class TestQueryCache:
    """Test query result caching."""

    def test_cache_miss_returns_none(self):
        """Uncached query should return None."""
        limiter = RateLimiter(cache_ttl_seconds=300)
        result = limiter.get_cached_result(user_id=123, question="test?")
        assert result is None

    def test_cache_hit_returns_result(self):
        """Cached query should return stored result."""
        limiter = RateLimiter(cache_ttl_seconds=300)
        expected = {"answer": "cached answer", "cost_usd": 0.0}
        limiter.cache_result(user_id=123, question="test?", result=expected)
        result = limiter.get_cached_result(user_id=123, question="test?")
        assert result == expected

    def test_cache_expires(self):
        """Cached result should expire after TTL."""
        limiter = RateLimiter(cache_ttl_seconds=1)
        limiter.cache_result(user_id=123, question="test?", result={"answer": "old"})
        time.sleep(1.1)
        result = limiter.get_cached_result(user_id=123, question="test?")
        assert result is None

    def test_cache_key_includes_question(self):
        """Different questions should have different cache entries."""
        limiter = RateLimiter(cache_ttl_seconds=300)
        limiter.cache_result(user_id=123, question="q1?", result={"answer": "a1"})
        result = limiter.get_cached_result(user_id=123, question="q2?")
        assert result is None
