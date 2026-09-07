"""
test_logs_streamer.py
Test suite for TOTP verification, log buffering, and log streaming endpoints.
"""

import hmac
import hashlib
import struct
import time
import base64
import logging
from log_streamer import (
    verify_totp,
    get_totp_secret,
    create_session_token,
    verify_session_token,
    log_manager,
    setup_log_streamer,
)

def generate_current_totp(secret_base32: str) -> str:
    """Helper to generate current valid 6-digit TOTP code."""
    key = base64.b32decode(secret_base32, casefold=True)
    current_step = int(time.time() // 30)
    msg = struct.pack(">Q", current_step)
    h = hmac.new(key, msg, hashlib.sha1).digest()
    offset = h[-1] & 0x0F
    truncated = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(truncated % 1000000).zfill(6)


def test_totp_verification():
    secret = get_totp_secret()
    print(f"Testing with secret: {secret}")
    
    # 1. Valid code
    valid_code = generate_current_totp(secret)
    assert verify_totp(valid_code, secret), f"Valid code {valid_code} failed verification"
    print(f"[PASS] Valid TOTP code verified: {valid_code}")

    # 2. Invalid code
    invalid_code = "000000" if valid_code != "000000" else "111111"
    assert not verify_totp(invalid_code, secret), f"Invalid code {invalid_code} unexpectedly passed"
    print(f"[PASS] Invalid TOTP code rejected: {invalid_code}")

    # 3. Malformed / empty code
    assert not verify_totp("", secret)
    assert not verify_totp("abc", secret)
    assert not verify_totp("12345", secret)
    print("[PASS] Malformed inputs safely rejected")


def test_session_token():
    token = create_session_token()
    assert verify_session_token(token), "Generated session token verification failed"
    print(f"[PASS] Session token valid: {token[:20]}...")

    assert not verify_session_token("invalid_token_payload")
    print("[PASS] Invalid session token rejected")


def test_log_buffering():
    setup_log_streamer()
    test_logger = logging.getLogger("app.test")
    
    test_logger.info("Test INFO log message 12345")
    test_logger.warning("Test WARN log message 67890")
    test_logger.error("Test ERROR log message ABCDE")

    recent = log_manager.get_recent_logs(10)
    messages = [r["message"] for r in recent]

    assert any("Test INFO log message 12345" in m for m in messages), "INFO log not captured in buffer"
    assert any("Test WARN log message 67890" in m for m in messages), "WARN log not captured in buffer"
    assert any("Test ERROR log message ABCDE" in m for m in messages), "ERROR log not captured in buffer"

    print("[PASS] Log buffer successfully captured logging output")


def test_html_rendering():
    from log_streamer import render_log_viewer_html
    # Unauthenticated
    unauth_html = render_log_viewer_html(authenticated=False, error_message="Test Error")
    assert "Runtime Logs Access" in unauth_html
    assert "Test Error" in unauth_html
    assert "Verification Code" in unauth_html
    print("[PASS] render_log_viewer_html(authenticated=False) correctly renders login page with error")

    # Authenticated
    auth_html = render_log_viewer_html(authenticated=True)
    assert "AP Citizen 360 Logs" in auth_html
    assert "Connected • Live" in auth_html
    assert "searchInput" in auth_html
    assert "autoScrollBtn" in auth_html
    assert "pauseBtn" in auth_html
    print("[PASS] render_log_viewer_html(authenticated=True) correctly renders live terminal dashboard")


if __name__ == "__main__":
    print("\n--- RUNNING LOG STREAMER & TOTP TESTS ---")
    test_totp_verification()
    test_session_token()
    test_log_buffering()
    test_html_rendering()
    print("\n>>> ALL LOG STREAMER & TOTP TESTS PASSED SUCCESSFULLY! <<<\n")



