import http.client
import json
import os
import re
import socket
import tempfile
import threading
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from contribution_mapper import runner
from contribution_mapper.github_reader import GitHubReaderError
from contribution_mapper.technocore_reader import TechnocoreReaderError
from contribution_mapper.ui import (
    MapperServer,
    RequestError,
    codespaces_host,
    main,
    parse_run_request,
)
from contribution_mapper.ui_page import render_page

TOKEN = "test-token-123"
REPORT = {"report_version": "1.4", "repository": {"full_name": "a/b"}}


class ParseRunRequestTests(unittest.TestCase):
    def good(self, **over):
        body = {"owner": "example", "repository": "project"}
        body.update(over)
        return body

    def test_minimal_request_uses_defaults(self):
        args, kwargs = parse_run_request(self.good())
        self.assertEqual(args, ("example", "project", "technocore"))
        self.assertEqual(kwargs["source"], "export")
        self.assertIsNone(kwargs["commit"])
        self.assertIsNone(kwargs["proof_data"])
        self.assertIsNone(kwargs["output"])

    def test_values_are_trimmed_and_blank_becomes_none(self):
        args, kwargs = parse_run_request(self.good(
            owner=" example ", room=" lobby ", commit="  ", artifact_url="",
            source="recent"))
        self.assertEqual(args, ("example", "project", "lobby"))
        self.assertIsNone(kwargs["commit"])
        self.assertIsNone(kwargs["artifact_url"])
        self.assertEqual(kwargs["source"], "recent")

    def test_proof_is_parsed_to_an_object(self):
        _, kwargs = parse_run_request(self.good(proof='{"schema": "x"}'))
        self.assertEqual(kwargs["proof_data"], {"schema": "x"})

    def test_rejections(self):
        bad_bodies = [
            None, [], "x", 5,
            {}, {"owner": "x"}, {"repository": "x"},
            self.good(owner=""), self.good(owner="a/b"), self.good(repository=".."),
            self.good(owner="a b"), self.good(owner=5), self.good(owner="x" * 101),
            self.good(source="history"), self.good(room=5), self.good(room="x" * 49),
            self.good(commit=5), self.good(commit="x" * 129),
            self.good(artifact_url="http://example.com"),
            self.good(artifact_url="ftp://example.com"),
            self.good(proof=5), self.good(proof="not json"),
            self.good(proof="x" * (64 * 1024 + 1)),
        ]
        for body in bad_bodies:
            with self.assertRaises(RequestError, msg=repr(body)[:60]):
                parse_run_request(body)

    def test_private_key_text_is_refused_and_not_echoed(self):
        secret = "-----BEGIN PRIVATE KEY----- SECRETSECRET"
        with self.assertRaises(RequestError) as ctx:
            parse_run_request(self.good(proof=secret))
        self.assertNotIn("SECRETSECRET", str(ctx.exception))


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.start()

    def start(self, runner_fn=None, extra_hosts=None):
        def default_runner(*args, **kwargs):
            self.calls.append((args, kwargs))
            return dict(REPORT)

        self.server = MapperServer(
            ("127.0.0.1", 0), token=TOKEN, extra_hosts=extra_hosts,
            runner=runner_fn or default_runner)
        self.port = self.server.server_address[1]
        quiet = patch("contribution_mapper.ui._Handler.log_message")
        quiet.start()
        self.addCleanup(quiet.stop)
        self.thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.02), daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        if getattr(self, "_stopped", None) is self.server:
            return
        self._stopped = self.server
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path, body=None, headers=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        hdrs = {"Host": host or f"127.0.0.1:{self.port}"}
        hdrs.update(headers or {})
        data = body if isinstance(body, (bytes, type(None))) else json.dumps(body).encode()
        conn.request(method, path, body=data, headers=hdrs)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response, raw

    def post(self, body, token=TOKEN, **kw):
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Mapper-Token"] = token
        headers.update(kw.pop("headers", {}))
        return self.request("POST", "/api/run", body, headers, **kw)


