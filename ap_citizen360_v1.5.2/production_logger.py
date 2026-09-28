"""
production_logger.py
Enterprise-grade Production Logging & Network Routing Audit Subsystem.

Features:
- Standardized log level tags: [INFO ], [WARN ], [ERROR], [DEBUG], [CRIT ]
- High-precision timestamps with millisecond accuracy (YYYY-MM-DD HH:MM:SS.mmm)
- Production-grade file rotation in logs/ directory:
    * logs/app.log     - Comprehensive system log (all levels >= INFO)
    * logs/error.log   - Critical triage log (WARN, ERROR, CRITICAL only)
    * logs/network.log - Full network routing audit log (HTTP, WS, Outbound calls)
- ANSI colorized console formatter for terminal and container outputs
- Full network routing interception (ASGI Middleware):
    * Real client IP:Port resolution (with X-Forwarded-For proxy chain support)
    * Server host:port destination resolution
    * Inbound request logging: [CLIENT:PORT ➔ SERVER:PORT]
    * Outbound response routing: [SERVER:PORT ➔ CLIENT:PORT] with status, latency (ms), and size
    * Proper severity mapping: 2xx/3xx -> INFO, 4xx -> WARN, 5xx -> ERROR
    * WebSocket connection, frames, and disconnection routing
- Outbound external HTTP request tracking (requests library hook)
- Seamless integration with real-time web UI log streaming (log_streamer.py)
"""

import os
import sys
import time
import json
import uuid
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from http import HTTPStatus

# ── Color Palette & Constants ──────────────────────────────────────────────────
ANSI_RESET = "\033[0m"
ANSI_DIM = "\033[2m"
ANSI_BOLD = "\033[1m"
ANSI_CYAN = "\033[36m"
ANSI_BLUE = "\033[34m"
ANSI_GREEN = "\033[32m"
ANSI_YELLOW = "\033[33m"
ANSI_RED = "\033[31m"
ANSI_MAGENTA = "\033[35m"
ANSI_BOLD_RED_BG = "\033[1;37;41m"
ANSI_BOLD_YELLOW = "\033[1;33m"
ANSI_BOLD_GREEN = "\033[1;32m"
ANSI_BOLD_CYAN = "\033[1;36m"

LEVEL_TAGS = {
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO ",
    logging.WARNING: "WARN ",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRIT ",
}

LEVEL_COLORS = {
    logging.DEBUG: "\033[90m",          # Muted Gray
    logging.INFO: ANSI_CYAN,            # Cyan
    logging.WARNING: ANSI_BOLD_YELLOW,  # Bright Yellow / Amber
    logging.ERROR: ANSI_RED,            # Bright Red
    logging.CRITICAL: ANSI_BOLD_RED_BG, # Bold White on Red Background
}


# ── Formatters ─────────────────────────────────────────────────────────────────
class ProductionFileFormatter(logging.Formatter):
    """
    Standardized plain-text production formatter for file logs.
    Includes millisecond timestamps and uniformly aligned tags: [INFO ], [WARN ], [ERROR], [DEBUG].
    """
    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        dt = datetime.fromtimestamp(record.created)
        base_time = dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")
        return f"{base_time}.{int(record.msecs):03d}"

    def format(self, record: logging.LogRecord) -> str:
        tag = LEVEL_TAGS.get(record.levelno, record.levelname[:5].ljust(5))
        record.level_tag = tag  # Custom attribute for formatting
        
        # Format timestamp with milliseconds
        asctime = self.formatTime(record)
        
        msg = record.getMessage()
        exc_text = ""
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                exc_text = f"\n{record.exc_text}"

        return f"{asctime} [{tag}] [{record.name}] {msg}{exc_text}"


