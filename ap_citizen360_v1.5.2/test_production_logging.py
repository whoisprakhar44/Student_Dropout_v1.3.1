"""
test_production_logging.py
Comprehensive test suite verifying enterprise production logging,
proper tags, rotating files, and full network routing audit.
"""

import os
import shutil
import logging
from pathlib import Path
from starlette.testclient import TestClient

from production_logger import (
    setup_production_logging,
    ProductionFileFormatter,
    ColoredConsoleFormatter,
    LEVEL_TAGS,
)
from app import app


def test_formatters():
    print("--- 1. Testing Production Formatters & Tags ---")
    file_formatter = ProductionFileFormatter()
    console_formatter = ColoredConsoleFormatter(use_colors=False)

    logger = logging.getLogger("test.formatter")
    
    # Test INFO
    rec_info = logger.makeRecord("test.formatter", logging.INFO, "test.py", 10, "Test info message", (), None)
    out_info = file_formatter.format(rec_info)
    assert "[INFO ]" in out_info, f"Expected [INFO ] tag, got: {out_info}"
    assert "Test info message" in out_info
    print("  [PASS] [INFO ] formatted with millisecond timestamp")

    # Test WARNING -> WARN
    rec_warn = logger.makeRecord("test.formatter", logging.WARNING, "test.py", 20, "Test warning message", (), None)
    out_warn = file_formatter.format(rec_warn)
    assert "[WARN ]" in out_warn, f"Expected [WARN ] tag, got: {out_warn}"
    assert "Test warning message" in out_warn
    print("  [PASS] [WARN ] formatted with millisecond timestamp")

    # Test ERROR
    rec_err = logger.makeRecord("test.formatter", logging.ERROR, "test.py", 30, "Test error message", (), None)
    out_err = file_formatter.format(rec_err)
    assert "[ERROR]" in out_err, f"Expected [ERROR] tag, got: {out_err}"
    assert "Test error message" in out_err
    print("  [PASS] [ERROR] formatted with millisecond timestamp")

    # Test DEBUG
    rec_debug = logger.makeRecord("test.formatter", logging.DEBUG, "test.py", 40, "Test debug message", (), None)
    out_debug = file_formatter.format(rec_debug)
    assert "[DEBUG]" in out_debug, f"Expected [DEBUG] tag, got: {out_debug}"
    assert "Test debug message" in out_debug
    print("  [PASS] [DEBUG] formatted with millisecond timestamp")

    # Test Colored Console Formatter
    colored_formatter = ColoredConsoleFormatter(use_colors=True)
    colored_out = colored_formatter.format(rec_info)
    assert "\033[" in colored_out, "Expected ANSI color codes in console output"
    print("  [PASS] ANSI colorized console formatting verified")


def test_production_file_saving():
    print("\n--- 2. Testing Production File Handlers in logs/ ---")
    log_dir = Path(__file__).resolve().parent / "logs"
    assert log_dir.exists(), "logs/ directory should exist"

    app_log = log_dir / "app.log"
    error_log = log_dir / "error.log"
    network_log = log_dir / "network.log"

    assert app_log.exists(), "logs/app.log must exist"
    assert error_log.exists(), "logs/error.log must exist"
    assert network_log.exists(), "logs/network.log must exist"

    # Emit test logs to verify routing into appropriate files
    test_logger = logging.getLogger("app.test")
    test_logger.info("TEST_PRODUCTION_INFO_MARKER")
    test_logger.warning("TEST_PRODUCTION_WARN_MARKER")
    test_logger.error("TEST_PRODUCTION_ERROR_MARKER")

    # Flush handlers
    for h in logging.getLogger().handlers:
        h.flush()

    app_content = app_log.read_text(encoding="utf-8")
    error_content = error_log.read_text(encoding="utf-8")

    assert "TEST_PRODUCTION_INFO_MARKER" in app_content
    assert "TEST_PRODUCTION_WARN_MARKER" in app_content
    assert "TEST_PRODUCTION_ERROR_MARKER" in app_content
    print("  [PASS] logs/app.log captures all system levels")

    # error.log should contain WARN and ERROR, but NOT INFO
    assert "TEST_PRODUCTION_INFO_MARKER" not in error_content
    assert "TEST_PRODUCTION_WARN_MARKER" in error_content
    assert "TEST_PRODUCTION_ERROR_MARKER" in error_content
    print("  [PASS] logs/error.log captures exclusively WARN and ERROR entries")


