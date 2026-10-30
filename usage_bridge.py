#!/usr/bin/env python3
"""Local-only bridge from Codex app-server rate limits to the TodooCard web UI."""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def parse_rate_limits(result: Any) -> dict[str, Any]:
    item = result if isinstance(result, dict) else {}
    by_id = item.get("rateLimitsByLimitId")
    limits = by_id.get("codex") if isinstance(by_id, dict) else None
    if not isinstance(limits, dict):
        limits = item.get("rateLimits")
    if not isinstance(limits, dict) or str(limits.get("limitId") or "codex").lower() != "codex":
        raise ValueError("Codex rate-limit bucket was not returned")

    def window(value: Any) -> dict[str, Any]:
        source = value if isinstance(value, dict) else {}
        return {
            "used_percent": source.get("usedPercent"),
            "window_minutes": source.get("windowDurationMins"),
            "resets_at": source.get("resetsAt"),
        }

    primary = window(limits.get("primary"))
    secondary = window(limits.get("secondary"))
    if primary["used_percent"] is None and secondary["used_percent"] is None:
        raise ValueError("Codex usage percentages were empty")
    return {
        "primary": primary,
        "secondary": secondary,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "source": "codex app-server account/rateLimits/read",
    }


def find_codex_binary(configured: str | None = None) -> str:
    candidates = [configured, os.environ.get("CODEX_BINARY"), shutil.which("codex")]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return os.path.abspath(candidate)
    raise FileNotFoundError("codex executable not found; set CODEX_BINARY to its full path")


def read_codex_usage(binary: str, timeout: float = 15.0) -> dict[str, Any]:
    process = subprocess.Popen(
        [binary, "app-server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    messages: queue.Queue[dict[str, Any]] = queue.Queue()

    def reader() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            try:
                messages.put(json.loads(line))
            except (json.JSONDecodeError, TypeError):
                continue

    threading.Thread(target=reader, daemon=True).start()
    try:
        if process.stdin is None:
            raise RuntimeError("codex app-server stdin is unavailable")

        def send(message: dict[str, Any]) -> None:
            process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
            process.stdin.flush()

        send({"id": 1, "method": "initialize", "params": {"clientInfo": {"name": "todoo-daily-card", "version": "1"}}})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                message = messages.get(timeout=max(0.05, deadline - time.monotonic()))
            except queue.Empty as error:
                raise TimeoutError("Codex initialize timed out") from error
            if message.get("id") == 1:
                break
        else:
            raise TimeoutError("Codex initialize timed out")

        send({"method": "initialized"})
        send({"id": 2, "method": "account/rateLimits/read", "params": None})
        while time.monotonic() < deadline:
            try:
                message = messages.get(timeout=max(0.05, deadline - time.monotonic()))
            except queue.Empty as error:
                raise TimeoutError("Codex usage request timed out") from error
            if message.get("id") == 2:
                if message.get("error"):
                    raise RuntimeError(str(message["error"]))
                return parse_rate_limits(message.get("result"))
        raise TimeoutError("Codex usage request timed out")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()


class UsageHandler(BaseHTTPRequestHandler):
    server_version = "TodooUsageBridge/1.0"

    def _headers(self, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._headers(204)

    def do_GET(self) -> None:  # noqa: N802
        if self.path not in ("/", "/api/codex-usage", "/health"):
            self._headers(404)
            self.wfile.write(b'{"error":"not found"}')
            return
        try:
            if self.path == "/health":
                payload = {"ok": True}
            else:
                payload = read_codex_usage(self.server.codex_binary)  # type: ignore[attr-defined]
            self._headers(200)
        except Exception as error:  # keep the tiny local service alive for retry
            payload = {"error": str(error), "type": type(error).__name__}
            self._headers(503)
        self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Expose local Codex usage to the TodooCard dashboard")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--codex-binary")
    parser.add_argument("--once", action="store_true", help="print one JSON snapshot and exit")
    args = parser.parse_args()
    binary = find_codex_binary(args.codex_binary)
    if args.once:
        print(json.dumps(read_codex_usage(binary), ensure_ascii=False, indent=2))
        return
    server = ThreadingHTTPServer(("127.0.0.1", args.port), UsageHandler)
    server.codex_binary = binary  # type: ignore[attr-defined]
    print(f"TodooCard usage bridge: http://127.0.0.1:{args.port}")
    print("Only usage percentages and reset times are exposed; press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
