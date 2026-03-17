#!/usr/bin/env python3
"""Local capture sink for live demo functional validation.

This process provides deterministic local HTTP endpoints for webhook and
notification integrations, and writes every request to endpoint-specific JSONL
files under <out-dir>/captures.
"""

from __future__ import annotations

import argparse
import json
import threading
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


EXACT_ENDPOINTS = {
    "/mock/approval": "approval",
    "/mock/notification": "notification",
    "/mock/callback": "callback",
    "/mock/siem": "siem",
    "/mock/slack": "slack",
    "/v3/mail/send": "sendgrid",
}


def _timestamp() -> str:
    return datetime.now(UTC).isoformat()


class CaptureStore:
    def __init__(self, out_dir: Path, fail_endpoints: set[str]) -> None:
        self.out_dir = out_dir
        self.capture_dir = out_dir / "captures"
        self.capture_dir.mkdir(parents=True, exist_ok=True)
        self.fail_endpoints = fail_endpoints
        self._lock = threading.Lock()

    def classify_endpoint(self, path: str) -> str:
        if path in EXACT_ENDPOINTS:
            return EXACT_ENDPOINTS[path]
        if path.startswith("/mock/pagerduty"):
            return "pagerduty"
        if path.startswith("/mock/siem"):
            return "siem"
        return "unknown"

    def should_fail(self, endpoint: str) -> bool:
        return endpoint in self.fail_endpoints

    def append(
        self,
        endpoint: str,
        method: str,
        path: str,
        query: dict[str, list[str]],
        headers: dict[str, str],
        body: bytes,
    ) -> None:
        event: dict[str, Any] = {
            "timestamp": _timestamp(),
            "endpoint": endpoint,
            "method": method,
            "path": path,
            "query": query,
            "headers": headers,
            "body_raw": body.decode("utf-8", errors="replace"),
        }

        try:
            event["body_json"] = json.loads(event["body_raw"]) if event["body_raw"] else None
        except json.JSONDecodeError:
            event["body_json"] = None

        target = self.capture_dir / f"{endpoint}.jsonl"
        with self._lock:
            with target.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event, sort_keys=True))
                fh.write("\n")

    def read(self, endpoint: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        endpoints = [endpoint] if endpoint else sorted(
            p.stem for p in self.capture_dir.glob("*.jsonl")
        )
        rows: list[dict[str, Any]] = []
        for name in endpoints:
            path = self.capture_dir / f"{name}.jsonl"
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        rows.sort(key=lambda item: item.get("timestamp", ""))
        if limit is not None and limit >= 0:
            return rows[-limit:]
        return rows


class SinkHandler(BaseHTTPRequestHandler):
    store: CaptureStore
    base_url: str

    server_version = "NexraMockSink/1.0"

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/_health":
            self._json(HTTPStatus.OK, {"ok": True, "timestamp": _timestamp()})
            return

        if parsed.path == "/_config":
            payload = {
                "ok": True,
                "base_url": self.base_url,
                "fail_endpoints": sorted(self.store.fail_endpoints),
                "out_dir": str(self.store.out_dir),
                "capture_dir": str(self.store.capture_dir),
                "endpoints": {
                    "approval": f"{self.base_url}/mock/approval",
                    "notification": f"{self.base_url}/mock/notification",
                    "callback": f"{self.base_url}/mock/callback",
                    "siem": f"{self.base_url}/mock/siem",
                    "slack": f"{self.base_url}/mock/slack",
                    "pagerduty": f"{self.base_url}/mock/pagerduty/v2/enqueue",
                    "sendgrid": f"{self.base_url}/v3/mail/send",
                },
            }
            self._json(HTTPStatus.OK, payload)
            return

        if parsed.path == "/_captures":
            query = parse_qs(parsed.query)
            endpoint = query.get("endpoint", [None])[0]
            limit_raw = query.get("limit", [None])[0]
            limit = int(limit_raw) if limit_raw and limit_raw.isdigit() else None
            rows = self.store.read(endpoint=endpoint, limit=limit)
            self._json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "count": len(rows),
                    "endpoint": endpoint,
                    "captures": rows,
                },
            )
            return

        self._json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "NOT_FOUND"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        endpoint = self.store.classify_endpoint(parsed.path)
        body = self._read_body()

        headers = {
            key: value
            for key, value in self.headers.items()
        }
        query = parse_qs(parsed.query)

        self.store.append(
            endpoint=endpoint,
            method="POST",
            path=parsed.path,
            query=query,
            headers=headers,
            body=body,
        )

        if self.store.should_fail(endpoint):
            self._json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "ok": False,
                    "endpoint": endpoint,
                    "error": "FORCED_FAILURE",
                },
            )
            return

        if endpoint == "sendgrid":
            self._json(HTTPStatus.ACCEPTED, {"ok": True, "endpoint": endpoint})
            return

        self._json(HTTPStatus.OK, {"ok": True, "endpoint": endpoint})

    def log_message(self, fmt: str, *args: object) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local capture sink for live demo tests")
    parser.add_argument("--port", type=int, default=8800)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--fail-endpoint",
        action="append",
        default=[],
        help="Endpoint name to force-fail (repeatable). Supported: approval,notification,callback,siem,slack,pagerduty,sendgrid",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fail_endpoints = {name.strip().lower() for name in args.fail_endpoint if name.strip()}

    store = CaptureStore(out_dir=args.out_dir, fail_endpoints=fail_endpoints)
    base_url = f"http://127.0.0.1:{args.port}"

    config_payload = {
        "base_url": base_url,
        "fail_endpoints": sorted(fail_endpoints),
        "capture_dir": str(store.capture_dir),
    }
    (args.out_dir / "mock_sink_config.json").write_text(
        json.dumps(config_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    SinkHandler.store = store
    SinkHandler.base_url = base_url

    server = ThreadingHTTPServer(("127.0.0.1", args.port), SinkHandler)
    print(f"[mock-sink] listening on {base_url}")
    print(f"[mock-sink] captures directory: {store.capture_dir}")
    if fail_endpoints:
        print(f"[mock-sink] forced failures: {sorted(fail_endpoints)}")

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("[mock-sink] stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
