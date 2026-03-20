# 🏦 Renaissance Quantitative Fund
### Forex Algorithmic Trading System
> **Target:** 30% Annual Growth Rate | **Strategy:** Multi-Factor Momentum + Justiniano (2026) Risk Framework
> **Data:** Alpha Vantage API | **Universe:** 5 Major Forex Pairs

---

## 📁 Project Structure

```
ren_fund/
│
├── config/
│   ├── __init__.py
│   ├── settings.py          ← Strategy params, risk limits, universe
│   └── api_config.py        ← Alpha Vantage API key
│
├── data/
│   ├── raw/                 ← Downloaded OHLCV CSV files
│   ├── processed/           ← Feature-engineered data + equity curves
│   └── cache/               ← Pickle cache (avoids redundant API calls)
│
├── strategy/
│   ├── __init__.py
│   ├── risk_management.py   ← Justiniano (2026) Eq. 3,4,9,11,12,18,21,22,36,46,54
│   ├── signals.py           ← RSI, MACD, Bollinger, ATR, Momentum, Z-Score
│   └── portfolio.py         ← Cross-sectional ranking & position sizing
│
├── backtest/
│   ├── __init__.py
│   ├── engine.py            ← Event-driven backtester (slippage + commissions)
│   └── metrics.py           ← Sharpe, Sortino, CAGR, MaxDD, Calmar, Win-Rate
│
├── execution/
│   ├── __init__.py
│   ├── live_trader.py       ← Real-time signal generation + paper trading
│   └── order_manager.py     ← Order book, fill tracking, P&L ledger
│
├── logs/
│   ├── trades/              ← Per-trade JSON logs (entry, exit, P&L, reason)
│   └── system/              ← Rotating system INFO/WARNING/ERROR logs
│
├── reports/
│   └── charts/              ← Auto-saved dashboard PNGs
│
├── utils/
│   ├── __init__.py
│   ├── logger.py            ← Coloured rotating log handler
│   └── data_fetcher.py      ← Alpha Vantage wrapper with cache + rate limiting
│
├── visualize/
│   ├── __init__.py
│   └── dashboard.py         ← 9-panel performance dashboard (run standalone)
│
├── research/                ← Drop research PDFs here
│   └── justiniano_2026.pdf  ← Primary risk framework paper
│
├── main.py                  ← ▶  BACKTEST entry point
├── live_main.py             ← ▶  FORWARD TEST / PAPER TRADE entry point
└── requirements.txt
```

---

## ⚙️ Setup (VS Code)

```bash
# 1. Create virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt
```

---

## 🔬 Run Backtest (Historical 2023–2024)

```bash
python main.py
```

- Pulls 2 years of daily OHLCV for all 5 pairs from Alpha Vantage
- Runs full event-driven backtest with slippage + commissions
- Logs every trade to `logs/trades/`
- Saves equity curve + trade ledger to `data/processed/`
- Renders 9-panel dashboard to `reports/charts/`

---

## 📡 Run Forward / Paper Test (Real-Time)

```bash
python live_main.py
```

- Fetches live quotes every 60 seconds
- Generates signals and manages paper positions
- Logs all orders to `logs/trades/`
- Renders live dashboard after session ends

---

## 📊 Visualise Results (Standalone)

```bash
python visualize/dashboard.py
```

Reads saved CSV outputs and renders the full dashboard.

---

## 🧮 Mathematical Framework (Justiniano 2026)

| Equation | Description |
|----------|-------------|
| Eq. 3  | Buy TP/SL price: `Pc = C0 * (1 + r/L)` |
| Eq. 4  | Sell TP/SL price: `Pv = C0 * (1 - r/L)` |
| Eq. 9  | Margin: `m = s * γ * C0 / L` |
| Eq. 11 | Risk amount: `m = R * M` |
| Eq. 12 | Lot size: `s = L * m / (γ * C0)` |
| Eq. 18 | Buy P&L: `Gc = s * γ * (Pc - C0)` |
| Eq. 21 | Leveraged buy P&L: `Gc = L*m*(Pc/C0 - 1)` |
| Eq. 22 | Leveraged sell P&L: `Gv = L*m*(1 - Pv/C0)` |
| Eq. 36 | Global TP for multiple buys |
| Eq. 46 | Global TP for multiple sells |
| Eq. 54 | Global TP for mixed portfolio |

---

## ⚠️ Disclaimer

This system is for educational and research purposes only.
It does not constitute financial advice. Forex trading involves substantial risk.
