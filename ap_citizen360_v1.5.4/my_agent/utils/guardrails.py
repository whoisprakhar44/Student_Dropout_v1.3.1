"""
my_agent/utils/guardrails.py
---------------------------
Content guardrails: Hate Speech, Gibberish, and Profanity detection.
Calibrated specifically for AP Citizen 360 / Student Dropout NL2SQL queries.
"""
import re
import math
import logging
from collections import Counter
from typing import Dict, Any, Tuple, Optional, List

logger = logging.getLogger("guardrails")

# Optional ML and NLP imports with graceful fallbacks
try:
    from detoxify import Detoxify
    _DETOXIFY_AVAILABLE = True
except ImportError:
    _DETOXIFY_AVAILABLE = False

try:
    from better_profanity import profanity
    _PROFANITY_AVAILABLE = True
except ImportError:
    _PROFANITY_AVAILABLE = False


###########################################################
# Hate Speech Guardrail (Detoxify / BERT)
###########################################################

class HateSpeechGuardrail:
    """
    BERT-based toxicity and hate speech classifier using Detoxify.
    Thresholds are calibrated for government analytics systems to avoid
    false positives on legitimate affirmative action / demographic queries (e.g. SC/ST, minorities).
    """

    def __init__(
        self,
        toxicity_threshold: float = 0.65,
        severe_threshold: float = 0.45,
        identity_threshold: float = 0.65,  # Calibrated up from 0.40 to avoid blocking welfare demographic queries
        insult_threshold: float = 0.65,
        threat_threshold: float = 0.40,
        obscene_threshold: float = 0.70,
    ):
        self.enabled = _DETOXIFY_AVAILABLE
        self.thresholds = {
            "toxicity": toxicity_threshold,
            "severe_toxicity": severe_threshold,
            "identity_attack": identity_threshold,
            "insult": insult_threshold,
            "threat": threat_threshold,
            "obscene": obscene_threshold,
        }
        self.model = None

        if self.enabled:
            try:
                # Load Detoxify original model once (singleton pattern)
                self.model = Detoxify("original")
                logger.info("HateSpeechGuardrail: Detoxify model loaded successfully.")
            except Exception as e:
                logger.warning("HateSpeechGuardrail: Failed to load Detoxify model (%s). Disabling ML hate speech check.", e)
                self.enabled = False
        else:
            logger.info("HateSpeechGuardrail: detoxify library not installed. Running in passthrough mode.")

    def predict(self, text: str) -> Dict[str, float]:
        if not self.enabled or not self.model:
            return {}
        return self.model.predict(text)

    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        if not self.enabled or not self.model:
            return True, "Passed (Detoxify not active)", {"scores": {}, "violations": []}

        try:
            scores = self.predict(text)
            violations: List[Dict[str, Any]] = []

            for label, threshold in self.thresholds.items():
                val = float(scores.get(label, 0.0))
                if val >= threshold:
                    violations.append({
                        "category": label,
                        "score": round(val, 3),
                        "threshold": threshold
                    })

            if violations:
                return (
                    False,
                    "Toxic or offensive language detected.",
                    {
                        "scores": {k: round(float(v), 3) for k, v in scores.items()},
                        "violations": violations
                    }
                )

            return (
                True,
                "Passed",
                {
                    "scores": {k: round(float(v), 3) for k, v in scores.items()},
                    "violations": []
                }
            )
        except Exception as e:
            logger.error("HateSpeechGuardrail: error during prediction (%s). Allowing query.", e)
            return True, "Passed (Error during check)", {"error": str(e)}


###########################################################
# Gibberish Guardrail (Calibrated for NL2SQL)
###########################################################

