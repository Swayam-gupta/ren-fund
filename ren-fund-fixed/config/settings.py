# =============================================================================
#  config/settings.py
#  All strategy, risk, and operational parameters — edit here only
# =============================================================================

# ── Forex Universe ─────────────────────────────────────────────────────────────
FOREX_PAIRS = [
    ("EUR", "USD"),   # EURUSD
    ("GBP", "USD"),   # GBPUSD
    ("USD", "JPY"),   # USDJPY
    ("AUD", "USD"),   # AUDUSD
    ("USD", "CAD"),   # USDCAD
]

# ── Market Conventions ─────────────────────────────────────────────────────────
STANDARD_LOT     = 100_000     # γ  — 1 standard lot = 100,000 base units
DEFAULT_LEVERAGE = 500         # L  — leverage ratio  1:500
MIN_LOT_SIZE     = 0.01        # minimum micro lot
MAX_LOT_SIZE     = 10.0        # position cap per trade

# ── Risk Management (Justiniano 2026, Eq. 11) ──────────────────────────────────
RISK_PER_TRADE_PCT   = 0.02    # R  — risk 2% of total equity per trade
INITIAL_CAPITAL      = 10_000  # starting portfolio value (USD)
MAX_OPEN_POSITIONS   = 5       # maximum concurrent positions
MAX_DRAWDOWN_LIMIT   = 0.20    # hard stop if drawdown exceeds 20%

# ── TP / SL Configuration (Justiniano 2026, Eq. 3 & 4) ────────────────────────
DEFAULT_TP_PCT = 1.5           # r_tp — take-profit as % lever-adjusted
DEFAULT_SL_PCT = 0.75          # r_sl — stop-loss  as % lever-adjusted

# ── Technical Indicator Parameters ────────────────────────────────────────────
RSI_PERIOD       = 14
RSI_OVERSOLD     = 35
RSI_OVERBOUGHT   = 65
MACD_FAST        = 12
MACD_SLOW        = 26
MACD_SIGNAL      = 9
BB_PERIOD        = 20
BB_STD           = 2.0
ATR_PERIOD       = 14
MOMENTUM_LOOKBACK= 10

# ── Backtest Settings ──────────────────────────────────────────────────────────
BACKTEST_START   = "2023-01-01"
BACKTEST_END     = "2024-12-31"
COMMISSION_PCT   = 0.0002      # 2 bps round-trip spread
SLIPPAGE_PCT     = 0.0001      # 1 bp fill slippage model

# ── Performance Target ─────────────────────────────────────────────────────────
TARGET_CAGR      = 0.30        # 30% annual growth rate

# ── Logging ────────────────────────────────────────────────────────────────────
TRADE_LOG_DIR    = "logs/trades"
SYSTEM_LOG_DIR   = "logs/system"
REPORTS_DIR      = "reports/charts"
