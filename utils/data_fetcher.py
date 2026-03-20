# =============================================================================
#  utils/data_fetcher.py
#  Alpha Vantage REST wrapper — rate-limit safe, pickle-cached, retry-enabled
# =============================================================================

import os
import time
import pickle
import hashlib
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple

from config.api_config import (
    ALPHA_VANTAGE_API_KEY,
    ALPHA_VANTAGE_BASE_URL,
    API_CALL_DELAY_SECONDS,
    API_MAX_RETRIES,
    CACHE_DIR,
    CACHE_TTL_HOURS,
)
from utils.logger import get_logger

log = get_logger("data_fetcher")


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _cache_key_path(key: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, hashlib.md5(key.encode()).hexdigest() + ".pkl")


def _load_cache(key: str) -> Optional[pd.DataFrame]:
    path = _cache_key_path(key)
    if not os.path.exists(path):
        return None
    age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(path))
    if age > timedelta(hours=CACHE_TTL_HOURS):
        log.debug(f"Cache stale — {path}")
        return None
    with open(path, "rb") as f:
        data = pickle.load(f)
    log.debug(f"Cache HIT  — {path}")
    return data


def _save_cache(key: str, df: pd.DataFrame) -> None:
    path = _cache_key_path(key)
    with open(path, "wb") as f:
        pickle.dump(df, f)
    log.debug(f"Cache SAVE — {path}")


# ── Raw HTTP request with retry ────────────────────────────────────────────────

def _get(params: dict) -> dict:
    params["apikey"] = ALPHA_VANTAGE_API_KEY
    for attempt in range(1, API_MAX_RETRIES + 1):
        try:
            resp = requests.get(ALPHA_VANTAGE_BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # Alpha Vantage rate-limit message
            if "Note" in data or "Information" in data:
                msg = data.get("Note", data.get("Information", ""))
                log.warning(f"  API rate-limit signal (attempt {attempt}): {msg[:120]}")
                time.sleep(API_CALL_DELAY_SECONDS * 3)
                continue

            time.sleep(API_CALL_DELAY_SECONDS)   # polite pause
            return data

        except requests.RequestException as exc:
            log.error(f"  HTTP error attempt {attempt}/{API_MAX_RETRIES}: {exc}")
            time.sleep(5 * attempt)

    raise ConnectionError(
        "Alpha Vantage API unavailable after all retries. "
        "Check your internet connection and API key."
    )


# ── Public fetch functions ─────────────────────────────────────────────────────

def fetch_fx_daily(
    from_currency: str,
    to_currency:   str,
    outputsize:    str = "full",
    start_date:    Optional[str] = None,
    end_date:      Optional[str] = None,
) -> pd.DataFrame:
    """
    Fetch daily OHLCV for a forex pair.

    Returns
    -------
    pd.DataFrame  columns: open, high, low, close  |  index: DatetimeIndex
    """
    cache_key = f"FX_DAILY_{from_currency}_{to_currency}_{outputsize}"
    df = _load_cache(cache_key)

    if df is None:
        log.info(f"  Fetching FX_DAILY {from_currency}/{to_currency}  [{outputsize}] ...")
        raw = _get({
            "function":    "FX_DAILY",
            "from_symbol": from_currency,
            "to_symbol":   to_currency,
            "outputsize":  outputsize,
        })

        ts_key = "Time Series FX (Daily)"
        if ts_key not in raw:
            raise ValueError(
                f"Unexpected Alpha Vantage response — keys: {list(raw.keys())}\n"
                f"Full response: {str(raw)[:400]}"
            )

        df = (
            pd.DataFrame(raw[ts_key])
            .T
            .rename(columns={
                "1. open": "open", "2. high": "high",
                "3. low":  "low",  "4. close": "close",
            })
            .astype(float)
        )
        df.index = pd.to_datetime(df.index)
        df.index.name = "date"
        df.sort_index(inplace=True)

        # Save raw copy
        raw_path = os.path.join("data", "raw", f"{from_currency}{to_currency}_daily.csv")
        os.makedirs("data/raw", exist_ok=True)
        df.to_csv(raw_path)

        _save_cache(cache_key, df)

    if start_date:
        df = df[df.index >= start_date]
    if end_date:
        df = df[df.index <= end_date]

    log.info(
        f"  {from_currency}{to_currency}: {len(df)} bars  "
        f"[{df.index[0].date()} → {df.index[-1].date()}]"
    )
    return df


def fetch_fx_quote(from_currency: str, to_currency: str) -> dict:
    """Real-time exchange rate snapshot."""
    log.info(f"  Live quote {from_currency}/{to_currency} ...")
    raw  = _get({
        "function":      "CURRENCY_EXCHANGE_RATE",
        "from_currency": from_currency,
        "to_currency":   to_currency,
    })
    info = raw.get("Realtime Currency Exchange Rate", {})
    return {
        "pair":      f"{from_currency}{to_currency}",
        "rate":      float(info.get("5. Exchange Rate", 0)),
        "bid":       float(info.get("8. Bid Price", 0)),
        "ask":       float(info.get("9. Ask Price", 0)),
        "timestamp": info.get("6. Last Refreshed", ""),
    }


def load_all_pairs(
    pairs:      list,
    start_date: Optional[str] = None,
    end_date:   Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """
    Load daily OHLCV for every (from_ccy, to_ccy) pair in `pairs`.
    Returns { 'EURUSD': pd.DataFrame, ... }
    """
    universe = {}
    for from_ccy, to_ccy in pairs:
        sym = f"{from_ccy}{to_ccy}"
        try:
            universe[sym] = fetch_fx_daily(
                from_ccy, to_ccy,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            log.error(f"  Could not load {sym}: {exc}")
    return universe
