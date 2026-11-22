"""Deterministic output guardrail: normalizes LLM text and redacts PII."""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class OutputGuardResult:
    sanitized_text: str
    pii_redacted: bool
    redacted_types: list[str] = field(default_factory=list)
    redaction_count: int = 0


def extract_text(content: Any) -> str:
    """Normalize LangChain message content (plain str or Gemini 3 list of blocks) to str."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "\n".join(p for p in parts if p).strip()
    return str(content)


# Ordered carefully: more specific identifiers (email, PAN, SSN, Aadhaar) run before phone/address.
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_AADHAAR_RE = re.compile(r"\b[2-9]\d{3}[\s-]\d{4}[\s-]\d{4}\b")
_PHONE_RE = re.compile(
    r"(?:"
    r"\+\d{1,3}[\s.-]?\d{10}\b"                                           # +91-9876543210
    r"|\+\d{1,3}[\s.-]?\(?\d{3,5}\)?[\s.-]\d{3,5}(?:[\s.-]\d{3,4})?\b"   # +91 98220 11223 / +1 (555) 123-4567
    r"|(?<!\d)\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b"                       # (555) 123-4567 / 555-123-4567
    r"|(?<!\d)[6-9]\d{9}\b"                                              # standalone 10-digit Indian mobile
    r")"
)

# Labeled addresses (handles optional markdown bolding around the label)
_LABELED_ADDRESS_RE = re.compile(
    r"(?i)(\*{0,2}(?:home\s+|residential\s+|personal\s+)?address\*{0,2}\s*[:\-]\s*\*{0,2}\s*)"
    r"(?!\[REDACTED_ADDRESS\])"
    r"([^\n]+)"
)

# Inline unlabeled addresses: house/building number + street keyword + 5-or-6-digit PIN/ZIP
_INLINE_ADDRESS_RE = re.compile(
    r"(?i)\b\d{1,5}\s+[A-Za-z0-9.\s,'-]{2,60}?"
    r"\b(?:Road|Rd|Street|St|Stage|Drive|Dr|Enclave|View|Avenue|Ave|Lane|Ln|"
    r"Nagar|Colony|Sector|Block|Layout|Cross|Main|Marg|Park|Apartment|Apt|Floor)\b"
    r"[^.\n]{0,60}?\b\d{5,6}\b"
)

# Context-aware salary redaction (avoids redacting policy numbers like WFH stipends)
_SALARY_RE = re.compile(
    r"(?i)(\*{0,2}(?:base\s+salary|annual\s+salary|salary|ctc|compensation|base\s+pay)\*{0,2}"
    r"\s*(?:is|of|:|-)?\s*\*{0,2})"
    r"(?:(?:₹|Rs\.?|INR|\$|USD)\s*)?"
    r"[\d,]+(?:\.\d{1,2})?"
    r"(?:\s*(?:LPA|lakh|lakhs|per\s+year|per\s+annum|/year))?"
)


def redact_pii(content: Any) -> OutputGuardResult:
    """Scrub PII from model output and return sanitized text with an audit summary."""
    text = extract_text(content)
    redacted_types: list[str] = []
    total_count = 0

    def _apply_simple(pattern: re.Pattern[str], token: str, label: str) -> None:
        nonlocal text, total_count
        text, count = pattern.subn(token, text)
        if count > 0:
            total_count += count
            if label not in redacted_types:
                redacted_types.append(label)

    def _apply_preserve_prefix(pattern: re.Pattern[str], token: str, label: str) -> None:
        nonlocal text, total_count
        text, count = pattern.subn(rf"\g<1>{token}", text)
        if count > 0:
            total_count += count
            if label not in redacted_types:
                redacted_types.append(label)

    _apply_simple(_EMAIL_RE, "[REDACTED_EMAIL]", "email")
    _apply_simple(_PAN_RE, "[REDACTED_PAN]", "pan_id")
    _apply_simple(_SSN_RE, "[REDACTED_SSN]", "ssn")
    _apply_simple(_AADHAAR_RE, "[REDACTED_AADHAAR]", "aadhaar")
    _apply_simple(_PHONE_RE, "[REDACTED_PHONE]", "phone")
    _apply_preserve_prefix(_LABELED_ADDRESS_RE, "[REDACTED_ADDRESS]", "address")
    _apply_simple(_INLINE_ADDRESS_RE, "[REDACTED_ADDRESS]", "address")
    _apply_preserve_prefix(_SALARY_RE, "[REDACTED_SALARY]", "salary")

    return OutputGuardResult(
        sanitized_text=text,
        pii_redacted=total_count > 0,
        redacted_types=redacted_types,
        redaction_count=total_count,
    )


if __name__ == "__main__":
    # Test 1: Heavy PII leak (matches our seeded DB format + Gemini 3 list-of-blocks format)
    sample_blocks = [
        {
            "type": "text",
            "text": (
                "Employee E101 (Aarav Sharma) works in Engineering.\n"
                "- Work Email: aarav.sharma@company.com\n"
                "- Personal Email: aarav.personal@gmail.com\n"
                "- Phone: +91-9876543210\n"
                "- PAN: ABCDE1234F\n"
                "- **Home Address:** 42 Indiranagar 2nd Stage, Bengaluru 560038\n"
                "- Inline check: Sneha lives at 18 Baner Road, Pune 411045.\n"
                "- Base Salary: ₹24,00,000 per year"
            ),
            "extras": {"signature": "dummy"},
        }
    ]

    res1 = redact_pii(sample_blocks)
    print("=== Test 1: PII Leak Redaction ===")
    print(res1.sanitized_text)
    print(f"Redacted={res1.pii_redacted} | Count={res1.redaction_count} | Types={res1.redacted_types}\n")

    # Test 2: False-positive check (legitimate HR/IT text must stay untouched)
    clean_text = (
        "Employee E102 has 7 annual leave days left as of 2026-11-01. "
        "Open ticket IT-2002 is for laptop AST-502 (serial SN-TPX-88202). "
        "Remote employees get a ₹25,000 WFH setup stipend [Source: remote_work_and_expenses.md — Section 1]."
    )
    res2 = redact_pii(clean_text)
    print("=== Test 2: False-Positive Check ===")
    print(res2.sanitized_text)
    print(f"Redacted={res2.pii_redacted} | Count={res2.redaction_count} | Types={res2.redacted_types}")

    assert res1.pii_redacted is True
    assert "aarav.personal@gmail.com" not in res1.sanitized_text
    assert "9876543210" not in res1.sanitized_text
    assert "ABCDE1234F" not in res1.sanitized_text
    assert "Indiranagar" not in res1.sanitized_text
    assert "Baner Road" not in res1.sanitized_text
    assert "24,00,000" not in res1.sanitized_text
    assert "E101" in res1.sanitized_text

    assert res2.pii_redacted is False
    assert res2.sanitized_text == clean_text
    print("\nALL OUTPUT GUARDRAIL ASSERTIONS PASSED.")