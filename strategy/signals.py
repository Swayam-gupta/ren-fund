# =============================================================================
#  strategy/signals.py
#  Technical indicator library + composite signal engine
#  Indicators: RSI · MACD · Bollinger Bands · ATR · Momentum · Z-Score · EMA
# =============================================================================

import numpy as np
import pandas as pd

from config.settings import (
    RSI_PERIOD, RSI_OVERSOLD, RSI_OVERBOUGHT,
    MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BB_PERIOD, BB_STD,
    ATR_PERIOD, MOMENTUM_LOOKBACK,
)


# ── Indicator functions ────────────────────────────────────────────────────────

def compute_rsi(close: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Wilder smoothed RSI."""
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(com=period - 1, min_periods=period).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=period - 1, min_periods=period).mean()
    rs    = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).rename("rsi")


def compute_macd(
    close:  pd.Series,
    fast:   int = MACD_FAST,
    slow:   int = MACD_SLOW,
    signal: int = MACD_SIGNAL,
) -> pd.DataFrame:
    """MACD line, signal line, histogram."""
    ema_fast    = close.ewm(span=fast,   adjust=False).mean()
    ema_slow    = close.ewm(span=slow,   adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame({
        "macd":        macd_line,
        "macd_signal": signal_line,
        "macd_hist":   macd_line - signal_line,
    }, index=close.index)


def compute_bollinger(
    close:  pd.Series,
    period: int   = BB_PERIOD,
    n_std:  float = BB_STD,
) -> pd.DataFrame:
    """Bollinger Bands + %B."""
    mid   = close.rolling(period).mean()
    std   = close.rolling(period).std()
    upper = mid + n_std * std
    lower = mid - n_std * std
    pctb  = (close - lower) / (upper - lower + 1e-12)
    return pd.DataFrame({
        "bb_upper": upper,
        "bb_mid":   mid,
        "bb_lower": lower,
        "bb_pctb":  pctb,
    }, index=close.index)


def compute_atr(
    high:   pd.Series,
    low:    pd.Series,
    close:  pd.Series,
    period: int = ATR_PERIOD,
) -> pd.Series:
    """Wilder Average True Range."""
    prev  = close.shift(1)
    tr    = pd.concat([
        high - low,
        (high - prev).abs(),
        (low  - prev).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean().rename("atr")


def compute_momentum(close: pd.Series, lookback: int = MOMENTUM_LOOKBACK) -> pd.Series:
    """Rate-of-change momentum."""
    return close.pct_change(lookback).rename("momentum")


def compute_zscore(series: pd.Series, window: int = 20) -> pd.Series:
    """Rolling z-score for mean-reversion detection."""
    mu  = series.rolling(window).mean()
    std = series.rolling(window).std()
    return ((series - mu) / (std + 1e-12)).rename("zscore")


def compute_ema(close: pd.Series, span: int) -> pd.Series:
    return close.ewm(span=span, adjust=False).mean()


# ── Feature builder ────────────────────────────────────────────────────────────

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds all indicator columns to an OHLCV DataFrame and drops NaN rows.
    Input  must have columns: open, high, low, close
    Output adds: rsi, macd, macd_signal, macd_hist, bb_*, atr, momentum, zscore,
                 ema20, ema50
    """
    df    = df.copy()
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    df["rsi"]      = compute_rsi(close)
    df             = pd.concat([df, compute_macd(close)],     axis=1)
    df             = pd.concat([df, compute_bollinger(close)], axis=1)
    df["atr"]      = compute_atr(high, low, close)
    df["momentum"] = compute_momentum(close)
    df["zscore"]   = compute_zscore(close)
    df["ema20"]    = compute_ema(close, 20)
    df["ema50"]    = compute_ema(close, 50)

    df.dropna(inplace=True)
    return df


# ── Signal generation ──────────────────────────────────────────────────────────

def _score_row(row: pd.Series) -> int:
    """
    Composite 5-factor signal.
    Returns +1 (buy), -1 (sell), 0 (flat).
    A signal requires ≥ 4 of 5 factors to agree.
    """
    buy = sell = 0

    # 1. EMA trend
    if   row["ema20"] > row["ema50"]: buy  += 1
    elif row["ema20"] < row["ema50"]: sell += 1

    # 2. MACD histogram
    if   row["macd_hist"] > 0: buy  += 1
    elif row["macd_hist"] < 0: sell += 1

    # 3. RSI not in opposing extreme
    if row["rsi"] < RSI_OVERBOUGHT: buy  += 1
    if row["rsi"] > RSI_OVERSOLD:   sell += 1

    # 4. Bollinger %B
    if   row["bb_pctb"] < 0.35: buy  += 1
    elif row["bb_pctb"] > 0.65: sell += 1

    # 5. Short-term momentum
    if   row["momentum"] > 0: buy  += 1
    elif row["momentum"] < 0: sell += 1

    if buy  >= 4: return  1
    if sell >= 4: return -1
    return 0


def apply_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Apply signal generation row-wise and store in 'signal' column."""
    df          = df.copy()
    df["signal"] = df.apply(_score_row, axis=1)
    return df
