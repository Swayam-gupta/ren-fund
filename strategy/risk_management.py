# =============================================================================
#  strategy/risk_management.py
#
#  Direct implementation of:
#    Justiniano, G. (2026). "Mathematics for Risk Management in the Forex Market"
#
#  Equations implemented
#  ─────────────────────
#  Eq.  3  Pc = C0 * (1 + r/L)          → Buy  TP / SL price
#  Eq.  4  Pv = C0 * (1 - r/L)          → Sell TP / SL price
#  Eq.  9  m  = s*γ*C0 / L              → Margin from lot size
#  Eq. 11  m  = R * M                   → Risk amount from account %
#  Eq. 12  s  = L*m / (γ*C0)            → Lot size from risk amount
#  Eq. 18  Gc = s*γ*(Pc - C0)           → Buy  P&L (lot-based)
#  Eq. 21  Gc = L*m*(Pc/C0 - 1)         → Buy  P&L (margin-based)
#  Eq. 22  Gv = L*m*(1 - Pv/C0)         → Sell P&L (margin-based)
#  Eq. 23  Gv = s*γ*(C0 - Pv)           → Sell P&L (lot-based)
#  Eq. 36  Pc = [γΣ(s_i C_i)+G] / γΣs_i → Global TP/SL — multiple buys
#  Eq. 46  Pv = [γΣ(s_i C_i)-G] / γΣs_i → Global TP/SL — multiple sells
#  Eq. 54  Pg = [γ(ΣscCc-ΣsvCv)+G] /    → Global TP/SL — mixed portfolio
#               [γ(Σsc-Σsv)]
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
import math

from config.settings import (
    STANDARD_LOT, DEFAULT_LEVERAGE,
    RISK_PER_TRADE_PCT, DEFAULT_TP_PCT, DEFAULT_SL_PCT,
    MIN_LOT_SIZE, MAX_LOT_SIZE,
)


# ── Position data model ────────────────────────────────────────────────────────

@dataclass
class Position:
    pair:     str
    side:     str       # 'buy' | 'sell'
    lot:      float     # s — lot size
    entry:    float     # C0 — entry price
    tp:       float = 0.0
    sl:       float = 0.0
    margin:   float = 0.0
    leverage: int   = DEFAULT_LEVERAGE
    gamma:    int   = STANDARD_LOT

    def __post_init__(self):
        if self.margin == 0.0:
            self.margin = compute_margin(self.lot, self.entry,
                                         self.leverage, self.gamma)


# ── Scalar formulae ────────────────────────────────────────────────────────────

def buy_price(C0: float, r: float, L: int = DEFAULT_LEVERAGE) -> float:
    """Eq. 3 — Final price for a BUY position.
    r > 0 → take-profit  |  r < 0 → stop-loss
    """
    return C0 * (1.0 + r / L)


def sell_price(C0: float, r: float, L: int = DEFAULT_LEVERAGE) -> float:
    """Eq. 4 — Final price for a SELL position.
    r > 0 → take-profit  |  r < 0 → stop-loss
    """
    return C0 * (1.0 - r / L)


def compute_margin(
    s:     float,
    C0:    float,
    L:     int = DEFAULT_LEVERAGE,
    gamma: int = STANDARD_LOT,
) -> float:
    """Eq. 9 — Margin required to open a position.  m = s*γ*C0 / L
    """
    return (s * gamma * C0) / L


def risk_amount(M: float, R: float = RISK_PER_TRADE_PCT) -> float:
    """Eq. 11 — Dollar risk per trade.  m = R * M
    """
    return R * M


def compute_lot_size(
    m:             float,
    C0:            float,
    L:             int   = DEFAULT_LEVERAGE,
    gamma:         int   = STANDARD_LOT,
    round_to_min:  bool  = True,
) -> float:
    """Eq. 12 — Lot size from risk amount.  s = L*m / (γ*C0)
    """
    s = (L * m) / (gamma * C0)
    if round_to_min:
        s = round(s / MIN_LOT_SIZE) * MIN_LOT_SIZE
        s = max(MIN_LOT_SIZE, min(s, MAX_LOT_SIZE))
    return round(s, 2)


def buy_pnl_lot(
    s:     float,
    Pc:    float,
    C0:    float,
    gamma: int = STANDARD_LOT,
) -> float:
    """Eq. 18 — Buy P&L using lot size.  Gc = s*γ*(Pc - C0)
    """
    return s * gamma * (Pc - C0)


def sell_pnl_lot(
    s:     float,
    Pv:    float,
    C0:    float,
    gamma: int = STANDARD_LOT,
) -> float:
    """Eq. 23 — Sell P&L using lot size.  Gv = s*γ*(C0 - Pv)
    """
    return s * gamma * (C0 - Pv)


