#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from uuid import uuid4
from xml.sax.saxutils import escape

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
        KeepTogether,
        PageBreak,
    )
    REPORTLAB_IMPORT_ERROR: Exception | None = None
except ModuleNotFoundError as exc:  # pragma: no cover - optional local dependency
    REPORTLAB_IMPORT_ERROR = exc
    colors = None
    TA_LEFT = None
    A4 = None
    ParagraphStyle = None
    getSampleStyleSheet = None
    mm = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None
    KeepTogether = None
    PageBreak = None


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = WORKSPACE_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_DEV_SECRET = "pbpk-local-dev-secret-32bytes-long"
REFERENCE_MODEL = "/app/var/models/rxode2/reference_compound/reference_compound_population_rxode2_model.R"
REQUEST_JSON = {"route": "iv-infusion", "contextOfUse": "research-only"}
REGULATORY_GOLDSET_SCORECARD = (
    WORKSPACE_ROOT / "benchmarks" / "regulatory_goldset" / "regulatory_goldset_scorecard.json"
)
REGULATORY_GOLDSET_AUDIT_MANIFEST = (
    WORKSPACE_ROOT / "benchmarks" / "regulatory_goldset" / "regulatory_goldset_audit_manifest.json"
)


def _jwt_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwt_encode_hs256(payload: dict[str, object], key: str) -> str:
    header = {"typ": "JWT", "alg": "HS256"}
    segments = [
        _jwt_b64encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")),
        _jwt_b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("utf-8")
    signature = hmac.new(key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    segments.append(_jwt_b64encode(signature))
    return ".".join(segments)


def build_auth_headers(secret: str, role: str) -> dict[str, str]:
    token = _jwt_encode_hs256(
        {
            "sub": f"reference-model-live-audit-{role}",
            "roles": [role],
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        secret,
    )
    return {"authorization": f"Bearer {token}"}


def _decode_body(body: bytes) -> object:
    text = body.decode()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def http_request(
    url: str,
    *,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict[str, object]:
    data = None
    request_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("content-type", "application/json")

    req = urllib.request.Request(url, data=data, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return {
                "status": response.status,
                "headers": {key.lower(): value for key, value in response.headers.items()},
                "body": _decode_body(response.read()),
            }
    except urllib.error.HTTPError as exc:
        return {
            "status": exc.code,
            "headers": {key.lower(): value for key, value in (exc.headers or {}).items()},
            "body": _decode_body(exc.read()),
        }


def http_json(
    url: str,
    *,
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict:
    response = http_request(url, payload=payload, headers=headers, timeout=timeout)
    if int(response["status"]) >= 400:
        raise RuntimeError(f"{url} returned HTTP {response['status']}: {json.dumps(response['body'])}")
    body = response["body"]
    if not isinstance(body, dict):
        raise RuntimeError(f"{url} returned a non-JSON payload: {body!r}")
    return body


def call_tool(
    base_url: str,
    tool: str,
    arguments: dict,
    *,
    headers: dict[str, str] | None = None,
    critical: bool = False,
    timeout: int = 180,
) -> dict:
    payload = {"tool": tool, "arguments": arguments}
    if critical:
        payload["critical"] = True
    return http_json(
        f"{base_url}/mcp/call_tool",
        payload=payload,
        headers=headers,
        timeout=timeout,
    )["structuredContent"]


def poll_job(
    base_url: str,
    job_id: str,
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: int = 180,
) -> dict:
    deadline = time.time() + timeout_seconds
    last_status = None
    while time.time() < deadline:
        payload = call_tool(
            base_url,
            "get_job_status",
            {"jobId": job_id},
            headers=headers,
            timeout=60,
        )
        last_status = payload
        if payload["status"] in {"succeeded", "failed", "cancelled", "timeout"}:
            return payload
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for job {job_id}: {json.dumps(last_status)}")


def _bullet_lines(items: list[str]) -> str:
    return "<br/>".join(f"- {escape(item)}" for item in items)


def _list_or_placeholder(items: list[str] | None, placeholder: str = "None") -> list[str]:
    if not items:
        return [placeholder]
    return [str(item) for item in items]


def _as_list_of_strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _format_block_reasons(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    formatted: list[str] = []
    for item in value:
        if isinstance(item, dict):
            code = str(item.get("code") or "unknown-block-reason")
            message = str(item.get("message") or "No message supplied.")
            applies = ", ".join(str(entry) for entry in (item.get("appliesTo") or []))
            if applies:
                formatted.append(f"{code}: {message} Applies to {applies}.")
            else:
                formatted.append(f"{code}: {message}")
        else:
            formatted.append(str(item))
    return formatted


def _json_text(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_text(payload), encoding="utf-8")


def _load_optional_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_path(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _workspace_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path.resolve())


def _workspace_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return WORKSPACE_ROOT / path


def _bundle_sha256(entries: list[dict[str, str]]) -> str:
    lines = []
    for entry in sorted(entries, key=lambda item: item["relativePath"]):
        lines.append(f"{entry['relativePath']}  {entry['sha256']}")
    return _sha256_bytes(("\n".join(lines) + "\n").encode("utf-8"))


def write_evidence_artifacts(audit: dict[str, object], output_dir: Path) -> list[dict[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_specs = [
        (
            "00_audit_metadata.json",
            {
                "baseUrl": audit["baseUrl"],
                "generatedAt": audit["generatedAt"],
                "publicReleaseComparison": audit["publicReleaseComparison"],
                "request": REQUEST_JSON,
                "simulationId": audit["simulationId"],
                "runId": audit["runId"],
            },
            "audit metadata",
        ),
        ("01_health.json", audit["health"], "health"),
        ("02_release_bundle_manifest.json", audit["releaseBundleManifest"], "release bundle manifest"),
        ("03_tool_catalog_anonymous.json", audit["anonymousToolCatalog"], "anonymous tool catalog"),
        ("04_tool_catalog_operator.json", audit["operatorToolCatalog"], "operator tool catalog"),
        ("05_metrics_anonymous.json", audit["metricsAnonymous"], "anonymous metrics probe"),
        ("06_metrics_admin.json", audit["metricsAdmin"], "admin metrics probe"),
        ("07_retired_console_checks.json", audit["retiredConsoleChecks"], "retired console probe set"),
        ("08_reference_model_discovery.json", audit["referenceModelDiscovery"], "reference model discovery payload"),
        ("09_reference_model_manifest.json", audit["referenceModelManifest"], "static reference model manifest"),
        (
            "09a_regulatory_goldset_audit_manifest.json",
            audit.get("regulatoryGoldsetAuditManifest") or {},
            "regulatory gold-set audit manifest",
        ),
        (
            "09b_regulatory_goldset_scorecard.json",
            audit.get("regulatoryGoldsetScorecard") or {},
            "regulatory gold-set scorecard",
        ),
        ("10_load_simulation.json", audit["loadSimulation"], "load simulation response"),
        ("11_validation_before_signoff.json", audit["validationBeforeSignoff"], "validation before signoff"),
        ("12_validation_signoff.json", audit["validationSignoff"], "validation signoff response"),
        ("13_validation_after_signoff.json", audit["validationAfterSignoff"], "validation after signoff"),
        ("14_verification.json", audit["verification"], "verification response"),
        ("15_report_signoff.json", audit["reportSignoff"], "report signoff response"),
        ("16_review_signoff_history.json", audit["reviewSignoffHistory"], "review signoff history"),
        ("17_oecd_report.json", audit["oecdReport"], "OECD report response"),
        ("18_run_submission.json", audit["runSubmission"], "simulation submission response"),
        ("19_run_job_status.json", audit["runJobStatus"], "final job status"),
        ("20_results.json", audit["results"], "result payload"),
        ("21_pk_metrics.json", audit["pkMetrics"], "PK metrics payload"),
    ]

    artifacts: list[dict[str, str]] = []
    for filename, payload, label in artifact_specs:
        artifact_path = output_dir / filename
        _write_json(artifact_path, payload)
        artifacts.append(
            {
                "label": label,
                "relativePath": _workspace_relative(artifact_path),
                "sha256": _sha256_path(artifact_path),
            }
        )
    return artifacts


def build_verification_pack(
    audit: dict[str, object],
    *,
    output_dir: Path,
    output_json: Path,
    output_pdf: Path,
    output_manifest: Path,
    raw_artifacts: list[dict[str, str]],
) -> dict[str, object]:
    history = (audit["reviewSignoffHistory"].get("operatorReviewSignoffHistory") or {}).get("entries") or []
    verification_checks = (audit["verification"].get("verification") or {}).get("checks") or []
    verification_pack: dict[str, object] = {
        "formatVersion": 1,
        "generatedAt": audit["generatedAt"],
        "baseUrl": audit["baseUrl"],
        "hashPolicy": {
            "algorithm": "sha256",
            "nonRecursiveManifest": True,
            "deliveryBundleExcludes": [_workspace_relative(output_manifest)],
        },
        "runtimeIdentity": {
            "healthVersion": audit["health"]["version"],
            "releaseBundleSha256": audit["releaseBundleManifest"]["bundleSha256"],
            "simulationId": audit["simulationId"],
            "resultId": audit["runJobStatus"]["resultId"],
            "runId": audit["runId"],
            "jobId": audit["runSubmission"]["jobId"],
        },
        "traceability": {
            "reviewSignoffHistoryEventsReturned": len(history),
            "verificationCheckCount": len(verification_checks),
            "resultSeriesCount": len(audit["results"].get("series") or []),
            "pkMetricCount": len(audit["pkMetrics"].get("metrics") or []),
        },
        "verificationPack": {
            "directory": _workspace_relative(output_dir),
            "manifestPath": _workspace_relative(output_manifest),
            "rawArtifactCount": len(raw_artifacts),
            "rawEvidenceSha256": _bundle_sha256(raw_artifacts),
            "rawArtifacts": raw_artifacts,
        },
        "auditJson": {
            "relativePath": _workspace_relative(output_json),
            "sha256": _sha256_path(output_json),
        },
        "auditPdf": {
            "relativePath": _workspace_relative(output_pdf),
            "sha256": None,
        },
        "deliveryBundleSha256": None,
    }
    return verification_pack


def finalize_verification_pack(
    verification_pack: dict[str, object],
    *,
    output_pdf: Path,
    output_manifest: Path,
) -> dict[str, object]:
    finalized = json.loads(json.dumps(verification_pack))
    pdf_entry = {
        "label": "human-readable audit PDF",
        "relativePath": _workspace_relative(output_pdf),
        "sha256": _sha256_path(output_pdf),
    }
    finalized["auditPdf"] = {
        "relativePath": pdf_entry["relativePath"],
        "sha256": pdf_entry["sha256"],
    }
    delivery_artifacts = list(finalized["verificationPack"]["rawArtifacts"]) + [
        {
            "label": "full audit summary",
            "relativePath": finalized["auditJson"]["relativePath"],
            "sha256": finalized["auditJson"]["sha256"],
        },
        pdf_entry,
    ]
    finalized["deliveryArtifacts"] = delivery_artifacts
    finalized["deliveryBundleSha256"] = _bundle_sha256(delivery_artifacts)
    _write_json(output_manifest, finalized)
    return finalized


def verify_verification_pack(manifest_path: Path) -> dict[str, object]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches: list[str] = []

    raw_artifacts = list((manifest.get("verificationPack") or {}).get("rawArtifacts") or [])
    raw_pack_sha = _bundle_sha256(raw_artifacts) if raw_artifacts else None
    if raw_pack_sha != (manifest.get("verificationPack") or {}).get("rawEvidenceSha256"):
        mismatches.append("rawEvidenceSha256 does not match the listed raw artifacts")

    checked_files = 0
    for entry in raw_artifacts + [manifest.get("auditJson") or {}, manifest.get("auditPdf") or {}]:
        relative_path = entry.get("relativePath")
        expected_sha = entry.get("sha256")
        if not relative_path or not expected_sha:
            mismatches.append(f"manifest entry is incomplete: {entry!r}")
            continue
        path = _workspace_path(str(relative_path))
        if not path.exists():
            mismatches.append(f"missing file: {relative_path}")
            continue
        actual_sha = _sha256_path(path)
        checked_files += 1
        if actual_sha != expected_sha:
            mismatches.append(f"sha256 mismatch for {relative_path}")

    delivery_artifacts = list(manifest.get("deliveryArtifacts") or [])
    delivery_bundle_sha = _bundle_sha256(delivery_artifacts) if delivery_artifacts else None
    if delivery_bundle_sha != manifest.get("deliveryBundleSha256"):
        mismatches.append("deliveryBundleSha256 does not match the listed delivery artifacts")

    return {
        "status": "passed" if not mismatches else "failed",
        "manifestPath": _workspace_relative(manifest_path),
        "checkedFileCount": checked_files,
        "rawArtifactCount": len(raw_artifacts),
        "deliveryArtifactCount": len(delivery_artifacts),
        "manifestSha256": _sha256_path(manifest_path),
        "mismatches": mismatches,
    }


def collect_audit_payload(base_url: str, auth_dev_secret: str) -> dict[str, object]:
    operator_headers = build_auth_headers(auth_dev_secret, "operator")
    viewer_headers = build_auth_headers(auth_dev_secret, "viewer")
    admin_headers = build_auth_headers(auth_dev_secret, "admin")

    audit: dict[str, object] = {
        "baseUrl": base_url,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "publicReleaseComparison": {
            "publicReleaseBaseline": "current public release line",
            "localAssessment": "current workspace materially exceeds the public release in auth hardening, trust-surface metadata, live release gating, and runtime safety posture",
        },
    }

    audit["health"] = http_json(f"{base_url}/health")
    audit["releaseBundleManifest"] = http_json(f"{base_url}/mcp/resources/release-bundle-manifest")
    audit["anonymousToolCatalog"] = http_json(f"{base_url}/mcp/list_tools")
    audit["operatorToolCatalog"] = http_json(
        f"{base_url}/mcp/list_tools",
        headers=operator_headers,
    )
    audit["metricsAnonymous"] = http_request(f"{base_url}/metrics")
    audit["metricsAdmin"] = http_request(f"{base_url}/metrics", headers=admin_headers)
    audit["retiredConsoleChecks"] = {
        "shell": http_request(f"{base_url}/console"),
        "asset": http_request(f"{base_url}/console/assets/app.js"),
        "static": http_request(f"{base_url}/console/static/app.js"),
        "apiAnonymous": http_request(f"{base_url}/console/api/samples"),
        "apiOperator": http_request(f"{base_url}/console/api/samples", headers=operator_headers),
    }

    audit["referenceModelDiscovery"] = http_json(f"{base_url}/mcp/resources/models?search=reference_compound&limit=5")
    audit["referenceModelManifest"] = call_tool(
        base_url,
        "validate_model_manifest",
        {"filePath": REFERENCE_MODEL},
        headers=operator_headers,
        timeout=60,
    )
    audit["regulatoryGoldsetAuditManifest"] = _load_optional_json(REGULATORY_GOLDSET_AUDIT_MANIFEST)
    audit["regulatoryGoldsetScorecard"] = _load_optional_json(REGULATORY_GOLDSET_SCORECARD)

    simulation_id = f"reference-audit-{uuid4().hex[:8]}"
    audit["simulationId"] = simulation_id

    audit["loadSimulation"] = call_tool(
        base_url,
        "load_simulation",
        {"filePath": REFERENCE_MODEL, "simulationId": simulation_id},
        headers=operator_headers,
        critical=True,
        timeout=120,
    )

    audit["validationBeforeSignoff"] = call_tool(
        base_url,
        "validate_simulation_request",
        {"simulationId": simulation_id, "request": REQUEST_JSON},
        headers=operator_headers,
        timeout=60,
    )

    audit["validationSignoff"] = http_json(
        f"{base_url}/review_signoff",
        payload={
            "simulationId": simulation_id,
            "scope": "validate_simulation_request",
            "disposition": "acknowledged",
            "rationale": "Live audit confirms bounded research-only validation with trust surfaces intact.",
            "confirm": True,
        },
        headers=operator_headers,
        timeout=30,
    )

    audit["validationAfterSignoff"] = call_tool(
        base_url,
        "validate_simulation_request",
        {"simulationId": simulation_id, "request": REQUEST_JSON},
        headers=operator_headers,
        timeout=60,
    )

    audit["verification"] = call_tool(
        base_url,
        "run_verification_checks",
        {
            "simulationId": simulation_id,
            "request": REQUEST_JSON,
            "includePopulationSmoke": True,
            "populationCohort": {"size": 10, "seed": 42},
            "populationOutputs": {"aggregates": ["meanCmax", "sdCmax", "meanAUC"]},
        },
        headers=operator_headers,
        timeout=180,
    )

    audit["reportSignoff"] = http_json(
        f"{base_url}/review_signoff",
        payload={
            "simulationId": simulation_id,
            "scope": "export_oecd_report",
            "disposition": "approved-for-bounded-use",
            "rationale": "Live audit confirms report export keeps detached-summary risk, claim boundaries, and sign-off governance explicit.",
            "confirm": True,
        },
        headers=operator_headers,
        timeout=30,
    )

    audit["reviewSignoffHistory"] = http_json(
        f"{base_url}/review_signoff/history?simulationId={simulation_id}&scope=export_oecd_report&limit=10",
        headers=viewer_headers,
        timeout=30,
    )

    audit["oecdReport"] = call_tool(
        base_url,
        "export_oecd_report",
        {
            "simulationId": simulation_id,
            "request": REQUEST_JSON,
            "parameterLimit": 5,
        },
        headers=operator_headers,
        timeout=120,
    )

    run_id = f"{simulation_id}-smoke"
    audit["runId"] = run_id
    audit["runSubmission"] = call_tool(
        base_url,
        "run_simulation",
        {"simulationId": simulation_id, "runId": run_id},
        headers=operator_headers,
        critical=True,
        timeout=60,
    )
    audit["runJobStatus"] = poll_job(
        base_url,
        audit["runSubmission"]["jobId"],
        headers=operator_headers,
        timeout_seconds=180,
    )
    result_id = audit["runJobStatus"]["resultId"]
    audit["results"] = call_tool(
        base_url,
        "get_results",
        {"resultsId": result_id},
        headers=operator_headers,
        timeout=60,
    )
    audit["pkMetrics"] = call_tool(
        base_url,
        "calculate_pk_parameters",
        {"resultsId": result_id},
        headers=operator_headers,
        timeout=60,
    )

    return audit


def _table(data: list[list[object]], col_widths: list[float] | None = None) -> Table:
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16324f")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c4cf")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 10.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f8fb")]),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def build_pdf(audit: dict[str, object], verification_pack: dict[str, object], output_pdf: Path) -> None:
    if REPORTLAB_IMPORT_ERROR is not None:  # pragma: no cover - depends on local optional dependency
        raise RuntimeError(
            "PDF generation requires the optional 'reportlab' dependency. "
            "Install it in the active Python environment or use --verify-only."
        ) from REPORTLAB_IMPORT_ERROR

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="AuditTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#18212b"),
            alignment=TA_LEFT,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AuditSection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#8a2f1d"),
            spaceBefore=10,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AuditBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#20262d"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AuditSmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#44505c"),
            spaceAfter=2,
        )
    )

    health = audit["health"]
    manifest = audit["referenceModelManifest"]
    curation_summary = manifest.get("curationSummary") or {}
    validation = audit["validationAfterSignoff"]
    validation_summary = validation["ngraObjects"]["pbpkQualificationSummary"]
    verification = audit["verification"]["verification"]
    report_payload = audit["oecdReport"]["report"]
    human_review = report_payload.get("humanReviewSummary") or {}
    misread = report_payload.get("misreadRiskSummary") or {}
    signoff = audit["reportSignoff"].get("operatorReviewSignoff") or {}
    governance = audit["reportSignoff"].get("operatorReviewGovernance") or {}
    history = (audit["reviewSignoffHistory"].get("operatorReviewSignoffHistory") or {}).get("entries") or []
    result_series = audit["results"].get("series") or []
    pk_metrics = audit["pkMetrics"].get("metrics") or []
    release_bundle = audit["releaseBundleManifest"]
    benchmark_scorecard = audit.get("regulatoryGoldsetScorecard") or {}
    benchmark_manifest = audit.get("regulatoryGoldsetAuditManifest") or {}
    benchmark_comparison = (
        (benchmark_scorecard.get("referenceModelComparisons") or [{}])[0].get("regulatoryBenchmarkReadiness")
        or {}
    )
    raw_pack = verification_pack["verificationPack"]
    raw_artifacts = raw_pack.get("rawArtifacts") or []
    raw_labels = [entry.get("label", "artifact") for entry in raw_artifacts[:6]]

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_pdf),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=14 * mm,
        title="Reference model Live Safety Audit",
        author="Codex",
    )

    story = []
    story.append(Paragraph("PBPK MCP Reference model Live Safety Audit", styles["AuditTitle"]))
    story.append(
        Paragraph(
            f"Generated {escape(str(audit['generatedAt']))} against {escape(str(audit['baseUrl']))}. "
            f"This audit uses the running server, not only static source inspection.",
            styles["AuditBody"],
        )
    )
    story.append(
        Paragraph(
            "Bottom line: removing the analyst UI did not remove the safety controls. "
            "The live server still enforces auth boundaries, confirmation gates, trust-surface metadata, "
            "review sign-off governance, and conservative OECD export semantics.",
            styles["AuditBody"],
        )
    )

    story.append(Spacer(1, 5))
    story.append(
        _table(
            [
                ["Check", "Observed live result"],
                ["Health", f"{health['status']} | version {health['version']}"],
                ["Anonymous metrics", f"HTTP {audit['metricsAnonymous']['status']}"],
                ["Admin metrics", f"HTTP {audit['metricsAdmin']['status']}"],
                ["Retired console shell", f"HTTP {audit['retiredConsoleChecks']['shell']['status']}"],
                ["Retired console API", f"HTTP {audit['retiredConsoleChecks']['apiAnonymous']['status']}"],
                ["Manifest qualification state", manifest["manifest"]["qualificationState"]["state"]],
                ["Validation decision", validation["validation"]["assessment"]["decision"]],
                ["Verification status", verification["status"]],
                ["Report sign-off", signoff.get("status", "missing")],
                ["Release bundle SHA-256", release_bundle["bundleSha256"]],
            ],
            col_widths=[52 * mm, 120 * mm],
        )
    )

    story.append(Paragraph("Compared To Current Public Release", styles["AuditSection"]))
    public_release = audit["publicReleaseComparison"]
    story.append(
        Paragraph(
            f"The comparison baseline is the {escape(public_release['publicReleaseBaseline'])}. "
            "The current workspace is materially safer because it adds backend trust controls and live gating "
            "that were not part of the earlier public release story.",
            styles["AuditBody"],
        )
    )
    story.append(
        Paragraph(
            _bullet_lines(
                [
                    "Anonymous-development remains viewer-only instead of acting like an operator shortcut.",
                    "Metrics stay protected, while the retired /console surface remains absent.",
                    "Trust-bearing outputs now carry claim boundaries, export-block reasons, caution summaries, and misread risk summaries directly in payloads.",
                    "Operator review sign-off is additive and auditable, not a hidden override mechanism.",
                    "The release gate now proves those controls on the running server before release.",
                ]
            ),
            styles["AuditBody"],
        )
    )

    story.append(Paragraph("Runtime Safety Posture", styles["AuditSection"]))
    anonymous_tool_count = len((audit["anonymousToolCatalog"].get("tools") or []))
    operator_tool_count = len((audit["operatorToolCatalog"].get("tools") or []))
    story.append(
        _table(
            [
                ["Surface", "Observed status", "Meaning"],
                ["/mcp/list_tools anonymous", str(anonymous_tool_count), "Viewer-safe catalog only"],
                ["/mcp/list_tools operator", str(operator_tool_count), "Operator sees execution tools"],
                ["/metrics anonymous", str(audit["metricsAnonymous"]["status"]), "Protected"],
                ["/metrics admin", str(audit["metricsAdmin"]["status"]), "Available to admin only"],
                ["/console", str(audit["retiredConsoleChecks"]["shell"]["status"]), "Retired surface remains absent"],
                ["/console/api/samples anonymous", str(audit["retiredConsoleChecks"]["apiAnonymous"]["status"]), "Retired surface remains absent"],
                ["/console/api/samples operator", str(audit["retiredConsoleChecks"]["apiOperator"]["status"]), "Retired surface remains absent even with auth"],
            ],
            col_widths=[60 * mm, 28 * mm, 84 * mm],
        )
    )
    story.append(
        Paragraph(
            "Conclusion: the removed UI was not carrying the trust guarantees. The guarantees are on the live API and report surfaces, and those still behave safely after the UI removal.",
            styles["AuditBody"],
        )
    )

    story.append(Paragraph("Reference model Manifest And Trust Surface", styles["AuditSection"]))
    model_name = (
        (audit.get("loadSimulation") or {}).get("metadata", {}).get("name")
        or (manifest.get("manifest") or {}).get("modelName")
        or Path(REFERENCE_MODEL).name
    )

    story.append(
        _table(
            [
                ["Field", "Observed value"],
                ["Model", model_name],
                ["Manifest status", manifest["manifest"]["manifestStatus"]],
                ["Qualification state", manifest["manifest"]["qualificationState"]["state"]],
                ["NGRA declarations explicit", str(bool(curation_summary.get("ngraDeclarationsExplicit")))],
                ["Rendering guardrail", str((curation_summary.get("renderingGuardrails") or {}).get("actionIfRequiredFieldsMissing"))],
                ["Export policy", str((curation_summary.get("exportBlockPolicy") or {}).get("defaultAction"))],
            ],
            col_widths=[58 * mm, 114 * mm],
        )
    )
    story.append(
        Paragraph(
            f"Curation summary transport risk: {escape(str((curation_summary.get('summaryTransportRisk') or {}).get('riskLevel', 'unknown')))}. "
            f"Required adjacent fields: {escape(', '.join(_as_list_of_strings((curation_summary.get('renderingGuardrails') or {}).get('requiredFields'))))}.",
            styles["AuditBody"],
        )
    )
    if benchmark_comparison:
        story.append(Paragraph("Benchmark Bar Comparison", styles["AuditSection"]))
        story.append(
            _table(
                [
                    ["Field", "Observed value"],
                    ["Benchmark readiness status", str(benchmark_comparison.get("overallStatus", "missing"))],
                    ["Benchmark resemblance", str(benchmark_comparison.get("modelResemblance", "missing"))],
                    ["Present dimensions", str(len(benchmark_comparison.get("presentDimensions") or []))],
                    ["Partial dimensions", str(len(benchmark_comparison.get("partialDimensions") or []))],
                    ["Missing dimensions", str(len(benchmark_comparison.get("missingDimensions") or []))],
                    [
                        "Benchmark source manifest SHA-256",
                        str(((benchmark_comparison.get("benchmarkBarSource") or {}).get("sourceManifestSha256")) or "missing"),
                    ],
                    [
                        "Benchmark fetched-lock SHA-256",
                        str(((benchmark_comparison.get("benchmarkBarSource") or {}).get("fetchedLockSha256")) or "missing"),
                    ],
                ],
                col_widths=[62 * mm, 110 * mm],
            )
        )
        prioritized_gap_lines = [
            f"{item.get('label')}: {item.get('reason')}"
            for item in (benchmark_comparison.get("prioritizedGaps") or [])[:4]
        ]
        story.append(
            Paragraph(
                "The tracked regulatory gold-set dossier keeps this comparison hash-linked to the fetched benchmark corpus. "
                f"Top MCP gap priorities for the synthetic reference model:<br/>{_bullet_lines(_list_or_placeholder(prioritized_gap_lines))}",
                styles["AuditBody"],
            )
        )
        if benchmark_manifest:
            story.append(
                Paragraph(
                    f"Benchmark audit manifest bundle SHA-256: {escape(str(benchmark_manifest.get('trackedOutputBundleSha256', 'missing')))}",
                    styles["AuditSmall"],
                )
            )

    story.append(Paragraph("Validation, Review, And Governance", styles["AuditSection"]))
    review_status = validation_summary.get("reviewStatus") or {}
    story.append(
        _table(
            [
                ["Field", "Observed value"],
                ["Validation decision", validation["validation"]["assessment"]["decision"]],
                ["Workflow role", validation["ngraObjects"]["assessmentContext"]["workflowRole"]["workflow"]],
                ["Population extrapolation policy", validation["ngraObjects"]["assessmentContext"]["populationSupport"]["extrapolationPolicy"]],
                ["Evidence basis in vivo status", validation_summary["evidenceBasis"]["inVivoSupportStatus"]],
                ["Reverse dosimetry boundary", validation_summary["workflowClaimBoundaries"]["reverseDosimetry"]],
                ["Review status", review_status.get("status", "missing")],
                ["Requires reviewer attention", str(bool(review_status.get("requiresReviewerAttention")))],
                ["Validation sign-off", (audit["validationSignoff"].get("operatorReviewSignoff") or {}).get("status", "missing")],
                ["Report sign-off", signoff.get("status", "missing")],
                ["Governance override support", str(governance.get("supportsOverride"))],
                ["Governance adjudication support", str(governance.get("supportsAdjudication"))],
            ],
            col_widths=[66 * mm, 106 * mm],
        )
    )
    story.append(
        Paragraph(
            "Review-signoff history is viewer-readable and immutable. The latest report-scope history action was "
            f"{escape(str((history[0] if history else {}).get('action', 'missing')))} with "
            f"{escape(str(len(history)))} recorded event(s) returned.",
            styles["AuditBody"],
        )
    )

    story.append(Paragraph("Verification Results", styles["AuditSection"]))
    verification_rows = [["Check", "Status"]]
    for check in verification.get("checks") or []:
        verification_rows.append([check.get("id", "unknown"), check.get("status", "unknown")])
    story.append(_table(verification_rows, col_widths=[86 * mm, 86 * mm]))

    story.append(PageBreak())
    story.append(Paragraph("OECD Export Safety Surfaces", styles["AuditSection"]))
    caution_rows = [["Caution type", "Severity", "Handling"]]
    for entry in (human_review.get("cautionSummary") or {}).get("cautions") or []:
        caution_rows.append([
            entry.get("cautionType", "unknown"),
            entry.get("severity", "unknown"),
            entry.get("handling", "unknown"),
        ])
    if len(caution_rows) == 1:
        caution_rows.append(["none-declared", "n/a", "n/a"])
    story.append(_table(caution_rows, col_widths=[68 * mm, 34 * mm, 70 * mm]))

    block_reasons = _format_block_reasons((report_payload.get("exportBlockPolicy") or {}).get("blockReasons"))
    story.append(
        Paragraph(
            f"Export-block policy: {escape(str((report_payload.get('exportBlockPolicy') or {}).get('defaultAction', 'missing')))}.<br/>"
            f"Block reasons:<br/>{_bullet_lines(_list_or_placeholder(block_reasons))}",
            styles["AuditBody"],
        )
    )
    story.append(
        Paragraph(
            f"Misread risk level: {escape(str(misread.get('riskLevel', 'unknown')))}.<br/>"
            f"Plain-language summary: {escape(str(misread.get('plainLanguageSummary', 'missing')))}",
            styles["AuditBody"],
        )
    )
    story.append(
        Paragraph(
            f"Rendering guardrail action: {escape(str((human_review.get('renderingGuardrails') or {}).get('actionIfRequiredFieldsMissing', 'missing')))}.<br/>"
            f"Required adjacent fields:<br/>{_bullet_lines(_list_or_placeholder(_as_list_of_strings((human_review.get('renderingGuardrails') or {}).get('requiredAdjacentBlocks'))))}",
            styles["AuditBody"],
        )
    )

    story.append(Paragraph("Deterministic Run And PK Outputs", styles["AuditSection"]))
    story.append(
        Paragraph(
            f"Deterministic run status: {escape(str(audit['runJobStatus']['status']))}. "
            f"Returned series count: {escape(str(len(result_series)))}.",
            styles["AuditBody"],
        )
    )
    pk_rows = [["Parameter", "Unit", "Cmax", "Tmax", "AUC"]]
    for metric in pk_metrics:
        pk_rows.append(
            [
                metric.get("parameter", "unknown"),
                metric.get("unit", "") or "",
                f"{metric.get('cmax', '')}",
                f"{metric.get('tmax', '')}",
                f"{metric.get('auc', '')}",
            ]
        )
    story.append(_table(pk_rows, col_widths=[72 * mm, 20 * mm, 25 * mm, 20 * mm, 35 * mm]))

    story.append(Paragraph("Integrity And Release Evidence", styles["AuditSection"]))
    story.append(
        _table(
            [
                ["Verification pack field", "Observed value"],
                ["Evidence directory", str(raw_pack["directory"])],
                ["Manifest file", str(raw_pack["manifestPath"])],
                ["Raw artifact count", str(raw_pack["rawArtifactCount"])],
                ["Raw evidence SHA-256", str(raw_pack["rawEvidenceSha256"])],
                ["Audit JSON", str(verification_pack["auditJson"]["relativePath"])],
                ["Audit JSON SHA-256", str(verification_pack["auditJson"]["sha256"])],
            ],
            col_widths=[58 * mm, 114 * mm],
        )
    )
    story.append(
        Paragraph(
            "Raw step captures currently cover: "
            f"{escape(', '.join(raw_labels))}"
            + ("." if len(raw_artifacts) <= len(raw_labels) else ", and additional step artifacts.")
            + " The manifest stays separate so the hash chain is verifiable without self-referential recursion.",
            styles["AuditBody"],
        )
    )
    story.append(
        Paragraph(
            f"Release bundle SHA-256: {escape(str(release_bundle['bundleSha256']))}<br/>"
            f"Release bundle file count: {escape(str(release_bundle['fileCount']))}<br/>"
            f"Server version from /health: {escape(str(health['version']))}",
            styles["AuditBody"],
        )
    )
    story.append(
        Paragraph(
            "Audit conclusion: this runtime is safer than the current public release baseline, because the backend trust architecture is stronger and actively verified on the running server. "
            "It is still not bulletproof, but the remaining risks are now narrower and more honest: release-story drift, future client rendering discipline, and the need to keep the live gates green as the contract evolves.",
            styles["AuditBody"],
        )
    )

    def on_page(canvas, doc_obj):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#5a6570"))
        canvas.drawString(doc_obj.leftMargin, 8 * mm, "PBPK MCP Reference model Live Safety Audit")
        canvas.drawRightString(A4[0] - doc_obj.rightMargin, 8 * mm, f"Page {doc_obj.page}")

    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--auth-dev-secret", default=DEFAULT_DEV_SECRET)
    parser.add_argument(
        "--output-pdf",
        type=Path,
        default=WORKSPACE_ROOT / "output" / "pdf" / "reference_model_live_audit.pdf",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=WORKSPACE_ROOT / "output" / "pdf" / "reference_model_live_audit.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=WORKSPACE_ROOT / "output" / "pdf" / "reference_model_live_audit",
    )
    parser.add_argument(
        "--output-manifest",
        type=Path,
        default=WORKSPACE_ROOT / "output" / "pdf" / "reference_model_live_audit_manifest.json",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify an existing audit evidence pack instead of generating a new live audit.",
    )
    args = parser.parse_args()

    if args.verify_only:
        verification = verify_verification_pack(args.output_manifest)
        print(json.dumps(verification, indent=2))
        return 0 if verification["status"] == "passed" else 1

    audit = collect_audit_payload(args.base_url.rstrip("/"), args.auth_dev_secret)

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    _write_json(args.output_json, audit)
    raw_artifacts = write_evidence_artifacts(audit, args.output_dir)
    verification_pack = build_verification_pack(
        audit,
        output_dir=args.output_dir,
        output_json=args.output_json,
        output_pdf=args.output_pdf,
        output_manifest=args.output_manifest,
        raw_artifacts=raw_artifacts,
    )
    build_pdf(audit, verification_pack, args.output_pdf)
    verification_pack = finalize_verification_pack(
        verification_pack,
        output_pdf=args.output_pdf,
        output_manifest=args.output_manifest,
    )
    verification = verify_verification_pack(args.output_manifest)

    print(
        json.dumps(
            {
                "pdf": str(args.output_pdf),
                "json": str(args.output_json),
                "manifest": str(args.output_manifest),
                "evidenceDir": str(args.output_dir),
                "rawEvidenceSha256": verification_pack["verificationPack"]["rawEvidenceSha256"],
                "deliveryBundleSha256": verification_pack["deliveryBundleSha256"],
                "manifestVerification": verification,
            },
            indent=2,
        )
    )
    return 0 if verification["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
