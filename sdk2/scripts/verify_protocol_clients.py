"""Verify actual clients, separate environments and backend application parity."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def ready(process, url):
    for _ in range(200):
        if process.poll() is not None:
            raise RuntimeError("Fixture exited; inspect its log")
        try:
            with urlopen(url, timeout=0.2):
                return
        except OSError:
            time.sleep(0.025)
    raise RuntimeError("Fixture did not start")


def normalized(report):
    # Preserve all domain results, schemas, core hints, warnings and rendering
    # requirements. Normalize only verified transport envelopes and measured
    # runtime identities/timestamps. Raw reports remain available for review.
    result = {
        key: report[key]
        for key in [
            "catalog",
            "viewerCatalog",
            "resources",
            "templates",
            "prompts",
            "results",
            "errors",
        ]
    }
    for key in ["catalog", "viewerCatalog"]:
        result[key] = [dict(item) for item in result[key]]
        for item in result[key]:
            meta = item.pop("_meta", {})
            policy = meta.pop("org.toxmcp/toolPolicy", {})
            if policy:
                item.setdefault("annotations", {}).update(policy)
            assert not meta, meta
            execution = item.pop("execution", None)
            if execution is not None:
                assert execution == {"taskSupport": "forbidden"}
    identities = {}
    for label, wire in result["results"].items():
        structured = wire.get("structuredContent", {})
        if isinstance(structured, dict):
            for field in ["jobId"]:
                if field in structured:
                    identities[structured[field]] = "<backend-job-id>"
            snapshot = structured.get("governance", {}).get("snapshotId")
            if snapshot:
                identities[snapshot] = "<backend-snapshot-id>"

    def clean(value, field=None):
        if isinstance(value, list):
            return [clean(item) for item in value]
        if isinstance(value, dict):
            value = dict(value)
            metadata = dict(value.get("_meta", {}))
            stamp = metadata.pop("io.modelcontextprotocol/serverInfo", None)
            if stamp is not None:
                assert stamp["name"] == "pbpk-mcp-sdk2" and stamp["version"] == "0.1.0"
            annotations = metadata.pop("org.toxmcp/resultAnnotations", None)
            if annotations is not None:
                value["annotations"] = annotations
            cache = metadata.pop("io.modelcontextprotocol/cacheHint", None)
            if cache is not None:
                assert cache == {"ttlMs": 0, "cacheScope": "private"}, cache
            if metadata:
                value["_meta"] = metadata
            else:
                value.pop("_meta", None)
            if "resultType" in value:
                assert value.pop("resultType") == "complete"
            if "ttlMs" in value:
                assert value.pop("ttlMs") == 0 and value.pop("cacheScope") == "private"
            if value.get("isError") is False:
                value.pop("isError")
            return {key: clean(item, key) for key, item in value.items()}
        if isinstance(value, str):
            if value in identities:
                return identities[value]
            if field == "text":
                try:
                    parsed = json.loads(value)
                except ValueError:
                    return value
                return json.dumps(clean(parsed), sort_keys=True, separators=(",", ":"))
            if field in {
                "generatedAt",
                "createdAt",
                "lastAccessedAt",
                "lastAccessed",
                "modifiedAt",
                "queuedAt",
            }:
                assert "T" in value
                return "<backend-timestamp>"
        if field in {"queuedAt", "submittedAt", "startedAt", "finishedAt"} and isinstance(
            value, (float, int)
        ):
            assert value > 0
            return "<backend-timestamp>"
        return value

    result = clean(result)
    # Submission can race the worker. Verify legal states, then compare the
    # terminal record independently. This is not a scientific value change.
    for label in ["run", "idempotent-repeat"]:
        wire = result["results"][label]
        for data in [wire["structuredContent"], json.loads(wire["content"][0]["text"])]:
            assert data["status"] in {"queued", "running", "succeeded"}, data
            data["status"] = "<submission-race>"
            assert data["attempts"] in {0, 1}
            data["attempts"] = "<submission-race>"
        text = json.loads(wire["content"][0]["text"])
        text["status"] = "<submission-race>"
        text["attempts"] = "<submission-race>"
        wire["content"][0]["text"] = json.dumps(text, sort_keys=True, separators=(",", ":"))
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in ["backend-python", "legacy-python", "output-dir"]:
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--server-python", default=sys.executable)
    parser.add_argument("--server-root")
    parser.add_argument("--backend-root")
    args = parser.parse_args()
    output = Path(args.output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = {
        key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "VIRTUAL_ENV"}
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    reports = []
    with tempfile.TemporaryDirectory(prefix="pbpk-client-matrix-") as directory:
        workspace = Path(directory)
        model = workspace / "transport-fixture.pkml"
        model.write_text("<synthetic-transport-fixture/>\n")
        for modern in [False, True]:
            for transport in ["http", "stdio"]:
                label = ("modern" if modern else "legacy") + "-" + transport
                backend_port, frontend_port = port(), port()
                backend_url = f"http://127.0.0.1:{backend_port}"
                backend_env = dict(env)
                if args.backend_root:
                    backend_env["PYTHONPATH"] = str(Path(args.backend_root).resolve())
                front_env = {**env, "PBPK_SDK2_BACKEND_URL": backend_url}
                if args.server_root:
                    front_env["PYTHONPATH"] = str(Path(args.server_root).resolve())
                processes = []
                with (output / (label + ".log")).open("w") as log:
                    try:
                        backend = subprocess.Popen(
                            [
                                str(Path(args.backend_python).absolute()),
                                str(ROOT / "scripts/backend_fixture.py"),
                                "--port",
                                str(backend_port),
                                "--workspace",
                                str(workspace),
                            ],
                            cwd=workspace,
                            env=backend_env,
                            stdout=log,
                            stderr=log,
                        )
                        processes.append(backend)
                        ready(backend, backend_url + "/health")
                        command = [
                            str(
                                Path(
                                    args.server_python if modern else args.legacy_python
                                ).absolute()
                            ),
                            str(ROOT / "scripts/protocol_probe.py"),
                            "--backend-url",
                            backend_url,
                            "--server-python",
                            str(Path(args.server_python).absolute()),
                            "--model",
                            str(model),
                            "--output",
                            str(output / (label + ".json")),
                        ]
                        if args.server_root:
                            command += ["--server-root", str(Path(args.server_root).resolve())]
                        if modern:
                            command += ["--modern"]
                        if transport == "http":
                            frontend = subprocess.Popen(
                                [
                                    str(Path(args.server_python).absolute()),
                                    "-c",
                                    "from pbpk_mcp_sdk2.http import create_app; import uvicorn; uvicorn.run(create_app(),host='127.0.0.1',port="
                                    + str(frontend_port)
                                    + ",log_level='error')",
                                ],
                                cwd=workspace,
                                env=front_env,
                                stdout=log,
                                stderr=log,
                            )
                            processes.append(frontend)
                            frontend_url = f"http://127.0.0.1:{frontend_port}"
                            ready(frontend, frontend_url + "/health")
                            command += ["--url", frontend_url + "/mcp"]
                        subprocess.run(
                            command,
                            cwd=workspace,
                            env=env,
                            stdout=log,
                            stderr=log,
                            check=True,
                            timeout=120,
                        )
                    finally:
                        for process in reversed(processes):
                            process.terminate()
                            process.wait(timeout=15)
                report = json.loads((output / (label + ".json")).read_text())
                report = normalized(report)
                # The fixture path is the only deployment-dependent model input.
                encoded = (
                    json.dumps(report, sort_keys=True)
                    .replace(str(model), "<synthetic-model-path>")
                    .replace(str(workspace), "<synthetic-model-directory>")
                )
                report = json.loads(encoded)
                (output / (label + "-normalized.json")).write_text(
                    json.dumps(report, indent=2) + "\n"
                )
                reports.append(report)
                print(
                    label,
                    "19 privileged / 13 viewer tools;",
                    len(report["results"]),
                    "results; role + confirmation checks passed",
                    flush=True,
                )
    assert all(
        report == reports[0] for report in reports[1:]
    ), "Application or catalog parity changed; inspect normalized reports"
    summary = {
        "combinations": 4,
        "applicationResults": len(reports[0]["results"]),
        "privilegedTools": 19,
        "viewerTools": 13,
        "catalogSha256": hashlib.sha256(
            json.dumps(reports[0]["catalog"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "limitations": [
            "Offline InMemoryAdapter fixture, not R/ospsuite qualification",
            "Backend job/snapshot IDs, wall-clock timestamps and queued-worker races normalized; raw reports retained",
        ],
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__":
    main()
