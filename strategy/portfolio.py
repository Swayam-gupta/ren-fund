# =============================================================================
#  strategy/portfolio.py
#  Cross-sectional signal ranking and portfolio construction
# =============================================================================

from __future__ import annotations
from typing import Dict, List, Tuple, Optional
import pandas as pd

from config.settings import (
    MAX_OPEN_POSITIONS, DEFAULT_LEVERAGE, STANDARD_LOT, RISK_PER_TRADE_PCT,
)
from strategy.risk_management import (
    create_position, Position, global_price_mixed,
    global_price_buys, global_price_sells,
)
from utils.logger import get_logger

log = get_logger("portfolio")


def rank_signals(
    signals:  Dict[str, int],
    features: Dict[str, pd.Series],
) -> List[Tuple[str, int, float]]:
    """
    Rank active signals by a composite strength score.
    Returns list of (pair, signal, score) sorted descending by score,
    capped at MAX_OPEN_POSITIONS entries.
    """
    scored = []
    for pair, sig in signals.items():
        if sig == 0:
            continue
        row = features.get(pair)
        if row is None:
            continue

        # Score = weighted combination of indicator magnitudes
        mom   = abs(float(row.get("momentum", 0)))
        hist  = abs(float(row.get("macd_hist", 0)))
        rsi   = float(row.get("rsi", 50))
        rsi_s = abs(rsi - 50) / 50.0        # 1.0 at extremes, 0 at neutral

        score = mom * 10.0 + hist * 1000.0 + rsi_s
        scored.append((pair, sig, score))

    scored.sort(key=lambda x: x[2], reverse=True)
    return scored[:MAX_OPEN_POSITIONS]


def build_portfolio(
    ranked:    List[Tuple[str, int, float]],
    prices:    Dict[str, float],
    account:   float,
    leverage:  int   = DEFAULT_LEVERAGE,
    gamma:     int   = STANDARD_LOT,
    risk_pct:  float = RISK_PER_TRADE_PCT,
) -> List[Position]:
    """
    Convert ranked signals → Position objects with full risk parameters.
    """
    positions = []
    for pair, sig, score in ranked:
        entry = prices.get(pair)
        if not entry or entry <= 0:
            log.warning(f"  No valid price for {pair} — skipped")
            continue
        side = "buy" if sig > 0 else "sell"
        try:
            pos = create_position(
                pair=pair, side=side, entry=entry,
                account=account, leverage=leverage,
                gamma=gamma, risk_pct=risk_pct,
            )
            positions.append(pos)
        except Exception as exc:
            log.error(f"  Could not create position {pair}: {exc}")
    return positions


def compute_global_target(
    positions:  List[Position],
    target_pnl: float,
) -> Optional[float]:
    """
    Compute the Justiniano global TP/SL price across a mixed portfolio.
    Uses Eq. 36, 46, or 54 depending on composition.
    """
    if not positions:
        return None
    buys  = [p for p in positions if p.side == "buy"]
    sells = [p for p in positions if p.side == "sell"]
    try:
        if buys and not sells:
            return global_price_buys(buys, target_pnl)
        elif sells and not buys:
            return global_price_sells(sells, target_pnl)
        else:
            return global_price_mixed(buys, sells, target_pnl)
    except (ZeroDivisionError, ValueError) as exc:
        log.warning(f"  Global target computation failed: {exc}")
        return None