class GibberishDetector:
    """
    Statistical and heuristic text quality analyzer.
    Calibrated specifically for short NL2SQL queries and AP administrative terms.
    """

    def __init__(self):
        self.common_bigrams = {
            "th","he","in","er","an","re","on","at","en","nd",
            "ti","es","or","te","of","ed","is","it","al","ar",
            "st","to","nt","ng","se","ha","as","ou","io","le",
            "ve","co","me","de","hi","ri","ro","ic","ne","ea"
        }

        self.keyboard_patterns = [
            "asdf", "qwer", "zxcv", "poiuy",
            "lkjh", "mnb", "12345", "09876", "hjkl"
        ]

        # Domain terms, district names, welfare acronyms for AP Citizen 360
        self.domain_tokens = {
            "aay", "bpl", "sc", "st", "bc", "oc", "udise", "jvd", "mdm", "aadhaar", "aadhar",
            "anantapur", "chittoor", "kadapa", "kurnool", "srikakulam", "visakhapatnam",
            "vizianagaram", "prakasam", "nellore", "guntur", "krishna", "godavari",
            "bapatla", "nandyal", "palnadu", "konaseema", "eluru", "ntr", "tirupati",
            "dropout", "dropouts", "enrolment", "enrollment", "student", "students",
            "school", "schools", "mandal", "district", "attendance", "caste", "gender",
            "count", "total", "list", "show", "how", "many", "average", "highest", "lowest", "top"
        }

    def entropy(self, text: str) -> float:
        freq = Counter(text)
        length = len(text)
        if length == 0:
            return 0.0
        return -sum((c / length) * math.log2(c / length) for c in freq.values())

    def repeated_characters(self, text: str) -> bool:
        # Flag 5 or more repeated consecutive identical characters (e.g. "aaaaaa", "111111")
        return bool(re.search(r"(.)\1{4,}", text.lower()))

    def keyboard_smash(self, text: str) -> bool:
        text_lower = text.lower()
        return any(x in text_lower for x in self.keyboard_patterns)

    def abnormal_word_length(self, words: List[str]) -> bool:
        if not words:
            return False
        avg = sum(len(w) for w in words) / len(words)
        # Any average word length > 18 or single words > 30 characters without spaces is abnormal
        return avg > 18 or any(len(w) > 30 for w in words)

    def bigram_score(self, text: str) -> float:
        letters = re.sub(r"[^a-z]", "", text.lower())
        if len(letters) < 2:
            return 1.0  # Cannot compute bigrams for <2 letters, do not penalize

        total = 0
        common = 0
        for i in range(len(letters) - 1):
            total += 1
            if letters[i:i+2] in self.common_bigrams:
                common += 1

        return common / total if total > 0 else 1.0

    def random_symbol_ratio(self, text: str) -> float:
        if not text:
            return 0.0
        symbols = len(re.findall(r"[^A-Za-z0-9\s.,!?;:'\"()-]", text))
        return symbols / len(text)

    def vowel_ratio(self, text: str) -> float:
        letters = re.findall(r"[a-z]", text.lower())
        if not letters:
            return 0.5  # Neutral default
        vowels = sum(c in "aeiou" for c in letters)
        return vowels / len(letters)

    def repetition_ratio(self, words: List[str]) -> float:
        if not words:
            return 0.0
        unique = len(set(words))
        return 1.0 - (unique / len(words))

    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        reasons: List[str] = []
        score = 0.0
        text_clean = text.strip()

        if not text_clean:
            return False, "Query is empty.", {"confidence": 1.0, "reasons": ["Empty"]}

        words = re.findall(r"[A-Za-z]+", text_clean.lower())

        # Check for domain keywords / district names
        has_domain_token = any(w in self.domain_tokens for w in words)

        # 1. Very short nonsense (e.g. single character or 2 random consonants like "xf")
        if len(text_clean) < 3 and not has_domain_token:
            reasons.append("Extremely Short")
            score += 0.55

        # 2. Keyboard smash (e.g. "asdfghjkl", "qwertyuiop")
        if self.keyboard_smash(text_clean):
            reasons.append("Keyboard Smash")
            score += 0.55

        # 3. Repeated characters (e.g. "asddddddd", "11111111")
        if self.repeated_characters(text_clean):
            reasons.append("Repeated Characters")
            score += 0.55

        # 4. Abnormally long unbroken strings (e.g. "askjdhfkjasdhfkjahsdkfjhasd")
        if self.abnormal_word_length(words):
            reasons.append("Abnormally Long Words")
            score += 0.55

        # 5. Excessive random symbols (e.g. "%$^&*#@@!!!")
        if len(text_clean) > 5 and self.random_symbol_ratio(text_clean) > 0.35:
            reasons.append("Too Many Symbols")
            score += 0.55

        # 6. Low entropy & few bigrams (only evaluated if query has sufficient length > 25 chars)
        if len(text_clean) >= 25:
            if self.entropy(text_clean) < 2.2:
                reasons.append("Low Entropy")
                score += 0.20

            if self.bigram_score(text_clean) < 0.12 and not has_domain_token:
                reasons.append("Few English Bigrams")
                score += 0.20

            v = self.vowel_ratio(text_clean)
            if (v < 0.10 or v > 0.85) and not has_domain_token:
                reasons.append("Abnormal Vowel Ratio")
                score += 0.15

        # 7. Word repetition (e.g. "dropout dropout dropout dropout dropout")
        if len(words) >= 4 and self.repetition_ratio(words) > 0.75:
            reasons.append("Word Repetition")
            score += 0.30

        # If domain tokens match, discount score by 0.30 to protect domain jargon
        if has_domain_token:
            score = max(0.0, score - 0.30)

        confidence = min(score, 1.0)
        is_valid = confidence < 0.50

        if not is_valid:
            return (
                False,
                "Query appears to be gibberish or nonsensical input.",
                {
                    "confidence": round(confidence, 2),
                    "reasons": reasons
                }
            )

        return (
            True,
            "Passed",
            {
                "confidence": round(confidence, 2),
                "reasons": reasons
            }
        )


