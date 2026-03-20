# =============================================================================
#  visualize/dashboard.py
#  9-panel performance dashboard for both backtest and forward-test results
#
#  Run standalone:
#    python visualize/dashboard.py              ← uses data/processed/ CSVs
# =============================================================================

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import matplotlib.ticker as mtick
from typing import Optional

from config.settings import REPORTS_DIR, TARGET_CAGR, INITIAL_CAPITAL
from utils.logger import get_logger

log = get_logger("dashboard")

# ── Colour palette (GitHub dark-mode inspired) ────────────────────────────────
BG     = "#0d1117";   PANEL  = "#161b22";  GRID  = "#21262d"
GREEN  = "#3fb950";   RED    = "#f85149";  BLUE  = "#58a6ff"
GOLD   = "#e3b341";   WHITE  = "#f0f6fc";  GREY  = "#8b949e"
PURPLE = "#bc8cff";   TEAL   = "#39d353"

plt.rcParams.update({
    "figure.facecolor": BG,    "axes.facecolor":  PANEL,
    "axes.edgecolor":   GRID,  "axes.labelcolor": WHITE,
    "text.color":       WHITE, "xtick.color":     GREY,
    "ytick.color":      GREY,  "grid.color":      GRID,
    "grid.linewidth":   0.5,   "font.family":     "DejaVu Sans",
    "font.size":        9,     "legend.framealpha": 0.3,
})


# ── Helpers ────────────────────────────────────────────────────────────────────

def _style(ax, title: str, ylabel: str = ""):
    ax.set_title(title, color=WHITE, fontsize=10, fontweight="bold", pad=8)
    if ylabel:
        ax.set_ylabel(ylabel, color=GREY, fontsize=8)
    ax.grid(True, alpha=0.35)
    ax.tick_params(labelsize=7)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)


def _no_data(ax, title: str):
    ax.text(0.5, 0.5, "No data yet", ha="center", va="center",
            transform=ax.transAxes, color=GREY, fontsize=11)
    _style(ax, title)


# ── Individual panels ──────────────────────────────────────────────────────────

def _panel_equity(ax, equity: pd.Series):
    """Equity curve + 30% CAGR benchmark."""
    idx    = range(len(equity))
    vals   = equity.values
    start  = vals[0]
    up     = vals[-1] >= start

    ax.fill_between(idx, start, vals, alpha=0.15, color=GREEN if up else RED)
    ax.plot(idx, vals, color=GREEN if up else RED, lw=1.8, label="Portfolio Equity")
    ax.axhline(start, color=GREY, lw=0.7, ls=":", alpha=0.6)

    # 30% target overlay
    years  = len(vals) / 252
    target = start * (1 + TARGET_CAGR) ** (np.linspace(0, years, len(vals)))
    ax.plot(idx, target, color=GOLD, lw=1.1, ls="--", alpha=0.8,
            label=f"{TARGET_CAGR*100:.0f}% CAGR Target")

    # Final equity annotation
    ax.annotate(
        f"  ${vals[-1]:,.2f}",
        xy=(len(vals) - 1, vals[-1]),
        color=GREEN if up else RED, fontsize=8.5, fontweight="bold",
    )

    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}"))
    ax.legend(fontsize=7, loc="upper left")
    _style(ax, "Equity Curve vs 30% CAGR Target", "Portfolio Value ($)")


def _panel_drawdown(ax, equity: pd.Series):
    roll_max = equity.cummax()
    dd       = (equity - roll_max) / roll_max * 100
    ax.fill_between(range(len(dd)), dd.values, 0, color=RED, alpha=0.55)
    ax.plot(range(len(dd)), dd.values, color=RED, lw=0.9)
    ax.axhline(-20, color=GOLD, ls="--", lw=0.9, label="20% Limit")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(fontsize=7)
    _style(ax, "Drawdown", "Drawdown (%)")


def _panel_rolling_sharpe(ax, equity: pd.Series, window: int = 60):
    rets = equity.pct_change().dropna()
    rs   = rets.rolling(window).apply(
        lambda r: r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0,
        raw=True,
    )
    idx = range(len(rs))
    ax.plot(idx, rs.values, color=BLUE, lw=1.1)
    ax.axhline(1.0, color=GREEN, ls="--", lw=0.8, alpha=0.7, label="Sharpe=1")
    ax.axhline(0.0, color=GREY,  ls="--", lw=0.5, alpha=0.5)
    ax.legend(fontsize=7)
    _style(ax, f"{window}-Day Rolling Sharpe", "Sharpe Ratio")


