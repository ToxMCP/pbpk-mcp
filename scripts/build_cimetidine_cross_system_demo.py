#!/usr/bin/env python3

import csv
import json
import math
import re
import shutil
import subprocess
import textwrap
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(
    "/Volumes/Storage/topotox_offload/20260220_space_relief/manual_offload/PBPK_MCP/var/demos/cimetidine_cross_system"
)
OUTPUTS_DIR = ROOT / "outputs"
PBPK_CONTAINER = "pbpk_mcp-api-1"
PBPK_PROJECT = "/home/mcp/Cimetidine-Model.pksim5"
PBPK_SNAPSHOT = "/home/mcp/Cimetidine-Model.json"
PBPK_EXPORT_DIR = "/home/mcp/cimetidine_cross_export"

COMPT0X_BASE = "http://127.0.0.1:8005/mcp"
AOP_BASE = "http://127.0.0.1:8003/mcp"

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


def run_cmd(args, *, capture=True):
    return subprocess.run(
        args,
        check=True,
        text=True,
        capture_output=capture,
    )


def mcp_call(base_url: str, method: str, params: dict, request_id: int):
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": method,
        "params": params,
    }
    request = urllib.request.Request(
        base_url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def write_json(path: Path, obj):
    path.write_text(json.dumps(obj, indent=2))


def dose_mg(name: str) -> int:
    match = re.search(r"po\s+(\d+)\s*mg", name)
    if not match:
        raise ValueError(f"Could not parse dose from scenario: {name}")
    return int(match.group(1))


def trapezoid(xs, ys):
    total = 0.0
    for idx in range(1, len(xs)):
        total += 0.5 * (ys[idx] + ys[idx - 1]) * (xs[idx] - xs[idx - 1])
    return total


def prepare_workspace():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def run_pbpk_export():
    shell = textwrap.dedent(
        f"""
        set -e
        rm -rf {PBPK_EXPORT_DIR}
        mkdir -p {PBPK_EXPORT_DIR}
        test -f {PBPK_PROJECT} || {{
          cp /app/var/models/Cimetidine-Model.pksim5 {PBPK_PROJECT}
          chmod u+w {PBPK_PROJECT}
        }}
        test -f {PBPK_SNAPSHOT} || {{
          cp /app/var/models/Cimetidine-Model.json {PBPK_SNAPSHOT}
          chmod u+w {PBPK_SNAPSHOT}
        }}
        cd /home/mcp
        Rscript -e 'library(ospsuite); library(rSharp); ospsuite:::initPKSim(); api <- getType("PKSim.R.Api"); pt <- api$call("GetMethod", "RunSimulationExport")$call("GetParameters")[[1]]$get("ParameterType"); opts <- callStatic("System.Activator", "CreateInstance", pt); tname <- paste0("System.Collections.Generic.List", intToUtf8(96), "1[System.String]"); lt <- getType(tname); sims <- callStatic("System.Activator", "CreateInstance", lt); for (nm in c("po 200 mg, Kanto 1981, n=8", "po 400 mg (tab), Somogyi 1981, n=8", "po 800 mg, Bodemar 1981, n=9")) sims$call("Add", nm); opts$set("ProjectFile", "{PBPK_PROJECT}"); opts$set("OutputFolder", "{PBPK_EXPORT_DIR}"); opts$set("RunSimulation", TRUE); opts$set("ExportAllSimulationsIfListIsEmpty", FALSE); opts$set("Simulations", sims); opts$set("ExportMode", 3, asInteger=TRUE); callStatic("PKSim.R.Api", "RunSimulationExport", opts)'
        """
    ).strip()
    run_cmd(["docker", "exec", PBPK_CONTAINER, "sh", "-lc", shell])
    run_cmd(["docker", "cp", f"{PBPK_CONTAINER}:{PBPK_EXPORT_DIR}/.", str(OUTPUTS_DIR)])
    run_cmd(["docker", "cp", f"{PBPK_CONTAINER}:{PBPK_PROJECT}", str(ROOT / "Cimetidine-Model.pksim5")])
    run_cmd(["docker", "cp", f"{PBPK_CONTAINER}:{PBPK_SNAPSHOT}", str(ROOT / "Cimetidine-Model.json")])


def fetch_context():
    comptox_search = mcp_call(
        COMPT0X_BASE,
        "tools/call",
        {"name": "search_chemical", "arguments": {"query": "cimetidine", "search_type": "equals"}},
        1,
    )
    details = mcp_call(
        COMPT0X_BASE,
        "tools/call",
        {
            "name": "get_chemical_details",
            "arguments": {"identifier": "DTXSID4020329", "id_type": "dtxsid", "subset": "all"},
        },
        2,
    )
    bioactivity = mcp_call(
        COMPT0X_BASE,
        "tools/call",
        {"name": "get_bioactivity_summary_by_dtxsid", "arguments": {"dtxsid": "DTXSID4020329"}},
        3,
    )
    httk = mcp_call(
        COMPT0X_BASE,
        "tools/call",
        {"name": "search_httk", "arguments": {"dtxsid": "DTXSID4020329"}},
        4,
    )

    aop_direct = mcp_call(
        AOP_BASE,
        "tools/call",
        {"name": "map_chemical_to_aops", "arguments": {"name": "cimetidine"}},
        5,
    )
    aop_liver = mcp_call(
        AOP_BASE,
        "tools/call",
        {"name": "search_aops", "arguments": {"text": "liver", "limit": 5}},
        6,
    )
    aop_27 = mcp_call(
        AOP_BASE,
        "tools/call",
        {"name": "get_aop", "arguments": {"aop_id": "AOP:27"}},
        7,
    )
    aop_27_ke = mcp_call(
        AOP_BASE,
        "tools/call",
        {"name": "list_key_events", "arguments": {"aop_id": "AOP:27"}},
        8,
    )
    aop_494 = mcp_call(
        AOP_BASE,
        "tools/call",
        {"name": "get_aop", "arguments": {"aop_id": "AOP:494"}},
        9,
    )
    aop_494_ke = mcp_call(
        AOP_BASE,
        "tools/call",
        {"name": "list_key_events", "arguments": {"aop_id": "AOP:494"}},
        10,
    )

    context = {
        "comptox_search": comptox_search,
        "comptox_details": details,
        "comptox_bioactivity": bioactivity,
        "comptox_httk": httk,
        "aop_direct": aop_direct,
        "aop_liver_search": aop_liver,
        "aop_27": aop_27,
        "aop_27_key_events": aop_27_ke,
        "aop_494": aop_494,
        "aop_494_key_events": aop_494_ke,
    }
    return context


def persist_context(context):
    for name, payload in context.items():
        write_json(ROOT / f"{name}.json", payload)


def load_pbpk_results():
    data = {}
    for scenario in SCENARIOS:
        scenario_dir = OUTPUTS_DIR / scenario
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
        urine_col = next((col for col in columns if "Fraction excreted to urine" in col), None)
        absorbed_col = next(
            col for col in columns if "Fraction of oral drug mass absorbed into mucosa" in col
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
            "times_h": times_h,
            "peripheral": peripheral,
            "venous": venous,
            "urine": urine,
            "absorbed": absorbed,
            "csv_path": str(csv_path.resolve()),
            "json_path": str(json_path.resolve()),
            "available_outputs": [
                item.get("Path") or item.get("Name") or item.get("QuantityPath")
                for item in exported.get("OutputValues", [])
                if isinstance(item, dict)
            ],
        }
    return data


def build_summaries(context, pbpk):
    details = context["comptox_details"]["result"]["structuredContent"]
    bio = context["comptox_bioactivity"]["result"]["structuredContent"]["data"][0]
    httk = context["comptox_httk"]["result"]["structuredContent"]["data"]
    aop_direct = context["aop_direct"]["result"]["structuredContent"]["results"]
    aop_liver = context["aop_liver_search"]["result"]["structuredContent"]["results"]
    aop27 = context["aop_27"]["result"]["structuredContent"]
    aop27_kes = context["aop_27_key_events"]["result"]["structuredContent"]["results"]
    aop494 = context["aop_494"]["result"]["structuredContent"]
    aop494_kes = context["aop_494_key_events"]["result"]["structuredContent"]["results"]

    httk_summary = {}
    for record in httk:
        if record.get("species") == "Human" and record.get("parameter") == "TK.Half.Life":
            httk_summary["human_half_life_h"] = record.get("predicted")
        if (
            record.get("species") == "Human"
            and record.get("parameter") == "Css"
            and record.get("model") == "PBTK"
        ):
            httk_summary[f"human_css_{record.get('percentile').lower()}_mg_per_l"] = record.get("predicted")

    scenario_rows = []
    for scenario in SCENARIOS:
        series = pbpk[scenario]
        cmax = max(series["peripheral"])
        tmax = series["times_h"][series["peripheral"].index(cmax)]
        auc = trapezoid(series["times_h"], series["peripheral"])
        row = {
            "scenario": scenario,
            "dose_mg": series["dose_mg"],
            "cmax_umol_per_l": round(cmax, 6),
            "tmax_h": round(tmax, 4),
            "auc_last_umol_h_per_l": round(auc, 6),
            "last_conc_umol_per_l": round(series["peripheral"][-1], 6),
            "peak_venous_plasma_umol_per_l": round(max(series["venous"]), 6),
            "fraction_excreted_to_urine_final": None
            if series["urine"] is None
            else round(series["urine"][-1], 6),
            "fraction_absorbed_final": round(series["absorbed"][-1], 6),
            "csv_path": series["csv_path"],
            "json_path": series["json_path"],
        }
        scenario_rows.append(row)
    scenario_rows.sort(key=lambda item: item["dose_mg"])

    integrated = {
        "chemical": {
            "preferred_name": details["preferredName"],
            "dtxsid": details["dtxsid"],
            "dtxcid": details["dtxcid"],
            "casrn": details["casrn"],
            "formula": details["molFormula"],
            "average_mass": details["averageMass"],
            "monoisotopic_mass": details["monoisotopicMass"],
            "smiles": details["smiles"],
            "inchikey": details["inchikey"],
            "active_assays": details["activeAssays"],
            "total_assays": details["totalAssays"],
            "pubmed_count": details["pubmedCount"],
            "qc_level_desc": details["qcLevelDesc"],
        },
        "bioactivity_summary": bio,
        "httk_summary": httk_summary,
        "aop_context": {
            "direct_cimetidine_map_count": len(aop_direct),
            "direct_cimetidine_map_results": aop_direct,
            "liver_search_results": aop_liver,
            "selected_contextual_aops": [
                {
                    "id": aop27["id"],
                    "title": aop27["title"],
                    "key_event_count": len(aop27_kes),
                    "example_key_events": [item["title"] for item in aop27_kes[:3]],
                },
                {
                    "id": aop494["id"],
                    "title": aop494["title"].strip(),
                    "key_event_count": len(aop494_kes),
                    "example_key_events": [item["title"] for item in aop494_kes[:3]],
                },
            ],
            "note": "No direct cimetidine-to-AOP result was returned by the AOP MCP mapping tool. Liver AOPs are included as contextual mechanistic anchors only.",
        },
        "pbpk_scenarios": scenario_rows,
        "scenario_selection_rationale": "Three validated public oral cimetidine scenarios spanning 200 mg to 800 mg were rerun to bracket systemic exposure for cross-system interpretation.",
    }
    return integrated


def write_csv(path: Path, rows):
    if not rows:
        return
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def create_canvas(width=1500, height=920):
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    return image, draw, font


def draw_text(draw, xy, text, font, fill=(20, 20, 20)):
    draw.text(xy, text, font=font, fill=fill)


def draw_box(draw, xyxy, outline=(40, 40, 40), fill=None):
    draw.rectangle(xyxy, outline=outline, fill=fill, width=2)


def draw_multiline(draw, x, y, lines, font, line_gap=16, fill=(20, 20, 20)):
    for idx, line in enumerate(lines):
        draw_text(draw, (x, y + idx * line_gap), line, font, fill=fill)


def render_overview_figure(summary):
    image, draw, font = create_canvas(width=1600, height=980)
    width, _ = image.size

    draw_text(draw, (width // 2 - 170, 20), "Cimetidine cross-system overview", font)
    draw_text(
        draw,
        (70, 48),
        "CompTox chemical identity and HTTK context aligned with liver-oriented AOP context and PBPK scenario selection.",
        font,
        fill=(80, 80, 80),
    )

    left_box = (60, 100, 760, 430)
    right_box = (840, 100, 1540, 430)
    bottom_box = (60, 490, 1540, 900)
    draw_box(draw, left_box)
    draw_box(draw, right_box)
    draw_box(draw, bottom_box)

    chem = summary["chemical"]
    httk = summary["httk_summary"]
    aop = summary["aop_context"]

    left_lines = [
        "CompTox identity",
        f"Preferred name: {chem['preferred_name']}",
        f"DTXSID: {chem['dtxsid']}",
        f"CASRN: {chem['casrn']}",
        f"Formula: {chem['formula']}",
        f"Average mass: {chem['average_mass']}",
        f"Active assays: {chem['active_assays']} / {chem['total_assays']}",
        f"PubMed count: {int(chem['pubmed_count'])}",
        f"Human HTTK half-life: {httk.get('human_half_life_h', 'NA')} h",
        f"Human HTTK Css 50%: {httk.get('human_css_50%_mg_per_l', 'NA')} mg/L",
        f"Human HTTK Css 95%: {httk.get('human_css_95%_mg_per_l', 'NA')} mg/L",
        "SMILES:",
        chem["smiles"],
    ]
    draw_multiline(draw, 80, 120, left_lines, font)

    right_lines = [
        "AOP context",
        f"Direct cimetidine map results: {aop['direct_cimetidine_map_count']}",
        "Interpretation: no direct chemical-to-AOP mapping hit returned.",
        "Contextual liver AOP anchors from MCP search:",
        f"- {aop['selected_contextual_aops'][0]['id']}: {aop['selected_contextual_aops'][0]['title']}",
        f"  key events: {aop['selected_contextual_aops'][0]['key_event_count']}",
        f"- {aop['selected_contextual_aops'][1]['id']}: {aop['selected_contextual_aops'][1]['title']}",
        f"  key events: {aop['selected_contextual_aops'][1]['key_event_count']}",
        "Use: mechanistic context only, not a validated cimetidine AOP assignment.",
    ]
    draw_multiline(draw, 860, 120, right_lines, font)

    bottom_lines = [
        "PBPK scenario selection and output summary",
        "Rerun source: official public OSP cimetidine project executed via native PK-Sim runtime in the live PBPK container.",
        "Selected scenarios:",
    ]
    for row in summary["pbpk_scenarios"]:
        bottom_lines.append(
            f"- {row['dose_mg']} mg: Cmax {row['cmax_umol_per_l']:.3f} umol/L; "
            f"Tmax {row['tmax_h']:.2f} h; AUC_last {row['auc_last_umol_h_per_l']:.3f} umol*h/L"
        )
    bottom_lines.extend(
        [
            "",
            "Interpretation:",
            "These three oral scenarios provide a practical exposure range for aligning chemical identity, HTTK screening values,",
            "and liver-oriented mechanistic context with a reproducible PBPK run surface.",
        ]
    )
    draw_multiline(draw, 80, 510, bottom_lines, font)

    image.save(ROOT / "cimetidine_cross_system_overview.png")


def render_line_plot(path: Path, title: str, subtitle: str, y_label: str, series_map, *, log_y=False):
    image, draw, font = create_canvas(width=1450, height=880)
    width, height = image.size
    left, right, top, bottom = 110, 80, 100, 100
    plot_w = width - left - right
    plot_h = height - top - bottom

    all_points = [point for points in series_map.values() for point in points]
    x_values = [x for x, _ in all_points]
    y_values = [y for _, y in all_points]

    x_min = min(x_values)
    x_max = max(x_values)
    grid = (225, 225, 225)
    axis = (40, 40, 40)

    if log_y:
        positive = [value for value in y_values if value > 0]
        floor = min(positive) / 4.0

        def map_y(value):
            return math.log10(max(value, floor))

        y_min = math.log10(floor)
        y_max = math.log10(max(positive) * 1.1)
        tick_values = [0.01, 0.1, 1.0, 10.0]
        ticks = [(math.log10(value), f"{value:g}") for value in tick_values if floor <= value <= max(positive) * 1.1]
    else:
        def map_y(value):
            return value

        y_min = 0.0
        y_max = max(y_values) * 1.08
        ticks = [(y_min + (y_max - y_min) * idx / 6.0, f"{(y_min + (y_max - y_min) * idx / 6.0):.1f}") for idx in range(7)]

    def sx(value):
        return left + (value - x_min) / (x_max - x_min) * plot_w

    def sy(value):
        yv = map_y(value)
        return top + plot_h - (yv - y_min) / (y_max - y_min) * plot_h

    draw.line((left, top + plot_h, left + plot_w, top + plot_h), fill=axis, width=2)
    draw.line((left, top, left, top + plot_h), fill=axis, width=2)

    for idx in range(9):
        tick = x_min + (x_max - x_min) * idx / 8.0
        px = sx(tick)
        draw.line((px, top, px, top + plot_h), fill=grid, width=1)
        draw_text(draw, (px - 8, top + plot_h + 10), f"{tick:.0f}", font)

    for tick, label in ticks:
        py = top + plot_h - (tick - y_min) / (y_max - y_min) * plot_h
        draw.line((left, py, left + plot_w, py), fill=grid, width=1)
        draw_text(draw, (12, py - 6), label, font)

    draw_text(draw, (width // 2 - 160, 20), title, font)
    draw_text(draw, (left, 48), subtitle, font, fill=(80, 80, 80))
    draw_text(draw, (width // 2 - 25, height - 35), "Time (h)", font)
    draw_text(draw, (12, 16), y_label, font)

    for scenario in SCENARIOS:
        points = series_map[scenario]
        poly = []
        for x_value, y_value in points:
            poly.extend((sx(x_value), sy(y_value)))
        draw.line(poly, fill=COLORS[scenario], width=4)

    legend_x = width - 300
    legend_y = 120
    for scenario in SCENARIOS:
        draw.line((legend_x, legend_y + 7, legend_x + 32, legend_y + 7), fill=COLORS[scenario], width=4)
        draw_text(draw, (legend_x + 42, legend_y), f"{dose_mg(scenario)} mg", font)
        legend_y += 24

    image.save(path)


def render_pk_summary(path: Path, scenario_rows):
    image, draw, font = create_canvas(width=1450, height=820)
    width, _ = image.size
    margin = 70
    gap = 70
    panel_w = (width - margin * 2 - gap) // 2
    panel_h = 520
    top = 140

    draw_text(draw, (width // 2 - 110, 20), "Cross-dose PK summary", font)
    draw_text(
        draw,
        (margin, 48),
        "Public cimetidine oral scenarios rerun in the live PBPK container.",
        font,
        fill=(80, 80, 80),
    )

    panels = [("Cmax (umol/L)", "cmax_umol_per_l"), ("AUC_last (umol*h/L)", "auc_last_umol_h_per_l")]
    for panel_idx, (label, key) in enumerate(panels):
        x0 = margin + panel_idx * (panel_w + gap)
        y0 = top
        x1 = x0 + panel_w
        y1 = y0 + panel_h
        draw_box(draw, (x0, y0, x1, y1))
        draw_text(draw, (x0 + 10, y0 - 22), label, font)
        max_value = max(row[key] for row in scenario_rows) * 1.1
        bar_w = 95
        spacing = (panel_w - 3 * bar_w) // 4
        for idx, row in enumerate(scenario_rows):
            bx0 = x0 + spacing + idx * (bar_w + spacing)
            bx1 = bx0 + bar_w
            by1 = y1 - 40
            bar_h = row[key] / max_value * (panel_h - 90)
            by0 = by1 - bar_h
            draw.rectangle((bx0, by0, bx1, by1), fill=COLORS[row["scenario"]], outline=COLORS[row["scenario"]])
            draw_text(draw, (bx0 + 16, by1 + 8), f"{row['dose_mg']} mg", font)
            draw_text(draw, (bx0 + 4, by0 - 16), f"{row[key]:.2f}", font)

    image.save(path)


def render_baseline_processes(path: Path, baseline):
    image, draw, font = create_canvas(width=1500, height=980)
    width, _ = image.size
    margin_x = 80
    margin_y = 120
    gap_x = 60
    gap_y = 70
    panel_w = (width - margin_x * 2 - gap_x) // 2
    panel_h = 320

    draw_text(draw, (width // 2 - 150, 20), "Baseline 200 mg process panel", font)
    draw_text(draw, (margin_x, 48), baseline["scenario"], font, fill=(80, 80, 80))

    panels = [
        ("Peripheral venous plasma", baseline["times_h"], baseline["peripheral"], (27, 94, 32), "umol/L"),
        ("Venous plasma", baseline["times_h"], baseline["venous"], (21, 101, 192), "umol/L"),
        ("Fraction absorbed", baseline["times_h"], baseline["absorbed"], (183, 28, 28), "fraction"),
        ("Fraction excreted to urine", baseline["times_h"], baseline["urine"], (140, 90, 0), "fraction"),
    ]

    for idx, (title, xs, ys, color, unit) in enumerate(panels):
        col = idx % 2
        row = idx // 2
        x0 = margin_x + col * (panel_w + gap_x)
        y0 = margin_y + row * (panel_h + gap_y)
        x1 = x0 + panel_w
        y1 = y0 + panel_h
        draw_box(draw, (x0, y0, x1, y1))
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
            yt = y_min + (y_max - y_min) * tick_idx / 4.0
            py = sy(yt)
            draw.line((x0 + 50, py, x1 - 20, py), fill=(230, 230, 230), width=1)
            draw_text(draw, (x0 + 8, py - 6), f"{yt:.2f}" if y_max <= 1.2 else f"{yt:.1f}", font)

        poly = []
        for xv, yv in zip(xs, ys):
            poly.extend((sx(xv), sy(yv)))
        draw.line(poly, fill=color, width=4)

    image.save(path)


def main():
    prepare_workspace()
    context = fetch_context()
    persist_context(context)
    run_pbpk_export()
    pbpk = load_pbpk_results()
    summary = build_summaries(context, pbpk)

    write_json(ROOT / "integrated_summary.json", summary)
    write_json(ROOT / "pbpk_summary.json", {"scenarios": summary["pbpk_scenarios"]})
    write_csv(ROOT / "scenario_table.csv", summary["pbpk_scenarios"])

    baseline = {
        "scenario": SCENARIOS[0],
        "times_h": pbpk[SCENARIOS[0]]["times_h"],
        "peripheral": pbpk[SCENARIOS[0]]["peripheral"],
        "venous": pbpk[SCENARIOS[0]]["venous"],
        "absorbed": pbpk[SCENARIOS[0]]["absorbed"],
        "urine": pbpk[SCENARIOS[0]]["urine"] or [0.0 for _ in pbpk[SCENARIOS[0]]["times_h"]],
    }

    linear_series = {
        scenario: list(zip(pbpk[scenario]["times_h"], pbpk[scenario]["peripheral"]))
        for scenario in SCENARIOS
    }

    render_overview_figure(summary)
    render_line_plot(
        ROOT / "cimetidine_cross_system_pbpk_linear.png",
        title="Cimetidine PBPK exposure comparison",
        subtitle="Peripheral venous plasma concentration for three public oral cimetidine scenarios.",
        y_label="Peripheral venous plasma cimetidine (umol/L)",
        series_map=linear_series,
        log_y=False,
    )
    render_line_plot(
        ROOT / "cimetidine_cross_system_pbpk_semilog.png",
        title="Cimetidine PBPK exposure comparison",
        subtitle="Semilog view for early and terminal concentration behavior across dose levels.",
        y_label="Peripheral venous plasma cimetidine (umol/L, log scale)",
        series_map=linear_series,
        log_y=True,
    )
    render_pk_summary(ROOT / "cimetidine_cross_system_pk_summary.png", summary["pbpk_scenarios"])
    render_baseline_processes(ROOT / "cimetidine_cross_system_baseline_processes.png", baseline)

    report = textwrap.dedent(
        f"""
        # Cimetidine cross-system MCP demo

        ## Scope
        This bundle combines EPA CompTox MCP, AOP MCP, and the PBPK container runtime around a single public cimetidine case study.

        ## Chemical identity
        - Preferred name: {summary['chemical']['preferred_name']}
        - DTXSID: {summary['chemical']['dtxsid']}
        - CASRN: {summary['chemical']['casrn']}
        - Formula: {summary['chemical']['formula']}
        - Active assays: {summary['chemical']['active_assays']} / {summary['chemical']['total_assays']}

        ## HTTK context
        - Human HTTK half-life: {summary['httk_summary'].get('human_half_life_h')}
        - Human HTTK Css 50%: {summary['httk_summary'].get('human_css_50%_mg_per_l')}
        - Human HTTK Css 95%: {summary['httk_summary'].get('human_css_95%_mg_per_l')}

        ## AOP context
        - Direct cimetidine map count: {summary['aop_context']['direct_cimetidine_map_count']}
        - Contextual liver AOPs used:
          - {summary['aop_context']['selected_contextual_aops'][0]['id']}: {summary['aop_context']['selected_contextual_aops'][0]['title']}
          - {summary['aop_context']['selected_contextual_aops'][1]['id']}: {summary['aop_context']['selected_contextual_aops'][1]['title']}
        - Note: {summary['aop_context']['note']}

        ## PBPK scenarios
        """
    ).strip() + "\n"
    for row in summary["pbpk_scenarios"]:
        report += (
            f"- {row['dose_mg']} mg: Cmax {row['cmax_umol_per_l']}, "
            f"Tmax {row['tmax_h']} h, AUC_last {row['auc_last_umol_h_per_l']}\n"
        )
    report += textwrap.dedent(
        """

        ## Figures
        - cimetidine_cross_system_overview.png
        - cimetidine_cross_system_pbpk_linear.png
        - cimetidine_cross_system_pbpk_semilog.png
        - cimetidine_cross_system_pk_summary.png
        - cimetidine_cross_system_baseline_processes.png
        """
    )
    (ROOT / "report.md").write_text(report)

    manifest = [
        "report.md",
        "integrated_summary.json",
        "pbpk_summary.json",
        "scenario_table.csv",
        "cimetidine_cross_system_overview.png",
        "cimetidine_cross_system_pbpk_linear.png",
        "cimetidine_cross_system_pbpk_semilog.png",
        "cimetidine_cross_system_pk_summary.png",
        "cimetidine_cross_system_baseline_processes.png",
    ]
    for item in manifest:
        print(ROOT / item)


if __name__ == "__main__":
    main()
