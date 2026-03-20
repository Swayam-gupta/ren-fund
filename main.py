#!/usr/bin/env python3
# =============================================================================
#  main.py
#  BACKTEST entry point — runs full 2-year event-driven simulation
#  Usage:  python main.py
# =============================================================================

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import (
    FOREX_PAIRS, BACKTEST_START, BACKTEST_END,
    INITIAL_CAPITAL, TARGET_CAGR, REPORTS_DIR,
)
from utils.data_fetcher import load_all_pairs
from utils.logger import get_logger
from backtest.engine import BacktestEngine
from visualize.dashboard import render_dashboard

log = get_logger("main")


def main():
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║   RENAISSANCE QUANTITATIVE FUND  ·  BACKTEST ENGINE     ║")
    log.info("║   Strategy: Multi-Factor FX  |  Target CAGR: 30%        ║")
    log.info("╚══════════════════════════════════════════════════════════╝")
    log.info(f"  Capital  : ${INITIAL_CAPITAL:,.2f}")
    log.info(f"  Universe : {[f'{a}{b}' for a,b in FOREX_PAIRS]}")
    log.info(f"  Period   : {BACKTEST_START} → {BACKTEST_END}")

    # ── 1. Fetch data ──────────────────────────────────────────────────────────
    log.info("\n[1/3]  Fetching historical data from Alpha Vantage ...")
    universe = load_all_pairs(
        FOREX_PAIRS, start_date=BACKTEST_START, end_date=BACKTEST_END
    )

    if not universe:
        log.error(
            "No data loaded.\n"
            "  • Check your internet connection\n"
            "  • Verify API key in config/api_config.py\n"
            "  • Alpha Vantage free tier: 25 calls/day, 5 calls/min"
        )
        sys.exit(1)

    log.info(f"  Loaded {len(universe)} pairs  ✓")

    # ── 2. Run backtest ────────────────────────────────────────────────────────
    log.info("\n[2/3]  Running backtest engine ...")
    engine  = BacktestEngine(universe, initial_capital=INITIAL_CAPITAL)
    results = engine.run()

    equity  = results["equity"]
    trades  = results["trades"]
    metrics = results["metrics"]

    # ── 3. Render dashboard ────────────────────────────────────────────────────
    log.info("\n[3/3]  Rendering performance dashboard ...")
    chart_path = render_dashboard(
        equity, trades,
        title="Backtest 2023–2024",
        save_to=os.path.join(REPORTS_DIR, "backtest_dashboard.png"),
    )

    # ── Summary ────────────────────────────────────────────────────────────────
    achieved_cagr = metrics.get("CAGR (%)", 0)
    hit_target    = achieved_cagr >= TARGET_CAGR * 100

    log.info("\n" + "━" * 52)
    log.info(f"  CAGR Achieved  : {achieved_cagr:.2f}%")
    log.info(f"  Target CAGR    : {TARGET_CAGR * 100:.0f}%")
    log.info(f"  Target Met     : {'✅  YES' if hit_target else '⚠️   Not yet — tune settings.py'}")
    log.info(f"  Dashboard      : {chart_path}")
    log.info("━" * 52 + "\n")


if __name__ == "__main__":
    main()
