# =============================================================================
#  execution/live_trader.py
#  Forward / Paper Trader — pulls real-time Alpha Vantage data every 60 s,
#  generates signals, manages positions, and logs every order.
# =============================================================================

import time
import os
from datetime import datetime
from typing import Dict, List

import pandas as pd

from config.settings import (
    FOREX_PAIRS, INITIAL_CAPITAL, DEFAULT_LEVERAGE,
    STANDARD_LOT, MAX_OPEN_POSITIONS, MAX_DRAWDOWN_LIMIT, TRADE_LOG_DIR,
)
from utils.data_fetcher import fetch_fx_daily
from strategy.signals import build_features, apply_signals
from strategy.risk_management import (
    create_position, buy_pnl_lot, sell_pnl_lot, position_summary,
)
from strategy.portfolio import rank_signals, build_portfolio
from execution.order_manager import OrderManager
from utils.logger import get_logger

log = get_logger("live_trader")

POLL_SECONDS = 60      # seconds between refresh cycles


class LiveTrader:

    def __init__(self, capital: float = INITIAL_CAPITAL, max_cycles: int = 20):
        self.capital          = capital
        self.peak_capital     = capital
        self.max_cycles       = max_cycles
        self.order_mgr        = OrderManager()
        self.open_positions   : Dict[str, dict] = {}   # pair → {oid, pos}
        self._cycle           = 0
        self._equity_log      : List[dict] = []

    # ── Entry point ────────────────────────────────────────────────────────────

    def run(self) -> dict:
        log.info("╔══════════════════════════════════════════════════════════╗")
        log.info("║   RENAISSANCE QUANT FUND  ·  FORWARD / PAPER TRADER     ║")
        log.info(f"║   Capital: ${self.capital:,.2f}  |  Max Cycles: {self.max_cycles:<4}           ║")
        log.info(f"║   Universe: {[f'{a}{b}' for a,b in FOREX_PAIRS]}        ")
        log.info("╚══════════════════════════════════════════════════════════╝")

        while self._cycle < self.max_cycles:
            self._cycle += 1
            ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            log.info(f"\n{'─'*58}")
            log.info(f"  CYCLE {self._cycle:02d}/{self.max_cycles}  ·  {ts} UTC")
            log.info(f"{'─'*58}")

            try:
                self._cycle_step()
            except Exception as exc:
                log.error(f"Cycle error: {exc}", exc_info=True)

            # Snapshot equity
            s = self.order_mgr.summary()
            self._equity_log.append({
                "cycle":       self._cycle,
                "timestamp":   ts,
                "cash":        round(self.capital, 4),
                "equity":      round(self.capital, 4),   # no unrealised MTM
                "open_trades": len(self.open_positions),
                "realised_pnl": round(s["realised_pnl"], 4),
            })

            if self._cycle < self.max_cycles:
                log.info(f"  ⏳  Next refresh in {POLL_SECONDS}s ...")
                time.sleep(POLL_SECONDS)

        return self._finalise()

    # ── Single cycle ───────────────────────────────────────────────────────────

    def _cycle_step(self):
        # 1. Fetch latest bar for each pair
        features : Dict[str, pd.Series] = {}
        prices   : Dict[str, float]     = {}

        for from_ccy, to_ccy in FOREX_PAIRS:
            sym = f"{from_ccy}{to_ccy}"
            try:
                df      = fetch_fx_daily(from_ccy, to_ccy, outputsize="compact")
                feat_df = apply_signals(build_features(df))
                if feat_df.empty:
                    continue
                features[sym] = feat_df.iloc[-1].copy()
                prices[sym]   = float(feat_df.iloc[-1]["close"])
                log.info(
                    f"  {sym}: close={prices[sym]:.5f}  "
                    f"signal={int(features[sym]['signal'])}"
                )
            except Exception as exc:
                log.warning(f"  {sym} fetch failed: {exc}")

        if not features:
            log.warning("  No market data available — skipping cycle.")
            return

        # 2. Check TP/SL on open positions
        self._monitor_positions(features, prices)

        # 3. Drawdown guard
        if not self._drawdown_ok():
            log.error("  ⛔  DRAWDOWN LIMIT — force-closing all positions.")
            self._close_all(prices)
            return

        # 4. Open new positions
        slots = MAX_OPEN_POSITIONS - len(self.open_positions)
        if slots > 0:
            active  = set(self.open_positions.keys())
            signals = {s: int(r["signal"])
                       for s, r in features.items()
                       if s not in active}
            ranked  = rank_signals(signals, features)

            if ranked:
                new_pos = build_portfolio(ranked[:slots], prices, self.capital)
                for pos in new_pos:
                    if pos.margin > self.capital * 0.95:
                        log.warning(f"  ⚠  Insufficient margin {pos.pair}")
                        continue
                    oid = self.order_mgr.submit(
                        pair=pos.pair, side=pos.side, lot=pos.lot,
                        price=pos.entry, tp=pos.tp, sl=pos.sl,
                        margin=pos.margin,
                    )
                    self.capital -= pos.margin
                    self.open_positions[pos.pair] = {"oid": oid, "pos": pos}
                    log.info(f"  ✅  {position_summary(pos)}")
            else:
                log.info("  📊  No qualifying signals this cycle.")
        else:
            log.info(f"  📋  All {MAX_OPEN_POSITIONS} position slots occupied.")

        # 5. Status
        s = self.order_mgr.summary()
        log.info(
            f"  💼  Cash=${self.capital:,.4f}  "
            f"Realised P&L=${s['realised_pnl']:+.4f}  "
            f"Open={s['open']}  Closed={s['closed']}"
        )

    # ── TP/SL monitoring ───────────────────────────────────────────────────────

    def _monitor_positions(self, features, prices):
        to_close = []
        for sym, info in self.open_positions.items():
            pos = info["pos"]
            row = features.get(sym)
            if row is None:
                continue
            hi  = float(row["high"])
            lo  = float(row["low"])

            reason = None
            if pos.side == "buy":
                if hi >= pos.tp: reason = "tp"
                elif lo <= pos.sl: reason = "sl"
            else:
                if lo <= pos.tp: reason = "tp"
                elif hi >= pos.sl: reason = "sl"

            if reason:
                ep  = pos.tp if reason == "tp" else pos.sl
                pnl = (buy_pnl_lot(pos.lot, ep, pos.entry, pos.gamma)
                       if pos.side == "buy"
                       else sell_pnl_lot(pos.lot, ep, pos.entry, pos.gamma))
                self.order_mgr.close(info["oid"], ep, pnl, reason)
                self.capital += pos.margin + pnl
                to_close.append(sym)

        for sym in to_close:
            del self.open_positions[sym]

    def _close_all(self, prices):
        for sym, info in list(self.open_positions.items()):
            pos = info["pos"]
            ep  = prices.get(sym, pos.entry)
            pnl = (buy_pnl_lot(pos.lot, ep, pos.entry, pos.gamma)
                   if pos.side == "buy"
                   else sell_pnl_lot(pos.lot, ep, pos.entry, pos.gamma))
            self.order_mgr.close(info["oid"], ep, pnl, "force_close")
            self.capital += pos.margin + pnl
            del self.open_positions[sym]

    def _drawdown_ok(self) -> bool:
        self.peak_capital = max(self.peak_capital, self.capital)
        dd = (self.peak_capital - self.capital) / self.peak_capital
        return dd <= MAX_DRAWDOWN_LIMIT

    # ── Session finalise ───────────────────────────────────────────────────────

    def _finalise(self) -> dict:
        log.info("\n" + "═" * 58)
        log.info("  FORWARD TEST SESSION COMPLETE")
        log.info("═" * 58)
        s = self.order_mgr.summary()
        log.info(f"  Final Cash:     ${self.capital:,.4f}")
        log.info(f"  Realised P&L:   ${s['realised_pnl']:+.4f}")
        log.info(f"  Closed Trades:  {s['closed']}")
        log.info(f"  Still Open:     {s['open']}")

        os.makedirs("data/processed", exist_ok=True)
        eq_df = pd.DataFrame(self._equity_log)
        eq_df.to_csv("data/processed/forward_equity.csv", index=False)
        log.info("  Equity log  → data/processed/forward_equity.csv")

        trades_df = self.order_mgr.to_df()
        if not trades_df.empty:
            trades_df.to_csv("data/processed/forward_trades.csv", index=False)
            log.info("  Trade ledger → data/processed/forward_trades.csv")

        return {
            "equity_log":    eq_df,
            "trades":        trades_df,
            "final_capital": self.capital,
            "realised_pnl":  s["realised_pnl"],
        }
