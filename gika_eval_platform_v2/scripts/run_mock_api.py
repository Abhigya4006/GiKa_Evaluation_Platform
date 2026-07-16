


from __future__ import annotations


import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import argparse
import json

from app.api_client.mock_api import build_response
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger("mock_api")


def _run_stdlib(host: str, port: int) -> None:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path.rstrip("/") == "/health":
                self._send(200, {"status": "ok"})
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path.rstrip("/") != "/retrieve":
                self._send(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                req = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self._send(400, {"error": "invalid json"})
                return
            resp = build_response(
                req.get("query_id", ""),
                # V1: no top_k on the wire. The mock's internal cap is a
                # mock-only ``mock_max_nodes`` extra (defaults inside build_response).
                max_nodes=int(req.get("mock_max_nodes", 10)),
                dataset_id=req.get("dataset_id"),
            )
            self._send(200, resp)

        def log_message(self, fmt: str, *args) -> None:  # silence default logging
            return

    server = ThreadingHTTPServer((host, port), Handler)
    logger.info("Mock API (stdlib) listening on http://%s:%d/retrieve", host, port)
    print(f"Mock API (stdlib) on http://{host}:{port}/retrieve  — Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Run the mock retrieval API.")
    parser.add_argument("--host", default=settings.mock_api_host)
    parser.add_argument("--port", type=int, default=settings.mock_api_port)
    args = parser.parse_args()

    try:
        import uvicorn  # type: ignore
        from app.api_client.mock_api import app

        if app is None:
            raise ImportError("FastAPI app unavailable")
        logger.info("Mock API (uvicorn/FastAPI) on http://%s:%d/retrieve", args.host, args.port)
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    except Exception as exc:  # noqa: BLE001
        logger.info("uvicorn/FastAPI unavailable (%s); using stdlib server.", type(exc).__name__)
        _run_stdlib(args.host, args.port)


if __name__ == "__main__":
    main()
