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


def is_litellm_log(record: logging.LogRecord) -> bool:
    """
    Return True if the log record pertains to /litellm endpoints or LiteLLM proxy.
    Used to completely suppress litellm logs across all loggers, handlers, and streams.
    """
    try:
        msg = record.getMessage()
    except Exception:
        msg = str(getattr(record, "msg", ""))

    msg_lower = msg.lower()
    if "/litellm" in msg_lower or "litellm" in msg_lower:
        return True

    # Check record.args (e.g. Uvicorn access log tuple: client, method, path, http_ver, status)
    args = getattr(record, "args", None)
    if args:
        if isinstance(args, dict):
            for v in args.values():
                v_str = str(v).lower()
                if "/litellm" in v_str or "litellm" in v_str:
                    return True
        elif isinstance(args, (tuple, list)):
            for a in args:
                a_str = str(a).lower()
                if "/litellm" in a_str or "litellm" in a_str:
                    return True

    # Check logger name (e.g. httpx / httpcore calling LiteLLM backend)
    rec_name = getattr(record, "name", "").lower()
    if rec_name in ("httpx", "httpcore"):
        litellm_url = os.getenv("LITELLM_URL", "")
        if litellm_url and litellm_url.lower() in msg_lower:
            return True

    return False


class LiteLLMLogFilter(logging.Filter):
    """
    Global logging filter to completely suppress any logs related to /litellm endpoints,
    proxying, or LiteLLM calls across all loggers and handlers.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        return not is_litellm_log(record)


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
        self.addFilter(LiteLLMLogFilter())

    def emit(self, record: logging.LogRecord) -> None:
        if is_litellm_log(record):
            return
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
        """Return list of recent log entries, strictly excluding any litellm logs."""
        logs = [entry for entry in self.buffer if not self._is_litellm_entry(entry)]
        return logs[-limit:] if limit > 0 else logs

    @staticmethod
    def _is_litellm_entry(entry: Dict[str, Any]) -> bool:
        text = f"{entry.get('name', '')} {entry.get('message', '')} {entry.get('formatted', '')}".lower()
        return "/litellm" in text or "litellm" in text

    async def subscribe(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Subscribe to live log stream."""
        q = asyncio.Queue(maxsize=500)
        self.subscribers.add(q)
        try:
            while True:
                entry = await q.get()
                if not self._is_litellm_entry(entry):
                    yield entry
        finally:
            self.subscribers.discard(q)


# Singleton log stream manager
log_manager = LogStreamManager(buffer_size=1000)


def install_litellm_log_filter():
    """
    Apply LiteLLMLogFilter to all loggers and handlers to prevent
    any /litellm logs from appearing anywhere (console, terminal, files, or streams).
    """
    flt = LiteLLMLogFilter()

    # 1. Attach to singleton log manager
    log_manager.addFilter(flt)

    # 2. Attach to root logger and all its existing handlers (stdout/stderr)
    root_logger = logging.getLogger()
    root_logger.addFilter(flt)
    for h in root_logger.handlers:
        h.addFilter(flt)

    # 3. Attach to standard server and application loggers
    target_loggers = [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "app",
        "httpx",
        "httpcore",
        "fastapi",
        "starlette",
        "production_logger",
    ]
    for name in target_loggers:
        lg = logging.getLogger(name)
        lg.addFilter(flt)
        for h in lg.handlers:
            h.addFilter(flt)

    # 4. Mute verbose query-level httpx/httpcore access logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def setup_log_streamer():
    """Attach log_manager to root and app loggers and install LiteLLM log filter."""
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

    install_litellm_log_filter()



TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
LOGS_LOGIN_HTML_PATH = TEMPLATES_DIR / "logs_login.html"
LOGS_VIEWER_HTML_PATH = TEMPLATES_DIR / "logs.html"


def render_log_viewer_html(authenticated: bool = False, error_message: str = "", base_path: str = "") -> str:
    """Load and render self-contained HTML page for logs viewer or authenticator login from templates with subpath awareness."""
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
        html = html.replace("{{ERROR_BANNER}}", error_banner).replace("{error_message}", error_message)
    else:
        if LOGS_VIEWER_HTML_PATH.exists():
            html = LOGS_VIEWER_HTML_PATH.read_text(encoding="utf-8")
        else:
            html = """<!DOCTYPE html>
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

    html = html.replace("{{BASE_PATH}}", base_path)
    base_script = f"<script>window.__BASE_PATH__ = '{base_path}';</script>"
    if "<head>" in html:
        html = html.replace("<head>", f"<head>\n  {base_script}", 1)
    elif "<HEAD>" in html:
        html = html.replace("<HEAD>", f"<HEAD>\n  {base_script}", 1)
    elif "<body>" in html:
        html = html.replace("<body>", f"<body>\n  {base_script}", 1)
    else:
        html = base_script + "\n" + html

    return html

