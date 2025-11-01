from __future__ import annotations

from mcp_bridge.audit import LocalAuditTrail
from mcp_bridge.security.phi import PHIFilter
from mcp_bridge.services.llm import LLMClient, LLMResponse, LLMTransport


class EchoTransport(LLMTransport):
    def __init__(self) -> None:
        self.calls: list[str] = []

    def generate(self, prompt: str, **kwargs):
        self.calls.append(prompt)
        return prompt.upper()


def test_llm_client_redacts_and_logs(tmp_path):
    audit_dir = tmp_path / "audit"
    audit = LocalAuditTrail(audit_dir, enabled=True)
    transport = EchoTransport()
    client = LLMClient(transport=transport, audit_trail=audit, redactor=PHIFilter())

    prompt = "SSN 123-45-6789 should never leave. Source doc hash abc."
    response: LLMResponse = client.generate(
        prompt,
        identity={"subject": "tester", "roles": ["analyst"]},
        source_hash="doc-hash-123",
        metadata={"purpose": "unit-test"},
    )

    assert "123-45-6789" not in response.redacted_prompt
    assert "[REDACTED:SSN]" in response.redacted_prompt
    assert response.output == response.redacted_prompt.upper()
    assert transport.calls[0] == response.redacted_prompt

    events = audit.fetch_events(limit=5, event_type="llm.outbound")
    assert events, "audit should contain llm.outbound event"
    event = events[0]
    assert event["llm"]["sourceHash"] == "doc-hash-123"
    assert event["llm"]["redacted"] is True
    assert event["llm"]["metadata"]["purpose"] == "unit-test"