def _panel_monthly_returns(ax, equity: pd.Series):
    if not isinstance(equity.index, pd.DatetimeIndex):
        _no_data(ax, "Monthly Returns")
        return
    monthly = equity.resample("ME").last().pct_change().dropna() * 100
    if monthly.empty:
        _no_data(ax, "Monthly Returns")
        return
    colors = [GREEN if r >= 0 else RED for r in monthly]
    ax.bar(range(len(monthly)), monthly.values, color=colors, alpha=0.85)
    ax.axhline(0, color=GREY, lw=0.5)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    _style(ax, "Monthly Returns", "Return (%)")


def _panel_pnl_dist(ax, trades: pd.DataFrame):
    if trades.empty or "pnl" not in trades.columns:
        _no_data(ax, "P&L Distribution")
        return
    pnl  = trades["pnl"]
    bins = min(40, max(8, len(pnl) // 3))
    ax.hist(pnl[pnl >= 0], bins=bins, color=GREEN, alpha=0.75, label="Win")
    ax.hist(pnl[pnl < 0],  bins=bins, color=RED,   alpha=0.75, label="Loss")
    ax.axvline(pnl.mean(), color=GOLD, ls="--", lw=1.1,
               label=f"Mean ${pnl.mean():.4f}")
    ax.legend(fontsize=7)
    _style(ax, "Trade P&L Distribution", "Frequency")


def _panel_pair_pnl(ax, trades: pd.DataFrame):
    if trades.empty or "pair" not in trades.columns:
        _no_data(ax, "P&L by Currency Pair")
        return
    pp = trades.groupby("pair")["pnl"].sum().sort_values()
    ax.barh(pp.index, pp.values,
            color=[GREEN if v >= 0 else RED for v in pp.values], alpha=0.85)
    ax.axvline(0, color=GREY, lw=0.5)
    ax.xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:.2f}"))
    _style(ax, "Total P&L by Currency Pair", "P&L ($)")


def _panel_win_rate(ax, trades: pd.DataFrame):
    if trades.empty or "pnl" not in trades.columns:
        _no_data(ax, "Rolling Win Rate")
        return
    wins = (trades["pnl"] > 0).astype(int)
    w    = min(20, len(trades))
    wr   = wins.rolling(w).mean() * 100
    ax.plot(range(len(wr)), wr.values, color=BLUE, lw=1.1)
    ax.axhline(50, color=GREY,  ls="--", lw=0.6, alpha=0.7, label="50%")
    ax.axhline(60, color=GREEN, ls="--", lw=0.6, alpha=0.7, label="60%")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter())
    ax.legend(fontsize=7)
    _style(ax, f"Rolling {w}-Trade Win Rate", "Win Rate (%)")


def _panel_side_pnl(ax, trades: pd.DataFrame):
    if trades.empty or "side" not in trades.columns:
        _no_data(ax, "Buy vs Sell P&L")
        return
    sp     = trades.groupby("side")["pnl"].agg(["sum", "count"])
    sides  = sp.index.tolist()
    totals = sp["sum"].values
    counts = sp["count"].values
    bars   = ax.bar(sides, totals,
                    color=[GREEN if t >= 0 else RED for t in totals],
                    alpha=0.85, width=0.45)
    for bar, cnt in zip(bars, counts):
        ypos = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2,
                ypos + (abs(ypos) * 0.03),
                f"n={cnt}", ha="center", va="bottom", fontsize=8, color=WHITE)
    ax.axhline(0, color=GREY, lw=0.5)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:.4f}"))
    _style(ax, "Buy vs Sell — Total P&L", "P&L ($)")


