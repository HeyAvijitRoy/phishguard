#!/usr/bin/env python3
"""
export_mitm_text_summary.py

Print a compact text summary of each HTTP flow in a mitmproxy .mitm capture.

Example:
  python evaluation/export_mitm_text_summary.py --flows evaluation/privacy_audit_browser.mitm
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterator


def load_flow_reader() -> Any:
    """Import mitmproxy lazily so setup errors are reported cleanly."""

    try:
        from mitmproxy.io import FlowReader
    except Exception as exc:  # pragma: no cover - dependency/setup failure
        raise RuntimeError(
            "mitmproxy is required to read .mitm files. Check whether it is installed in the active environment; if not, create and use a dedicated venv named 'mitm-env' and install it there."
        ) from exc

    return FlowReader


def iter_flows(flow_path: Path) -> Iterator[Any]:
    """Yield flows parsed from a .mitm file."""

    flow_reader_type = load_flow_reader()
    with flow_path.open("rb") as file_handle:
        reader = flow_reader_type(file_handle)
        for flow in reader.stream():
            yield flow


def request_response_size(message: Any) -> int:
    """Return the raw byte size of a mitmproxy request or response body."""

    if message is None:
        return 0
    raw_content = getattr(message, "raw_content", None)
    if raw_content is None:
        return 0
    return len(raw_content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a compact summary of mitmproxy HTTP flows.")
    parser.add_argument("--flows", required=True, help="Path to a mitmproxy flows file (.mitm)")

    try:
        args = parser.parse_args()
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2

    flow_path = Path(args.flows)
    if not flow_path.exists() or not flow_path.is_file():
        print(f"ERROR: Flow file not found: {flow_path}", file=sys.stderr)
        return 2

    print("index\tmethod\thost\tpath\treq_body_bytes\tresp_body_bytes")

    try:
        for flow_index, flow in enumerate(iter_flows(flow_path), start=1):
            request = getattr(flow, "request", None)
            if request is None:
                continue

            response = getattr(flow, "response", None)
            host = (getattr(request, "host", "") or "").lower()
            path = getattr(request, "path", "") or ""
            method = getattr(request, "method", "") or ""
            request_size = request_response_size(request)
            response_size = request_response_size(response)

            print(f"{flow_index}\t{method}\t{host}\t{path}\t{request_size}\t{response_size}")
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: Failed to parse flows file '{flow_path}': {exc}", file=sys.stderr)
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())