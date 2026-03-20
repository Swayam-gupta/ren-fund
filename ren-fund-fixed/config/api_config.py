# =============================================================================
#  config/api_config.py
#  API credentials and endpoint configuration
# =============================================================================

# ── Alpha Vantage ─────────────────────────────────────────────────────────────
ALPHA_VANTAGE_API_KEY  = "HQ7YBLSP7DBCI0R7"
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# Free tier limits: 25 API calls / day  |  5 calls / minute
API_CALL_DELAY_SECONDS = 13    # ~4.6 calls / min  → safe under 5/min limit
API_MAX_RETRIES        = 3

# Cache settings
CACHE_DIR       = "data/cache"
CACHE_TTL_HOURS = 24           # re-fetch data older than this many hours
