"""Typed access to config/signal.toml.

Nothing else in ingest/ is allowed to hardcode an indicator or signal parameter.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on the local 3.9 interpreter
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "config" / "signal.toml"
DATA_DIR = REPO_ROOT / "data"
STATIC_DIR = Path(__file__).resolve().parent / "static"

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SignalConfig:
    """Everything the classifier needs. Passed explicitly, never read globally."""

    bb_period: int
    bb_stddev: float
    bb_ddof: int
    sma_period: int
    min_bars: int
    zone_pct: float

    @property
    def upper_zone(self) -> float:
        """The bearish threshold. Derived, so the two sides cannot drift apart."""
        return 1.0 - self.zone_pct


@dataclass(frozen=True)
class UniverseConfig:
    history_years: int
    batch_size: int
    max_retries: int
    backoff_base_s: float


@dataclass(frozen=True)
class Config:
    signal: SignalConfig
    universe: UniverseConfig
    horizons: Dict[str, int]

    def params_dict(self) -> Dict[str, object]:
        """The snapshot written into meta.json so the UI can show what produced it."""
        s = self.signal
        return {
            "bb_period": s.bb_period,
            "bb_stddev": s.bb_stddev,
            "bb_ddof": s.bb_ddof,
            "sma_period": s.sma_period,
            "min_bars": s.min_bars,
            "zone_pct": s.zone_pct,
        }


def load_config(path: Path = CONFIG_PATH) -> Config:
    with open(path, "rb") as fh:
        raw = tomllib.load(fh)

    ind, sig = raw["indicators"], raw["signal"]
    signal = SignalConfig(
        bb_period=int(ind["bb_period"]),
        bb_stddev=float(ind["bb_stddev"]),
        bb_ddof=int(ind["bb_ddof"]),
        sma_period=int(ind["sma_period"]),
        min_bars=int(ind["min_bars"]),
        zone_pct=float(sig["zone_pct"]),
    )
    _validate(signal)

    uni = raw["universe"]
    universe = UniverseConfig(
        history_years=int(uni["history_years"]),
        batch_size=int(uni["batch_size"]),
        max_retries=int(uni["max_retries"]),
        backoff_base_s=float(uni["backoff_base_s"]),
    )
    return Config(
        signal=signal,
        universe=universe,
        horizons={k: int(v) for k, v in raw["horizons"].items()},
    )


def _validate(s: SignalConfig) -> None:
    if not 0.0 < s.zone_pct < 0.5:
        raise ValueError(
            f"zone_pct must be in (0, 0.5), got {s.zone_pct}. At or above 0.5 the "
            "bullish and bearish zones overlap and the signal is meaningless."
        )
    if s.bb_period < 2:
        raise ValueError("bb_period must be >= 2")
    if s.bb_stddev <= 0:
        raise ValueError("bb_stddev must be > 0")
    if s.bb_ddof not in (0, 1):
        raise ValueError("bb_ddof must be 0 (population) or 1 (sample)")
    if s.min_bars < max(s.bb_period, s.sma_period):
        raise ValueError(
            f"min_bars ({s.min_bars}) is below sma_period ({s.sma_period}); bars "
            "would be classified before the trend filter has any value."
        )


@lru_cache(maxsize=1)
def get_config() -> Config:
    return load_config()
