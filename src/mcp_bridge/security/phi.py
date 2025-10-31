"""Utilities for detecting and redacting Protected Health Information (PHI)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Pattern, Sequence


@dataclass(frozen=True)
class PHIFinding:
    """Details about a detected PHI match."""

    type: str
    value: str
    start: int
    end: int


class PHIFilter:
    """Regex-driven PHI detector/redactor."""

    _DEFAULT_PATTERNS: Sequence[tuple[str, str]] = (
        ("SSN", r"\b\d{3}-\d{2}-\d{4}\b"),
        ("SSN", r"\b\d{9}\b"),
        ("PHONE", r"\b\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
        ("EMAIL", r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
        ("MRN", r"(?i)\bMRN[:\s]*\d{3,}\b"),
        ("DOB", r"\b(?:\d{2}[/\-]){2}\d{2,4}\b"),
    )

    def __init__(self, patterns: Iterable[tuple[str, str]] | None = None) -> None:
        raw_patterns = list(patterns or self._DEFAULT_PATTERNS)
        compiled: list[tuple[str, Pattern[str]]] = []
        for name, pattern in raw_patterns:
            compiled.append((name.upper(), re.compile(pattern)))
        self._patterns: Sequence[tuple[str, Pattern[str]]] = tuple(compiled)

    def detect(self, text: str) -> List[PHIFinding]:
        """Return all PHI matches in ``text``."""

        findings: list[PHIFinding] = []
        seen_ranges: set[tuple[int, int]] = set()
        for name, pattern in self._patterns:
            for match in pattern.finditer(text):
                start, end = match.span()
                key = (start, end)
                if key in seen_ranges:
                    continue
                seen_ranges.add(key)
                findings.append(
                    PHIFinding(type=name, value=match.group(), start=start, end=end)
                )
        findings.sort(key=lambda finding: finding.start)
        return findings

    def redact(self, text: str, *, label_format: str = "[REDACTED:{type}]") -> tuple[str, List[PHIFinding]]:
        """Redact PHI occurrences and return the redacted text plus findings."""

        findings = self.detect(text)
        if not findings:
            return text, []

        pieces: list[str] = []
        cursor = 0
        for finding in findings:
            if finding.start < cursor:
                continue  # overlapping match already handled
            pieces.append(text[cursor:finding.start])
            pieces.append(label_format.format(type=finding.type))
            cursor = finding.end
        pieces.append(text[cursor:])
        return "".join(pieces), findings


__all__ = ["PHIFinding", "PHIFilter"]
