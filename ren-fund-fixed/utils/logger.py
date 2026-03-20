# =============================================================================
#  utils/logger.py
#  Colour-coded console + rotating file logger
# =============================================================================

import logging
import logging.handlers
import os
import sys
from datetime import datetime

try:
    import colorlog
    _HAS_COLOR = True
except ImportError:
    _HAS_COLOR = False


def get_logger(name: str, log_dir: str = "logs/system", level: str = "INFO") -> logging.Logger:
    """
    Returns a named logger that writes to:
      - Console  : coloured, INFO+
      - File     : plain text, rotating 5 MB / 10 backups, DEBUG+
    """
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)

    if logger.handlers:          # already configured → reuse
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Rotating file handler ─────────────────────────────────────────────────
    log_file = os.path.join(log_dir, f"{name}_{datetime.now().strftime('%Y%m%d')}.log")
    fh = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=10, encoding="utf-8"
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    # ── Console handler ───────────────────────────────────────────────────────
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(getattr(logging, level.upper(), logging.INFO))

    if _HAS_COLOR:
        ch.setFormatter(colorlog.ColoredFormatter(
            fmt="%(log_color)s%(asctime)s | %(levelname)-8s%(reset)s"
                " | %(cyan)s%(name)s%(reset)s | %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                "DEBUG":    "white",
                "INFO":     "green",
                "WARNING":  "yellow",
                "ERROR":    "red",
                "CRITICAL": "bold_red",
            },
        ))
    else:
        ch.setFormatter(logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        ))

    logger.addHandler(ch)
    logger.propagate = False
    return logger
