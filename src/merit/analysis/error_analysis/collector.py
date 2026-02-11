"""Error-analysis data collection from SQLite."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import UUID

from merit.analysis.types import GuardrailViolationError
from merit.storage.sqlite.store import SQLiteStore


class ErrorDataCollector:
    """Collect failed/error execution data for remote analysis."""

    def __init__(self, db_path: Path) -> None:
        self._store = SQLiteStore(db_path)
        self._db_path = self._store.path

    async def get_latest_run_id(self) -> UUID | None:
        """Return the latest run identifier ordered by start time."""
        return await asyncio.to_thread(self._get_latest_run_id_sync)

    async def get_run(self, run_id: UUID) -> dict[str, Any]:
        """Return run-level summary and environment details."""
        return await asyncio.to_thread(self._get_run_sync, run_id)

    async def get_failure_signatures(
        self,
        run_id: UUID,
        *,
        run_timestamp: str,
        max_failed_tests: int,
        max_traceback_chars: int,
    ) -> list[dict[str, Any]]:
        """Return service-ready failure signature payloads."""
        return await asyncio.to_thread(
            self._get_failure_signatures_sync,
            run_id,
            run_timestamp,
            max_failed_tests,
            max_traceback_chars,
        )

    def _get_latest_run_id_sync(self) -> UUID | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT run_id FROM runs ORDER BY start_time DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return UUID(str(row["run_id"]))

    def _get_run_sync(self, run_id: UUID) -> dict[str, Any]:
        run = self._store.get_run(run_id)
        if run is None:
            msg = f"Run not found: {run_id}"
            raise ValueError(msg)

        return {
            "run_id": str(run.run_id),
            "start_time": run.start_time.isoformat(),
            "end_time": run.end_time.isoformat() if run.end_time else None,
            "environment": run.environment.to_dict(),
            "summary": {
                "failed": run.result.failed,
                "errors": run.result.errors,
                "skipped": run.result.skipped,
                "xfailed": run.result.xfailed,
                "total": run.result.total,
                "duration_ms": run.result.total_duration_ms,
                "stopped_early": run.result.stopped_early,
            },
        }

    def _get_failure_signatures_sync(
        self,
        run_id: UUID,
        run_timestamp: str,
        max_failed_tests: int,
        max_traceback_chars: int,
    ) -> list[dict[str, Any]]:
        run_id_str = str(run_id)
        with self._connect() as conn:
            execution_rows = conn.execute(
                """
                SELECT *
                FROM test_executions
                WHERE run_id = ? AND status IN ('failed', 'error')
                ORDER BY test_name ASC, execution_id ASC
                LIMIT ?
                """,
                (run_id_str, max_failed_tests + 1),
            ).fetchall()

            if len(execution_rows) > max_failed_tests:
                msg = f"failed/error count exceeds max_failed_tests ({max_failed_tests})"
                raise GuardrailViolationError(msg)

            execution_ids = [str(row["execution_id"]) for row in execution_rows]
            if not execution_ids:
                return []

            assertion_rows = self._fetch_assertions(conn, run_id_str, execution_ids)
            assertion_ids = [int(row["id"]) for row in assertion_rows]
            predicate_rows = self._fetch_predicates(conn, run_id_str, assertion_ids)

        predicates_by_assertion_id: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in predicate_rows:
            predicates_by_assertion_id[int(row["assertion_id"])].append(dict(row))

        assertions_by_execution_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in assertion_rows:
            assertion_data = dict(row)
            assertion_data["predicates"] = predicates_by_assertion_id.get(int(row["id"]), [])
            assertions_by_execution_id[str(row["test_execution_id"])].append(assertion_data)

        signatures: list[dict[str, Any]] = []
        for row in execution_rows:
            traceback = row["error_traceback"]
            if isinstance(traceback, str) and len(traceback) > max_traceback_chars:
                msg = f"traceback exceeds max_traceback_chars ({max_traceback_chars})"
                raise GuardrailViolationError(msg)

            execution_id = str(row["execution_id"])
            assertions = assertions_by_execution_id.get(execution_id, [])
            failed_assertions = [
                self._to_failed_assertion(assertion)
                for assertion in assertions
                if not bool(assertion["passed"])
            ]

            execution_error = str(row["error_message"] or "")
            assertion_error = str(failed_assertions[0]["error"]) if failed_assertions else ""
            fix_error_message = execution_error or assertion_error or "Test failed"
            cluster_key = self._build_cluster_key(assertions)
            if not cluster_key:
                cluster_key = (
                    f"STATUS={self._status_label(False)}\n"
                    f"ERROR={fix_error_message}\n"
                    f"TEST={row['test_name']}"
                )

            signatures.append(
                {
                    "case_id": str(row["case_id"] or execution_id),
                    "timestamp": run_timestamp,
                    "test_name": str(row["test_name"]),
                    "test_module": str(row["file_path"] or ""),
                    "cluster_key": cluster_key,
                    "fix_context": {
                        "error_message": fix_error_message,
                        "failed_assertions": failed_assertions,
                        "test_file": str(row["file_path"] or ""),
                        "input_data": {},
                        "actual_output": {},
                        "code_locations": self._parse_code_locations(traceback),
                    },
                }
            )

        return signatures

    def _fetch_assertions(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        execution_ids: list[str],
    ) -> list[sqlite3.Row]:
        if not execution_ids:
            return []

        placeholders = ",".join("?" for _ in execution_ids)
        query = f"""
            SELECT *
            FROM assertions
            WHERE run_id = ? AND test_execution_id IN ({placeholders})
            ORDER BY id ASC
        """
        return conn.execute(query, (run_id, *execution_ids)).fetchall()

    def _fetch_predicates(
        self,
        conn: sqlite3.Connection,
        run_id: str,
        assertion_ids: list[int],
    ) -> list[sqlite3.Row]:
        if not assertion_ids:
            return []

        placeholders = ",".join("?" for _ in assertion_ids)
        query = f"""
            SELECT *
            FROM predicates
            WHERE run_id = ? AND assertion_id IN ({placeholders})
            ORDER BY id ASC
        """
        return conn.execute(query, (run_id, *assertion_ids)).fetchall()

    def _build_cluster_key(self, assertions: list[dict[str, Any]]) -> str:
        lines: list[str] = []

        for index, assertion in enumerate(assertions, start=1):
            expression = self._parse_expression_repr(str(assertion["expression_repr"]))
            predicates = [dict(predicate) for predicate in assertion["predicates"]]

            lines.append(f"ASSERTION {index}")
            lines.append(f"status={self._status_label(bool(assertion['passed']))}")
            lines.append(f"expr={expression['expr']}")
            lines.append(f"error={assertion['error_message'] or ''}")
            lines.append(f"lines_above={expression['lines_above']}")
            lines.append(f"lines_below={expression['lines_below']}")

            resolved_args = expression["resolved_args"]
            if resolved_args:
                for key in sorted(resolved_args):
                    lines.append(f"arg:{key}={resolved_args[key]}")

            if predicates:
                for predicate in predicates:
                    lines.append(
                        "predicate="
                        f"{predicate['predicate_name']}|value={predicate['value']}|"
                        f"confidence={predicate['confidence']}|strict={predicate['strict']}|"
                        f"actual={predicate['actual']}|reference={predicate['reference']}|"
                        f"message={predicate['message'] or ''}"
                    )

            lines.append("--")

        return "\n".join(lines).strip()

    def _to_failed_assertion(self, assertion: dict[str, Any]) -> dict[str, Any]:
        expression = self._parse_expression_repr(str(assertion["expression_repr"]))
        pretty = self._format_assertion_pretty(expression, assertion)
        error_message = str(assertion["error_message"] or expression["expr"])

        return {
            "expression": expression["expr"],
            "error": error_message,
            "resolved_args": expression["resolved_args"],
            "pretty": pretty,
        }

    def _format_assertion_pretty(
        self,
        expression: dict[str, Any],
        assertion: dict[str, Any],
    ) -> str:
        lines: list[str] = []

        if expression["lines_above"]:
            lines.append(expression["lines_above"])

        lines.append(f"assert {expression['expr']}")

        if expression["lines_below"]:
            lines.append(expression["lines_below"])

        error_message = assertion["error_message"]
        if error_message:
            lines.append(f"error: {error_message}")

        resolved_args: dict[str, str] = expression["resolved_args"]
        if resolved_args:
            lines.append("resolved_args:")
            for key in sorted(resolved_args):
                lines.append(f"  - {key} = {resolved_args[key]}")

        predicates = [dict(predicate) for predicate in assertion["predicates"]]
        if predicates:
            lines.append("predicates:")
            for predicate in predicates:
                lines.append(
                    "  - "
                    f"{predicate['predicate_name']} "
                    f"(value={predicate['value']}, confidence={predicate['confidence']})"
                )

        return "\n".join(lines)

    def _parse_expression_repr(self, raw_expression: str) -> dict[str, Any]:
        expression_data = json.loads(raw_expression)

        return {
            "expr": str(expression_data.get("expr", "")),
            "lines_above": str(expression_data.get("lines_above", "")).strip(),
            "lines_below": str(expression_data.get("lines_below", "")).strip(),
            "resolved_args": {
                str(key): str(value)
                for key, value in dict(expression_data.get("resolved_args", {})).items()
            },
        }

    def _parse_code_locations(self, traceback: object) -> list[dict[str, Any]]:
        if not traceback:
            return []

        parsed = json.loads(str(traceback))
        frames = list(parsed.get("frames", []))

        locations: list[dict[str, Any]] = []
        for frame in frames:
            filepath = frame.get("filename")
            lineno = frame.get("lineno")
            function_name = str(frame.get("name") or "<unknown>")

            component = function_name
            if filepath and lineno:
                component = f"{function_name}:{lineno}"

            locations.append(
                {
                    "component": component,
                    "filepath": filepath,
                    "lineno": int(lineno) if lineno is not None else None,
                    "function": function_name,
                }
            )

        return locations

    @staticmethod
    def _status_label(passed: bool) -> str:
        return "passed" if passed else "failed"

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn
