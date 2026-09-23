"""Price-per-1K-tokens tables for popular models (USD). Cached-pricing aware.

Prices are approximate list prices; override with your own table via
``UsageTracker(pricing={...})`` or by editing this file. None of this is
financial advice — it's a spend estimator.
"""

# input / output / cached-input prices per 1K tokens
PRICING = {
    # --- OpenAI ---
    "gpt-4o": {"in": 0.0025, "out": 0.0100, "cached_in": 0.00125},
    "gpt-4o-mini": {"in": 0.00015, "out": 0.00060, "cached_in": 0.000075},
    "gpt-4.1": {"in": 0.0020, "out": 0.0080, "cached_in": 0.0005},
    "gpt-4.1-mini": {"in": 0.0004, "out": 0.0016, "cached_in": 0.0001},
    "o3": {"in": 0.0020, "out": 0.0080, "cached_in": 0.0005},
    "o4-mini": {"in": 0.0011, "out": 0.0044, "cached_in": 0.000275},
    # --- Anthropic ---
    "claude-sonnet-4-5": {"in": 0.0030, "out": 0.0150, "cached_in": 0.0003},
    "claude-opus-4-1": {"in": 0.0150, "out": 0.0750, "cached_in": 0.0015},
    "claude-haiku-4-5": {"in": 0.0010, "out": 0.0050, "cached_in": 0.0001},
    # --- Google ---
    "gemini-2.5-pro": {"in": 0.00125, "out": 0.0100, "cached_in": 0.0003125},
    "gemini-2.5-flash": {"in": 0.0003, "out": 0.0025, "cached_in": 0.000075},
    # --- xAI ---
    "grok-4": {"in": 0.0030, "out": 0.0150, "cached_in": 0.00075},
    # --- Meta (hosted) ---
    "llama-4-maverick": {"in": 0.0002, "out": 0.0006, "cached_in": 0.0},
    # --- DeepSeek ---
    "deepseek-chat": {"in": 0.00027, "out": 0.00110, "cached_in": 0.00007},
    "deepseek-reasoner": {"in": 0.00055, "out": 0.00219, "cached_in": 0.00014},
}


def estimate_cost(model, prompt_tokens, completion_tokens, cached_tokens=0):
    """Estimate USD cost for one call. Unknown models cost $0 (still tracked)."""
    p = PRICING.get(model)
    if p is None:
        return 0.0
    fresh_in = max(prompt_tokens - cached_tokens, 0)
    return (
        fresh_in / 1000 * p["in"]
        + cached_tokens / 1000 * p.get("cached_in", p["in"])
        + completion_tokens / 1000 * p["out"]
    )
