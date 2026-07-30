"""Classification of a close series into BULLISH / BEARISH / NEUTRAL.

    BULLISH  = close > SMA50  AND  close > lower  AND  pct_b <= zone_pct
    BEARISH  = close < SMA50  AND  close < upper  AND  pct_b >= 1 - zone_pct
    NEUTRAL  = otherwise

The `close > lower` clause is not redundant with the %B test. `pct_b <= 0.25`
alone would also admit pct_b = -0.4, a stock that has broken clean through the
lower band. That is a breakdown, not a pullback, and it is excluded. So BULLISH
is really 0 < pct_b <= zone_pct, and BEARISH is 1 - zone_pct <= pct_b < 1.
"""
from __future__ import annotations

import pandas as pd

from .config import SignalConfig
from .indicators import bollinger, percent_b, sma

BULLISH = "BULLISH"
BEARISH = "BEARISH"
NEUTRAL = "NEUTRAL"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

SIGNAL_STATES = (BULLISH, BEARISH, NEUTRAL, INSUFFICIENT_DATA)

# Tolerance for the two zone comparisons.
#
# pandas computes a rolling standard deviation with an online algorithm, which is
# fast but accumulates last-bit error: a window whose population sigma is exactly
# 4 comes back as 4.000000000000007. That pushes a %B of exactly 0.25 to
# 0.25000000000000044, and a bare `<= 0.25` then rejects a bar that sits precisely
# on the boundary. Which side of the line such a bar falls on would be decided by
# float noise rather than by price.
#
# 1e-9 is a billionth of the band width -- economically meaningless, numerically
# decisive. It is not a strategy parameter, so it does not belong in signal.toml.
ZONE_EPSILON = 1e-9


def classify(close: pd.Series, cfg: SignalConfig) -> pd.DataFrame:
    """Classify every bar of `close`.

    Returns a frame indexed like `close` with columns:
    close, sma50, mid, upper, lower, sigma, pct_b, signal.

    Every bar is labelled, not just the last one, because `prev_signal` and the
    "changed today" marker both need the bar before the latest.
    """
    close = close.astype(float)
    sma_trend = sma(close, cfg.sma_period)
    bands = bollinger(close, cfg.bb_period, cfg.bb_stddev, cfg.bb_ddof)
    pct_b = percent_b(close, bands.upper, bands.lower)

    # Count real observations, not index positions, so a gappy series is not
    # credited with history it does not have.
    observed = close.notna().cumsum()

    has_history = (
        (observed >= cfg.min_bars)
        & close.notna()
        & sma_trend.notna()
        & bands.upper.notna()
        & bands.lower.notna()
    )
    # A zero-width band leaves pct_b NaN. That bar has plenty of history, it just
    # cannot be scored -- it is NEUTRAL, not INSUFFICIENT_DATA.
    scorable = has_history & pct_b.notna()

    bullish = (
        scorable
        & (close > sma_trend)
        & (close > bands.lower)
        & (pct_b <= cfg.zone_pct + ZONE_EPSILON)
    )
    bearish = (
        scorable
        & (close < sma_trend)
        & (close < bands.upper)
        & (pct_b >= cfg.upper_zone - ZONE_EPSILON)
    )

    signal = pd.Series(NEUTRAL, index=close.index, dtype=object)
    signal[bullish] = BULLISH
    signal[bearish] = BEARISH
    signal[~has_history] = INSUFFICIENT_DATA

    return pd.DataFrame(
        {
            "close": close,
            "sma50": sma_trend,
            "mid": bands.mid,
            "upper": bands.upper,
            "lower": bands.lower,
            "sigma": bands.sigma,
            "pct_b": pct_b,
            "signal": signal,
        }
    )


def latest_state(frame: pd.DataFrame) -> dict:
    """Collapse a classified frame to the payload for one (symbol, timeframe).

    `prev_signal` is the classification of the previous bar, computed from that
    bar's own indicators -- not a cached value from yesterday's run.
    """
    if frame.empty:
        return {
            "bar_date": None,
            "close": None,
            "sma50": None,
            "pct_b": None,
            "signal": INSUFFICIENT_DATA,
            "prev_signal": INSUFFICIENT_DATA,
        }

    last = frame.iloc[-1]
    prev_signal = frame["signal"].iloc[-2] if len(frame) >= 2 else INSUFFICIENT_DATA

    return {
        "bar_date": frame.index[-1].date().isoformat(),
        "close": _num(last["close"]),
        "sma50": _num(last["sma50"]),
        "pct_b": _num(last["pct_b"]),
        "signal": last["signal"],
        "prev_signal": prev_signal,
    }


def changed(signal: str, prev_signal: str) -> bool:
    """True when the latest bar flipped the signal.

    Coming out of INSUFFICIENT_DATA does not count. That is a data event -- a
    symbol crossing the 60-bar threshold -- not a market event, and it would
    otherwise pollute the actionable list with newly-listed names.
    """
    if INSUFFICIENT_DATA in (signal, prev_signal):
        return False
    return signal != prev_signal


def _num(value, digits: int = 4):
    """Round for the wire, and turn NaN into null rather than the string 'NaN'."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)
