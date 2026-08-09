import hashlib
import json
import logging
from typing import Tuple

from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine

logger = logging.getLogger("guardrails.ingress")

# Initialize Presidio engines
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# Custom Indian PII Recognizers
aadhaar_pattern = Pattern(
    name="aadhaar_pattern",
    regex=r"\b\d{4}\s?\d{4}\s?\d{4}\b",
    score=0.85
)
aadhaar_recognizer = PatternRecognizer(
    supported_entity="IN_AADHAAR",
    patterns=[aadhaar_pattern]
)

pan_pattern = Pattern(
    name="pan_pattern",
    regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b",
    score=0.85
)
pan_recognizer = PatternRecognizer(
    supported_entity="IN_PAN",
    patterns=[pan_pattern]
)

voter_pattern = Pattern(
    name="voter_pattern",
    regex=r"\b[A-Z]{3}[0-9]{7}\b",
    score=0.85
)
voter_recognizer = PatternRecognizer(
    supported_entity="IN_VOTER",
    patterns=[voter_pattern]
)

analyzer.registry.add_recognizer(aadhaar_recognizer)
analyzer.registry.add_recognizer(pan_recognizer)
analyzer.registry.add_recognizer(voter_recognizer)


def analyze_and_redact(text: str) -> Tuple[str, dict]:
    """
    Analyzes the input text for PII using Presidio.
    Returns a tuple of (redacted_text, audit_log_data).
    """
    if not text:
        return text, {}

    # Entities to scan for
    entities = ["IN_AADHAAR", "IN_PAN", "IN_VOTER", "PHONE_NUMBER", "EMAIL_ADDRESS"]
    
    results = analyzer.analyze(text=text, entities=entities, language="en")
    
    if not results:
        return text, {}

    # Perform anonymization (redaction)
    anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
    
    # Hash findings for audit log
    findings = []
    for res in results:
        # Extract the actual PII substring to hash it deterministically
        pii_text = text[res.start:res.end]
        pii_hash = hashlib.sha256(pii_text.encode('utf-8')).hexdigest()
        findings.append({
            "entity_type": res.entity_type,
            "hash": pii_hash,
            "start": res.start,
            "end": res.end,
            "score": res.score
        })

    audit_log = {
        "pii_detected": True,
        "findings": findings
    }

    return anonymized_result.text, audit_log
