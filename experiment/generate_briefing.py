"""
Generates one short, plain-English "daily briefing" explaining what the
recommendation data actually shows and why — grounded entirely in the real
structured data already computed elsewhere in this project (no invented
figures), and deliberately steered away from "you should buy/sell"
language. This is an EXPLANATION tool, not an advice tool — see
LIVE_TRADING_PLAN.md and the "NOT investment advice" framing already on
the recommendations page for why that distinction is being kept
intentionally sharp, not just as a disclaimer.

Runs once per day at build time (not a live chat) — a single API call,
baked into the static site. If the API call fails for any reason (missing
key, network issue, rate limit), this degrades to "briefing unavailable
today" rather than breaking the rest of the daily run — the trading logic
must never depend on this succeeding.
"""

import os
import logging

logger = logging.getLogger(__name__)

BRIEFING_MODEL = "claude-haiku-4-5-20251001"  # cheap/fast — this is structured summarization, not deep reasoning

SYSTEM_PROMPT = """You write a short daily briefing for a personal research dashboard that tracks 50 systematic trading strategies in PAPER TRADING (no real money). Your job is to EXPLAIN what the data shows, never to RECOMMEND action.

Hard rules, no exceptions:
- Never write "you should buy/sell/hold" or any imperative telling the reader what to do with their money.
- Never invent a number, ticker, correlation, or return that isn't in the data provided to you.
- If a stock's buy consensus is driven by highly-correlated strategies (redundant signals, not independent confirmation), say so explicitly — that's exactly the kind of nuance a raw percentage hides.
- Reference validation tier or sample size when discussing any specific strategy's return, since "Building history" / "Preliminary" strategies have not accumulated enough evidence to be read as proof of anything.
- Never use hype language ("massive," "huge opportunity," "don't miss") — the tone is a research analyst's internal note, not marketing copy.
- Keep it to 150-220 words, in plain prose (short paragraphs are fine, no bullet-point lists of "picks").
- End with one sentence noting this is a systematic paper-trading research tool, not financial advice.
"""


def _build_user_prompt(data: dict) -> str:
    rec = data.get("recommendations", {})
    best = rec.get("best_strategy")
    corr_pairs = data.get("correlation", {}).get("most_correlated_pairs", [])[:5]

    lines = [f"Date: {rec.get('date', 'unknown')}", f"Active strategies: {rec.get('n_active_strategies', 0)}"]

    if best:
        lines.append(f"Current qualifying leader (Emerging+ validation tier only): {best['display_name']}, ROI {best.get('roi')}")
    else:
        lines.append("No strategy has reached the validation tier required to be named a leader yet.")

    lines.append("\nTop buy consensus today:")
    for item in rec.get("top_buy", [])[:5]:
        lines.append(f"  {item['symbol']}: {item['count']}/{item['n_active_strategies']} strategies ({item['pct']:.0%}), leader's stance: {item['best_strategy_stance']}")

    lines.append("\nTop sell consensus today:")
    for item in rec.get("top_sell", [])[:5]:
        lines.append(f"  {item['symbol']}: {item['count']}/{item['n_active_strategies']} strategies ({item['pct']:.0%})")

    lines.append("\nMost correlated strategy pairs (possible redundancy, not independent confirmation):")
    for p in corr_pairs:
        lines.append(f"  {p['strategy_a']} <-> {p['strategy_b']}: {p['correlation']:+.2f} ({p.get('confidence','')})")

    eff = data.get("effective_signal_count", {})
    if eff.get("effective_n") is not None:
        lines.append(f"\nEffective independent signals: {eff['effective_n']:.1f} of {eff['nominal_n']} nominal")

    lines.append("\nWrite the briefing now, following all rules in the system prompt exactly.")
    return "\n".join(lines)


def generate_daily_briefing(data: dict) -> dict:
    """
    Returns {"text": str, "generated": bool, "error": str_or_None}.
    Never raises — a failure here must not break the daily trading run.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"text": None, "generated": False, "error": "ANTHROPIC_API_KEY not set"}

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=BRIEFING_MODEL,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_user_prompt(data)}],
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
        return {"text": text.strip(), "generated": True, "error": None}
    except Exception as e:
        logger.warning(f"Daily briefing generation failed: {e}")
        return {"text": None, "generated": False, "error": str(e)}