class ColoredConsoleFormatter(logging.Formatter):
    """
    High-contrast ANSI colorized console formatter for terminal and container outputs.
    Enhances readability of log tags, network routing arrows, and status codes.
    """
    def __init__(self, use_colors: bool = True):
        super().__init__()
        self.use_colors = use_colors

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        dt = datetime.fromtimestamp(record.created)
        base_time = dt.strftime(datefmt or "%Y-%m-%d %H:%M:%S")
        return f"{base_time}.{int(record.msecs):03d}"

    def format(self, record: logging.LogRecord) -> str:
        tag = LEVEL_TAGS.get(record.levelno, record.levelname[:5].ljust(5))
        asctime = self.formatTime(record)
        msg = record.getMessage()

        exc_text = ""
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            if record.exc_text:
                exc_text = f"\n{record.exc_text}"

        if not self.use_colors:
            return f"{asctime} [{tag}] [{record.name}] {msg}{exc_text}"

        level_color = LEVEL_COLORS.get(record.levelno, ANSI_RESET)
        
        # Colorize routing symbols in message if present
        colored_msg = msg
        if "➔" in colored_msg:
            colored_msg = colored_msg.replace("➔", f"{ANSI_BOLD_GREEN}➔{ANSI_RESET}")
        if "⬅" in colored_msg:
            colored_msg = colored_msg.replace("⬅", f"{ANSI_MAGENTA}⬅{ANSI_RESET}")
        if "✕" in colored_msg:
            colored_msg = colored_msg.replace("✕", f"{ANSI_RED}✕{ANSI_RESET}")
        if "🔌" in colored_msg:
            colored_msg = colored_msg.replace("🔌", f"{ANSI_BOLD_CYAN}🔌{ANSI_RESET}")

        formatted = (
            f"{ANSI_DIM}{asctime}{ANSI_RESET} "
            f"{level_color}[{tag}]{ANSI_RESET} "
            f"{ANSI_BLUE}[{record.name}]{ANSI_RESET} "
            f"{colored_msg}{exc_text}"
        )
        return formatted


# ── Configuration & Setup ──────────────────────────────────────────────────────
_logging_initialized = False
network_logger = logging.getLogger("app.network")


def setup_production_logging(
    log_dir_path: Optional[str] = None,
    log_level: Optional[str] = None,
    max_bytes: int = 15 * 1024 * 1024,  # 15 MB per file
    backup_count: int = 10,
    enable_console_colors: Optional[bool] = None,
) -> None:
    """
    Initialize production logging configuration.
    Sets up rotating file handlers for app.log, error.log, and network.log,
    along with colorized console output and integration with log_streamer.py.
    """
    global _logging_initialized
    if _logging_initialized:
        return

    # Determine paths and settings
    base_dir = Path(__file__).resolve().parent
    env_dir = os.getenv("LOG_DIR", "logs")
    log_dir = Path(log_dir_path or (base_dir / env_dir)).resolve()
    log_dir.mkdir(parents=True, exist_ok=True)

    level_str = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper().strip()
    root_level = getattr(logging, level_str, logging.INFO)

    env_color = os.getenv("LOG_CONSOLE_COLOR", "").lower()
    if enable_console_colors is not None:
        use_colors = enable_console_colors
    elif env_color in ("false", "0", "no"):
        use_colors = False
    elif env_color in ("true", "1", "yes"):
        use_colors = True
    else:
        use_colors = sys.stdout.isatty()

    file_formatter = ProductionFileFormatter()
    console_formatter = ColoredConsoleFormatter(use_colors=use_colors)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Root captures all, handlers filter
    root_logger.handlers.clear()

    # 1. Console Stream Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(root_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 2. Production Rotating File Handler: app.log (all system events >= root_level)
    app_log_path = log_dir / "app.log"
    app_file_handler = RotatingFileHandler(
        app_log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,
    )
    app_file_handler.setLevel(root_level)
    app_file_handler.setFormatter(file_formatter)
    root_logger.addHandler(app_file_handler)

    # 3. Production Rotating File Handler: error.log (WARN, ERROR, CRITICAL only)
    error_log_path = log_dir / "error.log"
    error_file_handler = RotatingFileHandler(
        error_log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,
    )
    error_file_handler.setLevel(logging.WARNING)
    error_file_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_file_handler)

    # 4. Production Rotating File Handler: network.log (Dedicated network routing audit)
    network_log_path = log_dir / "network.log"
    network_file_handler = RotatingFileHandler(
        network_log_path,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
        delay=True,
    )
    network_file_handler.setLevel(logging.DEBUG)
    network_file_handler.setFormatter(file_formatter)

    # Dedicated network logger for explicit routing logs
    network_logger.setLevel(logging.DEBUG)
    if network_file_handler not in network_logger.handlers:
        network_logger.addHandler(network_file_handler)

    # 5. Connect real-time log_streamer (for live web terminal & TOTP UI)
    try:
        from log_streamer import log_manager
        log_manager.setFormatter(file_formatter)
        if log_manager not in root_logger.handlers:
            root_logger.addHandler(log_manager)
    except ImportError:
        pass

    # Align uvicorn loggers with standard production formatters
    for uvicorn_logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        u_logger = logging.getLogger(uvicorn_logger_name)
        u_logger.handlers.clear()
        u_logger.propagate = True

    # 6. Install outbound HTTP request logger for requests calls (Ollama, vLLM, APIs)
    install_outbound_network_logger()

    _logging_initialized = True
    root_logger.info(
        f"Production logging initialized. Logs directory: {log_dir} "
        f"[app.log, error.log, network.log] (Level: {level_str})"
    )


