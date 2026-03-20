#!/usr/bin/env python3
# =============================================================================
#  live_main.py
#  FORWARD TEST / PAPER TRADING entry point
#  Pulls real-time Alpha Vantage data, trades on paper, logs everything.
#  Usage:  python live_main.py
# =============================================================================

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import INITIAL_CAPITAL, REPORTS_DIR
from execution.live_trader import LiveTrader
from utils.logger import get_logger

log = get_logger("live_main")


def main():
    log.info("╔══════════════════════════════════════════════════════════╗")
    log.info("║   RENAISSANCE QUANTITATIVE FUND  ·  PAPER TRADER        ║")
    log.info("║   Mode: FORWARD TEST  |  Data: Alpha Vantage Real-Time  ║")
    log.info("╚══════════════════════════════════════════════════════════╝")

    # max_cycles = number of refresh cycles (1 cycle = 60 seconds on live data)
    # Increase for longer sessions e.g. max_cycles=480 ≈ 8 hours
    trader  = LiveTrader(capital=INITIAL_CAPITAL, max_cycles=20)
    results = trader.run()

    # ── Render performance dashboard ───────────────────────────────────────────
    eq_df  = results.get("equity_log")
    trades = results.get("trades")

    if eq_df is None or eq_df.empty:
        log.warning("No equity data to visualise.")
        return

    import pandas as pd
    from visualize.dashboard import render_dashboard

    # Normalise equity series
    equity = eq_df["equity"].astype(float).reset_index(drop=True)

    chart_path = render_dashboard(
        equity, trades if trades is not None else pd.DataFrame(),
        title="Forward Test (Paper Trading)",
        save_to=os.path.join(REPORTS_DIR, "forward_dashboard.png"),
    )

    log.info(f"\n  📊  Dashboard saved → {chart_path}\n")


if __name__ == "__main__":
    main()
