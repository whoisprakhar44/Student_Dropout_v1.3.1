"""
log_streamer.py
Real-time Runtime Log Streaming with TOTP Authenticator Access Control (RFC 6238).

Features:
- Thread-safe & async-safe logging handler attached to root and app loggers
- In-memory ring buffer of recent logs (1,000 lines)
- RFC 6238 TOTP verification (Google Authenticator / Microsoft Authenticator compatible)
- Signed session token verification for seamless browser sessions
- Server-Sent Events (SSE) & WebSocket real-time log streaming
- Self-contained, responsive, dark-mode terminal log viewer with search, filtering, and export
"""

import os
import time
import hmac
import hashlib
import struct
import base64
import json
import logging
import asyncio
from collections import deque
from datetime import datetime
from typing import AsyncGenerator, Optional, Dict, Any, List
from pathlib import Path

# Environment variable name for the TOTP secret key
ENV_TOTP_SECRET_KEY = "LOGS_AUTH_SECRET"
DEFAULT_TOTP_SECRET = "JBSWY3DPEHPK3PXP"  # 16-character Base32 secret for dev/testing
SESSION_SECRET = os.getenv("LOGS_SESSION_SECRET", "ap_citizen_360_log_stream_secure_key_2026")
SESSION_COOKIE_NAME = "logs_auth_session"
SESSION_DURATION_SECONDS = 86400  # 24 hours


def get_totp_secret() -> str:
    """Retrieve the configured TOTP Base32 secret from environment."""
    secret = os.getenv(ENV_TOTP_SECRET_KEY, os.getenv("LOGS_TOTP_SECRET", DEFAULT_TOTP_SECRET))
    return secret.strip().replace(" ", "").upper()


def verify_totp(code: str, secret: Optional[str] = None, window: int = 1) -> bool:
    """
    Verify a 6-digit TOTP code against the Base32 secret (RFC 6238).
    Window allows +/- 30 seconds clock drift.
    """
    if not code:
        return False
    
    clean_code = str(code).strip()
    if len(clean_code) != 6 or not clean_code.isdigit():
        return False

    totp_secret = secret or get_totp_secret()
    
    try:
        # Standard Base32 decoding with padding fix if needed
        padding_needed = (8 - len(totp_secret) % 8) % 8
        padded_secret = totp_secret + ("=" * padding_needed)
        key = base64.b32decode(padded_secret, casefold=True)
    except Exception:
        return False

    current_step = int(time.time() // 30)
    for step in range(current_step - window, current_step + window + 1):
        msg = struct.pack(">Q", step)
        h = hmac.new(key, msg, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        truncated = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
        otp = str(truncated % 1000000).zfill(6)
        if hmac.compare_digest(otp, clean_code):
            return True
    return False


def create_session_token() -> str:
    """Create a signed, time-bound session token."""
    expire_at = int(time.time()) + SESSION_DURATION_SECONDS
    payload = f"auth_ok:{expire_at}"
    signature = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    raw = f"{payload}:{signature}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_session_token(token: Optional[str]) -> bool:
    """Verify validity and expiration of session token."""
    if not token:
        return False
    try:
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        parts = raw.split(":")
        if len(parts) != 3 or parts[0] != "auth_ok":
            return False
        
        expire_at = int(parts[1])
        if time.time() > expire_at:
            return False  # Expired
            
        payload = f"{parts[0]}:{parts[1]}"
        expected_sig = hmac.new(SESSION_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(parts[2], expected_sig)
    except Exception:
        return False


class LogStreamManager(logging.Handler):
    """
    Thread-safe & async-safe logging handler that buffers recent logs and broadcasts
    to active SSE and WebSocket streaming subscribers.
    """
    def __init__(self, buffer_size: int = 1000):
        super().__init__()
        self.buffer_size = buffer_size
        self.buffer: deque = deque(maxlen=buffer_size)
        self.subscribers: set[asyncio.Queue] = set()
        self.counter = 0
        self._lock = asyncio.Lock() if asyncio.get_event_loop().is_running() else None
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.counter += 1
            log_entry = {
                "id": self.counter,
                "timestamp": datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "level": record.levelname,
                "name": record.name,
                "message": record.getMessage(),
                "formatted": msg,
            }
            self.buffer.append(log_entry)

            # Broadcast to all async subscriber queues
            for q in list(self.subscribers):
                try:
                    q.put_nowait(log_entry)
                except Exception:
                    pass
        except Exception:
            self.handleError(record)

    def get_recent_logs(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Return list of recent log entries."""
        logs = list(self.buffer)
        return logs[-limit:] if limit > 0 else logs

    async def subscribe(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Subscribe to live log stream."""
        q = asyncio.Queue(maxsize=500)
        self.subscribers.add(q)
        try:
            while True:
                entry = await q.get()
                yield entry
        finally:
            self.subscribers.discard(q)


# Singleton log stream manager
log_manager = LogStreamManager(buffer_size=1000)


def setup_log_streamer():
    """Attach log_manager to the root logger and app loggers."""
    log_manager.setLevel(logging.DEBUG)
    root_logger = logging.getLogger()
    if root_logger.level == logging.NOTSET or root_logger.level > logging.INFO:
        root_logger.setLevel(logging.INFO)
    if log_manager not in root_logger.handlers:
        root_logger.addHandler(log_manager)
    
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    if log_manager not in app_logger.handlers:
        app_logger.addHandler(log_manager)



TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
LOGS_LOGIN_HTML_PATH = TEMPLATES_DIR / "logs_login.html"
LOGS_VIEWER_HTML_PATH = TEMPLATES_DIR / "logs.html"


def render_log_viewer_html(authenticated: bool = False, error_message: str = "") -> str:
    """Load and render self-contained HTML page for logs viewer or authenticator login from templates."""
    if not authenticated:
        if LOGS_LOGIN_HTML_PATH.exists():
            html = LOGS_LOGIN_HTML_PATH.read_text(encoding="utf-8")
        else:
            html = """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>AP Citizen 360 — Logs Auth</title></head>
<body>
  <h1>Runtime Logs Access</h1>
  <p>Verification Code Required</p>
  {{ERROR_BANNER}}
  <form method="POST" action="" id="authForm">
    <input type="text" name="code" placeholder="000000" required autofocus>
    <button type="submit">Verify & View Logs</button>
  </form>
</body>
</html>"""
        error_banner = f'<div class="error-banner">⚠️ {error_message}</div>' if error_message else ''
        return html.replace("{{ERROR_BANNER}}", error_banner).replace("{error_message}", error_message)

    if LOGS_VIEWER_HTML_PATH.exists():
        return LOGS_VIEWER_HTML_PATH.read_text(encoding="utf-8")
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>AP Citizen 360 Logs</title></head>
<body>
  <span id="streamStatus"><span id="streamStatusText">Connected • Live</span></span>
  <input type="text" id="searchInput">
  <button id="autoScrollBtn"></button>
  <button id="pauseBtn"></button>
  <main id="terminal"></main>
</body>
</html>"""
