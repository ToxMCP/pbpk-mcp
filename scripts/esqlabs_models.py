#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_METADATA_ROOT = WORKSPACE_ROOT / "var" / "models" / "esqlabs"
SOURCE_POLICY_PATH = PUBLIC_METADATA_ROOT / "sources.json"
DEFAULT_INDEX_PATH = PUBLIC_METADATA_ROOT / "index.json"
MODELS_ROOT_ENV = "PBPK_ESQLABS_MODELS_ROOT"
BRIDGE_PATH = WORKSPACE_ROOT / "scripts" / "ospsuite_bridge.R"
DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_CONTAINER = "pbpk_mcp-api-1"
DEFAULT_SMOKE_MODELS = [
    "pregnant-pksim",
    "xspec-pcpksim-rat",
    "tissuetmdd-repeated-dose",
    "esqlabsr-simple",
]


CATALOG: list[dict[str, str]] = [
    {
        "simulationId": "esqapp-aciclovir",
        "repo": "ESQapp",
        "repoPath": "tests/testthat/data/Models/Simulations/Aciclovir.pkml",
        "filename": "Aciclovir.pkml",
    },
    {
        "simulationId": "xspec-pcberezh-mouse",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCBerezhkovskiy_CPPKSimStandard_Mouse.pkml",
        "filename": "Sim_Compound_PCBerezhkovskiy_CPPKSimStandard_Mouse.pkml",
    },
    {
        "simulationId": "xspec-pcberezh-rabbit",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCBerezhkovskiy_CPPKSimStandard_Rabbit.pkml",
        "filename": "Sim_Compound_PCBerezhkovskiy_CPPKSimStandard_Rabbit.pkml",
    },
    {
        "simulationId": "xspec-pcberezh-rat",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCBerezhkovskiy_CPPKSimStandard_Rat.pkml",
        "filename": "Sim_Compound_PCBerezhkovskiy_CPPKSimStandard_Rat.pkml",
    },
    {
        "simulationId": "xspec-pcpksim-mouse",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCPKSimStandard_CPPKSimStandard_Mouse.pkml",
        "filename": "Sim_Compound_PCPKSimStandard_CPPKSimStandard_Mouse.pkml",
    },
    {
        "simulationId": "xspec-pcpksim-rabbit",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCPKSimStandard_CPPKSimStandard_Rabbit.pkml",
        "filename": "Sim_Compound_PCPKSimStandard_CPPKSimStandard_Rabbit.pkml",
    },
    {
        "simulationId": "xspec-pcpksim-rat",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCPKSimStandard_CPPKSimStandard_Rat.pkml",
        "filename": "Sim_Compound_PCPKSimStandard_CPPKSimStandard_Rat.pkml",
    },
    {
        "simulationId": "xspec-pcpt-mouse",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCPT_CPPKSimStandard_Mouse.pkml",
        "filename": "Sim_Compound_PCPT_CPPKSimStandard_Mouse.pkml",
    },
    {
        "simulationId": "xspec-pcpt-rabbit",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCPT_CPPKSimStandard_Rabbit.pkml",
        "filename": "Sim_Compound_PCPT_CPPKSimStandard_Rabbit.pkml",
    },
    {
        "simulationId": "xspec-pcpt-rat",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCPT_CPPKSimStandard_Rat.pkml",
        "filename": "Sim_Compound_PCPT_CPPKSimStandard_Rat.pkml",
    },
    {
        "simulationId": "xspec-pcrr-mouse",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCRR_CPPKSimStandard_Mouse.pkml",
        "filename": "Sim_Compound_PCRR_CPPKSimStandard_Mouse.pkml",
    },
    {
        "simulationId": "xspec-pcrr-rabbit",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCRR_CPPKSimStandard_Rabbit.pkml",
        "filename": "Sim_Compound_PCRR_CPPKSimStandard_Rabbit.pkml",
    },
    {
        "simulationId": "xspec-pcrr-rat",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCRR_CPPKSimStandard_Rat.pkml",
        "filename": "Sim_Compound_PCRR_CPPKSimStandard_Rat.pkml",
    },
    {
        "simulationId": "xspec-pcschmitt-mouse",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCSchmitt_CPPKSimStandard_Mouse.pkml",
        "filename": "Sim_Compound_PCSchmitt_CPPKSimStandard_Mouse.pkml",
    },
    {
        "simulationId": "xspec-pcschmitt-rabbit",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCSchmitt_CPPKSimStandard_Rabbit.pkml",
        "filename": "Sim_Compound_PCSchmitt_CPPKSimStandard_Rabbit.pkml",
    },
    {
        "simulationId": "xspec-pcschmitt-rat",
        "repo": "PBPK-for-cross-species-extrapolation",
        "repoPath": "Models/Simulations/AllSpecies/Sim_Compound_PCSchmitt_CPPKSimStandard_Rat.pkml",
        "filename": "Sim_Compound_PCSchmitt_CPPKSimStandard_Rat.pkml",
    },
    {
        "simulationId": "tissuetmdd-repeated-dose",
        "repo": "TissueTMDD",
        "repoPath": "inst/extdata/repeated dose model.pkml",
        "filename": "repeated dose model.pkml",
    },
    {
        "simulationId": "esqlabsr-aciclovir",
        "repo": "esqlabsR",
        "repoPath": "inst/extdata/examples/TestProject/Models/Simulations/Aciclovir.pkml",
        "filename": "Aciclovir.pkml",
    },
    {
        "simulationId": "esqlabsr-simple",
        "repo": "esqlabsR",
        "repoPath": "tests/data/simple.pkml",
        "filename": "simple.pkml",
    },
    {
        "simulationId": "esqlabsr-simple2",
        "repo": "esqlabsR",
        "repoPath": "tests/data/simple2.pkml",
        "filename": "simple2.pkml",
    },
    {
        "simulationId": "preg-2w-pksim",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/2_weeks_simulation_PKSim.pkml",
        "filename": "2_weeks_simulation_PKSim.pkml",
    },
    {
        "simulationId": "preg-2w-poulin",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/2_weeks_simulation_Poulin.pkml",
        "filename": "2_weeks_simulation_Poulin.pkml",
    },
    {
        "simulationId": "preg-2w-rr",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/2_weeks_simulation_R&R.pkml",
        "filename": "2_weeks_simulation_R&R.pkml",
    },
    {
        "simulationId": "preg-2w-schmitt",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/2_weeks_simulation_Schmitt.pkml",
        "filename": "2_weeks_simulation_Schmitt.pkml",
    },
    {
        "simulationId": "preg-6m-pksim",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/6_month_simulation_PKSim.pkml",
        "filename": "6_month_simulation_PKSim.pkml",
    },
    {
        "simulationId": "preg-6m-poulin",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/6_month_simulation_Poulin.pkml",
        "filename": "6_month_simulation_Poulin.pkml",
    },
    {
        "simulationId": "preg-6m-rr",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/6_month_simulation_R&R.pkml",
        "filename": "6_month_simulation_R&R.pkml",
    },
    {
        "simulationId": "preg-6m-schmitt",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/6_month_simulation_Schmitt.pkml",
        "filename": "6_month_simulation_Schmitt.pkml",
    },
    {
        "simulationId": "pregnant-pksim",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/Pregnant_simulation_PKSim.pkml",
        "filename": "Pregnant_simulation_PKSim.pkml",
    },
    {
        "simulationId": "pregnant-poulin",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/Pregnant_simulation_Poulin.pkml",
        "filename": "Pregnant_simulation_Poulin.pkml",
    },
    {
        "simulationId": "pregnant-rr",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/Pregnant_simulation_R&R.pkml",
        "filename": "Pregnant_simulation_R&R.pkml",
    },
    {
        "simulationId": "pregnant-schmitt",
        "repo": "pregnancy-neonates-batch-run",
        "repoPath": "pkmlFiles and physiological db/Pregnant_simulation_Schmitt.pkml",
        "filename": "Pregnant_simulation_Schmitt.pkml",
    },
]


