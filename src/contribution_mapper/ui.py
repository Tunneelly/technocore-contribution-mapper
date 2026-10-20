"""Local web interface for the Contribution Mapper.

``contribution-mapper-ui`` starts a small web server on your own machine.
The page it serves calls the same ``run_mapper`` logic as the command line;
nothing in the results is canned. By default it listens on 127.0.0.1 only.

Protections, because a local server can be reached by any website open in
your browser:

* every request's Host header must be a loopback name or an allowed host
  (this blocks DNS-rebinding attacks);
* the API needs a random per-launch token that only the served page knows;
* cross-origin requests are refused;
* request bodies are size-capped and strictly validated;
* the page is served with a strict Content-Security-Policy.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable
from urllib.parse import urlsplit

from contribution_mapper.github_reader import GitHubReaderError
from contribution_mapper.runner import SOURCES, run_mapper
from contribution_mapper.technocore_reader import TechnocoreReaderError
from contribution_mapper.ui_page import render_page

MAX_BODY_BYTES = 128 * 1024
MAX_PROOF_CHARS = 64 * 1024
DEFAULT_PORT = 8765
DEFAULT_ROOM = "technocore"
LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1"}
_NAME = re.compile(r"[A-Za-z0-9_.-]{1,100}")


class RequestError(ValueError):
    """The request body is not acceptable; the message is safe to show."""


def _optional_text(payload: dict, key: str, limit: int) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise RequestError(f"{key} must be text.")
    value = value.strip()
    if len(value) > limit:
        raise RequestError(f"{key} is too long.")
    return value or None


def parse_run_request(payload: Any) -> tuple[tuple[str, str, str], dict]:
    """Validate a /api/run body; return positional args and keyword args."""
    if not isinstance(payload, dict):
        raise RequestError("Request body must be a JSON object.")

    owner = _optional_text(payload, "owner", 100)
    repository = _optional_text(payload, "repository", 100)
    for label, value in (("owner", owner), ("repository", repository)):
        if value is None:
            raise RequestError(f"Enter the GitHub {label}.")
        if _NAME.fullmatch(value) is None or value in {".", ".."}:
            raise RequestError(f"The GitHub {label} contains invalid characters.")

    room = _optional_text(payload, "room", 48) or DEFAULT_ROOM
    source = _optional_text(payload, "source", 16) or "export"
    if source not in SOURCES:
        raise RequestError("source must be 'recent' or 'export'.")

    commit = _optional_text(payload, "commit", 128)
    artifact_url = _optional_text(payload, "artifact_url", 2048)
    if artifact_url is not None and not artifact_url.lower().startswith("https://"):
        raise RequestError("The artifact URL must start with https://.")

    proof_data = None
    proof_text = payload.get("proof")
    if proof_text is not None:
        if not isinstance(proof_text, str):
            raise RequestError("proof must be text.")
        if len(proof_text) > MAX_PROOF_CHARS:
            raise RequestError("The proof is too large.")
        if proof_text.strip():
            if "PRIVATE KEY" in proof_text.upper():
                raise RequestError(
                    "That looks like a private key. Never paste secrets; "
                    "only the public proof file is needed."
                )
            try:
                proof_data = json.loads(proof_text)
            except json.JSONDecodeError:
                raise RequestError("The proof is not valid JSON.") from None

    return (owner, repository, room), {
        "artifact_url": artifact_url,
        "commit": commit,
        "source": source,
        "proof_data": proof_data,
        "output": None,
    }


def _split_host(header: str) -> tuple[str, int | None]:
    header = header.strip().lower()
    if header.startswith("["):  # [::1]:port
        end = header.find("]")
        if end == -1:
            return "", None
        host, rest = header[1:end], header[end + 1:]
        port_text = rest[1:] if rest.startswith(":") else ""
    elif header.count(":") == 1:
        host, port_text = header.split(":")
    else:
        host, port_text = header, ""
    if port_text and not port_text.isdigit():
        return "", None
    return host, int(port_text) if port_text else None


class MapperServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        *,
        token: str,
        extra_hosts: set[str] | None = None,
        runner: Callable[..., dict] = run_mapper,
    ):
        super().__init__(address, _Handler)
        self.token = token
        self.extra_hosts = {h.lower() for h in (extra_hosts or set())}
        self.runner = runner

    def host_allowed(self, header: str | None) -> bool:
        if not header:
            return False
        host, port = _split_host(header)
        if host in LOOPBACK_NAMES:
            return port == self.server_address[1]
        return host in self.extra_hosts


class _Handler(BaseHTTPRequestHandler):
    server: MapperServer
    server_version = "ContributionMapperUI"
    sys_version = ""

    # -- helpers ---------------------------------------------------------
    def _headers(self, status: int, content_type: str, length: int,
                 extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _json(self, status: int, body: dict) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(data))
        self.wfile.write(data)

    def _error(self, status: int, message: str) -> None:
        self._json(status, {"error": message})

    def _guard(self) -> bool:
        if not self.server.host_allowed(self.headers.get("Host")):
            self._error(403, "Host not allowed.")
            return False
        return True

    # -- routes ----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        if not self._guard():
            return
        path = urlsplit(self.path).path
        if path == "/":
            nonce = secrets.token_urlsafe(16)
            data = render_page(self.server.token, nonce).encode("utf-8")
            csp = (
                "default-src 'none'; "
                f"script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; "
                "connect-src 'self'; img-src data:; base-uri 'none'; "
                "form-action 'none'; frame-ancestors 'none'"
            )
            self._headers(200, "text/html; charset=utf-8", len(data),
                          {"Content-Security-Policy": csp})
            self.wfile.write(data)
        elif path == "/favicon.ico":
            self._headers(204, "image/x-icon", 0)
        elif path == "/api/run":
            self._error(405, "Use POST.")
        else:
            self._error(404, "Not found.")

    def do_POST(self) -> None:  # noqa: N802
        if not self._guard():
            return
        if urlsplit(self.path).path != "/api/run":
            self._error(404, "Not found.")
            return

        origin = self.headers.get("Origin")
        if origin is not None and urlsplit(origin).netloc.lower() != (
            self.headers.get("Host") or ""
        ).lower():
            self._error(403, "Cross-origin requests are not allowed.")
            return

        supplied = self.headers.get("X-Mapper-Token") or ""
        if not secrets.compare_digest(supplied, self.server.token):
            self._error(403, "Missing or invalid token. Reload the page.")
            return

        if not (self.headers.get("Content-Type") or "").lower().startswith(
            "application/json"
        ):
            self._error(415, "Content-Type must be application/json.")
            return

        try:
            length = int(self.headers.get("Content-Length") or "")
        except ValueError:
            self._error(411, "Content-Length is required.")
            return
        if length < 0 or length > MAX_BODY_BYTES:
            self._error(413, "Request body is too large.")
            return

        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            args, kwargs = parse_run_request(payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error(400, "Request body is not valid JSON.")
            return
        except RequestError as exc:
            self._error(400, str(exc))
            return

        try:
            report = self.server.runner(*args, **kwargs)
        except ValueError as exc:
            self._error(400, str(exc))
        except (GitHubReaderError, TechnocoreReaderError) as exc:
            self._error(502, str(exc))
        except Exception:  # noqa: BLE001 - never leak internals to the page
            print("Unexpected error while running the mapper:", file=sys.stderr)
            import traceback

            traceback.print_exc()
            self._error(500, "Unexpected error. See the terminal for details.")
        else:
            self._json(200, report)

    def do_PUT(self) -> None:  # noqa: N802
        self._error(405, "Method not allowed.")

    do_DELETE = do_PATCH = do_PUT  # noqa: N815

    def log_message(self, fmt: str, *args: Any) -> None:
        # One short line per request; never log bodies or the token.
        print(f"[ui] {self.command} {urlsplit(self.path).path} -> {args[1] if len(args) > 1 else ''}",
              file=sys.stderr)


def codespaces_host(port: int, env: dict[str, str] | None = None) -> str | None:
    """The forwarded hostname when running inside GitHub Codespaces."""
    env = os.environ if env is None else env
    name = env.get("CODESPACE_NAME")
    domain = env.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")
    if env.get("CODESPACES") == "true" and name and domain:
        return f"{name}-{port}.{domain}".lower()
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Launch the Contribution Mapper web interface on this machine."
    )
    parser.add_argument("--host", default="127.0.0.1",
                        help="Address to listen on (default: 127.0.0.1, this machine only)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                        help=f"Port (default: {DEFAULT_PORT}; 0 picks a free one)")
    parser.add_argument("--no-browser", action="store_true",
                        help="Do not try to open a browser window")
    parser.add_argument("--allow-host", action="append", default=[],
                        metavar="HOSTNAME",
                        help="Extra Host header to accept (for reverse proxies)")
    args = parser.parse_args(argv)

    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")

    token = secrets.token_urlsafe(32)
    try:
        server = MapperServer((args.host, args.port), token=token,
                              extra_hosts=set(args.allow_host))
    except OSError as exc:
        print(f"Could not start on {args.host}:{args.port}: {exc.strerror or exc}. "
              "Try another port with --port.", file=sys.stderr)
        return 2

    port = server.server_address[1]
    forwarded = codespaces_host(port)
    if forwarded:
        server.extra_hosts.add(forwarded)

    local_url = f"http://localhost:{port}"
    print("Contribution Mapper UI is running.")
    print(f"  Open: {local_url}")
    if forwarded:
        print(f"  In Codespaces, open the forwarded port {port} (it stays private to you):")
        print(f"        https://{forwarded}")
    if args.host not in LOOPBACK_NAMES:
        print(f"  Warning: listening on {args.host}, which other machines may reach. "
              "Only use --host on networks you trust.", file=sys.stderr)
    print("  Press Ctrl+C to stop.")

    if not args.no_browser and not forwarded:
        try:
            webbrowser.open(local_url)
        except Exception:  # noqa: BLE001 - opening a browser is best effort
            pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
