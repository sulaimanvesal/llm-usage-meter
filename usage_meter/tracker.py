"""SQLite-backed usage tracker: record every LLM call, query later.

The tracker is provider-agnostic — OpenAI, Anthropic, Gemini, anything that
reports token counts. Wrap your call function with ``@track_call`` or log
manually with ``tracker.log(...)``.
"""

from __future__ import annotations

import csv
import functools
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager

from .models import PRICING, estimate_cost

_SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    model TEXT NOT NULL,
    provider TEXT DEFAULT '',
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    cached_tokens INTEGER DEFAULT 0,
    latency_ms REAL DEFAULT 0,
    cost_usd REAL NOT NULL,
    tag TEXT DEFAULT '',
    error TEXT DEFAULT ''
);
"""

DEFAULT_DB = os.path.expanduser("~/.llm-usage-meter/usage.db")


class UsageTracker:
    """Records LLM calls to a local SQLite database. Zero API keys required."""

    def __init__(self, db_path: str = DEFAULT_DB, pricing: dict | None = None):
        self.db_path = db_path
        self.pricing = dict(PRICING)
        if pricing:
            self.pricing.update(pricing)
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def log(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_tokens: int = 0,
        latency_ms: float = 0.0,
        provider: str = "",
        tag: str = "",
        error: str = "",
    ) -> dict:
        """Log one LLM call. Returns the stored record dict."""
        p = self.pricing.get(model, {"in": 0, "out": 0, "cached_in": 0})
        fresh_in = max(prompt_tokens - cached_tokens, 0)
        cost = (
            fresh_in / 1000 * p["in"]
            + cached_tokens / 1000 * p.get("cached_in", p["in"])
            + completion_tokens / 1000 * p["out"]
        )
        record = {
            "id": uuid.uuid4().hex[:12],
            "ts": time.time(),
            "model": model,
            "provider": provider,
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "cached_tokens": int(cached_tokens),
            "latency_ms": float(latency_ms),
            "cost_usd": cost,
            "tag": tag,
            "error": error,
        }
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO calls VALUES "
                "(:id, :ts, :model, :provider, :prompt_tokens, :completion_tokens,"
                " :cached_tokens, :latency_ms, :cost_usd, :tag, :error)",
                record,
            )
        return record

    def summary(self, tag: str | None = None, since_ts: float | None = None) -> dict:
        """Aggregate totals, optionally filtered by tag and start time."""
        where, params = [], []
        if tag is not None:
            where.append("tag = ?")
            params.append(tag)
        if since_ts is not None:
            where.append("ts >= ?")
            params.append(since_ts)
        clause = f"WHERE {' AND '.join(where)}" if where else ""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            totals = conn.execute(
                f"SELECT COUNT(*) n, COALESCE(SUM(prompt_tokens),0) pin,"
                f" COALESCE(SUM(completion_tokens),0) pout,"
                f" COALESCE(SUM(cached_tokens),0) pcached,"
                f" COALESCE(SUM(cost_usd),0) cost,"
                f" COALESCE(AVG(latency_ms),0) avg_ms,"
                f" COALESCE(MAX(latency_ms),0) max_ms FROM calls {clause}",
                params,
            ).fetchone()
            by_model = conn.execute(
                f"SELECT model, COUNT(*) n, SUM(prompt_tokens) pin,"
                f" SUM(completion_tokens) pout, SUM(cost_usd) cost"
                f" FROM calls {clause} GROUP BY model ORDER BY cost DESC",
                params,
            ).fetchall()
        return {
            "calls": totals["n"],
            "prompt_tokens": totals["pin"],
            "completion_tokens": totals["pout"],
            "cached_tokens": totals["pcached"],
            "cost_usd": totals["cost"],
            "avg_latency_ms": totals["avg_ms"],
            "max_latency_ms": totals["max_ms"],
            "by_model": [dict(r) for r in by_model],
        }

    def recent(self, limit: int = 20) -> list[dict]:
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM calls ORDER BY ts DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def export_csv(self, path: str) -> str:
        rows = self.recent(limit=10_000_000)
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rows[0].keys() if rows else ["id"])
            w.writeheader()
            w.writerows(rows)
        return path

    def clear(self):
        with self._connect() as conn:
            conn.execute("DELETE FROM calls")


def track_call(tracker: UsageTracker, model: str, tag: str = "", provider: str = ""):
    """Decorator: time a function returning ``(result, usage_dict)`` and log it.

    ``usage_dict`` needs ``prompt_tokens`` and ``completion_tokens`` keys
    (mirrors OpenAI/Anthropic usage payloads); ``cached_tokens`` optional.
    """

    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result, usage = fn(*args, **kwargs)
            tracker.log(
                model=model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                cached_tokens=usage.get("cached_tokens", 0),
                latency_ms=(time.perf_counter() - start) * 1000,
                provider=provider,
                tag=tag,
            )
            return result

        return wrapper

    return deco
