"""Drive public SDK1/SDK2 APIs against the isolated transport and real backend."""

import argparse
import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

import anyio
import jwt
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SECRET = "pbpk-sdk2-offline-fixture-secret-32bytes!!"


def token(role, single_use=False):
    roles = ["viewer"] if role == "viewer" else ["viewer", "operator", "admin"]
    return jwt.encode(
        {
            "sub": "offline-transport-fixture",
            "roles": roles,
            **({"jti": str(uuid.uuid4())} if single_use else {}),
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        },
        SECRET,
        algorithm="HS256",
    )


@asynccontextmanager
async def connection(args, role="privileged", single_use=False):
    bearer = token(role, single_use)
    env = {
        key: value for key, value in os.environ.items() if key not in {"PYTHONPATH", "VIRTUAL_ENV"}
    }
    if args.server_root:
        env["PYTHONPATH"] = args.server_root
    env.update(PBPK_SDK2_BACKEND_URL=args.backend_url, PBPK_SDK2_BEARER_TOKEN=bearer)
    target = StdioServerParameters(
        command=args.server_python, args=["-m", "pbpk_mcp_sdk2.main", "--stdio"], env=env
    )
    # The console entrypoint is used through a tiny launcher because main exposes
    # both HTTP and stdio callables, without a module-level side effect.
    target.args = [str(Path(__file__).with_name("stdio_launcher.py"))]
    if args.modern:
        from mcp import Client

        if args.url:
            import httpx2
            from mcp.client.streamable_http import streamable_http_client

            async with httpx2.AsyncClient(
                headers={"Authorization": "Bearer " + bearer}
            ) as http_client:
                async with Client(
                    streamable_http_client(args.url, http_client=http_client)
                ) as client:
                    yield client, client.protocol_version
        else:
            async with Client(target) as client:
                yield client, client.protocol_version
    else:
        if args.url:
            from mcp.client.streamable_http import streamablehttp_client

            transport = streamablehttp_client(
                args.url, headers={"Authorization": "Bearer " + bearer}
            )
        else:
            transport = stdio_client(target)
        async with transport as streams, ClientSession(streams[0], streams[1]) as client:
            initialized = await client.initialize()
            yield client, initialized.protocolVersion


def wire(value):
    return value.model_dump(mode="json", by_alias=True, exclude_none=True)


