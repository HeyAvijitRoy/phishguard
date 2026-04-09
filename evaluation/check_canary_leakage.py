#!/usr/bin/env python3
"""
check_canary_leakage.py

Purpose:
- Read a mitmproxy flows file (.mitm)
- Decode HTTP request bodies safely
- Search for known subject/body canaries using raw, normalized, and compact matches
- Report any possible content leakage in JSON form

Usage:
  python evaluation/check_canary_leakage.py \
      --flows privacy_audit_browser.mitm \
      --canary-subject "PHISHGUARD_CANARY_SUBJECT_7F3A91" \
      --canary-body "PHISHGUARD_CANARY_BODY_29C8D4 unique payroll token"

Optional:
  --report privacy_audit_canary_report.jsonl

Example:
    python evaluation/check_canary_leakage.py --flows evaluation/privacy_audit_browser.mitm --canary-subject "PHISHGUARD_CANARY_SUBJECT_7F3A91" --canary-body "PHISHGUARD_CANARY_BODY_29C8D4 unique payroll token" --report evaluation/privacy_audit_canary_report.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence


@dataclass
class MatchResult:
    flow_index: int
    method: str
    host: str
    path: str
    matched_canary: str
    match_type: str
    body_preview: str


def load_flow_reader() -> Any:
    """Import mitmproxy lazily so setup errors can be surfaced cleanly."""

    try:
        from mitmproxy.io import FlowReader
    except Exception as exc:  # pragma: no cover - dependency/setup failure
        raise RuntimeError(
            "mitmproxy is required to read .mitm files. Check whether it is installed in the active environment; if not, create and use a dedicated venv named 'mitm-env' and install it there."
        ) from exc

    return FlowReader


def normalize_text(text: str) -> str:
    """
    Normalize text for resilient matching:
    - Unicode normalize
    - lowercase
    - collapse whitespace
    - strip zero-width and control-ish chars
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u200b", "").replace("\ufeff", "")
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact_text(text: str) -> str:
    """Collapse a string to lowercase alphanumeric characters only."""

    return re.sub(r"[^a-z0-9]+", "", normalize_text(text))


def safe_decode(data: bytes | None) -> str:
    """
    Best-effort decode of body bytes.
    """
    if not data:
        return ""

    # Try common encodings first, then fall back to replacement decoding.
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1252", "latin-1"):
        try:
            return data.decode(enc, errors="replace")
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def body_preview(text: str, max_len: int = 220) -> str:
    preview = text.replace("\r", "\\r").replace("\n", "\\n")
    return preview[:max_len]


def search_text(haystack_raw: str, canaries: Iterable[str]) -> list[tuple[str, str]]:
    """
    Return list of (matched_canary, match_type).
    """
    matches: list[tuple[str, str]] = []
    haystack_norm = normalize_text(haystack_raw)
    haystack_compact = compact_text(haystack_raw)

    for canary in canaries:
        raw_canary = canary
        normalized_canary = normalize_text(canary)
        compact_canary = compact_text(canary)
        
        if len(compact_canary) < 8:
            continue
        if raw_canary and raw_canary in haystack_raw:
            matches.append((canary, "raw"))
            continue
        if normalized_canary and normalized_canary in haystack_norm:
            matches.append((canary, "normalized"))
            continue
        if compact_canary and len(compact_canary) >= 12 and compact_canary in haystack_compact:
            matches.append((canary, "compact-alnum"))

    return matches


def iter_flows(flow_path: Path) -> Iterator[Any]:
    """Yield parsed mitmproxy flows from a .mitm file."""

    flow_reader_type = load_flow_reader()
    with flow_path.open("rb") as f:
        reader = flow_reader_type(f)
        for flow in reader.stream():
            yield flow


def parse_host_filters(values: Sequence[str]) -> set[str]:
    """Normalize repeatable --hosts arguments into a lowercase set."""

    hosts: set[str] = set()
    for value in values:
        for item in value.split(","):
            item = item.strip().lower()
            if item:
                hosts.add(item)
    return hosts


def request_body_text(request: Any) -> tuple[str, int]:
    """Return a decoded request body and its raw size in bytes."""

    raw_content = getattr(request, "raw_content", None)
    if raw_content is None:
        raw_content = b""
    return safe_decode(raw_content), len(raw_content)


def build_report(
    flow_path: Path,
    inspected_flows: int,
    canary_subjects: list[str],
    canary_bodies: list[str],
    findings: list[MatchResult],
    host_filters: set[str],
) -> dict[str, Any]:
    """Assemble the JSON report payload."""

    return {
        "flow_file": str(flow_path),
        "passed": len(findings) == 0,
        "verdict": "PASS" if not findings else "FAIL",
        "flows_inspected": inspected_flows,
        "canaries_tested": len(canary_subjects) + len(canary_bodies),
        "canary_inputs": {
            "subjects": canary_subjects,
            "bodies": canary_bodies,
        },
        "host_filters": sorted(host_filters),
        "matches_found": len(findings),
        "matches": [asdict(item) for item in findings],
    }


def write_report(report_path: Path, report: dict[str, Any]) -> None:
    """Write the JSON report to disk with a stable encoding."""

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan mitmproxy request bodies for canary leakage.")
    parser.add_argument("--flows", required=True, help="Path to a mitmproxy flows file (.mitm)")
    parser.add_argument(
        "--canary-subject",
        action="append",
        default=[],
        help="Known subject canary string; repeat for multiple values",
    )
    parser.add_argument(
        "--canary-body",
        action="append",
        default=[],
        help="Known body canary string; repeat for multiple values",
    )
    parser.add_argument(
        "--hosts",
        action="append",
        default=[],
        help="Optional host filter; repeat or provide comma-separated values",
    )
    parser.add_argument(
        "--report",
        default="privacy_audit_canary_report.jsonl",
        help="Path to write the JSON report",
    )

    try:
        args = parser.parse_args()
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    flow_path = Path(args.flows)
    if not flow_path.exists() or not flow_path.is_file():
        print(f"ERROR: Flow file not found: {flow_path}", file=sys.stderr)
        return 2

    canary_subjects = [value for value in args.canary_subject if value]
    canary_bodies = [value for value in args.canary_body if value]
    if not canary_subjects and not canary_bodies:
        print("ERROR: Provide at least one --canary-subject or --canary-body", file=sys.stderr)
        return 2

    host_filters = parse_host_filters(args.hosts)
    canaries = canary_subjects + canary_bodies

    findings: list[MatchResult] = []
    inspected = 0

    try:
        for flow_index, flow in enumerate(iter_flows(flow_path), start=1):
            request = getattr(flow, "request", None)
            if request is None:
                continue

            host = (getattr(request, "host", "") or "").lower()
            if host_filters and host not in host_filters:
                continue

            path = getattr(request, "path", "") or ""
            method = getattr(request, "method", "") or ""
            inspected += 1

            body_text, _body_size = request_body_text(request)
            if not body_text:
                continue

            hits = search_text(body_text, canaries)
            if not hits:
                continue

            preview = body_preview(body_text)
            for matched_canary, match_type in hits:
                findings.append(
                    MatchResult(
                        flow_index=flow_index,
                        method=method,
                        host=host,
                        path=path,
                        matched_canary=matched_canary,
                        match_type=match_type,
                        body_preview=preview,
                    )
                )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: Failed to parse flows file '{flow_path}': {exc}", file=sys.stderr)
        return 2

    report = build_report(flow_path, inspected, canary_subjects, canary_bodies, findings, host_filters)

    try:
        write_report(Path(args.report), report)
    except OSError as exc:
        print(f"ERROR: Failed to write report '{args.report}': {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())