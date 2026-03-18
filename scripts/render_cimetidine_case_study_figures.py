#!/usr/bin/env python3

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(
    "/Volumes/Storage/topotox_offload/20260220_space_relief/manual_offload/PBPK_MCP/var/demos/cimetidine"
)
OUTPUTS_ROOT = ROOT / "outputs"

SCENARIOS = [
    "po 200 mg, Kanto 1981, n=8",
    "po 400 mg (tab), Somogyi 1981, n=8",
    "po 800 mg, Bodemar 1981, n=9",
]

COLORS = {
    SCENARIOS[0]: (27, 94, 32),
    SCENARIOS[1]: (21, 101, 192),
    SCENARIOS[2]: (183, 28, 28),
}


def dose_mg(name: str) -> int:
    match = re.search(r"po\s+(\d+)\s*mg", name)
    if not match:
        raise ValueError(f"Could not parse dose from scenario: {name}")
    return int(match.group(1))


def load_data():
    data = {}
    for scenario in SCENARIOS:
        scenario_dir = OUTPUTS_ROOT / scenario
        csv_path = next(scenario_dir.glob("*-Results.csv"))
        json_path = next(scenario_dir.glob("*.json"))

        with csv_path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            columns = reader.fieldnames

        time_col = next(col for col in columns if col.startswith("Time ["))
        peripheral_col = next(
            col
            for col in columns
            if "PeripheralVenousBlood" in col
            and "Plasma (Peripheral Venous Blood)" in col
        )
        venous_col = next(
            col
            for col in columns
            if "VenousBlood|Plasma|Cimetidine|Concentration in container" in col
        )
        urine_col = next(
            (col for col in columns if "Fraction excreted to urine" in col), None
        )
        absorbed_col = next(
            col
            for col in columns
            if "Fraction of oral drug mass absorbed into mucosa" in col
        )

        with json_path.open() as handle:
            exported = json.load(handle)

        times_h = [float(row[time_col]) / 60.0 for row in rows]
        peripheral = [float(row[peripheral_col]) for row in rows]
        venous = [float(row[venous_col]) for row in rows]
        urine = [float(row[urine_col]) for row in rows] if urine_col else None
        absorbed = [float(row[absorbed_col]) for row in rows]

        data[scenario] = {
            "dose_mg": dose_mg(scenario),
            "csv_path": csv_path,
            "json_path": json_path,
            "times_h": times_h,
            "peripheral": peripheral,
            "venous": venous,
            "urine": urine,
            "absorbed": absorbed,
            "output_values": [
                item.get("Path") or item.get("Name") or item.get("QuantityPath")
                for item in exported.get("OutputValues", [])
                if isinstance(item, dict)
            ],
        }
    return data


def trapezoid(xs, ys):
    total = 0.0
    for idx in range(1, len(xs)):
        total += 0.5 * (ys[idx] + ys[idx - 1]) * (xs[idx] - xs[idx - 1])
    return total


def compute_metrics(data):
    rows = []
    for scenario in SCENARIOS:
        series = data[scenario]
        ys = series["peripheral"]
        xs = series["times_h"]
        cmax = max(ys)
        rows.append(
            {
                "scenario": scenario,
                "dose_mg": series["dose_mg"],
                "cmax_umol_per_l": cmax,
                "tmax_h": xs[ys.index(cmax)],
                "auc_last_umol_h_per_l": trapezoid(xs, ys),
            }
        )
    return rows


def create_canvas(width=1400, height=900):
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    return image, draw, font


def draw_text(draw, xy, text, font, fill=(20, 20, 20)):
    draw.text(xy, text, font=font, fill=fill)