# ── Outbound Network Logger (Hooks requests calls) ──────────────────────────────
_requests_hooked = False


def install_outbound_network_logger() -> None:
    """
    Instruments requests.Session.send to log all outbound HTTP network requests
    and incoming responses with exact latency, destination, and status code.
    """
    global _requests_hooked
    if _requests_hooked:
        return

    try:
        import requests.sessions
        _orig_send = requests.sessions.Session.send

        def _instrumented_send(self: Any, request: Any, **kwargs: Any) -> Any:
            method = getattr(request, "method", "GET")
            url = getattr(request, "url", "unknown")
            start_time = time.perf_counter()

            network_logger.info(f"➔ OUTBOUND HTTP [Local ➔ {url}] {method}")

            try:
                response = _orig_send(self, request, **kwargs)
                duration_ms = (time.perf_counter() - start_time) * 1000
                status_code = getattr(response, "status_code", 200)
                reason = getattr(response, "reason", "")

                # Estimate response body length
                size_bytes = 0
                if hasattr(response, "_content") and response._content is not None:
                    size_bytes = len(response._content)
                elif hasattr(response, "headers"):
                    cl = response.headers.get("Content-Length")
                    if cl and cl.isdigit():
                        size_bytes = int(cl)

                lvl = (
                    logging.ERROR if status_code >= 500
                    else logging.WARNING if status_code >= 400
                    else logging.INFO
                )
                network_logger.log(
                    lvl,
                    f"⬅ INBOUND HTTP [{url} ➔ Local] {status_code} {reason} | "
                    f"duration={duration_ms:.2f}ms | size={_format_bytes(size_bytes)}"
                )
                return response
            except Exception as exc:
                duration_ms = (time.perf_counter() - start_time) * 1000
                network_logger.error(
                    f"✕ OUTBOUND HTTP FAILED [Local ➔ {url}] {method} | "
                    f"duration={duration_ms:.2f}ms | error={type(exc).__name__}: {exc}"
                )
                raise

        requests.sessions.Session.send = _instrumented_send
        _requests_hooked = True
    except Exception:
        pass


def _format_bytes(size: int) -> str:
    """Format bytes count into clean human-readable representation."""
    if size < 1024:
        return f"{size}B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f}KB"
    return f"{size / (1024 * 1024):.2f}MB"


