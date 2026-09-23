import os
import tempfile

import pytest

from usage_meter.models import estimate_cost
from usage_meter.tracker import UsageTracker, track_call


@pytest.fixture
def tracker():
    db = os.path.join(tempfile.mkdtemp(), "test.db")
    return UsageTracker(db_path=db)


def test_log_and_summary(tracker):
    tracker.log(model="gpt-4o-mini", prompt_tokens=1000, completion_tokens=500)
    s = tracker.summary()
    assert s["calls"] == 1
    assert s["prompt_tokens"] == 1000
    assert s["completion_tokens"] == 500
    assert s["cost_usd"] > 0


def test_cost_math(tracker):
    # gpt-4o-mini: 0.00015 in / 0.00060 out per 1K
    rec = tracker.log(model="gpt-4o-mini", prompt_tokens=1000, completion_tokens=1000)
    assert abs(rec["cost_usd"] - (0.00015 + 0.00060)) < 1e-9


def test_cached_tokens_cheaper(tracker):
    full = tracker.log(model="claude-sonnet-4-5", prompt_tokens=10000, completion_tokens=0)
    cached = tracker.log(
        model="claude-sonnet-4-5", prompt_tokens=10000, completion_tokens=0, cached_tokens=10000
    )
    assert cached["cost_usd"] < full["cost_usd"]


def test_unknown_model_zero_cost(tracker):
    rec = tracker.log(model="not-a-real-model", prompt_tokens=500, completion_tokens=500)
    assert rec["cost_usd"] == 0.0
    assert tracker.summary()["calls"] == 1


def test_tag_filter(tracker):
    tracker.log(model="gpt-4o", prompt_tokens=100, completion_tokens=50, tag="a")
    tracker.log(model="gpt-4o", prompt_tokens=100, completion_tokens=50, tag="b")
    assert tracker.summary(tag="a")["calls"] == 1
    assert tracker.summary()["calls"] == 2


def test_by_model_breakdown(tracker):
    tracker.log(model="gpt-4o", prompt_tokens=100, completion_tokens=50)
    tracker.log(model="gpt-4o-mini", prompt_tokens=100, completion_tokens=50)
    s = tracker.summary()
    assert len(s["by_model"]) == 2
    assert s["by_model"][0]["cost"] >= s["by_model"][1]["cost"]  # sorted desc


def test_recent_ordering(tracker):
    tracker.log(model="gpt-4o", prompt_tokens=10, completion_tokens=10, tag="first")
    tracker.log(model="gpt-4o", prompt_tokens=10, completion_tokens=10, tag="second")
    recent = tracker.recent(2)
    assert recent[0]["tag"] == "second"
    assert recent[1]["tag"] == "first"


def test_decorator_logs_call(tracker):
    @track_call(tracker, model="gemini-2.5-flash", tag="dec")
    def fake_call():
        return "ok", {"prompt_tokens": 200, "completion_tokens": 100}

    assert fake_call() == "ok"
    s = tracker.summary(tag="dec")
    assert s["calls"] == 1
    assert s["prompt_tokens"] == 200


def test_export_csv(tracker):
    tracker.log(model="gpt-4o", prompt_tokens=10, completion_tokens=10)
    path = os.path.join(tempfile.mkdtemp(), "out.csv")
    tracker.export_csv(path)
    assert os.path.exists(path)
    with open(path) as f:
        header = f.readline()
    assert "cost_usd" in header


def test_clear(tracker):
    tracker.log(model="gpt-4o", prompt_tokens=10, completion_tokens=10)
    tracker.clear()
    assert tracker.summary()["calls"] == 0


def test_estimate_cost_unknown_model():
    assert estimate_cost("nope", 100, 100) == 0.0
