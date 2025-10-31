from __future__ import annotations

from mcp_bridge.security.phi import PHIFilter


def test_phi_filter_redacts_sensitive_tokens():
    text = "Patient Jane Doe, MRN: 123456789, SSN 123-45-6789, phone (555) 123-4567"
    redacted, findings = PHIFilter().redact(text)

    assert "123-45-6789" not in redacted
    assert "[REDACTED:SSN]" in redacted
    assert "[REDACTED:PHONE]" in redacted
    assert any(f.type == "MRN" for f in findings)
    assert any(f.type == "SSN" for f in findings)
    assert any(f.type == "PHONE" for f in findings)