# ── Full Network Routing Middleware (ASGI) ─────────────────────────────────────
class NetworkRoutingMiddleware:
    """
    Pure ASGI middleware that tracks and logs the complete routing lifecycle:
    - Real client IP:Port resolution (detecting proxy headers: X-Forwarded-For, X-Real-IP)
    - Destination server host:port resolution
    - Inbound request routing: [CLIENT_IP:PORT ➔ SERVER_HOST:PORT]
    - Outbound response routing: [SERVER_HOST:PORT ➔ CLIENT_IP:PORT]
    - Status code, millisecond latency, and payload size
    - Proper severity tags: 2xx/3xx -> INFO, 4xx -> WARN, 5xx -> ERROR
    - WebSocket connection handshakes, incoming/outgoing frames, and disconnection
    """

    def __init__(self, app: Any):
        self.app = app
        self.logger = network_logger

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        if scope["type"] == "http":
            await self._handle_http(scope, receive, send)
        elif scope["type"] == "websocket":
            await self._handle_websocket(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    def _extract_routing_endpoints(self, scope: Dict[str, Any]) -> tuple[str, str, Dict[str, str]]:
        """Extract sanitized (client_addr, server_addr, header_map) from ASGI scope."""
        header_map: Dict[str, str] = {}
        for k, v in scope.get("headers", []):
            try:
                header_map[k.decode("latin-1").lower()] = v.decode("latin-1")
            except Exception:
                pass

        # 1. Resolve Client IP & Port
        client_host = "127.0.0.1"
        client_port = "0"
        if scope.get("client"):
            c = scope["client"]
            if len(c) > 0 and c[0]:
                client_host = str(c[0])
            if len(c) > 1 and c[1] is not None:
                client_port = str(c[1])

        forwarded_for = header_map.get("x-forwarded-for")
        if forwarded_for:
            # First IP in the comma-separated chain is the client
            real_client_ip = forwarded_for.split(",")[0].strip()
        else:
            real_client_ip = (
                header_map.get("x-real-ip")
                or header_map.get("cf-connecting-ip")
                or client_host
            )

        forwarded_port = header_map.get("x-forwarded-port")
        if forwarded_port and forwarded_port.isdigit():
            real_client_port = forwarded_port
        else:
            real_client_port = client_port

        client_addr = f"{real_client_ip}:{real_client_port}"

        # 2. Resolve Server Host & Port
        server_host = "0.0.0.0"
        server_port = "80"
        if scope.get("server"):
            s = scope["server"]
            if len(s) > 0 and s[0]:
                server_host = str(s[0])
            if len(s) > 1 and s[1] is not None:
                server_port = str(s[1])

        host_header = header_map.get("host")
        if host_header:
            if ":" in host_header:
                h, p = host_header.split(":", 1)
                server_host = h
                if p.isdigit():
                    server_port = p
            else:
                server_host = host_header

        server_addr = f"{server_host}:{server_port}"
        return client_addr, server_addr, header_map

    async def _handle_http(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        client_addr, server_addr, headers = self._extract_routing_endpoints(scope)
        method = scope.get("method", "GET")
        path = scope.get("path", "/")
        query_bytes = scope.get("query_string", b"")
        query_str = f"?{query_bytes.decode('latin-1')}" if query_bytes else ""
        full_path = f"{path}{query_str}"
        http_version = scope.get("http_version", "1.1")

        request_id = headers.get("x-request-id")
        if not request_id:
            request_id = f"req_{uuid.uuid4().hex[:10]}"

        # Metadata tags for inbound log
        content_length = headers.get("content-length")
        content_type = headers.get("content-type")
        user_agent = headers.get("user-agent", "")
        if len(user_agent) > 50:
            user_agent = user_agent[:47] + "..."

        meta_parts = []
        if content_length:
            meta_parts.append(f"size={_format_bytes(int(content_length))}")
        if content_type:
            meta_parts.append(f"type={content_type.split(';')[0]}")
        if user_agent:
            meta_parts.append(f"ua={user_agent}")
        meta_str = f" | {' | '.join(meta_parts)}" if meta_parts else ""

        # Inbound Request Log
        self.logger.info(
            f"➔ INCOMING HTTP [{client_addr} ➔ {server_addr}] {method} {full_path} | "
            f"req_id={request_id} | HTTP/{http_version}{meta_str}"
        )

        start_time = time.perf_counter()
        status_code = 500
        response_bytes = 0

        async def wrapped_send(message: Dict[str, Any]) -> None:
            nonlocal status_code, response_bytes
            msg_type = message.get("type")
            if msg_type == "http.response.start":
                status_code = message.get("status", 200)
                # Inject correlation tracking header
                resp_headers = list(message.get("headers", []))
                resp_headers.append((b"x-request-id", request_id.encode("latin-1")))
                message = dict(message)
                message["headers"] = resp_headers
            elif msg_type == "http.response.body":
                body = message.get("body", b"")
                if body:
                    response_bytes += len(body)
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.logger.error(
                f"✕ FAILED HTTP [{server_addr} ➔ {client_addr}] 500 Internal Server Error | "
                f"{method} {full_path} | req_id={request_id} | "
                f"duration={duration_ms:.2f}ms | error={type(exc).__name__}: {exc}"
            )
            raise
        else:
            duration_ms = (time.perf_counter() - start_time) * 1000
            try:
                status_phrase = HTTPStatus(status_code).phrase
            except Exception:
                status_phrase = ""
            status_display = f"{status_code} {status_phrase}".strip()

            # Map status severity: 2xx/3xx -> INFO, 4xx -> WARN, 5xx -> ERROR
            if status_code >= 500:
                log_lvl = logging.ERROR
            elif status_code >= 400:
                log_lvl = logging.WARNING
            else:
                log_lvl = logging.INFO

            self.logger.log(
                log_lvl,
                f"⬅ OUTGOING HTTP [{server_addr} ➔ {client_addr}] {status_display} | "
                f"{method} {full_path} | req_id={request_id} | "
                f"duration={duration_ms:.2f}ms | size={_format_bytes(response_bytes)}"
            )

    async def _handle_websocket(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        client_addr, server_addr, headers = self._extract_routing_endpoints(scope)
        path = scope.get("path", "/")
        query_bytes = scope.get("query_string", b"")
        query_str = f"?{query_bytes.decode('latin-1')}" if query_bytes else ""
        full_path = f"{path}{query_str}"
        request_id = headers.get("x-request-id") or f"ws_{uuid.uuid4().hex[:10]}"

        self.logger.info(
            f"➔ INCOMING WS CONNECT [{client_addr} ➔ {server_addr}] {full_path} | req_id={request_id}"
        )

        async def wrapped_receive() -> Dict[str, Any]:
            msg = await receive()
            msg_type = msg.get("type", "")
            if msg_type == "websocket.receive":
                text = msg.get("text", "")
                bytes_data = msg.get("bytes", b"")
                size = len(text.encode("utf-8")) if text else len(bytes_data) if bytes_data else 0
                action_info = ""
                if text:
                    try:
                        data = json.loads(text)
                        if isinstance(data, dict) and "action" in data:
                            action_info = f" | action={data['action']}"
                    except Exception:
                        pass
                self.logger.info(
                    f"➔ INCOMING WS MSG [{client_addr} ➔ {server_addr}] {path} | "
                    f"size={_format_bytes(size)}{action_info}"
                )
            elif msg_type == "websocket.disconnect":
                code = msg.get("code", 1000)
                self.logger.info(
                    f"🔌 WS DISCONNECT [{client_addr} ✕ {server_addr}] {path} | code={code}"
                )
            return msg

        async def wrapped_send(msg: Dict[str, Any]) -> None:
            msg_type = msg.get("type", "")
            if msg_type == "websocket.accept":
                self.logger.info(
                    f"⬅ OUTGOING WS ACCEPT [{server_addr} ➔ {client_addr}] {path} | 101 Switching Protocols"
                )
            elif msg_type == "websocket.send":
                text = msg.get("text", "")
                bytes_data = msg.get("bytes", b"")
                size = len(text.encode("utf-8")) if text else len(bytes_data) if bytes_data else 0
                type_info = ""
                if text:
                    try:
                        data = json.loads(text)
                        if isinstance(data, dict) and "type" in data:
                            type_info = f" | type={data['type']}"
                    except Exception:
                        pass
                self.logger.info(
                    f"⬅ OUTGOING WS MSG [{server_addr} ➔ {client_addr}] {path} | "
                    f"size={_format_bytes(size)}{type_info}"
                )
            elif msg_type == "websocket.close":
                code = msg.get("code", 1000)
                self.logger.info(
                    f"🔌 WS CLOSE [{server_addr} ➔ {client_addr}] {path} | code={code}"
                )
            await send(msg)

        try:
            await self.app(scope, wrapped_receive, wrapped_send)
        except Exception as exc:
            self.logger.error(
                f"✕ WS ERROR [{client_addr} ✕ {server_addr}] {path} | error={type(exc).__name__}: {exc}"
            )
            raise
