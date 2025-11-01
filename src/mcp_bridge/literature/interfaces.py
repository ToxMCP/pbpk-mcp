"""Protocol definitions for literature ingestion pipeline components."""

from __future__ import annotations

from typing import Iterable, Protocol

from .models import ExtractionRecord, LiteratureExtractionResult, DocumentComponent


class LayoutExtractor(Protocol):
    """Extracts document components from a PDF file."""

    def extract(self, pdf_path: str) -> Iterable[DocumentComponent]:
        """Return an iterable of detected components ordered by appearance."""


class TextExtractor(Protocol):
    """Processes text components and yields structured records."""

    def extract(self, component: DocumentComponent) -> ExtractionRecord:
        ...


class TableExtractor(Protocol):
    """Processes table components and yields structured records."""

    def extract(self, component: DocumentComponent) -> ExtractionRecord:
        ...


class FigureExtractor(Protocol):
    """Processes figure/plot components and yields structured records."""

    def extract(self, component: DocumentComponent) -> ExtractionRecord:
        ...


class PostProcessor(Protocol):
    """Optional hook to post-process the aggregated extraction result."""

    def refine(self, result: LiteratureExtractionResult) -> LiteratureExtractionResult:
        ...

