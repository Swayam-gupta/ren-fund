# =============================================================================
#  execution/order_manager.py
#  In-memory order book with JSONL trade ledger
# =============================================================================

import os
import json
import uuid
from datetime import datetime
from typing import Dict, List
import pandas as pd

from config.settings import TRADE_LOG_DIR
from utils.logger import get_logger

log = get_logger("order_manager")


class OrderManager:
    def __init__(self):
        os.makedirs(TRADE_LOG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path          = os.path.join(TRADE_LOG_DIR, f"live_{ts}.jsonl")
        self.open_orders   : Dict[str, dict] = {}
        self.closed_orders : List[dict]      = []
        self.realised_pnl  : float           = 0.0
        log.info(f"Order ledger → {self.path}")

    def submit(
        self, pair, side, lot, price, tp, sl, margin,
    ) -> str:
        oid   = str(uuid.uuid4())[:8]
        order = dict(
            id=oid, pair=pair, side=side, lot=lot,
            entry=price, tp=tp, sl=sl, margin=margin,
            open_time=datetime.utcnow().isoformat(), status="open",
        )
        self.open_orders[oid] = order
        self._write(order)
        log.info(
            f"  OPEN  [{oid}] {pair} {side.upper():4s} "
            f"lot={lot} @ {price:.5f}  TP={tp:.5f}  SL={sl:.5f}"
        )
        return oid

    def close(self, oid: str, exit_price: float, pnl: float, reason: str):
        if oid not in self.open_orders:
            return
        order = self.open_orders.pop(oid)
        order.update(
            exit=exit_price, pnl=pnl,
            exit_reason=reason,
            close_time=datetime.utcnow().isoformat(),
            status="closed",
        )
        self.closed_orders.append(order)
        self.realised_pnl += pnl
        self._write(order)
        emoji = "🟢" if pnl >= 0 else "🔴"
        log.info(
            f"  {emoji} CLOSE [{oid}] {order['pair']} @ {exit_price:.5f} "
            f"P&L=${pnl:+.4f}  [{reason.upper()}]  "
            f"Cumulative P&L=${self.realised_pnl:+.4f}"
        )

    def open_pairs(self) -> List[str]:
        return [o["pair"] for o in self.open_orders.values()]

    def summary(self) -> dict:
        return dict(
            open=len(self.open_orders),
            closed=len(self.closed_orders),
            realised_pnl=round(self.realised_pnl, 4),
        )

    def to_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.closed_orders) if self.closed_orders \
               else pd.DataFrame()

    def _write(self, record: dict):
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