def buy_pnl_margin(
    m:  float,
    Pc: float,
    C0: float,
    L:  int = DEFAULT_LEVERAGE,
) -> float:
    """Eq. 21 — Buy P&L using margin.  Gc = L*m*(Pc/C0 - 1)
    """
    return L * m * (Pc / C0 - 1.0)


def sell_pnl_margin(
    m:  float,
    Pv: float,
    C0: float,
    L:  int = DEFAULT_LEVERAGE,
) -> float:
    """Eq. 22 — Sell P&L using margin.  Gv = L*m*(1 - Pv/C0)
    """
    return L * m * (1.0 - Pv / C0)


# ── Multi-position global TP / SL (Justiniano 2026, §5-7) ─────────────────────

def global_price_buys(
    positions:  List[Position],
    target_pnl: float,
    gamma:      int = STANDARD_LOT,
) -> float:
    """Eq. 36 — Single target price for N buy positions.
              γ·Σ(s_i · C_i) + G
    Pc = ─────────────────────────
                  γ · Σ s_i
    """
    num = gamma * sum(p.lot * p.entry for p in positions) + target_pnl
    den = gamma * sum(p.lot           for p in positions)
    if den == 0:
        raise ZeroDivisionError("Sum of buy lots is zero.")
    return num / den


def global_price_sells(
    positions:  List[Position],
    target_pnl: float,
    gamma:      int = STANDARD_LOT,
) -> float:
    """Eq. 46 — Single target price for N sell positions.
              γ·Σ(s_i · C_i) - G
    Pv = ─────────────────────────
                  γ · Σ s_i
    """
    num = gamma * sum(p.lot * p.entry for p in positions) - target_pnl
    den = gamma * sum(p.lot           for p in positions)
    if den == 0:
        raise ZeroDivisionError("Sum of sell lots is zero.")
    return num / den


def global_price_mixed(
    buys:       List[Position],
    sells:      List[Position],
    target_pnl: float,
    gamma:      int = STANDARD_LOT,
) -> float:
    """Eq. 54 — Single target price for mixed buy + sell portfolio.
              γ·(Σ sc·Cc  -  Σ sv·Cv) + G
    Pg = ────────────────────────────────────
                   γ·(Σ sc  -  Σ sv)
    """
    sum_sc_Cc = sum(p.lot * p.entry for p in buys)
    sum_sv_Cv = sum(p.lot * p.entry for p in sells)
    sum_sc    = sum(p.lot           for p in buys)
    sum_sv    = sum(p.lot           for p in sells)

    num = gamma * (sum_sc_Cc - sum_sv_Cv) + target_pnl
    den = gamma * (sum_sc    - sum_sv)
    if den == 0:
        raise ZeroDivisionError(
            "Net lot balance is zero (perfectly hedged). "
            "Cannot compute a single target price."
        )
    return num / den


# ── High-level factory ─────────────────────────────────────────────────────────

def create_position(
    pair:      str,
    side:      str,
    entry:     float,
    account:   float,
    leverage:  int   = DEFAULT_LEVERAGE,
    gamma:     int   = STANDARD_LOT,
    risk_pct:  float = RISK_PER_TRADE_PCT,
    tp_pct:    float = DEFAULT_TP_PCT,
    sl_pct:    float = DEFAULT_SL_PCT,
) -> Position:
    """
    Full position factory:
      1. Compute risk amount  (Eq. 11)
      2. Derive lot size      (Eq. 12)
      3. Calculate margin     (Eq.  9)
      4. Set TP and SL prices (Eq. 3 / 4)
    """
    m     = risk_amount(account, risk_pct)           # Eq. 11
    s     = compute_lot_size(m, entry, leverage, gamma)  # Eq. 12
    mrg   = compute_margin(s, entry, leverage, gamma)    # Eq.  9

    if side == "buy":
        tp = buy_price(entry,  tp_pct, leverage)     # Eq. 3  r > 0
        sl = buy_price(entry, -sl_pct, leverage)     # Eq. 3  r < 0
    elif side == "sell":
        tp = sell_price(entry,  tp_pct, leverage)    # Eq. 4  r > 0
        sl = sell_price(entry, -sl_pct, leverage)    # Eq. 4  r < 0
    else:
        raise ValueError(f"side must be 'buy' or 'sell', got '{side}'")

    return Position(
        pair=pair, side=side, lot=s, entry=entry,
        tp=tp, sl=sl, margin=mrg,
        leverage=leverage, gamma=gamma,
    )


def position_summary(pos: Position) -> str:
    return (
        f"[{pos.pair}] {pos.side.upper():4s} | "
        f"Entry={pos.entry:.5f}  TP={pos.tp:.5f}  SL={pos.sl:.5f} | "
        f"Lot={pos.lot}  Margin=${pos.margin:.2f}"
    )
