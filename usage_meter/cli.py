#!/usr/bin/env python3
"""CLI: `usage-meter report [--tag X] [--days N]` prints a spend report."""

import argparse
import datetime
import time

from usage_meter.tracker import UsageTracker


def fmt_money(v):
    return f"${v:,.4f}"


def main():
    ap = argparse.ArgumentParser(description="LLM usage & spend report")
    ap.add_argument("--tag", default=None, help="filter by tag")
    ap.add_argument("--days", type=int, default=None, help="last N days only")
    ap.add_argument("--recent", type=int, default=0, help="show N recent calls")
    ap.add_argument("--db", default=None, help="database path override")
    args = ap.parse_args()

    tracker = UsageTracker(db_path=args.db) if args.db else UsageTracker()
    since = time.time() - args.days * 86400 if args.days else None
    s = tracker.summary(tag=args.tag, since_ts=since)

    window = f"last {args.days}d" if args.days else "all time"
    tag = f" [tag={args.tag}]" if args.tag else ""
    print(f"=== LLM usage report ({window}{tag}) ===")
    print(f"calls:            {s['calls']}")
    print(f"prompt tokens:    {s['prompt_tokens']:,}")
    print(f"cached tokens:    {s['cached_tokens']:,}")
    print(f"completion tokens:{s['completion_tokens']:,}")
    print(f"total cost:       {fmt_money(s['cost_usd'])}")
    print(f"avg latency:      {s['avg_latency_ms']:.0f} ms")
    print(f"max latency:      {s['max_latency_ms']:.0f} ms")
    print("\n--- by model ---")
    for m in s["by_model"]:
        print(
            f"{m['model']:<22} calls={m['n']:<4} in={m['pin']:,} out={m['pout']:,} "
            f"cost={fmt_money(m['cost'])}"
        )
    if args.recent:
        print(f"\n--- last {args.recent} calls ---")
        for r in tracker.recent(args.recent):
            ts = datetime.datetime.fromtimestamp(r["ts"]).strftime("%m-%d %H:%M")
            print(
                f"{ts} {r['model']:<20} tok={r['prompt_tokens'] + r['completion_tokens']:<7}"
                f" ${r['cost_usd']:.5f}  tag={r['tag']}"
            )


if __name__ == "__main__":
    main()