def load_source_policies() -> dict[str, dict[str, Any]]:
    payload = json.loads(SOURCE_POLICY_PATH.read_text())
    policies = payload.get("sources")
    if not isinstance(policies, dict):
        raise ValueError(f"Missing sources object in {SOURCE_POLICY_PATH}")
    missing = sorted({entry["repo"] for entry in CATALOG} - set(policies))
    if missing:
        raise ValueError(f"Missing source policies for: {', '.join(missing)}")
    return policies


def source_commit(entry: dict[str, str], policy: dict[str, Any]) -> str:
    overrides = policy.get("fileCommitOverrides", {})
    return str(overrides.get(entry["repoPath"], policy["sourceCommit"]))


def resolve_models_root(value: str | None) -> Path:
    raw = value or os.getenv(MODELS_ROOT_ENV)
    if not raw:
        raise RuntimeError(
            f"Third-party models are not bundled. Set {MODELS_ROOT_ENV} or pass --models-root "
            "with an explicitly authorized private local model directory."
        )
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise RuntimeError(f"Third-party model root does not exist or is not a directory: {root}")
    return root


def model_path(entry: dict[str, str], models_root: Path) -> Path:
    return models_root / entry["repo"] / entry["filename"]


def git_blob_sha1(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode()
    return hashlib.sha1(header + data).hexdigest()


def public_entry(
    entry: dict[str, str],
    policies: dict[str, dict[str, Any]],
    models_root: Path,
) -> dict[str, Any]:
    repo = entry["repo"]
    repo_path = entry["repoPath"]
    policy = policies[repo]
    commit = source_commit(entry, policy)
    path = model_path(entry, models_root)
    data = path.read_bytes()
    raw_path = urllib.parse.quote(repo_path, safe="/")
    return {
        "simulationId": entry["simulationId"],
        "repository": repo,
        "repositoryUrl": policy["repositoryUrl"],
        "sourceCommit": commit,
        "sourcePath": repo_path,
        "sourceUrl": f"https://raw.githubusercontent.com/esqLABS/{repo}/{commit}/{raw_path}",
        "originalRelativePath": f"var/models/esqlabs/{repo}/{entry['filename']}",
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "gitBlobSha1": git_blob_sha1(data),
        "sourceMatchVerifiedAt": policy["sourceMatchVerifiedAt"],
        "declaredLicense": policy["declaredLicense"],
        "licenseEvidenceUrl": policy.get("licenseEvidenceUrl"),
        "licenseReviewStatus": policy["licenseReviewStatus"],
        "redistributionStatus": policy["redistributionStatus"],
    }


def runtime_entry(entry: dict[str, str], policies: dict[str, dict[str, Any]]) -> dict[str, str]:
    repo = entry["repo"]
    filename = entry["filename"]
    repo_path = entry["repoPath"]
    commit = source_commit(entry, policies[repo])
    raw_path = urllib.parse.quote(repo_path, safe="/")
    return {
        **entry,
        "containerPath": f"/app/var/models/esqlabs/{repo}/{filename}",
        "sourceUrl": f"https://raw.githubusercontent.com/esqLABS/{repo}/{commit}/{raw_path}",
        "repoUrl": policies[repo]["repositoryUrl"],
    }


def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, capture_output=True, text=True)


