# =============================================================================
#  backtest/engine.py
#  Event-driven backtesting engine with:
#    • Per-bar TP/SL exit checking
#    • Slippage and commission modelling
#    • Drawdown guard (hard stop)
#    • Full trade logging to JSONL
#    • Mark-to-market equity curve
# =============================================================================

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd

from config.settings import (
    INITIAL_CAPITAL, COMMISSION_PCT, SLIPPAGE_PCT,
    MAX_OPEN_POSITIONS, DEFAULT_LEVERAGE, STANDARD_LOT,
    RISK_PER_TRADE_PCT, TRADE_LOG_DIR, MAX_DRAWDOWN_LIMIT,
    BACKTEST_START, BACKTEST_END, TARGET_CAGR,
)
from strategy.signals import build_features, apply_signals
from strategy.risk_management import (
    create_position, buy_pnl_lot, sell_pnl_lot,
    position_summary, Position,
)
from strategy.portfolio import rank_signals, build_portfolio
from backtest.metrics import compute_all, print_scorecard
from utils.logger import get_logger

log = get_logger("backtest.engine")


# ── Trade recorder ─────────────────────────────────────────────────────────────

class TradeRecorder:
    def __init__(self):
        os.makedirs(TRADE_LOG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path   = os.path.join(TRADE_LOG_DIR, f"backtest_{ts}.jsonl")
        self.trades : List[dict] = []
        log.info(f"Trade log  → {self.path}")

    def record(self, trade: dict):
        self.trades.append(trade)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(trade) + "\n")

    def to_df(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame(columns=[
                "pair","side","entry","exit","lot",
                "pnl","exit_reason","entry_date","exit_date","duration_bars",
            ])
        return pd.DataFrame(self.trades)


# ── Open position wrapper ──────────────────────────────────────────────────────

class OpenTrade:
    def __init__(self, pos: Position, bar_idx: int, entry_date):
        self.uid        = str(uuid.uuid4())[:8]
        self.pos        = pos
        self.bar_idx    = bar_idx
        self.entry_date = entry_date

    def check_exit(self, high: float, low: float) -> Optional[str]:
        """Returns 'tp', 'sl', or None."""
        p = self.pos
        if p.side == "buy":
            if high >= p.tp: return "tp"
            if low  <= p.sl: return "sl"
        else:
            if low  <= p.tp: return "tp"
            if high >= p.sl: return "sl"
        return None

    def realised_pnl(self, exit_price: float) -> float:
        p        = self.pos
        gross    = (buy_pnl_lot(p.lot, exit_price, p.entry, p.gamma)
                    if p.side == "buy"
                    else sell_pnl_lot(p.lot, exit_price, p.entry, p.gamma))
        notional = p.lot * p.gamma * p.entry
        cost     = notional * (COMMISSION_PCT + SLIPPAGE_PCT)
        return gross - cost


# ── Main engine ────────────────────────────────────────────────────────────────

class BacktestEngine:

    def __init__(
        self,
        universe:        Dict[str, pd.DataFrame],
        initial_capital: float = INITIAL_CAPITAL,
    ):
        self.capital        = initial_capital
        self.peak_capital   = initial_capital
        self.open_trades    : List[OpenTrade] = []
        self.equity_curve   : List[dict]      = []
        self.recorder       = TradeRecorder()
        self._halted        = False

        # Compute features once
        log.info("Building feature sets ...")
        self.features: Dict[str, pd.DataFrame] = {}
        for sym, df in universe.items():
            self.features[sym] = apply_signals(build_features(df))
            log.info(f"  {sym}: {len(self.features[sym])} bars")

        # Common date index
        indices    = [df.index for df in self.features.values()]
        common_idx = indices[0]
        for idx in indices[1:]:
            common_idx = common_idx.intersection(idx)
        self.dates = common_idx.sort_values()
        log.info(
            f"Date range: {self.dates[0].date()} → {self.dates[-1].date()} "
            f"({len(self.dates)} bars)"
        )

    # ── Main loop ──────────────────────────────────────────────────────────────

    def run(self) -> Dict:
        log.info("=" * 58)
        log.info("  BACKTEST STARTING")
        log.info("=" * 58)

        for bar_idx, date in enumerate(self.dates):
            if self._halted:
                log.warning("Strategy halted — drawdown limit reached.")
                break

            bar = {sym: self.features[sym].loc[date]
                   for sym in self.features}

            self._process_exits(date, bar_idx, bar)

            if not self._check_drawdown():
                self._halted = True
                break

            if len(self.open_trades) < MAX_OPEN_POSITIONS:
                self._open_positions(date, bar_idx, bar)

            mtm = self._mark_to_market(bar)
            self.equity_curve.append({
                "date":        date,
                "equity":      self.capital + mtm,
                "cash":        self.capital,
                "open_trades": len(self.open_trades),
            })

            if bar_idx % 60 == 0:
                log.info(
                    f"  Bar {bar_idx:4d} | {date.date()} | "
                    f"Equity=${self.capital + mtm:,.2f} | "
                    f"Open={len(self.open_trades)}"
                )

        # ── Wrap up ────────────────────────────────────────────────────────────
        eq_df    = pd.DataFrame(self.equity_curve).set_index("date")
        equity   = eq_df["equity"].astype(float)
        trades   = self.recorder.to_df()

        metrics  = compute_all(equity, trades)
        print_scorecard(metrics)

        # Persist outputs
        os.makedirs("data/processed", exist_ok=True)
        eq_df.to_csv("data/processed/equity_curve.csv")
        if not trades.empty:
            trades.to_csv("data/processed/all_trades.csv", index=False)
        log.info("Equity curve → data/processed/equity_curve.csv")
        log.info("Trade ledger → data/processed/all_trades.csv")

        return {"equity": equity, "trades": trades, "metrics": metrics}

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _process_exits(self, date, bar_idx, bar):
        still_open = []
        for trade in self.open_trades:
            sym = trade.pos.pair
            row = bar.get(sym)
            if row is None:
                still_open.append(trade)
                continue

            reason = trade.check_exit(float(row["high"]), float(row["low"]))
            if reason:
                ep  = trade.pos.tp if reason == "tp" else trade.pos.sl
                # Apply exit slippage
                ep *= (1 - SLIPPAGE_PCT) if trade.pos.side == "buy" \
                      else (1 + SLIPPAGE_PCT)
                pnl = trade.realised_pnl(ep)
                self.capital += trade.pos.margin + pnl

                self.recorder.record({
                    "id":            trade.uid,
                    "pair":          sym,
                    "side":          trade.pos.side,
                    "entry":         round(trade.pos.entry, 5),
                    "exit":          round(ep, 5),
                    "lot":           trade.pos.lot,
                    "margin":        round(trade.pos.margin, 4),
                    "pnl":           round(pnl, 4),
                    "exit_reason":   reason,
                    "entry_date":    str(trade.entry_date.date()),
                    "exit_date":     str(date.date()),
                    "duration_bars": bar_idx - trade.bar_idx,
                    "leverage":      trade.pos.leverage,
                })
            else:
                still_open.append(trade)

        self.open_trades = still_open

    def _open_positions(self, date, bar_idx, bar):
        active  = {t.pos.pair for t in self.open_trades}
        signals = {sym: int(row["signal"])
                   for sym, row in bar.items()
                   if sym not in active}
        prices  = {sym: float(row["close"]) for sym, row in bar.items()}

        ranked = rank_signals(signals, bar)
        if not ranked:
            return

        slots     = MAX_OPEN_POSITIONS - len(self.open_trades)
        positions = build_portfolio(ranked[:slots], prices, self.capital)

        for pos in positions:
            if pos.margin > self.capital * 0.95:
                log.warning(f"  Insufficient margin for {pos.pair} — skipped")
                continue
            # Entry slippage
            pos.entry *= (1 + SLIPPAGE_PCT) if pos.side == "buy" \
                         else (1 - SLIPPAGE_PCT)
            self.capital -= pos.margin
            self.open_trades.append(OpenTrade(pos, bar_idx, date))
            log.debug(f"  OPEN  {position_summary(pos)}")

    def _mark_to_market(self, bar) -> float:
        mtm = 0.0
        for trade in self.open_trades:
            row = bar.get(trade.pos.pair)
            if row is None:
                continue
            mid = float(row["close"])
            if trade.pos.side == "buy":
                mtm += buy_pnl_lot(trade.pos.lot, mid,
                                    trade.pos.entry, trade.pos.gamma)
            else:
                mtm += sell_pnl_lot(trade.pos.lot, mid,
                                     trade.pos.entry, trade.pos.gamma)
        return mtm

    def _check_drawdown(self) -> bool:
        if self.capital > self.peak_capital:
            self.peak_capital = self.capital
        dd = (self.peak_capital - self.capital) / self.peak_capital
        if dd > MAX_DRAWDOWN_LIMIT:
            log.error(
                f"DRAWDOWN LIMIT BREACHED: {dd*100:.1f}% "
                f"(limit {MAX_DRAWDOWN_LIMIT*100:.0f}%) — halting."
            )
            return False
        return True
