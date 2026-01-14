"""Rate limiting, budget tracking, and query caching for Telegram bot."""
import hashlib
import time
from datetime import datetime
from typing import Optional, Tuple


class RateLimiter:
    """Manages rate limiting, daily budgets, and query caching."""

    def __init__(
        self,
        cooldown_seconds: int = 30,
        daily_budget_usd: float = 1.00,
        cache_ttl_seconds: int = 300,
    ):
        self.cooldown_seconds = cooldown_seconds
        self.daily_budget_usd = daily_budget_usd
        self.cache_ttl_seconds = cache_ttl_seconds

        # Rate limiting: {user_id: last_query_timestamp}
        self._last_query: dict[int, float] = {}

        # Budget tracking: {user_id: daily_spend_usd}
        self._daily_spend: dict[int, float] = {}
        self._spend_dates: dict[int, str] = {}

        # Query cache: {cache_key: (result, timestamp)}
        self._cache: dict[str, tuple[dict, float]] = {}

    def check_rate_limit(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Check if user can query. Returns (allowed, error_message)."""
        now = time.time()

        if user_id in self._last_query:
            elapsed = now - self._last_query[user_id]
            if elapsed < self.cooldown_seconds:
                wait_time = int(self.cooldown_seconds - elapsed)
                return False, f"Please wait {wait_time}s before next query."

        self._last_query[user_id] = now
        return True, None

    def check_budget(self, user_id: int) -> Tuple[bool, Optional[str]]:
        """Check if user has remaining budget. Returns (allowed, error_message)."""
        today = datetime.now().strftime("%Y-%m-%d")

        # Reset if new day
        if self._spend_dates.get(user_id) != today:
            self._daily_spend[user_id] = 0.0
            self._spend_dates[user_id] = today

        current_spend = self._daily_spend.get(user_id, 0.0)

        if current_spend >= self.daily_budget_usd:
            return False, f"Daily budget (${self.daily_budget_usd:.2f}) exceeded."

        return True, None

    def record_spend(self, user_id: int, cost_usd: float) -> None:
        """Record API spend for user."""
        today = datetime.now().strftime("%Y-%m-%d")

        if self._spend_dates.get(user_id) != today:
            self._daily_spend[user_id] = 0.0
            self._spend_dates[user_id] = today

        self._daily_spend[user_id] = self._daily_spend.get(user_id, 0.0) + cost_usd

    def get_daily_spend(self, user_id: int) -> float:
        """Get current daily spend for user."""
        today = datetime.now().strftime("%Y-%m-%d")

        if self._spend_dates.get(user_id) != today:
            return 0.0

        return self._daily_spend.get(user_id, 0.0)

    def get_remaining_budget(self, user_id: int) -> float:
        """Get remaining daily budget for user."""
        return max(0.0, self.daily_budget_usd - self.get_daily_spend(user_id))

    def _cache_key(self, user_id: int, question: str) -> str:
        """Generate cache key from user and question."""
        normalized = question.strip().lower()
        return hashlib.md5(f"{user_id}:{normalized}".encode()).hexdigest()

    def get_cached_result(self, user_id: int, question: str) -> Optional[dict]:
        """Get cached result if exists and not expired."""
        key = self._cache_key(user_id, question)

        if key not in self._cache:
            return None

        result, timestamp = self._cache[key]
        if time.time() - timestamp > self.cache_ttl_seconds:
            del self._cache[key]
            return None

        return result

    def cache_result(self, user_id: int, question: str, result: dict) -> None:
        """Cache query result."""
        key = self._cache_key(user_id, question)
        self._cache[key] = (result, time.time())

    def cleanup_expired_cache(self) -> int:
        """Remove expired cache entries. Returns count removed."""
        now = time.time()
        expired = [
            k for k, (_, ts) in self._cache.items()
            if now - ts > self.cache_ttl_seconds
        ]
        for k in expired:
            del self._cache[k]
        return len(expired)
