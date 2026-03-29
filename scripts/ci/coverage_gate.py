#!/usr/bin/env python3
"""Coverage quality gate for critical backend paths.

Reads pytest-cov JSON output and enforces stricter thresholds for selected files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


CRITICAL_THRESHOLDS: dict[str, float] = {
    "alphawatch/agents/nodes/chat.py": 90.0,
    "alphawatch/agents/nodes/brief.py": 90.0,
    "alphawatch/services/financial.py": 70.0,
}


def _pct(summary: dict[str, object]) -> float:
    value = summary.get("percent_covered")
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: coverage_gate.py <coverage.json>")
        return 2

    report_path = Path(sys.argv[1])
    if not report_path.exists():
        print(f"Coverage report not found: {report_path}")
        return 2

    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"Coverage report is not valid JSON: {exc}")
        return 2

    files = report.get("files", {})
    if not isinstance(files, dict):
        print("Invalid coverage JSON: 'files' field is missing or not an object")
        return 2

    failures: list[str] = []
    for file_path, min_threshold in CRITICAL_THRESHOLDS.items():
        file_info = files.get(file_path)
        if not isinstance(file_info, dict):
            failures.append(
                f"{file_path}: missing from coverage report (required >= {min_threshold:.1f}%)"
            )
            continue

        summary = file_info.get("summary", {})
        if not isinstance(summary, dict):
            failures.append(
                f"{file_path}: invalid summary in coverage report (required >= {min_threshold:.1f}%)"
            )
            continue

        covered = _pct(summary)
        if covered < min_threshold:
            failures.append(
                f"{file_path}: {covered:.1f}% < required {min_threshold:.1f}%"
            )
        else:
            print(f"OK {file_path}: {covered:.1f}% >= {min_threshold:.1f}%")

    if failures:
        print("Critical-path coverage gate failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Critical-path coverage gate passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
