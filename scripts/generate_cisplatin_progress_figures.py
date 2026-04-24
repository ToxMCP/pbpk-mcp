#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = []
    if bold:
        candidates.extend(
            [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/Library/Fonts/Arial Bold.ttf",
                "/System/Library/Fonts/SFNS.ttf",
            ]
        )
    candidates.extend(
        [
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/Library/Fonts/Arial.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        ]
    )
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def build_step1_progress_figure(output_dir: Path) -> Path:
    domains = [
        "Context of use",
        "Predictive evidence",
        "Transport justification",
        "Parameter provenance",
        "Uncertainty package",
        "Platform and governance",
    ]
    baseline = [2.0, 0.5, 1.0, 1.0, 1.5, 1.0]
    step1 = [3.0, 0.5, 1.0, 1.0, 1.5, 1.0]

    output_dir.mkdir(parents=True, exist_ok=True)
    figure_path = output_dir / "cisplatin_step1_qualification_progress.png"

    image = Image.new("RGB", (1400, 900), "#ffffff")
    draw = ImageDraw.Draw(image)

    title_font = load_font(34, bold=True)
    subtitle_font = load_font(20)
    label_font = load_font(18)
    small_font = load_font(15)

    draw.text((90, 55), "Cisplatin PBPK Regulatory Upgrade: Step 1 Progress", fill="#183247", font=title_font)
    draw.text(
        (90, 102),
        "Step 1 completed: context of use, workflow role, population support, evidence basis, and claim boundaries.",
        fill="#4f5f6f",
        font=subtitle_font,
    )

    chart_left = 420
    chart_right = 1240
    chart_top = 180
    row_gap = 88
    group_bar_height = 18
    bar_gap = 8
    scale_width = chart_right - chart_left

    level_labels = [
        "0 Missing",
        "1 Generic",
        "2 Bounded",
        "3 Dossier-specified",
        "4 Externally qualified",
    ]

    for tick in range(5):
        x = chart_left + int((tick / 4) * scale_width)
        draw.line((x, chart_top - 10, x, chart_top + row_gap * len(domains) - 16), fill="#dfe6ee", width=2)
        label_bbox = draw.textbbox((0, 0), level_labels[tick], font=small_font)
        label_width = label_bbox[2] - label_bbox[0]
        draw.text((x - label_width / 2, chart_top + row_gap * len(domains)), level_labels[tick], fill="#607182", font=small_font)

    draw.line((chart_left, chart_top - 10, chart_right, chart_top - 10), fill="#9aa9b8", width=2)

    baseline_fill = "#d7dee8"
    baseline_edge = "#7f8ea3"
    step1_fill = "#3f7cac"
    step1_edge = "#274f6a"

    for index, domain in enumerate(domains):
        y = chart_top + index * row_gap
        label_bbox = draw.textbbox((0, 0), domain, font=label_font)
        label_height = label_bbox[3] - label_bbox[1]
        draw.text((90, y - label_height / 2 + 2), domain, fill="#243447", font=label_font)

        baseline_top = y - group_bar_height - bar_gap // 2
        baseline_bottom = y - bar_gap // 2
        step1_top = y + bar_gap // 2
        step1_bottom = y + group_bar_height + bar_gap // 2

        baseline_width = int((baseline[index] / 4) * scale_width)
        step1_width = int((step1[index] / 4) * scale_width)

        draw.rounded_rectangle(
            (chart_left, baseline_top, chart_left + baseline_width, baseline_bottom),
            radius=7,
            fill=baseline_fill,
            outline=baseline_edge,
            width=2,
        )
        draw.rounded_rectangle(
            (chart_left, step1_top, chart_left + step1_width, step1_bottom),
            radius=7,
            fill=step1_fill,
            outline=step1_edge,
            width=2,
        )

        draw.text((chart_left + baseline_width + 10, baseline_top - 2), f"{baseline[index]:.1f}", fill="#243447", font=small_font)
        draw.text((chart_left + step1_width + 10, step1_top - 2), f"{step1[index]:.1f}", fill="#243447", font=small_font)

    legend_y = 730
    draw.rounded_rectangle((90, legend_y, 128, legend_y + 24), radius=5, fill=baseline_fill, outline=baseline_edge, width=2)
    draw.text((145, legend_y + 1), "Audit baseline", fill="#243447", font=label_font)
    draw.rounded_rectangle((340, legend_y, 378, legend_y + 24), radius=5, fill=step1_fill, outline=step1_edge, width=2)
    draw.text((395, legend_y + 1), "After step 1", fill="#243447", font=label_font)

    footer = (
        "Scores are qualitative audit judgments from the 2026-04-08 cisplatin review. "
        "This step improves only the context and claim-boundary domain. Predictive evidence, "
        "transport justification, provenance, uncertainty, and governance still need substantive upgrades."
    )
    footer_lines = "\n".join(textwrap.wrap(footer, width=115))
    draw.multiline_text((90, 790), footer_lines, fill="#4f5f6f", font=small_font, spacing=5)

    image.save(figure_path)
    return figure_path


