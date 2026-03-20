# =============================================================================
#  backtest/metrics.py
#  Full performance metrics library
#  Sharpe · Sortino · CAGR · Max Drawdown · Calmar · Win-Rate · Profit Factor
# =============================================================================

import numpy as np
import pandas as pd
from typing import Dict


def _estimate_years(equity: pd.Series) -> float:
    """
    Robustly estimate the number of years spanned by an equity series,
    handling DatetimeIndex, integer (bar) index, and short forward-test
    cycle indexes (< 252) gracefully.
    """
    idx0, idx1 = equity.index[0], equity.index[-1]

    # DatetimeIndex — use calendar days
    if hasattr(idx1 - idx0, "days"):
        days = (idx1 - idx0).days
        return days / 365.25 if days > 0 else 0.0

    # Integer / RangeIndex
    n = int(idx1) - int(idx0)
    if n <= 0:
        return 0.0
    # If the series has ≥ 252 bars treat each bar as a trading day
    # For short forward-test sessions (< 252 bars) treat each bar as 1 day
    # and cap annualisation so CAGR doesn't explode
    return n / 252.0


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] == 0:
        return 0.0
    years = _estimate_years(equity)
    if years <= 0:
        return 0.0
    raw = (equity.iloc[-1] / equity.iloc[0]) ** (1.0 / years) - 1
    # Cap annualised CAGR at ±10 000% to prevent scorecard nonsense
    # on very short forward-test sessions
    return max(-100.0, min(raw, 100.0))


def total_return(equity: pd.Series) -> float:
    """Simple total return — never annualised, always meaningful."""
    if equity.iloc[0] == 0:
        return 0.0
    return (equity.iloc[-1] / equity.iloc[0] - 1) * 100


def sharpe_ratio(returns: pd.Series, rf: float = 0.0, periods: int = 252) -> float:
    excess = returns - rf / periods
    std    = excess.std()
    if std == 0 or len(returns) < 2:
        return 0.0
    return round(excess.mean() / std * np.sqrt(periods), 3)


def sortino_ratio(returns: pd.Series, rf: float = 0.0, periods: int = 252) -> float:
    excess   = returns - rf / periods
    downside = excess[excess < 0].std()
    if downside == 0 or len(returns) < 2:
        return float("nan")
    return round(excess.mean() / downside * np.sqrt(periods), 3)


def max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd       = (equity - roll_max) / roll_max
    return float(dd.min())


def calmar_ratio(equity: pd.Series) -> float:
    mdd = abs(max_drawdown(equity))
    if mdd == 0:
        return 0.0
    c = cagr(equity)
    return round(c / mdd, 3)


def win_rate(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    return len(trades[trades["pnl"] > 0]) / len(trades)


def profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    gp = trades[trades["pnl"] > 0]["pnl"].sum()
    gl = abs(trades[trades["pnl"] < 0]["pnl"].sum())
    if gl == 0:
        return float("inf") if gp > 0 else 0.0
    return round(gp / gl, 3)


def avg_win(trades: pd.DataFrame) -> float:
    w = trades[trades["pnl"] > 0]["pnl"]
    return float(w.mean()) if not w.empty else 0.0


def avg_loss(trades: pd.DataFrame) -> float:
    l = trades[trades["pnl"] < 0]["pnl"]
    return float(l.mean()) if not l.empty else 0.0


def expectancy(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    wr = win_rate(trades)
    aw = avg_win(trades)
    al = abs(avg_loss(trades))
    return wr * aw - (1 - wr) * al


def compute_all(equity: pd.Series, trades: pd.DataFrame) -> Dict[str, object]:
    """Returns the full performance scorecard as an ordered dict."""
    rets    = equity.pct_change().dropna()
    years   = _estimate_years(equity)

    # Determine label for annualised metric
    cagr_val   = cagr(equity) * 100
    cagr_label = "CAGR (%)" if years >= 0.5 else "Ann. Return % (short test)"

    return {
        "Initial Capital ($)":    round(float(equity.iloc[0]),  2),
        "Final Equity ($)":       round(float(equity.iloc[-1]), 2),
        "Total Return (%)":       round(total_return(equity),   2),
        cagr_label:               round(cagr_val,               2),
        "Sharpe Ratio":           sharpe_ratio(rets),
        "Sortino Ratio":          sortino_ratio(rets),
        "Calmar Ratio":           calmar_ratio(equity),
        "Max Drawdown (%)":       round(max_drawdown(equity) * 100, 2),
        "Win Rate (%)":           round(win_rate(trades) * 100, 2),
        "Profit Factor":          profit_factor(trades),
        "Avg Win ($)":            round(avg_win(trades),        4),
        "Avg Loss ($)":           round(avg_loss(trades),       4),
        "Expectancy ($/trade)":   round(expectancy(trades),     4),
        "Total Trades":           len(trades),
        "Winning Trades":         len(trades[trades["pnl"] > 0]) if not trades.empty else 0,
        "Losing Trades":          len(trades[trades["pnl"] < 0]) if not trades.empty else 0,
        "Peak Equity ($)":        round(float(equity.max()),    2),
        "Test Duration (bars)":   len(equity),
    }


def print_scorecard(metrics: Dict) -> None:
    w = 54
    line = "═" * w
    print(f"\n  ╔{line}╗")
    print(f"  ║{'RENAISSANCE QUANTITATIVE FUND':^{w}}║")
    print(f"  ║{'PERFORMANCE SCORECARD':^{w}}║")
    print(f"  ╠{line}╣")
    for k, v in metrics.items():
        v_str = str(v)
        print(f"  ║  {k:<32} {v_str:>{w-35}}  ║")
    print(f"  ╚{line}╝\n")