def api_json(
    base_url: str, path: str, payload: dict[str, Any] | None = None, timeout: int = 60
) -> Any:
    url = f"{base_url.rstrip('/')}{path}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def loaded_ids(base_url: str) -> set[str]:
    data = api_json(base_url, "/mcp/resources/simulations?page=1&limit=500", timeout=30)
    return {item["simulationId"] for item in data.get("items", [])}


def write_index(output: Path, models_root: Path) -> None:
    policies = load_source_policies()
    payload = {
        "schemaVersion": "pbpk-third-party-model-index.v1",
        "releaseDecision": "not-approved-for-public-redistribution",
        "models": [public_entry(entry, policies, models_root) for entry in CATALOG],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n")


def assert_public_release_approved() -> None:
    policies = load_source_policies()
    blocked = sorted(
        repo
        for repo, policy in policies.items()
        if policy["redistributionStatus"] != "approved_for_public_release"
    )
    if blocked:
        raise RuntimeError(
            "Third-party model redistribution is not approved for: " + ", ".join(blocked)
        )


def assert_public_tree_excludes_third_party_assets() -> None:
    forbidden: list[Path] = []
    forbidden.extend(PUBLIC_METADATA_ROOT.rglob("*.pkml"))
    forbidden.extend(PUBLIC_METADATA_ROOT.rglob("*.profile.json"))
    smoke_report = PUBLIC_METADATA_ROOT / "smoke_run_report.json"
    if smoke_report.exists():
        forbidden.append(smoke_report)
    duplicate = WORKSPACE_ROOT / "var" / "models" / "Pregnant_simulation_PKSim.pkml"
    if duplicate.exists():
        forbidden.append(duplicate)
    if forbidden:
        paths = sorted(path.relative_to(WORKSPACE_ROOT).as_posix() for path in set(forbidden))
        raise RuntimeError(
            "Public tree contains third-party model assets that are not approved for redistribution: "
            + ", ".join(paths)
        )

    payload = json.loads(DEFAULT_INDEX_PATH.read_text())
    if payload.get("releaseDecision") != "not-approved-for-public-redistribution":
        raise RuntimeError(
            "Third-party model inventory does not retain the fail-closed release decision"
        )


def prepare_live_server(container: str, models_root: Path) -> None:
    run(
        [
            "docker",
            "exec",
            "-u",
            "0",
            container,
            "sh",
            "-lc",
            "mkdir -p /app/scripts /app/var/models/esqlabs && chown -R mcp:mcp /app/scripts /app/var/models",
        ]
    )
    run(["docker", "cp", str(BRIDGE_PATH), f"{container}:/app/scripts/ospsuite_bridge.R"])
    run(["docker", "cp", f"{models_root}/.", f"{container}:/app/var/models/esqlabs"])

    patch_code = """
from pathlib import Path
path = Path('/app/src/mcp_bridge/adapter/ospsuite.py')
if path.exists():
    text = path.read_text()
    text = text.replace('from threading import Lock', 'from threading import RLock')
    text = text.replace('self._lock = Lock()', 'self._lock = RLock()')
    path.write_text(text)
"""
    run(["docker", "exec", "-u", "0", container, "python3", "-c", patch_code], check=False)
    run(["docker", "restart", container])

    deadline = time.time() + 60
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            api_json(DEFAULT_BASE_URL, "/health", timeout=5)
            return
        except Exception as exc:  # pragma: no cover - operational polling
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Timed out waiting for {container} health") from last_error


def load_models(
    base_url: str, model_ids: set[str] | None = None, skip_existing: bool = True
) -> dict[str, Any]:
    existing = loaded_ids(base_url) if skip_existing else set()
    results: list[dict[str, Any]] = []
    policies = load_source_policies()

    for entry in (runtime_entry(item, policies) for item in CATALOG):
        simulation_id = entry["simulationId"]
        if model_ids and simulation_id not in model_ids:
            continue
        if skip_existing and simulation_id in existing:
            results.append({"simulationId": simulation_id, "status": "already_loaded"})
            continue
        response = api_json(
            base_url,
            "/mcp/call_tool",
            payload={
                "tool": "load_simulation",
                "arguments": {
                    "filePath": entry["containerPath"],
                    "simulationId": simulation_id,
                },
            },
            timeout=180,
        )
        if response.get("isError"):
            results.append({"simulationId": simulation_id, "status": "error", "response": response})
        else:
            results.append({"simulationId": simulation_id, "status": "loaded"})

    return {
        "loaded": sum(1 for item in results if item["status"] == "loaded"),
        "already_loaded": sum(1 for item in results if item["status"] == "already_loaded"),
        "errors": [item for item in results if item["status"] == "error"],
        "results": results,
    }


def poll_job(base_url: str, job_id: str, timeout_seconds: int = 300) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_payload: dict[str, Any] | None = None
    while time.time() < deadline:
        response = api_json(
            base_url,
            "/mcp/call_tool",
            payload={"tool": "get_job_status", "arguments": {"jobId": job_id}},
            timeout=30,
        )
        job = response["structuredContent"]["job"]
        last_payload = job
        if job["status"] in {"succeeded", "failed", "cancelled", "timeout"}:
            return job
        time.sleep(2)
    raise RuntimeError(f"Timed out waiting for job {job_id}: {last_payload}")


def smoke_run(base_url: str, model_ids: list[str]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for simulation_id in model_ids:
        run_id = f"smoke-{simulation_id}-{int(time.time())}"
        start = time.time()
        submit = api_json(
            base_url,
            "/mcp/call_tool",
            payload={
                "tool": "run_simulation",
                "arguments": {"simulationId": simulation_id, "runId": run_id},
            },
            timeout=60,
        )
        job_id = submit["structuredContent"]["jobId"]
        job = poll_job(base_url, job_id)
        report: dict[str, Any] = {
            "simulationId": simulation_id,
            "jobId": job_id,
            "status": job["status"],
            "durationSeconds": round(time.time() - start, 3),
            "resultId": job.get("resultId"),
        }
        if job["status"] == "succeeded" and job.get("resultId"):
            metrics_response = api_json(
                base_url,
                "/mcp/call_tool",
                payload={
                    "tool": "calculate_pk_parameters",
                    "arguments": {"resultsId": job["resultId"]},
                },
                timeout=60,
            )
            structured = metrics_response.get("structuredContent", {})
            metrics = structured.get("metrics", [])
            report["metricCount"] = len(metrics)
            report["metricsPreview"] = metrics[:3]
        else:
            report["error"] = job.get("error")
        reports.append(report)
    return reports


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manage esqLABS PBPK provenance and authorized private model use."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    index_parser = subparsers.add_parser(
        "write-index", help="Write a machine-readable model index."
    )
    index_parser.add_argument(
        "--output",
        default=str(DEFAULT_INDEX_PATH),
        help="Path to write the JSON index.",
    )
    index_parser.add_argument(
        "--models-root",
        default=None,
        help=f"Private local model directory. Defaults to ${MODELS_ROOT_ENV}.",
    )
    index_parser.add_argument(
        "--public-release",
        action="store_true",
        help="Refuse to write unless every third-party source is approved for public redistribution.",
    )

    prepare_parser = subparsers.add_parser(
        "prepare-live-server",
        help="Sync models and bridge into the running API container and restart it.",
    )
    prepare_parser.add_argument("--container", default=DEFAULT_CONTAINER)
    prepare_parser.add_argument(
        "--models-root",
        default=None,
        help=f"Private local model directory. Defaults to ${MODELS_ROOT_ENV}.",
    )

    subparsers.add_parser(
        "check-public-tree",
        help="Fail if unapproved third-party model assets are present in the public repository tree.",
    )

    load_parser = subparsers.add_parser("load", help="Load models into the MCP registry.")
    load_parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    load_parser.add_argument("--model-id", action="append", default=[])
    load_parser.add_argument("--no-skip-existing", action="store_true")

    smoke_parser = subparsers.add_parser(
        "smoke-run",
        help="Run a representative subset of loaded models and capture PK metric previews.",
    )
    smoke_parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    smoke_parser.add_argument("--model-id", action="append", default=[])
    smoke_parser.add_argument(
        "--output",
        default=str(WORKSPACE_ROOT / "var" / "esqlabs_external_smoke_run_report.json"),
        help="Path to write the smoke report JSON.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "write-index":
        if args.public_release:
            try:
                assert_public_release_approved()
            except RuntimeError as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                return 2
        try:
            models_root = resolve_models_root(args.models_root)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        write_index(Path(args.output), models_root)
        print(Path(args.output))
        return 0

    if args.command == "prepare-live-server":
        try:
            models_root = resolve_models_root(args.models_root)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        prepare_live_server(args.container, models_root)
        print(f"prepared {args.container}")
        return 0

    if args.command == "check-public-tree":
        try:
            assert_public_tree_excludes_third_party_assets()
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        print("public tree excludes unapproved third-party model assets")
        return 0

    if args.command == "load":
        selected = set(args.model_id) if args.model_id else None
        result = load_models(
            args.base_url, model_ids=selected, skip_existing=not args.no_skip_existing
        )
        print(json.dumps(result, indent=2))
        return 0 if not result["errors"] else 1

    if args.command == "smoke-run":
        selected = args.model_id or DEFAULT_SMOKE_MODELS
        report = smoke_run(args.base_url, selected)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + "\n")
        print(output)
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    sys.exit(main())