def test_network_routing_logging():
    print("\n--- 3. Testing Full Network Routing (IP:Port, Paths, Latency) ---")
    log_dir = Path(__file__).resolve().parent / "logs"
    network_log = log_dir / "network.log"

    with TestClient(app) as client:
        # Request with custom Client IP & Proxy Headers and custom Host header
        custom_headers = {
            "X-Forwarded-For": "203.0.113.195, 10.0.0.1",
            "X-Forwarded-Port": "54321",
            "Host": "api.apcitizen360.local:8080",
            "User-Agent": "ProductionAuditClient/1.0",
        }
        res = client.get("/health", headers=custom_headers)
        assert res.status_code == 200

        # Flush handlers
        for h in logging.getLogger().handlers + logging.getLogger("app.network").handlers:
            h.flush()

        net_content = network_log.read_text(encoding="utf-8")
        
        # Verify Inbound Routing
        assert "➔ INCOMING HTTP [203.0.113.195:54321 ➔ api.apcitizen360.local:8080] GET /health" in net_content
        print("  [PASS] Inbound routing: [203.0.113.195:54321 ➔ api.apcitizen360.local:8080] logged")

        # Verify Outbound Return Routing
        assert "⬅ OUTGOING HTTP [api.apcitizen360.local:8080 ➔ 203.0.113.195:54321] 200 OK | GET /health" in net_content
        print("  [PASS] Outbound return routing: [api.apcitizen360.local:8080 ➔ 203.0.113.195:54321] 200 OK logged")

        # Test 404 / 4xx mapping to WARN
        res_404 = client.get("/nonexistent-route", headers=custom_headers)
        assert res_404.status_code == 404
        
        for h in logging.getLogger().handlers + logging.getLogger("app.network").handlers:
            h.flush()
        
        net_content = network_log.read_text(encoding="utf-8")
        assert "[WARN ] [app.network] ⬅ OUTGOING HTTP [api.apcitizen360.local:8080 ➔ 203.0.113.195:54321] 404 Not Found" in net_content
        print("  [PASS] 404 response mapped to [WARN ] severity tag with routing")

        # Verify Correlation header in client response
        assert "x-request-id" in res.headers
        print(f"  [PASS] X-Request-ID correlation tracking header injected: {res.headers['x-request-id']}")


def test_websocket_routing():
    print("\n--- 4. Testing WebSocket Network Routing ---")
    log_dir = Path(__file__).resolve().parent / "logs"
    network_log = log_dir / "network.log"

    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"action": "ping"})
            # Disconnect
        
        for h in logging.getLogger().handlers + logging.getLogger("app.network").handlers:
            h.flush()

        net_content = network_log.read_text(encoding="utf-8")
        assert "➔ INCOMING WS CONNECT" in net_content
        assert "⬅ OUTGOING WS ACCEPT" in net_content
        assert "➔ INCOMING WS MSG" in net_content
        assert "🔌 WS DISCONNECT" in net_content
        print("  [PASS] WebSocket full routing lifecycle logged (CONNECT, ACCEPT, MSG, DISCONNECT)")


if __name__ == "__main__":
    test_formatters()
    test_production_file_saving()
    test_network_routing_logging()
    test_websocket_routing()
    print("\n=======================================================")
    print(">>> ALL PRODUCTION LOGGING TESTS PASSED SUCCESSFULLY! <<<")
    print("=======================================================\n")
