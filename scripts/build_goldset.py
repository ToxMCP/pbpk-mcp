#!/usr/bin/env python3
"""Generate the synthetic literature gold set (30 documents + annotations).

The dataset is intentionally deterministic so that CI and developers can regenerate
the assets without relying on external downloads. Each entry produces:

* papers/paper-XXX.pdf             – minimalist single-page PDF with study text
* papers/paper-XXX.pdf.json        – PdfExtractKit-style layout payload
* annotations/paper-XXX.json       – Ground-truth facts & tables
* thumbnails/paper-XXX.png         – Placeholder QA thumbnail

Running this script will overwrite the existing gold-set artefacts.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass(frozen=True)
class GoldSetEntry:
    identifier: str
    weight_kg: float
    dose_mg: float
    cohort_size: int = 3

    @property
    def subject_rows(self) -> List[dict[str, str]]:
        rows: List[dict[str, str]] = []
        for idx in range(self.cohort_size):
            subject = chr(ord("A") + idx)
            weight = round(self.weight_kg + idx * 0.6, 1)
            rows.append(
                {
                    "Subject": subject,
                    "Weight (kg)": f"{weight:.1f}",
                    "Dose (mg)": f"{self.dose_mg:.1f}",
                }
            )
        return rows

    @property
    def table_matrix(self) -> dict[str, list]:
        headers = ["Subject", "Weight (kg)", "Dose (mg)"]
        return {
            "headers": headers,
            "rows": [[row[h] for h in headers] for row in self.subject_rows],
        }


DATASET: List[GoldSetEntry] = []
for index in range(1, 31):
    identifier = f"paper-{index:03d}"
    weight = round(58.0 + index * 0.9, 1)
    dose = round(35.0 + (index % 7) * 5.0, 1)
    DATASET.append(GoldSetEntry(identifier=identifier, weight_kg=weight, dose_mg=dose))

# 1x1 transparent PNG (base64 encoded)
THUMBNAIL_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg=="
)


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_pdf(path: Path, lines: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    escaped_lines = [_pdf_escape(line) for line in lines]
    content_parts = ["BT", "/F1 12 Tf", "14 TL", "72 750 Td"]
    for idx, line in enumerate(escaped_lines):
        if idx:
            content_parts.append("T*")
        content_parts.append(f"({line}) Tj")
    content_parts.append("ET")
    content = " ".join(content_parts).encode("latin-1")

    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n",
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        (
            f"5 0 obj\n<< /Length {len(content)} >>\nstream\n".encode("ascii")
            + content
            + b"\nendstream\nendobj\n"
        ),
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets: List[int] = []
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj)

    xref_position = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets:
        pdf.extend(f"{offset:010} 00000 n \n".encode("ascii"))
    pdf.extend(
        f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.write_bytes(pdf)


def _write_thumbnail(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(THUMBNAIL_BYTES)


def _write_layout(path: Path, entry: GoldSetEntry) -> None:
    layout = {
        "pages": [
            {
                "page": 1,
                "blocks": [
                    {
                        "id": "text-1",
                        "type": "text",
                        "bbox": [50, 720, 560, 760],
                        "text": (
                            f"Clinical brief for {entry.identifier}: "
                            f"weight is {entry.weight_kg:.1f} kg and dose is {entry.dose_mg:.1f} mg."
                        ),
                        "metadata": {
                            "text": (
                                f"Weight is {entry.weight_kg:.1f} kg and dose is {entry.dose_mg:.1f} mg."
                            )
                        },
                    },
                    {
                        "id": "table-1",
                        "type": "table",
                        "bbox": [50, 520, 560, 660],
                        "table": entry.table_matrix,
                        "metadata": {"table": entry.table_matrix},
                    },
                ],
            }
        ]
    }
    path.write_text(json.dumps(layout, indent=2), encoding="utf-8")


def _write_annotation(path: Path, entry: GoldSetEntry) -> None:
    annotation = {
        "sourceId": entry.identifier,
        "facts": [
            {
                "name": "body_weight_kg",
                "value": entry.weight_kg,
                "unit": "kg",
                "tolerance": 0.5,
            },
            {
                "name": "dose_mg",
                "value": entry.dose_mg,
                "unit": "mg",
                "tolerance": 0.5,
            },
        ],
        "tables": [
            {
                "componentId": "table-1",
                "rows": entry.subject_rows,
            }
        ],
    }
    path.write_text(json.dumps(annotation, indent=2), encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[1] / "reference" / "goldset"
    papers_dir = root / "papers"
    annotations_dir = root / "annotations"
    thumbnails_dir = root / "thumbnails"

    for target in (papers_dir, annotations_dir, thumbnails_dir):
        target.mkdir(parents=True, exist_ok=True)
        for child in target.glob("*"):
            if child.is_file():
                child.unlink()

    manifest_entries: list[dict[str, object]] = []
    for entry in DATASET:
        pdf_path = papers_dir / f"{entry.identifier}.pdf"
        layout_path = papers_dir / f"{entry.identifier}.pdf.json"
        annotation_path = annotations_dir / f"{entry.identifier}.json"
        thumbnail_path = thumbnails_dir / f"{entry.identifier}.png"

        text_lines = [
            f"Model Qualification Report {entry.identifier}",
            f"Weight is {entry.weight_kg:.1f} kg.",
            f"Dose is {entry.dose_mg:.1f} mg.",
            "Refer to Table 1 for cohort specifics.",
        ]
        _write_pdf(pdf_path, text_lines)
        _write_layout(layout_path, entry)
        _write_annotation(annotation_path, entry)
        _write_thumbnail(thumbnail_path)

        manifest_entries.append(
            {
                "sourceId": entry.identifier,
                "pdf": f"papers/{entry.identifier}.pdf",
                "annotation": f"annotations/{entry.identifier}.json",
                "thumbnail": f"thumbnails/{entry.identifier}.png",
                "tableComponent": "table-1",
            }
        )

    manifest = {
        "version": 1,
        "thresholds": {"fact_accuracy": 0.95, "table_row_recall": 0.90},
        "entries": manifest_entries,
    }
    (root / "index.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote {len(manifest_entries)} gold-set documents to {root}")


if __name__ == "__main__":
    main()
