"""AI resilience layer: retries with backoff, per-provider circuit breakers,
and usage logging. Designed for injectable clocks/sleep so tests need no network."""
import datetime as dt
import time

BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN = dt.timedelta(minutes=10)
BACKOFF_SECONDS = [1, 2]

# provider -> {"failures": int, "down_until": datetime|None}
_breakers: dict = {}


class AIUnavailable(Exception):
    def __init__(self, provider, message=None):
        self.provider = provider
        super().__init__(message or f"AI provider '{provider}' is temporarily unavailable")


def _breaker(provider):
    return _breakers.setdefault(provider, {"failures": 0, "down_until": None})


def reset_breakers():
    """Test helper."""
    _breakers.clear()


def call_ai(provider, operation, fn, db_session_factory=None, est_cost_microusd=0,
            max_retries=2, now_fn=None, sleep_fn=None):
    now_fn = now_fn or dt.datetime.utcnow
    sleep_fn = sleep_fn or time.sleep
    b = _breaker(provider)

    now = now_fn()
    if b["down_until"] is not None:
        if now < b["down_until"]:
            raise AIUnavailable(provider)
        # cooldown passed — half-open: allow the call
        b["down_until"] = None

    start = now_fn()
    last_exc = None
    result = None
    success = False
    for attempt in range(max_retries + 1):
        try:
            result = fn()
            success = True
            break
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                sleep_fn(BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)])
    end = now_fn()
    latency_ms = max(0, int((end - start).total_seconds() * 1000))

    if db_session_factory is not None:
        try:
            from backend.main import AIUsage
        except ImportError:
            try:
                from main import AIUsage  # when run as a flat module
            except ImportError:
                AIUsage = None
        if AIUsage is not None:
            try:
                db = db_session_factory()
                try:
                    db.add(AIUsage(
                        provider=provider,
                        operation=operation,
                        latency_ms=latency_ms,
                        success=1 if success else 0,
                        error="" if success else str(last_exc)[:500],
                        est_cost_microusd=est_cost_microusd,
                    ))
                    db.commit()
                finally:
                    db.close()
            except Exception as log_err:
                print(f"[ai_client] usage logging failed: {log_err}")

    if success:
        b["failures"] = 0
        return result

    b["failures"] += 1
    if b["failures"] >= BREAKER_THRESHOLD:
        b["down_until"] = now_fn() + BREAKER_COOLDOWN
        b["failures"] = 0
    raise last_exc


def get_health(now_fn=None):
    now_fn = now_fn or dt.datetime.utcnow
    now = now_fn()
    out = {}
    for provider, b in _breakers.items():
        down = b["down_until"] is not None and now < b["down_until"]
        out[provider] = {
            "up": not down,
            "down_until": b["down_until"].isoformat() if down else None,
            "consecutive_failures": b["failures"],
        }
    return out
