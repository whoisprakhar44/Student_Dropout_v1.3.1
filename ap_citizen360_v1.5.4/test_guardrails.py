"""
test_guardrails.py
------------------
Automated test suite verifying the Content Guardrails implementation.
Tests short queries, Andhra Pradesh domain terms, gibberish rejection,
and profanity filtering.
"""
import sys
import os
from pathlib import Path

# Add my_agent/utils to sys.path for direct isolated execution
_utils_dir = str(Path(__file__).resolve().parent / "my_agent" / "utils")
if _utils_dir not in sys.path:
    sys.path.insert(0, _utils_dir)

try:
    from my_agent.utils.guardrails import (
        GibberishDetector,
        ProfanityGuardrail,
        HateSpeechGuardrail,
        ContentGuardrailManager,
        _DETOXIFY_AVAILABLE,
        _PROFANITY_AVAILABLE,
    )
except ImportError:
    from guardrails import (
        GibberishDetector,
        ProfanityGuardrail,
        HateSpeechGuardrail,
        ContentGuardrailManager,
        _DETOXIFY_AVAILABLE,
        _PROFANITY_AVAILABLE,
    )


def test_gibberish_detector():
    print("\n--- Testing GibberishDetector ---")
    detector = GibberishDetector()

    valid_queries = [
        "Total dropouts",
        "Top 5 schools",
        "How many students in Kadapa?",
        "AAY card dropouts in Kurnool district",
        "Count of SC and ST students in 2025-26",
        "List dropout students from AAY ration-card households in Anantapur",
        "Average attendance in Chittoor",
        "UDISE report for school 282101001",
    ]

    for q in valid_queries:
        is_valid, msg, details = detector.validate(q)
        assert is_valid, f"FAILED: Valid query falsely rejected as gibberish: '{q}' -> {details}"
        print(f"  [PASS] Valid: '{q}' (confidence: {details.get('confidence')})")

    invalid_queries = [
        "asdfghjklqwerty",
        "zzzzzzzzzzzzzzz",
        "111111111111111",
        "!@#$%^&*()_+=-",
        "sdkjfhskdjfhksjdhfkshdfkjsdhfksjdfhksjdf",
        "x",
    ]

    for q in invalid_queries:
        is_valid, msg, details = detector.validate(q)
        assert not is_valid, f"FAILED: Gibberish was not detected for: '{q}' -> {details}"
        print(f"  [PASS] Gibberish caught: '{q}' -> {details.get('reasons')}")


def test_profanity_detector():
    print("\n--- Testing ProfanityGuardrail ---")
    guardrail = ProfanityGuardrail()
    if not _PROFANITY_AVAILABLE:
        print("  [SKIP] better_profanity not installed in this environment.")
        return

    clean_query = "How many dropouts in Guntur?"
    is_valid, msg, details = guardrail.validate(clean_query)
    assert is_valid, f"FAILED: Clean query falsely flagged for profanity: {details}"
    print(f"  [PASS] Clean query passed.")

    profane_query = "What the fuck is the dropout rate in Nellore?"
    is_valid, msg, details = guardrail.validate(profane_query)
    assert not is_valid, f"FAILED: Profanity was not detected!"
    print(f"  [PASS] Profanity caught -> Censored: {details.get('censored_text')}")


def test_manager():
    print("\n--- Testing ContentGuardrailManager ---")
    manager = ContentGuardrailManager()

    # Valid domain query
    is_valid, reason, details = manager.validate("Show top 10 schools by dropout count in Prakasam")
    assert is_valid, f"FAILED: Valid query failed manager: {reason}, {details}"
    print(f"  [PASS] Valid query passed manager.")

    # Gibberish query
    is_valid, reason, details = manager.validate("poiuytrewqlkjhgfdsamnbvcxz")
    assert not is_valid, f"FAILED: Gibberish was not caught by manager!"
    assert details.get("guardrail") == "gibberish"
    print(f"  [PASS] Gibberish caught by manager: {reason} (layer: {details.get('guardrail')})")


if __name__ == "__main__":
    print("Running Content Guardrails Test Suite...")
    print(f"Environment Status: detoxify={_DETOXIFY_AVAILABLE}, better_profanity={_PROFANITY_AVAILABLE}")
    try:
        test_gibberish_detector()
        test_profanity_detector()
        test_manager()
        print("\n==========================================")
        print("All Content Guardrail tests passed! [SUCCESS]")
        print("==========================================")
    except AssertionError as e:
        print(f"\n[TEST FAILED]: {e}")
        sys.exit(1)
