# =============================================================================
#  backtest/metrics.py
#  Full performance metrics library
#  Sharpe · Sortino · CAGR · Max Drawdown · Calmar · Win-Rate · Profit Factor
# =============================================================================

import numpy as np
import pandas as pd
from typing import Dict


def cagr(equity: pd.Series) -> float:
    if len(equity) < 2 or equity.iloc[0] == 0:
        return 0.0
    # Handle DatetimeIndex vs integer/range index
    idx0, idx1 = equity.index[0], equity.index[-1]
    if hasattr(idx1 - idx0, "days"):
        years = (idx1 - idx0).days / 365.25
    else:
        # Integer index: assume each bar = 1 trading day
        years = (int(idx1) - int(idx0)) / 252
    return 0.0 if years <= 0 else (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1


def sharpe_ratio(returns: pd.Series, rf: float = 0.0, periods: int = 252) -> float:
    excess = returns - rf / periods
    std    = excess.std()
    return 0.0 if std == 0 else excess.mean() / std * np.sqrt(periods)


def sortino_ratio(returns: pd.Series, rf: float = 0.0, periods: int = 252) -> float:
    excess    = returns - rf / periods
    downside  = excess[excess < 0].std()
    return 0.0 if downside == 0 else excess.mean() / downside * np.sqrt(periods)


def max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd       = (equity - roll_max) / roll_max
    return float(dd.min())


def calmar_ratio(equity: pd.Series) -> float:
    mdd = abs(max_drawdown(equity))
    return 0.0 if mdd == 0 else cagr(equity) / mdd


def win_rate(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    return len(trades[trades["pnl"] > 0]) / len(trades)


def profit_factor(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    gp = trades[trades["pnl"] > 0]["pnl"].sum()
    gl = abs(trades[trades["pnl"] < 0]["pnl"].sum())
    return float("inf") if gl == 0 else gp / gl


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
    """Returns the full scorecard as an ordered dict."""
    rets    = equity.pct_change().dropna()
    total_r = (equity.iloc[-1] / equity.iloc[0] - 1) * 100 if equity.iloc[0] != 0 else 0

    return {
        "Initial Capital ($)":  round(float(equity.iloc[0]),  2),
        "Final Equity ($)":     round(float(equity.iloc[-1]), 2),
        "Total Return (%)":     round(total_r,                2),
        "CAGR (%)":             round(cagr(equity) * 100,     2),
        "Sharpe Ratio":         round(sharpe_ratio(rets),     3),
        "Sortino Ratio":        round(sortino_ratio(rets),    3),
        "Calmar Ratio":         round(calmar_ratio(equity),   3),
        "Max Drawdown (%)":     round(max_drawdown(equity) * 100, 2),
        "Win Rate (%)":         round(win_rate(trades) * 100, 2),
        "Profit Factor":        round(profit_factor(trades),  3),
        "Avg Win ($)":          round(avg_win(trades),        4),
        "Avg Loss ($)":         round(avg_loss(trades),       4),
        "Expectancy ($/trade)": round(expectancy(trades),     4),
        "Total Trades":         len(trades),
        "Peak Equity ($)":      round(float(equity.max()),    2),
    }


def print_scorecard(metrics: Dict) -> None:
    w = 52
    line = "═" * w
    print(f"\n  ╔{line}╗")
    print(f"  ║{'RENAISSANCE QUANTITATIVE FUND':^{w}}║")
    print(f"  ║{'PERFORMANCE SCORECARD':^{w}}║")
    print(f"  ╠{line}╣")
    for k, v in metrics.items():
        v_str = str(v)
        print(f"  ║  {k:<28} {v_str:>{w-31}}  ║")
    print(f"  ╚{line}╝\n")
