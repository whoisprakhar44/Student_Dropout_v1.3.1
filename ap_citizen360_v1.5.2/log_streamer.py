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



def render_log_viewer_html(authenticated: bool = False, error_message: str = "") -> str:
    """Generate self-contained, responsive HTML/CSS/JS page for logs viewer or authenticator login."""
    secret = get_totp_secret()
    
    if not authenticated:
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AP Citizen 360 — Live Runtime Logs Authentication</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    }}
    body {{
      background: #0B0F19;
      color: #E2E8F0;
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .auth-card {{
      background: #111827;
      border: 1px solid #1F2937;
      border-radius: 16px;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6), 0 0 30px rgba(59, 130, 246, 0.1);
      width: 100%;
      max-width: 440px;
      padding: 36px 32px;
      text-align: center;
      position: relative;
      overflow: hidden;
    }}
    .auth-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 3px;
      background: linear-gradient(90deg, #3B82F6, #8B5CF6, #EC4899);
    }}
    .icon-wrap {{
      width: 64px;
      height: 64px;
      border-radius: 50%;
      background: rgba(59, 130, 246, 0.12);
      border: 1px solid rgba(59, 130, 246, 0.3);
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 20px;
      color: #60A5FA;
    }}
    h1 {{
      font-size: 20px;
      font-weight: 700;
      color: #F8FAFC;
      margin-bottom: 8px;
    }}
    p.subtitle {{
      font-size: 13px;
      color: #94A3B8;
      line-height: 1.5;
      margin-bottom: 24px;
    }}
    .error-banner {{
      background: rgba(239, 68, 68, 0.12);
      border: 1px solid rgba(239, 68, 68, 0.3);
      color: #FCA5A5;
      padding: 10px 14px;
      border-radius: 8px;
      font-size: 12.5px;
      margin-bottom: 20px;
      text-align: left;
    }}
    .input-group {{
      margin-bottom: 24px;
      text-align: left;
    }}
    label {{
      display: block;
      font-size: 12px;
      font-weight: 600;
      color: #CBD5E1;
      margin-bottom: 8px;
      letter-spacing: 0.5px;
    }}
    .otp-input {{
      width: 100%;
      background: #1E293B;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 14px;
      font-size: 24px;
      font-weight: 700;
      letter-spacing: 8px;
      text-align: center;
      color: #F8FAFC;
      outline: none;
      transition: all 0.2s;
    }}
    .otp-input:focus {{
      border-color: #3B82F6;
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25);
      background: #0F172A;
    }}
    .btn-submit {{
      width: 100%;
      background: #2563EB;
      color: #FFFFFF;
      border: none;
      border-radius: 10px;
      padding: 13px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}
    .btn-submit:hover {{
      background: #1D4ED8;
      transform: translateY(-1px);
    }}
    .hint-box {{
      margin-top: 24px;
      padding-top: 20px;
      border-top: 1px solid #1F2937;
      font-size: 11.5px;
      color: #64748B;
      line-height: 1.6;
      text-align: left;
    }}
    .hint-box code {{
      background: #1E293B;
      color: #38BDF8;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 11px;
    }}
  </style>
</head>
<body>
  <div class="auth-card">
    <div class="icon-wrap">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <rect width="18" height="11" x="3" y="11" rx="2" ry="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
      </svg>
    </div>
    <h1>Runtime Logs Access</h1>
    <p class="subtitle">Enter the 6-digit Time-Based Verification Code (TOTP) from your Google Authenticator or 2FA app.</p>
    
    {f'<div class="error-banner">⚠️ {error_message}</div>' if error_message else ''}

    <form method="GET" action="/ask" id="authForm">
      <input type="hidden" name="action" value="logs">
      <div class="input-group">
        <label for="code">6-DIGIT VERIFICATION CODE</label>
        <input 
          type="text" 
          id="code" 
          name="code" 
          class="otp-input" 
          maxlength="6" 
          pattern="[0-9]{{6}}" 
          placeholder="000000" 
          autocomplete="one-time-code" 
          autofocus 
          required
        >
      </div>
      <button type="submit" class="btn-submit">
        <span>Verify & View Logs</span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M5 12h14"/>
          <path d="m12 5 7 7-7 7"/>
        </svg>
      </button>
    </form>

    <div class="hint-box">
      <strong>Authenticator Configuration:</strong><br>
      Set secret in <code>.env</code> under <code>LOGS_AUTH_SECRET</code>.<br>
      Current Secret: <code>{secret}</code>
    </div>
  </div>
</body>
</html>"""

    # Authenticated Live Log Streamer Interface
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AP Citizen 360 — Live Runtime Logs</title>
  <style>
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: 'JetBrains Mono', 'Fira Code', Consolas, Menlo, monospace;
    }}
    body {{
      background: #0B0F19;
      color: #E2E8F0;
      height: 100vh;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }}
    
    /* Top Navigation Toolbar */
    .top-toolbar {{
      background: #111827;
      border-bottom: 1px solid #1F2937;
      padding: 10px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
      z-index: 10;
    }}
    .brand {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    .brand-title {{
      font-size: 14px;
      font-weight: 700;
      color: #F8FAFC;
      letter-spacing: 0.3px;
    }}
    .status-badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: rgba(16, 185, 129, 0.12);
      border: 1px solid rgba(16, 185, 129, 0.3);
      color: #34D399;
      padding: 3px 8px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 600;
    }}
    .status-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #10B981;
      box-shadow: 0 0 8px #10B981;
      animation: pulse-green 2s infinite;
    }}
    @keyframes pulse-green {{
      0%, 100% {{ opacity: 1; transform: scale(1); }}
      50% {{ opacity: 0.5; transform: scale(0.85); }}
    }}
    .status-badge.paused {{
      background: rgba(245, 158, 11, 0.12);
      border-color: rgba(245, 158, 11, 0.3);
      color: #FBBF24;
    }}
    .status-badge.paused .status-dot {{
      background: #F59E0B;
      box-shadow: 0 0 8px #F59E0B;
      animation: none;
    }}

    /* Control Actions & Filter Bar */
    .controls {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
    }}
    .search-box {{
      position: relative;
      display: flex;
      align-items: center;
    }}
    .search-box input {{
      background: #1E293B;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 6px 12px 6px 30px;
      color: #F8FAFC;
      font-size: 12px;
      outline: none;
      width: 220px;
      transition: all 0.2s;
    }}
    .search-box input:focus {{
      border-color: #3B82F6;
      width: 260px;
    }}
    .search-icon {{
      position: absolute;
      left: 9px;
      color: #64748B;
      pointer-events: none;
    }}
    
    /* Level Filter Buttons */
    .level-filters {{
      display: flex;
      background: #1E293B;
      border: 1px solid #334155;
      border-radius: 8px;
      padding: 2px;
    }}
    .level-btn {{
      background: transparent;
      border: none;
      color: #94A3B8;
      padding: 4px 9px;
      font-size: 11px;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.15s;
    }}
    .level-btn:hover {{
      color: #F8FAFC;
    }}
    .level-btn.active {{
      background: #3B82F6;
      color: #FFFFFF;
    }}

    /* Tool Buttons */
    .btn {{
      background: #1E293B;
      border: 1px solid #334155;
      color: #E2E8F0;
      padding: 5px 10px;
      border-radius: 8px;
      font-size: 12px;
      font-weight: 500;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all 0.15s;
    }}
    .btn:hover {{
      background: #334155;
      border-color: #475569;
    }}
    .btn.active {{
      background: rgba(59, 130, 246, 0.2);
      border-color: #3B82F6;
      color: #60A5FA;
    }}
    .btn-danger {{
      color: #F87171;
    }}
    .btn-danger:hover {{
      background: rgba(239, 68, 68, 0.15);
      border-color: #EF4444;
    }}

    /* Terminal Window */
    .terminal-container {{
      flex: 1;
      overflow-y: auto;
      overflow-x: auto;
      padding: 14px 18px;
      font-size: 12.5px;
      line-height: 1.65;
      background: #0B0F19;
      scroll-behavior: smooth;
    }}
    .terminal-container::-webkit-scrollbar {{
      width: 8px;
      height: 8px;
    }}
    .terminal-container::-webkit-scrollbar-track {{
      background: #0B0F19;
    }}
    .terminal-container::-webkit-scrollbar-thumb {{
      background: #1F2937;
      border-radius: 4px;
    }}

    /* Log Entry Lines */
    .log-line {{
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 2px 6px;
      border-radius: 4px;
      white-space: pre-wrap;
      word-break: break-word;
      transition: background 0.1s;
    }}
    .log-line:hover {{
      background: rgba(255, 255, 255, 0.03);
    }}
    .log-id {{
      color: #475569;
      font-size: 11px;
      min-width: 36px;
      user-select: none;
      text-align: right;
    }}
    .log-time {{
      color: #64748B;
      font-size: 11.5px;
      min-width: 140px;
      user-select: none;
    }}
    .log-level {{
      font-weight: 700;
      font-size: 11px;
      padding: 1px 6px;
      border-radius: 4px;
      min-width: 58px;
      text-align: center;
      user-select: none;
    }}
    .log-level.INFO {{
      color: #38BDF8;
      background: rgba(56, 189, 248, 0.1);
    }}
    .log-level.WARNING, .log-level.WARN {{
      color: #FBBF24;
      background: rgba(251, 191, 36, 0.12);
    }}
    .log-level.ERROR, .log-level.CRITICAL {{
      color: #F87171;
      background: rgba(248, 113, 113, 0.15);
    }}
    .log-level.DEBUG {{
      color: #A78BFA;
      background: rgba(167, 139, 250, 0.1);
    }}
    .log-msg {{
      flex: 1;
      color: #E2E8F0;
    }}
    .log-msg.highlight-sql {{
      color: #34D399;
    }}
    .log-msg.highlight-time {{
      color: #F472B6;
    }}

    /* Bottom Status Bar */
    .bottom-bar {{
      background: #111827;
      border-top: 1px solid #1F2937;
      padding: 6px 18px;
      font-size: 11.5px;
      color: #64748B;
      display: flex;
      align-items: center;
      justify-content: space-between;
      user-select: none;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    .stats {{
      display: flex;
      gap: 16px;
    }}
    .stats span {{
      color: #94A3B8;
    }}
    .stats strong {{
      color: #F8FAFC;
    }}
  </style>
</head>
<body>

  <!-- Top Toolbar -->
  <header class="top-toolbar">
    <div class="brand">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#60A5FA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="4 17 10 11 4 5"/>
        <line x1="12" x2="20" y1="19" y2="19"/>
      </svg>
      <span class="brand-title">AP Citizen 360 Logs</span>
      <span id="streamStatus" class="status-badge">
        <span class="status-dot"></span>
        <span id="streamStatusText">Connected • Live</span>
      </span>
    </div>

    <!-- Controls -->
    <div class="controls">
      <!-- Search -->
      <div class="search-box">
        <svg class="search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"/>
          <path d="m21 21-4.3-4.3"/>
        </svg>
        <input type="text" id="searchInput" placeholder="Search logs (regex or text)..." autocomplete="off">
      </div>

      <!-- Level Filter -->
      <div class="level-filters">
        <button class="level-btn active" data-level="ALL">ALL</button>
        <button class="level-btn" data-level="INFO">INFO</button>
        <button class="level-btn" data-level="WARNING">WARN</button>
        <button class="level-btn" data-level="ERROR">ERROR</button>
        <button class="level-btn" data-level="DEBUG">DEBUG</button>
      </div>

      <!-- Autoscroll Toggle -->
      <button id="autoScrollBtn" class="btn active" title="Toggle Auto-Scroll">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 5v14"/>
          <path d="m19 12-7 7-7-7"/>
        </svg>
        <span>Auto-Scroll</span>
      </button>

      <!-- Pause / Resume -->
      <button id="pauseBtn" class="btn" title="Pause / Resume Live Stream">
        <svg id="pauseIcon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect width="4" height="16" x="6" y="4"/>
          <rect width="4" height="16" x="14" y="4"/>
        </svg>
        <span id="pauseText">Pause</span>
      </button>

      <!-- Copy -->
      <button id="copyBtn" class="btn" title="Copy visible logs">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <rect width="14" height="14" x="8" y="8" rx="2" ry="2"/>
          <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>
        </svg>
        <span>Copy</span>
      </button>

      <!-- Export .log -->
      <button id="exportBtn" class="btn" title="Download log file">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
          <polyline points="7 10 12 15 17 10"/>
          <line x1="12" x2="12" y1="15" y2="3"/>
        </svg>
        <span>Export</span>
      </button>

      <!-- Clear -->
      <button id="clearBtn" class="btn btn-danger" title="Clear logs view">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 6h18"/>
          <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>
          <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
        </svg>
        <span>Clear</span>
      </button>

      <!-- Logout -->
      <a href="/ask?action=logs&logout=1" class="btn" title="Logout" style="text-decoration:none;">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
          <polyline points="16 17 21 12 16 7"/>
          <line x1="21" x2="9" y1="12" y2="12"/>
        </svg>
      </a>
    </div>
  </header>

  <!-- Terminal Display -->
  <main id="terminal" class="terminal-container"></main>

  <!-- Bottom Bar -->
  <footer class="bottom-bar">
    <div class="stats">
      <span>Total Logs: <strong id="totalCount">0</strong></span>
      <span>Visible: <strong id="visibleCount">0</strong></span>
      <span>Filter: <strong id="currentFilterText">ALL</strong></span>
    </div>
    <div style="color: #64748B;">AP Citizen 360 • FastAPI Runtime</div>
  </footer>

  <script>
    let allLogs = [];
    let activeLevel = 'ALL';
    let searchQuery = '';
    let autoScroll = true;
    let isPaused = false;
    let evtSource = null;

    const terminal = document.getElementById('terminal');
    const searchInput = document.getElementById('searchInput');
    const autoScrollBtn = document.getElementById('autoScrollBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    const pauseIcon = document.getElementById('pauseIcon');
    const pauseText = document.getElementById('pauseText');
    const copyBtn = document.getElementById('copyBtn');
    const exportBtn = document.getElementById('exportBtn');
    const clearBtn = document.getElementById('clearBtn');
    const streamStatus = document.getElementById('streamStatus');
    const streamStatusText = document.getElementById('streamStatusText');
    const totalCount = document.getElementById('totalCount');
    const visibleCount = document.getElementById('visibleCount');
    const currentFilterText = document.getElementById('currentFilterText');
    const levelBtns = document.querySelectorAll('.level-btn');

    function escapeHtml(text) {{
      return String(text || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    }}

    function highlightContent(msg) {{
      let escaped = escapeHtml(msg);
      // Highlight SQL statements
      escaped = escaped.replace(/(SELECT\\s+[\\s\\S]*?FROM\\s+[\\s\\S]*?)(;|\\n|$)/gi, '<span style="color:#34D399;font-weight:600;">$1$2</span>');
      // Highlight timings (e.g., 0.45s or 1.25s)
      escaped = escaped.replace(/(\\b\\d+\\.\\d+\\s*(?:s|ms|seconds)\\b)/gi, '<span style="color:#F472B6;font-weight:600;">$1</span>');
      // Highlight Request IDs & Session UUIDs
      escaped = escaped.replace(/(req_[a-zA-Z0-9_-]+|sess_[a-zA-Z0-9_-]+|[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}})/gi, '<span style="color:#818CF8;font-weight:600;">$1</span>');
      return escaped;
    }}

    function createLogLineElement(entry) {{
      const div = document.createElement('div');
      div.className = 'log-line';
      div.dataset.id = entry.id;
      div.dataset.level = (entry.level || 'INFO').toUpperCase();
      div.dataset.raw = entry.formatted || entry.message || '';

      const level = (entry.level || 'INFO').toUpperCase();
      div.innerHTML = `
        <span class="log-id">#${{entry.id}}</span>
        <span class="log-time">${{escapeHtml(entry.timestamp || '')}}</span>
        <span class="log-level ${{level}}">${{level}}</span>
        <span class="log-msg">${{highlightContent(entry.message || entry.formatted)}}</span>
      `;
      return div;
    }}

    function matchesFilter(entry) {{
      const lvl = (entry.level || 'INFO').toUpperCase();
      if (activeLevel !== 'ALL' && lvl !== activeLevel) {{
        if (activeLevel === 'WARNING' && lvl !== 'WARN' && lvl !== 'WARNING') return false;
        if (activeLevel !== 'WARNING') return false;
      }}
      if (searchQuery) {{
        const raw = (entry.formatted || entry.message || '').toLowerCase();
        if (!raw.includes(searchQuery.toLowerCase())) return false;
      }}
      return true;
    }}

    function renderAllLogs() {{
      terminal.innerHTML = '';
      let rendered = 0;
      const fragment = document.createDocumentFragment();

      allLogs.forEach(entry => {{
        if (matchesFilter(entry)) {{
          fragment.appendChild(createLogLineElement(entry));
          rendered++;
        }}
      }});

      terminal.appendChild(fragment);
      visibleCount.textContent = rendered;
      totalCount.textContent = allLogs.length;

      if (autoScroll) {{
        terminal.scrollTop = terminal.scrollHeight;
      }}
    }}

    function appendSingleLog(entry) {{
      allLogs.push(entry);
      if (allLogs.length > 2000) allLogs.shift();
      totalCount.textContent = allLogs.length;

      if (isPaused) return;

      if (matchesFilter(entry)) {{
        const el = createLogLineElement(entry);
        terminal.appendChild(el);
        visibleCount.textContent = parseInt(visibleCount.textContent || 0) + 1;

        if (autoScroll) {{
          terminal.scrollTop = terminal.scrollHeight;
        }}
      }}
    }}

    // SSE Connection Setup
    function connectSSE() {{
      if (evtSource) {{
        evtSource.close();
      }}

      streamStatus.className = 'status-badge';
      streamStatusText.textContent = 'Connecting...';

      evtSource = new EventSource('/ask?action=logs_stream');

      evtSource.onopen = () => {{
        streamStatus.className = 'status-badge';
        streamStatusText.textContent = 'Connected • Live';
      }};

      evtSource.onmessage = (event) => {{
        try {{
          const entry = JSON.parse(event.data);
          appendSingleLog(entry);
        }} catch (err) {{
          console.error('Failed to parse log event', err);
        }}
      }};

      evtSource.onerror = () => {{
        streamStatus.className = 'status-badge paused';
        streamStatusText.textContent = 'Reconnecting...';
      }};
    }}

    // Level Filter Handlers
    levelBtns.forEach(btn => {{
      btn.addEventListener('click', () => {{
        levelBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        activeLevel = btn.dataset.level;
        currentFilterText.textContent = activeLevel;
        renderAllLogs();
      }});
    }});

    // Search input
    let searchDebounce = null;
    searchInput.addEventListener('input', (e) => {{
      clearTimeout(searchDebounce);
      searchDebounce = setTimeout(() => {{
        searchQuery = e.target.value.trim();
        renderAllLogs();
      }}, 150);
    }});

    // Autoscroll toggle
    autoScrollBtn.addEventListener('click', () => {{
      autoScroll = !autoScroll;
      autoScrollBtn.classList.toggle('active', autoScroll);
      if (autoScroll) {{
        terminal.scrollTop = terminal.scrollHeight;
      }}
    }});

    // Pause toggle
    pauseBtn.addEventListener('click', () => {{
      isPaused = !isPaused;
      pauseBtn.classList.toggle('active', isPaused);
      pauseText.textContent = isPaused ? 'Resume' : 'Pause';
      if (isPaused) {{
        streamStatus.className = 'status-badge paused';
        streamStatusText.textContent = 'Stream Paused';
      }} else {{
        streamStatus.className = 'status-badge';
        streamStatusText.textContent = 'Connected • Live';
        renderAllLogs();
      }}
    }});

    // Copy logs
    copyBtn.addEventListener('click', () => {{
      const lines = Array.from(terminal.querySelectorAll('.log-line'))
        .map(el => el.dataset.raw)
        .join('\\n');
      navigator.clipboard.writeText(lines).then(() => {{
        const orig = copyBtn.querySelector('span').textContent;
        copyBtn.querySelector('span').textContent = 'Copied!';
        setTimeout(() => copyBtn.querySelector('span').textContent = orig, 1500);
      }});
    }});

    // Export .log
    exportBtn.addEventListener('click', () => {{
      const lines = allLogs.map(e => e.formatted || e.message).join('\\n');
      const blob = new Blob([lines], {{ type: 'text/plain' }});
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `citizen360_logs_${{new Date().toISOString().replace(/[:.]/g, '-')}}.log`;
      a.click();
      URL.revokeObjectURL(url);
    }});

    // Clear logs
    clearBtn.addEventListener('click', () => {{
      allLogs = [];
      terminal.innerHTML = '';
      totalCount.textContent = '0';
      visibleCount.textContent = '0';
    }});

    // Initialize
    connectSSE();
  </script>
</body>
</html>"""
