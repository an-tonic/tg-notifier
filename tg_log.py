"""
tg_log.py — drop this file next to any script that needs Telegram notifications.

Usage:
    from tg_log import log_to_tg

    log_to_tg("⚠️ Capital limit exceeded — stopping script")
"""

import logging
import requests

_PORT = 12345
_URL = f"http://127.0.0.1:{_PORT}/notify"

log = logging.getLogger(__name__)


def log_to_tg(message: str, raise_on_failure: bool = False) -> bool:
    """
    Send a message to all Telegram subscribers.

    Returns True on success, False on failure.
    Never raises by default — a notification failure should not crash your script
    unless you explicitly pass raise_on_failure=True.
    """
    try:
        resp = requests.post(_URL, json={"message": message}, timeout=5)
        resp.raise_for_status()
        return True
    except Exception as e:
        log.warning(f"log_to_tg failed: {e}")
        if raise_on_failure:
            raise
        return False