def build_step2_inventory_figure(output_dir: Path, inventory_path: Path) -> Path:
    payload = json.loads(inventory_path.read_text())
    studies = payload["studies"]

    output_dir.mkdir(parents=True, exist_ok=True)
    figure_path = output_dir / "cisplatin_step2_benchmark_inventory.png"

    image = Image.new("RGB", (1640, 1080), "#ffffff")
    draw = ImageDraw.Draw(image)

    title_font = load_font(34, bold=True)
    subtitle_font = load_font(20)
    header_font = load_font(18, bold=True)
    body_font = load_font(16)
    small_font = load_font(14)

    draw.text((70, 50), "Cisplatin PBPK Regulatory Upgrade: Step 2 Benchmark Inventory", fill="#183247", font=title_font)
    draw.text(
        (70, 97),
        "Adult IV study records are now attached to the performance dossier as traceability-only benchmark inventory.",
        fill="#4f5f6f",
        font=subtitle_font,
    )
    draw.text(
        (70, 125),
        "Observed-versus-predicted rows are still pending full-text extraction and digitization.",
        fill="#7a5a00",
        font=subtitle_font,
    )

    table_left = 70
    table_top = 190
    row_height = 86
    table_width = 1490
    columns = [
        ("Study", 280),
        ("Role", 240),
        ("Plasma PK", 120),
        ("Urine PK", 120),
        ("Kidney link", 140),
        ("Analyte class", 310),
        ("Status", 280),
    ]

    x_positions = [table_left]
    for _, width in columns:
        x_positions.append(x_positions[-1] + width)

    draw.rounded_rectangle((table_left, table_top, table_left + table_width, table_top + 52), radius=10, fill="#edf3f9", outline="#c2d0dd", width=2)
    for index, (label, _) in enumerate(columns):
        draw.text((x_positions[index] + 12, table_top + 15), label, fill="#183247", font=header_font)

    role_colors = {
        "calibration-candidate": ("#2d6a4f", "#d8f3dc"),
        "external-validation-candidate": ("#9c6644", "#f7eadf"),
        "qualification-support-secondary": ("#5c677d", "#e9ecef"),
    }

    for row_index, study in enumerate(studies):
        top = table_top + 62 + row_index * row_height
        bottom = top + row_height - 8
        fill = "#ffffff" if row_index % 2 == 0 else "#f9fbfd"
        draw.rounded_rectangle((table_left, top, table_left + table_width, bottom), radius=8, fill=fill, outline="#dde5ed", width=1)

        study_label = f"{study['shortLabel']} ({study['pmid']})"
        draw.text((x_positions[0] + 12, top + 11), study_label, fill="#243447", font=header_font)
        study_lines = "Matrices: " + ", ".join(study["matrices"])
        study_lines = "\n".join(textwrap.wrap(study_lines, width=28))
        draw.multiline_text((x_positions[0] + 12, top + 37), study_lines, fill="#5b6b7b", font=small_font, spacing=3)

        role = study["benchmarkRole"]
        role_outline, role_fill = role_colors.get(role, ("#607182", "#eef2f6"))
        badge_left = x_positions[1] + 12
        badge_top = top + 16
        badge_right = x_positions[1] + columns[1][1] - 16
        badge_bottom = top + 48
        draw.rounded_rectangle((badge_left, badge_top, badge_right, badge_bottom), radius=8, fill=role_fill, outline=role_outline, width=2)
        role_label = role.replace("-", " ")
        draw.multiline_text((badge_left + 10, badge_top + 5), "\n".join(textwrap.wrap(role_label, width=18)), fill=role_outline, font=small_font, spacing=2)

        for col_index, flag in ((2, study["supportsPlasmaPk"]), (3, study["supportsUrinePk"]), (4, study["supportsNephrotoxicityLink"])):
            cell_left = x_positions[col_index] + 38
            cell_top = top + 22
            cell_right = cell_left + 42
            cell_bottom = cell_top + 42
            if flag:
                draw.rounded_rectangle((cell_left, cell_top, cell_right, cell_bottom), radius=8, fill="#3f7cac", outline="#274f6a", width=2)
                draw.text((cell_left + 12, cell_top + 7), "Y", fill="#ffffff", font=header_font)
            else:
                draw.rounded_rectangle((cell_left, cell_top, cell_right, cell_bottom), radius=8, fill="#f1f4f7", outline="#b7c2ce", width=2)
                draw.text((cell_left + 12, cell_top + 7), "-", fill="#607182", font=header_font)

        analyte_text = ", ".join(study["analytes"])
        draw.multiline_text(
            (x_positions[5] + 12, top + 12),
            "\n".join(textwrap.wrap(analyte_text, width=30)),
            fill="#243447",
            font=body_font,
            spacing=4,
        )
        status_text = study["extractionStatus"].replace("-", " ")
        draw.multiline_text(
            (x_positions[6] + 12, top + 12),
            "\n".join(textwrap.wrap(status_text, width=24)),
            fill="#5b6b7b",
            font=body_font,
            spacing=4,
        )

    calibration_count = sum(1 for item in studies if item["benchmarkRole"] == "calibration-candidate")
    external_count = sum(1 for item in studies if item["benchmarkRole"] == "external-validation-candidate")
    secondary_count = sum(1 for item in studies if item["benchmarkRole"] == "qualification-support-secondary")
    plasma_count = sum(1 for item in studies if item["supportsPlasmaPk"])
    urine_count = sum(1 for item in studies if item["supportsUrinePk"])
    nephrotox_count = sum(1 for item in studies if item["supportsNephrotoxicityLink"])

    summary_top = table_top + 62 + len(studies) * row_height + 18
    summary_text = (
        f"Inventory summary: {len(studies)} adult IV studies curated. "
        f"Calibration candidates: {calibration_count}. "
        f"External validation candidates: {external_count}. "
        f"Secondary qualification-support studies: {secondary_count}. "
        f"Plasma PK coverage: {plasma_count} studies. "
        f"Urine PK coverage: {urine_count} studies. "
        f"Kidney-injury linkage: {nephrotox_count} studies."
    )
    draw.multiline_text((70, summary_top), "\n".join(textwrap.wrap(summary_text, width=150)), fill="#243447", font=body_font, spacing=4)

    footer = (
        "This figure shows traceability coverage only. It does not mean the cisplatin model has already passed predictive validation. "
        "The next upgrade is full-text extraction plus observed-versus-predicted row creation."
    )
    draw.multiline_text((70, summary_top + 55), "\n".join(textwrap.wrap(footer, width=150)), fill="#7a5a00", font=small_font, spacing=4)

    image.save(figure_path)
    return figure_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate cisplatin regulatory-upgrade progress figures.")
    parser.add_argument(
        "--output-dir",
        default="output/cisplatin_regulatory_upgrade/figures",
        help="Directory for generated figure artifacts.",
    )
    parser.add_argument(
        "--inventory-path",
        default="var/models/rxode2/cisplatin/cisplatin_benchmark_study_inventory.json",
        help="Path to the cisplatin benchmark inventory JSON file.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    step1_path = build_step1_progress_figure(output_dir)
    print(step1_path)

    inventory_path = Path(args.inventory_path)
    if inventory_path.exists():
        step2_path = build_step2_inventory_figure(output_dir, inventory_path)
        print(step2_path)


if __name__ == "__main__":
    main()
