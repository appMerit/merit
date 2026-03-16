"""Async HTTP client for remote error analysis."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from .types import AnalysisResponse, ServerConfig


class AnalysisClient:
    """Client for submitting analysis payloads and polling results."""

    RETRYABLE_STATUS_CODES = {408, 429}
    SERVER_ERROR_THRESHOLD = 500

    def __init__(self, config: ServerConfig, http_client: httpx.AsyncClient | None = None) -> None:
        self._validate_auth_config(config)
        self._config = config
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=config.base_url.rstrip("/"),
            timeout=config.timeout_s,
            headers=self._build_headers(config),
        )

    @staticmethod
    def _build_headers(config: ServerConfig) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        return headers

    @staticmethod
    def _validate_auth_config(config: ServerConfig) -> None:
        if config.api_key:
            return

        if AnalysisClient._is_localhost(config.base_url):
            return

        msg = "MERIT_API_KEY is required for non-localhost analysis endpoints"
        raise RuntimeError(msg)

    @staticmethod
    def _is_localhost(base_url: str) -> bool:
        parse_target = base_url if "://" in base_url else f"http://{base_url}"
        host = urlparse(parse_target).hostname
        return host in {"localhost", "127.0.0.1", "::1"}

    async def aclose(self) -> None:
        """Close the internal HTTP client if owned by this instance."""
        if self._owns_client and not self._http.is_closed:
            await self._http.aclose()

    async def analyze_errors(
        self,
        failure_signatures: list[dict[str, Any]],
        codebase_zip: Path,
    ) -> AnalysisResponse:
        """Submit an error analysis job and await terminal status."""
        submitted = await self._submit_analysis(failure_signatures, codebase_zip)
        status = str(submitted.get("status", "")).lower()

        if status in {"completed", "failed"}:
            return submitted

        job_id = submitted.get("job_id")
        if not isinstance(job_id, str) or not job_id:
            msg = "Analysis API did not return job_id"
            raise RuntimeError(msg)

        status_url = submitted.get("status_url")
        poll_target = (
            str(status_url)
            if isinstance(status_url, str) and status_url
            else f"/api/v1/error-analyzer/jobs/{job_id}"
        )

        return await self._poll_job(poll_target)

    async def _submit_analysis(
        self,
        failure_signatures: list[dict[str, Any]],
        codebase_zip: Path,
    ) -> AnalysisResponse:
        payload_bytes = json.dumps(failure_signatures).encode("utf-8")
        data = {
            "min_cluster_size": "5",
            "max_samples_per_cluster": "3",
        }

        attempts = self._config.retry_max_attempts
        for attempt in range(attempts):
            with codebase_zip.open("rb") as zip_file:
                files = {
                    "code_zip": ("code.zip", zip_file, "application/zip"),
                    "failure_signatures": (
                        "failure_signatures.json",
                        payload_bytes,
                        "application/json",
                    ),
                }

                try:
                    response = await self._http.post(
                        "/api/v1/error-analyzer/analyze",
                        data=data,
                        files=files,
                    )
                except (httpx.TimeoutException, httpx.TransportError):
                    if attempt == attempts - 1:
                        raise
                    await self._sleep_backoff(attempt)
                    continue

            if self._is_retryable_response(response.status_code):
                if attempt == attempts - 1:
                    await response.aread()
                    response.raise_for_status()
                await response.aread()
                await self._sleep_backoff(attempt)
                continue

            response.raise_for_status()
            payload: AnalysisResponse = response.json()
            return payload

        msg = "Analysis submission exhausted retries"
        raise RuntimeError(msg)

    async def _poll_job(self, poll_target: str) -> AnalysisResponse:
        for _ in range(self._config.poll_max_attempts):
            payload = await self._fetch_job_status(poll_target)
            status = str(payload.get("status", "")).lower()

            if status in {"completed", "failed"}:
                return payload

            await asyncio.sleep(self._config.poll_interval_s)

        timeout_seconds = int(self._config.poll_interval_s * self._config.poll_max_attempts)
        msg = f"Analysis polling timed out after {timeout_seconds}s"
        raise RuntimeError(msg)

    async def _fetch_job_status(self, poll_target: str) -> AnalysisResponse:
        attempts = self._config.retry_max_attempts

        for attempt in range(attempts):
            try:
                response = await self._http.get(poll_target)
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt == attempts - 1:
                    raise
                await self._sleep_backoff(attempt)
                continue

            if self._is_retryable_response(response.status_code):
                if attempt == attempts - 1:
                    await response.aread()
                    response.raise_for_status()
                await response.aread()
                await self._sleep_backoff(attempt)
                continue

            response.raise_for_status()
            payload: AnalysisResponse = response.json()
            return payload

        msg = "Analysis polling exhausted retries"
        raise RuntimeError(msg)

    def _is_retryable_response(self, status_code: int) -> bool:
        return (
            status_code in self.RETRYABLE_STATUS_CODES or status_code >= self.SERVER_ERROR_THRESHOLD
        )

    async def _sleep_backoff(self, attempt: int) -> None:
        delay = min(
            self._config.retry_max_delay_s,
            self._config.retry_base_delay_s * (2**attempt),
        )
        await asyncio.sleep(delay)