async def collect(args):
    results, errors = {}, {}
    async with connection(args) as (client, protocol):
        catalog = wire(await client.list_tools())["tools"]
        assert len(catalog) == 19, len(catalog)
        resources = wire(await client.list_resources())["resources"]
        templates = wire(await client.list_resource_templates())["resourceTemplates"]
        prompts = wire(await client.list_prompts())["prompts"]

        async def call(label, name, arguments, *, critical=None, key=None, error=False):
            from mcp import types

            if args.modern:
                invocation = {
                    **({"critical": critical} if critical is not None else {}),
                    **({"idempotencyKey": key} if key else {}),
                }
                result = await client.call_tool(
                    name,
                    arguments,
                    meta={"org.toxmcp/invocation": invocation} if invocation else None,
                )
            else:
                params = types.CallToolRequestParams(
                    name=name,
                    arguments=arguments,
                    **({"critical": critical} if critical is not None else {}),
                    **({"idempotencyKey": key} if key else {}),
                )
                result = await client.send_request(
                    types.CallToolRequest(params=params), types.CallToolResult
                )
            result = wire(result)
            assert result.get("isError", False) == error, result
            results[label] = result
            return result.get("structuredContent", json.loads(result["content"][0]["text"]))

        async def failure(label, name, arguments, critical=None):
            try:
                await call(label, name, arguments, critical=critical)
            except Exception as exc:
                if not hasattr(exc, "error"):
                    raise
                errors[label] = wire(exc.error)
                return
            raise AssertionError(f"{label} unexpectedly succeeded")

        await call("discover", "discover_models", {"limit": 2})
        await failure(
            "confirmation-required",
            "load_simulation",
            {"filePath": args.model, "simulationId": "transport-fixture"},
        )
        await call(
            "load",
            "load_simulation",
            {"filePath": args.model, "simulationId": "transport-fixture"},
            critical=True,
        )
        await call(
            "invalid-input",
            "load_simulation",
            {"filePath": args.model + ".exe", "simulationId": "bad"},
            critical=True,
            error=True,
        )
        await call(
            "set-parameter",
            "set_parameter_value",
            {
                "simulationId": "transport-fixture",
                "parameterPath": "Transport|Dose",
                "value": 2.5,
                "unit": "mg",
            },
            critical=True,
        )
        await call(
            "get-parameter",
            "get_parameter_value",
            {"simulationId": "transport-fixture", "parameterPath": "Transport|Dose"},
        )
        await call("list-parameters", "list_parameters", {"simulationId": "transport-fixture"})
        await call(
            "validate",
            "validate_simulation_request",
            {"simulationId": "transport-fixture", "stage": "preflight"},
        )
        job = await call(
            "run",
            "run_simulation",
            {
                "simulationId": "transport-fixture",
                "runId": "transport-results",
                "timeoutSeconds": 10,
            },
            critical=True,
            key="transport-repeat",
        )
        repeat = await call(
            "idempotent-repeat",
            "run_simulation",
            {
                "simulationId": "transport-fixture",
                "runId": "transport-results",
                "timeoutSeconds": 10,
            },
            critical=True,
            key="transport-repeat",
        )
        assert job["jobId"] == repeat["jobId"]
        for _ in range(200):
            status = await call("job-terminal", "get_job_status", {"jobId": job["jobId"]})
            if status["status"] in {"succeeded", "failed", "timeout", "cancelled"}:
                break
            await anyio.sleep(0.025)
        assert status["status"] == "succeeded", status
        result = await call("results", "get_results", {"resultsId": "transport-results"})
        metrics = await call(
            "pk-metrics", "calculate_pk_parameters", {"resultsId": "transport-results"}
        )
        assert metrics["metrics"][0]["cmax"] == 1.0 and metrics["metrics"][0]["auc"] == 0.5
        await call("cancel-terminal", "cancel_job", {"jobId": job["jobId"]}, critical=True)
        for uri in [
            "pbpk://schemas/catalog",
            "pbpk://capability-matrix",
            "pbpk://contract-manifest",
            "pbpk://release-bundle-manifest",
            "pbpk://simulations",
        ]:
            results[uri] = wire(await client.read_resource(uri))
        assert result["series"][0]["values"] == [
            {"time": 0.0, "value": 0.0},
            {"time": 1.0, "value": 1.0},
        ]

    async with connection(args, "viewer") as (client, _):
        viewer = wire(await client.list_tools())["tools"]
        assert len(viewer) == 13
        try:
            if args.modern:
                await client.call_tool(
                    "load_simulation",
                    {"filePath": args.model, "simulationId": "forbidden"},
                    meta={"org.toxmcp/invocation": {"critical": True}},
                )
            else:
                from mcp import types

                await client.send_request(
                    types.CallToolRequest(
                        params=types.CallToolRequestParams(
                            name="load_simulation",
                            arguments={"filePath": args.model, "simulationId": "forbidden"},
                            critical=True,
                        )
                    ),
                    types.CallToolResult,
                )
        except Exception as exc:
            if not hasattr(exc, "error"):
                raise
            errors["viewer-denied"] = wire(exc.error)
            assert exc.error.code == -32001
        else:
            raise AssertionError("Confirmation bypassed viewer role")
    async with connection(args, single_use=True) as (client, _):
        single_use_catalog = wire(await client.list_tools())["tools"]
        assert (
            len(single_use_catalog) == 19
        ), "Transport consumed the single-use token before the actual RPC"
    return {
        "singleUseTokenAccepted": True,
        "clientSDK": version("mcp"),
        "protocol": protocol,
        "catalog": catalog,
        "viewerCatalog": viewer,
        "resources": resources,
        "templates": templates,
        "prompts": prompts,
        "results": results,
        "errors": errors,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ["server-python", "backend-url", "model", "output"]:
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--server-root")
    parser.add_argument("--url")
    parser.add_argument("--modern", action="store_true")
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(anyio.run(collect, args), indent=2) + "\n")