def draw_line_plot(
    path,
    title,
    subtitle,
    x_label,
    y_label,
    series_map,
    colors,
    y_transform=None,
    y_ticks=None,
    legend_formatter=None,
):
    image, draw, font = create_canvas()
    width, height = image.size
    left, right, top, bottom = 110, 70, 100, 110
    plot_w = width - left - right
    plot_h = height - top - bottom

    all_points = []
    for _, points in series_map.items():
        all_points.extend(points)

    x_values = [x for x, _ in all_points]
    y_values = [y for _, y in all_points]

    if y_transform is None:
        transformed = lambda y: y
        y_min = 0.0
        y_max = max(y_values) * 1.08
    else:
        transformed = y_transform
        y_min = min(transformed(y) for y in y_values)
        y_max = max(transformed(y) for y in y_values)

    x_min = min(x_values)
    x_max = max(x_values)

    def sx(value):
        return left + (value - x_min) / (x_max - x_min) * plot_w

    def sy(value):
        y = transformed(value)
        return top + plot_h - (y - y_min) / (y_max - y_min) * plot_h

    axis = (40, 40, 40)
    grid = (225, 225, 225)

    draw.line((left, top + plot_h, left + plot_w, top + plot_h), fill=axis, width=2)
    draw.line((left, top, left, top + plot_h), fill=axis, width=2)

    for idx in range(9):
        x_tick = x_min + (x_max - x_min) * idx / 8.0
        px = sx(x_tick)
        draw.line((px, top, px, top + plot_h), fill=grid, width=1)
        draw_text(draw, (px - 8, top + plot_h + 10), f"{x_tick:.0f}", font)

    if y_ticks is None:
        tick_values = [y_min + (y_max - y_min) * idx / 6.0 for idx in range(7)]
        tick_labels = [f"{tick:.1f}" for tick in tick_values]
    else:
        tick_values = [tick[0] for tick in y_ticks]
        tick_labels = [tick[1] for tick in y_ticks]

    for tick_value, label in zip(tick_values, tick_labels):
        if y_transform is None:
            plot_y = top + plot_h - (tick_value - y_min) / (y_max - y_min) * plot_h
        else:
            plot_y = top + plot_h - (tick_value - y_min) / (y_max - y_min) * plot_h
        draw.line((left, plot_y, left + plot_w, plot_y), fill=grid, width=1)
        draw_text(draw, (12, plot_y - 6), label, font)

    draw_text(draw, (width // 2 - 170, 24), title, font)
    draw_text(draw, (left, 50), subtitle, font, fill=(80, 80, 80))
    draw_text(draw, (width // 2 - 30, height - 36), x_label, font)
    draw_text(draw, (12, 16), y_label, font)

    for scenario, points in series_map.items():
        polyline = []
        for x_value, y_value in points:
            polyline.extend((sx(x_value), sy(y_value)))
        draw.line(polyline, fill=colors[scenario], width=4)

    legend_x = width - 305
    legend_y = 120
    for scenario in SCENARIOS:
        label = (
            legend_formatter(scenario)
            if legend_formatter is not None
            else f"{dose_mg(scenario)} mg"
        )
        draw.line((legend_x, legend_y + 7, legend_x + 32, legend_y + 7), fill=colors[scenario], width=4)
        draw_text(draw, (legend_x + 42, legend_y), label, font)
        legend_y += 24

    image.save(path)


def draw_dual_panel_metrics(path, metrics):
    image, draw, font = create_canvas(width=1400, height=820)
    width, height = image.size
    margin = 70
    gap = 70
    panel_w = (width - margin * 2 - gap) // 2
    panel_h = 520
    top = 140

    titles = [
        ("Cmax (umol/L)", "cmax_umol_per_l"),
        ("AUC_last (umol*h/L)", "auc_last_umol_h_per_l"),
    ]

    draw_text(draw, (width // 2 - 120, 24), "Cimetidine PK summary", font)
    draw_text(
        draw,
        (margin, 56),
        "Three predefined oral scenarios exported from the official public OSP cimetidine project.",
        font,
        fill=(80, 80, 80),
    )

    for panel_idx, (panel_title, key) in enumerate(titles):
        x0 = margin + panel_idx * (panel_w + gap)
        y0 = top
        x1 = x0 + panel_w
        y1 = y0 + panel_h
        draw.rectangle((x0, y0, x1, y1), outline=(40, 40, 40), width=2)
        draw_text(draw, (x0 + 10, y0 - 24), panel_title, font)

        values = [row[key] for row in metrics]
        max_value = max(values) * 1.10
        bar_w = 90
        spacing = (panel_w - 3 * bar_w) // 4

        for idx, row in enumerate(metrics):
            bx0 = x0 + spacing + idx * (bar_w + spacing)
            bx1 = bx0 + bar_w
            bar_h = (row[key] / max_value) * (panel_h - 90)
            by1 = y1 - 40
            by0 = by1 - bar_h
            draw.rectangle((bx0, by0, bx1, by1), fill=COLORS[row["scenario"]], outline=COLORS[row["scenario"]])
            draw_text(draw, (bx0 + 10, by1 + 8), f'{row["dose_mg"]} mg', font)
            draw_text(draw, (bx0 + 4, by0 - 16), f'{row[key]:.2f}', font)

    image.save(path)


def draw_baseline_panel(path, baseline):
    image, draw, font = create_canvas(width=1500, height=980)
    width, height = image.size
    margin_x = 80
    margin_y = 110
    gap_x = 60
    gap_y = 80
    panel_w = (width - margin_x * 2 - gap_x) // 2
    panel_h = (height - margin_y * 2 - gap_y) // 2

    panels = [
        ("Peripheral venous plasma", baseline["times_h"], baseline["peripheral"], (27, 94, 32), "umol/L"),
        ("Venous plasma", baseline["times_h"], baseline["venous"], (21, 101, 192), "umol/L"),
        ("Fraction absorbed to mucosa", baseline["times_h"], baseline["absorbed"], (183, 28, 28), "fraction"),
        ("Fraction excreted to urine", baseline["times_h"], baseline["urine"], (140, 90, 0), "fraction"),
    ]

    draw_text(draw, (width // 2 - 120, 24), "Baseline process view: 200 mg oral cimetidine", font)
    draw_text(
        draw,
        (margin_x, 58),
        "Scenario: po 200 mg, Kanto 1981, n=8",
        font,
        fill=(80, 80, 80),
    )

    for idx, (title, xs, ys, color, unit) in enumerate(panels):
        col = idx % 2
        row = idx // 2
        x0 = margin_x + col * (panel_w + gap_x)
        y0 = margin_y + row * (panel_h + gap_y)
        x1 = x0 + panel_w
        y1 = y0 + panel_h
        draw.rectangle((x0, y0, x1, y1), outline=(40, 40, 40), width=2)
        draw_text(draw, (x0 + 10, y0 - 22), f"{title} ({unit})", font)

        x_min, x_max = min(xs), max(xs)
        y_min = 0.0
        y_max = max(ys) * 1.08 if max(ys) > 0 else 1.0

        def sx(value):
            return x0 + 50 + (value - x_min) / (x_max - x_min) * (panel_w - 70)

        def sy(value):
            return y0 + panel_h - 40 - (value - y_min) / (y_max - y_min) * (panel_h - 70)

        draw.line((x0 + 50, y0 + panel_h - 40, x1 - 20, y0 + panel_h - 40), fill=(40, 40, 40), width=2)
        draw.line((x0 + 50, y0 + 15, x0 + 50, y0 + panel_h - 40), fill=(40, 40, 40), width=2)

        for tick_idx in range(5):
            xt = x_min + (x_max - x_min) * tick_idx / 4.0
            px = sx(xt)
            draw.line((px, y0 + 15, px, y0 + panel_h - 40), fill=(230, 230, 230), width=1)
            draw_text(draw, (px - 8, y0 + panel_h - 28), f"{xt:.0f}", font)

        for tick_idx in range(5):
            yt = y_min + (y_max - y_min) * tick_idx / 4.0
            py = sy(yt)
            draw.line((x0 + 50, py, x1 - 20, py), fill=(230, 230, 230), width=1)
            draw_text(draw, (x0 + 6, py - 6), f"{yt:.2f}" if y_max <= 1.2 else f"{yt:.1f}", font)

        polyline = []
        for xv, yv in zip(xs, ys):
            polyline.extend((sx(xv), sy(yv)))
        draw.line(polyline, fill=color, width=4)

    image.save(path)


def write_manifest(metrics):
    lines = [
        "# Additional cimetidine case-study figures",
        "",
        "- `cimetidine_plasma_comparison_linear.png`: three-scenario oral exposure comparison on a linear y-axis.",
        "- `cimetidine_plasma_comparison_semilog.png`: same comparison on a semilog-style y-axis to expose the terminal phase.",
        "- `cimetidine_dose_normalized_plasma_comparison.png`: plasma exposure normalized by administered mg dose.",
        "- `cimetidine_pk_summary.png`: side-by-side bar summaries for Cmax and AUC_last.",
        "- `cimetidine_baseline_processes.png`: baseline 200 mg process panel showing plasma, absorption, and urinary excretion traces.",
        "",
        "## PK summary",
        "",
    ]
    for row in metrics:
        lines.append(
            f"- `{row['dose_mg']} mg`: Cmax `{row['cmax_umol_per_l']:.6f} umol/L`, "
            f"Tmax `{row['tmax_h']:.2f} h`, AUC_last `{row['auc_last_umol_h_per_l']:.6f} umol*h/L`."
        )
    (ROOT / "figures.md").write_text("\n".join(lines) + "\n")


def main():
    data = load_data()
    metrics = compute_metrics(data)

    linear_series = {
        scenario: list(zip(data[scenario]["times_h"], data[scenario]["peripheral"]))
        for scenario in SCENARIOS
    }
    draw_line_plot(
        ROOT / "cimetidine_plasma_comparison_linear.png",
        title="Cimetidine oral exposure comparison",
        subtitle="Peripheral venous plasma concentration across three predefined oral scenarios.",
        x_label="Time (h)",
        y_label="Peripheral venous plasma cimetidine (umol/L)",
        series_map=linear_series,
        colors=COLORS,
    )

    positive = [
        value
        for scenario in SCENARIOS
        for value in data[scenario]["peripheral"]
        if value > 0
    ]
    log_floor = min(positive) / 4.0

    def log_transform(value):
        return math.log10(max(value, log_floor))

    log_ticks = []
    tick_values = [0.01, 0.1, 1.0, 10.0]
    for tick in tick_values:
        if log_floor <= tick <= max(positive) * 1.1:
            log_ticks.append((math.log10(tick), f"{tick:g}"))

    draw_line_plot(
        ROOT / "cimetidine_plasma_comparison_semilog.png",
        title="Cimetidine oral exposure comparison",
        subtitle="Semilog y-axis view to expose early and terminal concentration behavior.",
        x_label="Time (h)",
        y_label="Peripheral venous plasma cimetidine (umol/L, log scale)",
        series_map=linear_series,
        colors=COLORS,
        y_transform=log_transform,
        y_ticks=log_ticks,
    )

    dose_normalized = {
        scenario: [
            (time_h, concentration / data[scenario]["dose_mg"])
            for time_h, concentration in zip(
                data[scenario]["times_h"], data[scenario]["peripheral"]
            )
        ]
        for scenario in SCENARIOS
    }
    draw_line_plot(
        ROOT / "cimetidine_dose_normalized_plasma_comparison.png",
        title="Dose-normalized cimetidine exposure",
        subtitle="Peripheral venous plasma concentration normalized by administered oral mg dose.",
        x_label="Time (h)",
        y_label="Peripheral venous plasma cimetidine (umol/L per mg)",
        series_map=dose_normalized,
        colors=COLORS,
    )

    draw_dual_panel_metrics(ROOT / "cimetidine_pk_summary.png", metrics)
    draw_baseline_panel(ROOT / "cimetidine_baseline_processes.png", data[SCENARIOS[0]])
    write_manifest(metrics)

    written = [
        "cimetidine_plasma_comparison_linear.png",
        "cimetidine_plasma_comparison_semilog.png",
        "cimetidine_dose_normalized_plasma_comparison.png",
        "cimetidine_pk_summary.png",
        "cimetidine_baseline_processes.png",
        "figures.md",
    ]
    for item in written:
        print(ROOT / item)


if __name__ == "__main__":
    main()