###########################################################
# Profanity Guardrail (better_profanity)
###########################################################

class ProfanityGuardrail:
    """
    Scans for explicit, vulgar, or obscene language using better_profanity.
    """

    def __init__(self):
        self.enabled = _PROFANITY_AVAILABLE
        if self.enabled:
            try:
                profanity.load_censor_words()
                logger.info("ProfanityGuardrail: Censor words loaded.")
            except Exception as e:
                logger.warning("ProfanityGuardrail: Failed to load censor words (%s).", e)
                self.enabled = False
        else:
            logger.info("ProfanityGuardrail: better_profanity not installed. Running in passthrough mode.")

    def validate(self, text: str) -> Tuple[bool, str, Dict[str, Any]]:
        if not self.enabled:
            return True, "Passed (Profanity filter disabled)", {"contains_profanity": False}

        try:
            contains = profanity.contains_profanity(text)
            if contains:
                return (
                    False,
                    "Profanity or inappropriate language detected.",
                    {
                        "contains_profanity": True,
                        "censored_text": profanity.censor(text)
                    }
                )

            return (
                True,
                "Passed",
                {
                    "contains_profanity": False,
                    "censored_text": text
                }
            )
        except Exception as e:
            logger.error("ProfanityGuardrail error (%s). Allowing query.", e)
            return True, "Passed (Error during check)", {"error": str(e)}


###########################################################
# Unified Content Guardrail Manager
###########################################################

class ContentGuardrailManager:
    """
    Unified manager executing input guardrails sequentially:
    1. Gibberish heuristics (fastest, ~0.1ms)
    2. Profanity lookup (~0.5ms)
    3. Toxic/Hate speech ML inference (if detoxify is installed, ~50ms)
    """

    def __init__(
        self,
        enable_hate_speech: bool = True,
        enable_profanity: bool = True,
        enable_gibberish: bool = True
    ):
        self.gibberish = GibberishDetector() if enable_gibberish else None
        self.profanity = ProfanityGuardrail() if enable_profanity else None
        self.hate_speech = HateSpeechGuardrail() if enable_hate_speech else None

    def validate(self, text: str) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Validates text against all enabled guardrails.
        Returns:
            (is_valid, violation_message, violation_details)
        """
        # Step 1: Gibberish detection
        if self.gibberish:
            is_valid, msg, details = self.gibberish.validate(text)
            if not is_valid:
                return False, msg, {"guardrail": "gibberish", **details}

        # Step 2: Profanity detection
        if self.profanity:
            is_valid, msg, details = self.profanity.validate(text)
            if not is_valid:
                return False, msg, {"guardrail": "profanity", **details}

        # Step 3: Toxic / Hate speech detection
        if self.hate_speech:
            is_valid, msg, details = self.hate_speech.validate(text)
            if not is_valid:
                return False, msg, {"guardrail": "hate_speech", **details}

        return True, None, {}
