#!/usr/bin/env python3
"""Zero-API-key demo: simulate an agent's LLM calls and print a spend report.

Run:  python demo.py
It logs a handful of fake calls (chat + agent loop + cached context) into a
temp database, then prints the report and the N most recent calls.
"""

import os
import random
import tempfile

from usage_meter.tracker import UsageTracker, track_call

random.seed(42)


def main():
    db = os.path.join(tempfile.mkdtemp(prefix="usage-meter-demo-"), "usage.db")
    tracker = UsageTracker(db_path=db)

    # 1) Manual logging: a chat call with prompt caching
    tracker.log(
        model="claude-sonnet-4-5",
        provider="anthropic",
        prompt_tokens=12_400,
        completion_tokens=860,
        cached_tokens=10_000,  # big system prompt cached
        latency_ms=2_340,
        tag="chat",
    )

    # 2) Decorator style: wrap any function returning (result, usage)
    @track_call(tracker, model="gpt-4o-mini", tag="agent-loop", provider="openai")
    def fake_agent_step(step):
        import time as _t

        _t.sleep(0.01)
        return f"step-{step} done", {
            "prompt_tokens": 3_200 + step * 400,
            "completion_tokens": 210,
            "cached_tokens": 2_800,
        }

    for step in range(6):
        fake_agent_step(step)

    # 3) A heavy reasoning call
    tracker.log(
        model="o3",
        provider="openai",
        prompt_tokens=8_900,
        completion_tokens=4_200,
        latency_ms=41_000,
        tag="deep-reasoning",
    )

    s = tracker.summary()
    print("=== demo summary ===")
    print(f"calls: {s['calls']}")
    print(f"prompt tokens: {s['prompt_tokens']:,}")
    print(f"completion tokens: {s['completion_tokens']:,}")
    print(f"estimated cost: ${s['cost_usd']:.4f}")
    print("--- by model ---")
    for m in s["by_model"]:
        print(f"  {m['model']:<20} cost=${m['cost']:.4f} (n={m['n']})")

    print("\n--- recent calls ---")
    for r in tracker.recent(3):
        print(
            f"  {r['model']:<20} in={r['prompt_tokens']} out={r['completion_tokens']} "
            f"cached={r['cached_tokens']} cost=${r['cost_usd']:.5f} tag={r['tag']}"
        )
    print(f"\nDB written to: {db}")


if __name__ == "__main__":
    main()