class PageTests(ServerTestCase):
    def test_page_is_served_with_token_nonce_and_security_headers(self):
        response, raw = self.request("GET", "/")
        html = raw.decode()
        self.assertEqual(response.status, 200)
        self.assertIn("text/html", response.getheader("Content-Type"))
        self.assertIn(f'const TOKEN = "{TOKEN}"', html)
        nonce = re.search(r'<script nonce="([^"]+)"', html).group(1)
        csp = response.getheader("Content-Security-Policy")
        self.assertIn(f"script-src 'nonce-{nonce}'", csp)
        self.assertIn("default-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.getheader("Cache-Control"), "no-store")
        self.assertEqual(response.getheader("Referrer-Policy"), "no-referrer")

    def test_nonce_changes_on_every_load(self):
        first = re.search(rb'nonce="([^"]+)"', self.request("GET", "/")[1]).group(1)
        second = re.search(rb'nonce="([^"]+)"', self.request("GET", "/")[1]).group(1)
        self.assertNotEqual(first, second)

    def test_page_loads_nothing_from_other_sites_and_has_no_inline_styles(self):
        html = render_page("t", "n")
        for forbidden in ("<script src", "<link", "@import", "url(http", "<img", "<iframe", ' style="'):
            self.assertNotIn(forbidden, html, forbidden)

    def test_page_never_assigns_untrusted_data_with_innerhtml(self):
        html = render_page("t", "n")
        self.assertNotIn("innerHTML", html)
        self.assertNotIn("insertAdjacentHTML", html)
        self.assertNotIn("document.write", html)

    def test_unknown_paths_and_methods(self):
        self.assertEqual(self.request("GET", "/nope")[0].status, 404)
        self.assertEqual(self.request("GET", "/api/run")[0].status, 405)
        self.assertEqual(self.request("PUT", "/api/run", b"{}")[0].status, 405)
        self.assertEqual(self.request("DELETE", "/")[0].status, 405)
        self.assertEqual(self.request("GET", "/favicon.ico")[0].status, 204)
        self.assertEqual(self.request("POST", "/other", b"{}")[0].status, 404)


class HostAndTokenTests(ServerTestCase):
    def test_foreign_host_header_is_refused_everywhere(self):
        for method, path in (("GET", "/"), ("GET", "/favicon.ico"), ("GET", "/nope")):
            self.assertEqual(self.request(method, path, host="evil.example")[0].status, 403)
        self.assertEqual(self.post({"owner": "a", "repository": "b"}, host="evil.example")[0].status, 403)
        self.assertEqual(self.calls, [])

    def test_wrong_port_in_host_header_is_refused(self):
        self.assertEqual(self.request("GET", "/", host=f"localhost:{self.port + 1}")[0].status, 403)
        self.assertEqual(self.request("GET", "/", host="localhost")[0].status, 403)

    def test_loopback_names_are_accepted(self):
        for host in (f"localhost:{self.port}", f"127.0.0.1:{self.port}", f"[::1]:{self.port}", f"LOCALHOST:{self.port}"):
            self.assertEqual(self.request("GET", "/", host=host)[0].status, 200, host)

    def test_missing_or_wrong_token_is_refused(self):
        body = {"owner": "a", "repository": "b"}
        self.assertEqual(self.post(body, token=None)[0].status, 403)
        self.assertEqual(self.post(body, token="wrong")[0].status, 403)
        self.assertEqual(self.post(body, token="")[0].status, 403)
        self.assertEqual(self.calls, [])

    def test_cross_origin_post_is_refused_even_with_the_token(self):
        response, _ = self.post({"owner": "a", "repository": "b"},
                                headers={"Origin": "https://evil.example"})
        self.assertEqual(response.status, 403)
        self.assertEqual(self.calls, [])

    def test_same_origin_post_is_accepted(self):
        response, _ = self.post({"owner": "a", "repository": "b"},
                                headers={"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(response.status, 200)

    def test_extra_allowed_host_with_and_without_port(self):
        self.stop_and_restart(extra_hosts={"mine-8765.app.github.dev"})
        self.assertEqual(self.request("GET", "/", host="mine-8765.app.github.dev")[0].status, 200)
        self.assertEqual(self.request("GET", "/", host="mine-8765.app.github.dev:443")[0].status, 200)
        self.assertEqual(self.request("GET", "/", host="other.app.github.dev")[0].status, 403)

    def stop_and_restart(self, **kw):
        self.stop()
        self.start(**kw)


class RunEndpointTests(ServerTestCase):
    def test_success_passes_validated_values_and_never_writes_a_file(self):
        response, raw = self.post({
            "owner": "example", "repository": "project", "room": "lobby",
            "source": "recent", "commit": "a" * 40,
            "artifact_url": "https://github.com/example/project",
            "proof": json.dumps({"schema": "s"})})
        self.assertEqual(response.status, 200)
        self.assertEqual(json.loads(raw), REPORT)
        (args, kwargs), = self.calls
        self.assertEqual(args, ("example", "project", "lobby"))
        self.assertEqual(kwargs["source"], "recent")
        self.assertEqual(kwargs["commit"], "a" * 40)
        self.assertEqual(kwargs["proof_data"], {"schema": "s"})
        self.assertIsNone(kwargs["output"])

    def test_validation_errors_are_400_with_a_message(self):
        for body, fragment in (
            ({"repository": "b"}, "owner"),
            ({"owner": "a", "repository": "b", "source": "x"}, "source"),
            ({"owner": "a", "repository": "b", "proof": "nope"}, "JSON"),
            ({"owner": "a", "repository": "b", "proof": "-----BEGIN PRIVATE KEY-----"}, "private key"),
            ([], "object"),
        ):
            response, raw = self.post(body)
            self.assertEqual(response.status, 400, body)
            self.assertIn(fragment.lower(), json.loads(raw)["error"].lower())
        self.assertEqual(self.calls, [])

    def test_invalid_json_body_and_bad_content_type(self):
        response, _ = self.post(b"{not json")
        self.assertEqual(response.status, 400)
        response, _ = self.request("POST", "/api/run", b"{}", {
            "X-Mapper-Token": TOKEN, "Content-Type": "text/plain"})
        self.assertEqual(response.status, 415)

    def test_oversized_body_is_refused_without_reading_it(self):
        # Declare a huge body but send almost none: the server must decide
        # from the header alone and never try to read it.
        response, _ = self.post(b"{}", headers={"Content-Length": str(128 * 1024 + 1)})
        self.assertEqual(response.status, 413)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.request("GET", "/")[0].status, 200)

    def test_runner_errors_are_mapped_and_internals_are_not_leaked(self):
        cases = [
            (ValueError("Room name is invalid."), 400, "Room name is invalid."),
            (GitHubReaderError("GitHub rate limit exceeded."), 502, "GitHub rate limit exceeded."),
            (TechnocoreReaderError("Could not reach the Technocore service."), 502, "Could not reach"),
        ]
        for exc, status, fragment in cases:
            def boom(*a, _e=exc, **k):
                raise _e
            self.stop_and_restart(runner_fn=boom)
            response, raw = self.post({"owner": "a", "repository": "b"})
            self.assertEqual(response.status, status)
            self.assertIn(fragment, json.loads(raw)["error"])

        def crash(*a, **k):
            raise RuntimeError("secret internal detail /home/user/path")
        self.stop_and_restart(runner_fn=crash)
        with patch("sys.stderr"):
            response, raw = self.post({"owner": "a", "repository": "b"})
        self.assertEqual(response.status, 500)
        self.assertNotIn(b"secret internal detail", raw)
        self.assertNotIn(b"/home/user", raw)

    def stop_and_restart(self, **kw):
        self.stop()
        self.start(**kw)


class RealRunnerIntegrationTests(ServerTestCase):
    """The endpoint calls the real run_mapper; only the network is faked."""

    def test_report_comes_from_real_logic_and_no_file_is_written(self):
        self.stop()
        self.start(runner_fn=runner.run_mapper)
        repo = {"full_name": "example/project", "html_url": "https://github.com/example/project"}
        room = {"room": "technocore", "count": 2, "first_seq": 10, "last_seq": 11,
                "generation": None, "truncated": False, "malformed_records_skipped": 0,
                "source": "export", "messages": [
                    {"seq": 10, "ts": "2026-10-18T09:00:00Z", "from": "did:key:zA", "text": "hello"},
                    {"seq": 11, "ts": "2026-10-18T09:00:05Z", "from": "did:key:zB",
                     "text": "shipped https://github.com/example/project"}]}
        sha = "b" * 40
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(runner, "read_public_repository", return_value=repo), \
             patch.object(runner, "read_public_room_export", return_value=room) as export, \
             patch.object(runner, "check_commit_exists", return_value={"status": "found", "commit": sha}):
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                response, raw = self.post({"owner": "example", "repository": "project",
                                           "commit": sha, "source": "export", "proof": "{}"})
                leftover = os.listdir(tmp)
            finally:
                os.chdir(cwd)
        report = json.loads(raw)
        self.assertEqual(response.status, 200)
        export.assert_called_once_with("technocore")
        self.assertEqual(report["evidence"]["record_count"], 1)
        self.assertEqual(report["evidence"]["records"][0]["status"], "unverified")
        self.assertEqual(report["retrieval_coverage"]["messages_examined"], 2)
        self.assertEqual(report["retrieval_coverage"]["first_seq_examined"], 10)
        self.assertFalse(report["retrieval_coverage"]["complete_history_searched"])
        self.assertEqual(report["commit_check"]["status"], "found")
        self.assertEqual(report["proof_verification"]["status"], "malformed")
        self.assertEqual(leftover, [])


class RunnerExtensionTests(unittest.TestCase):
    def room(self):
        return {"room": "lobby", "count": 0, "first_seq": None, "last_seq": 1,
                "generation": None, "messages": [], "source": "recent"}

    def test_proof_file_and_proof_data_together_is_an_error(self):
        with self.assertRaises(ValueError):
            runner.run_mapper("a", "b", "lobby", proof_file="x.json", proof_data={}, output=None)

    @patch("contribution_mapper.runner.read_public_room")
    @patch("contribution_mapper.runner.read_public_repository")
    def test_output_none_writes_nothing(self, mock_repo, mock_room):
        mock_repo.return_value = {"full_name": "a/b", "html_url": "https://github.com/a/b"}
        mock_room.return_value = self.room()
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                report = runner.run_mapper("a", "b", "lobby", output=None)
                self.assertEqual(os.listdir(tmp), [])
            finally:
                os.chdir(cwd)
        self.assertEqual(report["proof_verification"], {"status": "not_supplied"})


class LaunchHelperTests(unittest.TestCase):
    def test_codespaces_host_is_built_only_inside_codespaces(self):
        env = {"CODESPACES": "true", "CODESPACE_NAME": "Cool-Name-abc",
               "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN": "app.github.dev"}
        self.assertEqual(codespaces_host(8765, env), "cool-name-abc-8765.app.github.dev")
        self.assertIsNone(codespaces_host(8765, {}))
        self.assertIsNone(codespaces_host(8765, {**env, "CODESPACES": "false"}))
        self.assertIsNone(codespaces_host(8765, {"CODESPACES": "true"}))

    def test_port_in_use_returns_a_friendly_error(self):
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            port = busy.getsockname()[1]
            with patch("sys.stderr"):
                self.assertEqual(main(["--port", str(port), "--no-browser"]), 2)

    def test_invalid_port_is_rejected(self):
        with patch("sys.stderr"), self.assertRaises(SystemExit):
            main(["--port", "70000"])


if __name__ == "__main__":
    unittest.main()
