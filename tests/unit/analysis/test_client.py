from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from merit.analysis.client import AnalysisClient
from merit.analysis.types import ServerConfig


@pytest.mark.asyncio
async def test_analyze_errors_submits_and_polls_until_completed(tmp_path: Path) -> None:
    zip_path = tmp_path / "codebase.zip"
    zip_path.write_bytes(b"zip-bytes")

    requests: list[httpx.Request] = []
    post_body = ""
    poll_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_body, poll_count
        requests.append(request)

        if request.method == "POST" and request.url.path == "/api/v1/error-analyzer/analyze":
            post_body = request.read().decode("utf-8", errors="ignore")
            return httpx.Response(
                201,
                json={
                    "job_id": "job-1",
                    "status": "pending",
                    "status_url": "/api/v1/error-analyzer/jobs/job-1",
                },
            )

        if request.method == "GET" and request.url.path == "/api/v1/error-analyzer/jobs/job-1":
            poll_count += 1
            if poll_count == 1:
                return httpx.Response(
                    200,
                    json={
                        "job_id": "job-1",
                        "status": "running",
                        "progress": {"percent_complete": 40},
                    },
                )

            return httpx.Response(
                200,
                json={
                    "job_id": "job-1",
                    "status": "completed",
                    "result": {
                        "clusters_found": 1,
                        "report_data": {"clusters": []},
                    },
                },
            )

        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="https://api.example.com", transport=transport) as http:
        client = AnalysisClient(
            config=ServerConfig(
                base_url="https://api.example.com",
                api_key="secret",
                poll_interval_s=0.0,
                retry_base_delay_s=0.0,
                retry_max_delay_s=0.0,
            ),
            http_client=http,
        )

        result = await client.analyze_errors(
            failure_signatures=[
                {
                    "case_id": "case-1",
                    "timestamp": "2026-02-11T10:00:00Z",
                    "test_name": "test_case",
                    "test_module": "tests/test_mod.py",
                    "cluster_key": "ASSERTION 1",
                    "fix_context": {
                        "error_message": "boom",
                        "failed_assertions": [],
                        "test_file": "tests/test_mod.py",
                        "input_data": {},
                        "actual_output": {},
                        "code_locations": [],
                    },
                }
            ],
            codebase_zip=zip_path,
        )

    assert result["status"] == "completed"
    assert poll_count == 2
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/v1/error-analyzer/analyze"
    assert requests[1].url.path == "/api/v1/error-analyzer/jobs/job-1"
    assert 'name="code_zip"' in post_body
    assert 'name="failure_signatures"' in post_body
    assert 'name="min_cluster_size"' in post_body
    assert 'name="max_samples_per_cluster"' in post_body


@pytest.mark.asyncio
async def test_analyze_errors_returns_failed_terminal_payload(tmp_path: Path) -> None:
    zip_path = tmp_path / "codebase.zip"
    zip_path.write_bytes(b"zip-bytes")

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(
                201,
                json={
                    "job_id": "job-1",
                    "status": "pending",
                    "status_url": "/api/v1/error-analyzer/jobs/job-1",
                },
            )

        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "job_id": "job-1",
                    "status": "failed",
                    "error": {"message": "analysis exploded", "failed_at": "analyzing"},
                },
            )

        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="https://api.example.com", transport=transport) as http:
        client = AnalysisClient(
            config=ServerConfig(
                base_url="https://api.example.com",
                api_key="secret",
                poll_interval_s=0.0,
                retry_base_delay_s=0.0,
                retry_max_delay_s=0.0,
            ),
            http_client=http,
        )

        result = await client.analyze_errors(
            failure_signatures=[],
            codebase_zip=zip_path,
        )

    assert result["status"] == "failed"
    assert result["error"]["message"] == "analysis exploded"


@pytest.mark.asyncio
async def test_submit_retries_on_429_then_succeeds(tmp_path: Path) -> None:
    zip_path = tmp_path / "codebase.zip"
    zip_path.write_bytes(b"zip-bytes")

    post_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal post_count

        if request.method == "POST":
            post_count += 1
            if post_count == 1:
                return httpx.Response(429, json={"detail": "rate limited"})
            return httpx.Response(
                201,
                json={
                    "job_id": "job-1",
                    "status": "pending",
                    "status_url": "/api/v1/error-analyzer/jobs/job-1",
                },
            )

        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "job_id": "job-1",
                    "status": "completed",
                    "result": {"clusters_found": 0, "report_data": {"clusters": []}},
                },
            )

        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(base_url="https://api.example.com", transport=transport) as http:
        client = AnalysisClient(
            config=ServerConfig(
                base_url="https://api.example.com",
                api_key="secret",
                poll_interval_s=0.0,
                retry_max_attempts=3,
                retry_base_delay_s=0.0,
                retry_max_delay_s=0.0,
            ),
            http_client=http,
        )

        result = await client.analyze_errors(
            failure_signatures=[],
            codebase_zip=zip_path,
        )

    assert post_count == 2
    assert result["status"] == "completed"


def test_analysis_client_requires_api_key_for_remote_base_url() -> None:
    with pytest.raises(RuntimeError, match="MERIT_API_KEY"):
        AnalysisClient(ServerConfig(base_url="https://api.example.com"))


@pytest.mark.asyncio
async def test_analysis_client_allows_missing_api_key_for_localhost() -> None:
    async with httpx.AsyncClient(base_url="http://localhost:8000") as http:
        client = AnalysisClient(
            ServerConfig(base_url="http://localhost:8000"),
            http_client=http,
        )
        await client.aclose()
