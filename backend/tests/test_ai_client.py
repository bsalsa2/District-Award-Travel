import datetime as dt
import json

import pytest

from backend import ai_client
from backend.ai_client import call_ai, get_health, AIUnavailable


NOSLEEP = lambda s: None  # noqa: E731


class FakeClock:
    def __init__(self, start=None):
        self.now = start or dt.datetime(2026, 1, 1, 12, 0, 0)

    def __call__(self):
        return self.now

    def advance(self, **kw):
        self.now += dt.timedelta(**kw)


@pytest.fixture(autouse=True)
def clean_breakers():
    ai_client.reset_breakers()
    yield
    ai_client.reset_breakers()


def test_retry_then_success():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return {"ok": True}

    result = call_ai("groq", "op", fn, sleep_fn=NOSLEEP)
    assert result == {"ok": True}
    assert calls["n"] == 3


def test_always_fails_propagates_after_three_attempts():
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        raise ValueError("boom")

    with pytest.raises(ValueError):
        call_ai("groq", "op", fn, sleep_fn=NOSLEEP)
    assert calls["n"] == 3  # 1 + 2 retries


def test_breaker_opens_after_three_failed_invocations():
    clock = FakeClock()

    def fn():
        raise RuntimeError("down")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            call_ai("gemini", "op", fn, sleep_fn=NOSLEEP, now_fn=clock)

    called = {"n": 0}

    def fn2():
        called["n"] += 1
        return 1

    with pytest.raises(AIUnavailable) as exc:
        call_ai("gemini", "op", fn2, sleep_fn=NOSLEEP, now_fn=clock)
    assert exc.value.provider == "gemini"
    assert called["n"] == 0
    health = get_health(now_fn=clock)
    assert health["gemini"]["up"] is False
    assert health["gemini"]["down_until"] is not None


def test_breaker_resets_after_cooldown():
    clock = FakeClock()

    def fail():
        raise RuntimeError("down")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            call_ai("gemini", "op", fail, sleep_fn=NOSLEEP, now_fn=clock)

    clock.advance(minutes=11)
    called = {"n": 0}

    def ok():
        called["n"] += 1
        return "fine"

    assert call_ai("gemini", "op", ok, sleep_fn=NOSLEEP, now_fn=clock) == "fine"
    assert called["n"] == 1
    assert get_health(now_fn=clock)["gemini"]["up"] is True


def test_success_resets_failure_count():
    clock = FakeClock()

    def fail():
        raise RuntimeError("x")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            call_ai("groq", "op", fail, sleep_fn=NOSLEEP, now_fn=clock)
    assert get_health(now_fn=clock)["groq"]["consecutive_failures"] == 2

    call_ai("groq", "op", lambda: 1, sleep_fn=NOSLEEP, now_fn=clock)
    assert get_health(now_fn=clock)["groq"]["consecutive_failures"] == 0

    # one more failure should NOT open the breaker
    with pytest.raises(RuntimeError):
        call_ai("groq", "op", fail, sleep_fn=NOSLEEP, now_fn=clock)
    assert get_health(now_fn=clock)["groq"]["up"] is True


def test_json_decode_error_counts_as_failure():
    def fn():
        json.loads("{not json")

    with pytest.raises(json.JSONDecodeError):
        call_ai("groq", "op", fn, sleep_fn=NOSLEEP)
    assert get_health()["groq"]["consecutive_failures"] == 1