def _panel_scorecard(ax, equity: pd.Series, trades: pd.DataFrame):
    ax.axis("off")

    from backtest.metrics import compute_all
    metrics = compute_all(equity, trades)

    ax.text(0.5, 0.99, "PERFORMANCE SCORECARD",
            ha="center", va="top", transform=ax.transAxes,
            color=GOLD, fontsize=11, fontweight="bold")

    y    = 0.88
    step = 0.062

    for k, v in metrics.items():
        v_str = str(v)
        is_neg = isinstance(v, (int, float)) and v < 0
        is_pos = isinstance(v, (int, float)) and v > 0

        if "Drawdown" in k or "Loss" in k:
            col = RED
        elif is_pos and "Return" in k or "Sharpe" in k or "Sortino" in k \
                or "CAGR" in k or "Factor" in k or "Win" in k or "Expectancy" in k:
            col = GREEN
        elif is_neg:
            col = RED
        else:
            col = WHITE

        ax.text(0.04, y, k, ha="left", va="top",
                transform=ax.transAxes, color=GREY, fontsize=8.2)
        ax.text(0.97, y, v_str, ha="right", va="top",
                transform=ax.transAxes, color=col, fontsize=8.2, fontweight="bold")
        ax.axhline(y - 0.008, xmin=0.02, xmax=0.98, color=GRID, lw=0.4,
                   transform=ax.transAxes)
        y -= step


# ── Master renderer ────────────────────────────────────────────────────────────

def render_dashboard(
    equity:  pd.Series,
    trades:  pd.DataFrame,
    title:   str = "Backtest",
    save_to: Optional[str] = None,
) -> str:
    if save_to is None:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        save_to = os.path.join(REPORTS_DIR, "dashboard.png")

    fig = plt.figure(figsize=(24, 15), facecolor=BG)
    fig.suptitle(
        f"🏦  RENAISSANCE QUANTITATIVE FUND  ·  {title} Dashboard",
        fontsize=15, fontweight="bold", color=WHITE, y=0.995,
    )

    gs = gridspec.GridSpec(
        3, 3, figure=fig,
        hspace=0.44, wspace=0.30,
        top=0.95, bottom=0.05, left=0.06, right=0.97,
    )

    _panel_equity         (fig.add_subplot(gs[0, 0:2]), equity)
    _panel_scorecard      (fig.add_subplot(gs[0, 2]),   equity, trades)
    _panel_drawdown       (fig.add_subplot(gs[1, 0]),   equity)
    _panel_rolling_sharpe (fig.add_subplot(gs[1, 1]),   equity)
    _panel_monthly_returns(fig.add_subplot(gs[1, 2]),   equity)
    _panel_pnl_dist       (fig.add_subplot(gs[2, 0]),   trades)
    _panel_pair_pnl       (fig.add_subplot(gs[2, 1]),   trades)
    _panel_win_rate       (fig.add_subplot(gs[2, 2]),   trades)

    os.makedirs(os.path.dirname(save_to), exist_ok=True)
    fig.savefig(save_to, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    log.info(f"Dashboard saved → {save_to}")
    return save_to


# ── Standalone entrypoint ──────────────────────────────────────────────────────

def _load_csv(path: str) -> Optional[pd.DataFrame]:
    if not os.path.exists(path):
        return None
    return pd.read_csv(path)


if __name__ == "__main__":
    import sys

    # Try backtest outputs first, then forward-test
    eq_path = "data/processed/equity_curve.csv"
    tr_path = "data/processed/all_trades.csv"
    title   = "Backtest"

    if not os.path.exists(eq_path):
        eq_path = "data/processed/forward_equity.csv"
        tr_path = "data/processed/forward_trades.csv"
        title   = "Forward Test"

    eq_raw = _load_csv(eq_path)
    if eq_raw is None:
        print("\n  ❌  No results found. Run  python main.py  or  python live_main.py  first.\n")
        sys.exit(1)

    # Normalise equity column and index
    if "date" in eq_raw.columns:
        eq_raw["date"] = pd.to_datetime(eq_raw["date"])
        equity = eq_raw.set_index("date")["equity"].astype(float)
    else:
        equity = eq_raw["equity"].astype(float)
        equity.index = pd.RangeIndex(len(equity))

    tr_raw = _load_csv(tr_path)
    trades = tr_raw if tr_raw is not None else pd.DataFrame()

    path = render_dashboard(equity, trades, title=title)
    print(f"\n  ✅  Dashboard → {path}\n")
