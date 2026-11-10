"""Tests for the local frontend bridge (no network or microphone calls)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

_STATE = tempfile.TemporaryDirectory()
os.environ["RUBBERDUCKY_STATE_DIR"] = _STATE.name

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.app import app
from server.config_writer import update_ini_values


class ConfigWriterTests(unittest.TestCase):
    def test_updates_existing_key_and_preserves_comments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rubberducky.ini"
            path.write_text(
                "[voice]\n# keep me\nrecord_seconds = 5\nlanguage = hi-IN\n",
                encoding="utf-8",
            )
            changed = update_ini_values(path, {("voice", "record_seconds"): "9"})
            text = path.read_text(encoding="utf-8")
            self.assertIn("# keep me", text)
            self.assertIn("record_seconds = 9", text)
            self.assertIn("language = hi-IN", text)
            self.assertEqual(changed, ["voice.record_seconds"])

    def test_adds_missing_key_without_dropping_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rubberducky.ini"
            path.write_text("[llm]\nmodel = example/model\n", encoding="utf-8")
            update_ini_values(path, {("llm", "temperature"): "0.2"})
            text = path.read_text(encoding="utf-8")
            self.assertIn("model = example/model", text)
            self.assertIn("temperature = 0.2", text)

    def test_adds_missing_section(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rubberducky.ini"
            path.write_text("[voice]\nlanguage = hi-IN\n", encoding="utf-8")
            update_ini_values(path, {("logging", "level"): "DEBUG"})
            text = path.read_text(encoding="utf-8")
            self.assertIn("[logging]", text)
            self.assertIn("level = DEBUG", text)
            self.assertIn("language = hi-IN", text)


class BridgeApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def test_health(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["service"], "rubberducky-bridge")
        self.assertNotIn("OPENROUTER_API_KEY", response.text)

    def test_status(self) -> None:
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("state", body)
        self.assertIn("credentials", body)

    def test_config_hides_secrets(self) -> None:
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("llm", body)
        self.assertNotIn("OPENROUTER_API_KEY", response.text)
        self.assertNotIn("GNANI_API", response.text)

    def test_invalid_config_rejected(self) -> None:
        response = self.client.put("/api/config", json={"llm_provider": "anthropic"})
        self.assertEqual(response.status_code, 422)

    def test_groq_is_a_valid_config_provider(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "rubberducky.ini"
            path.write_text(
                "[llm]\nprovider = openrouter\nmodel = vendor/x\n", encoding="utf-8"
            )
            from core.config import reset_config_cache
            import core.config as config_module

            previous = config_module.DEFAULT_CONFIG_PATH
            config_module.DEFAULT_CONFIG_PATH = path
            reset_config_cache()
            try:
                response = self.client.put(
                    "/api/config", json={"llm_provider": "groq"}
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["llm"]["provider"], "groq")
            finally:
                config_module.DEFAULT_CONFIG_PATH = previous
                reset_config_cache()

    def test_git_context(self) -> None:
        response = self.client.get("/api/git/context")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("branch", body)
        self.assertIn("commits", body)

    def test_ignore_rules(self) -> None:
        response = self.client.get("/api/ignore/rules")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("gitignore", body)
        self.assertIn("suggestions", body)

    def test_ignore_requires_approval(self) -> None:
        response = self.client.post(
            "/api/ignore/apply",
            json={"patterns": ["tmp/"], "destination": "rubberducky", "approved": False},
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_session(self) -> None:
        response = self.client.get("/api/sessions/does-not-exist")
        self.assertEqual(response.status_code, 404)

    def test_websocket_snapshot_accepts_local_frontend_origin(self) -> None:
        with self.client.websocket_connect(
            "/ws/events", headers={"origin": "http://127.0.0.1:5173"}
        ) as websocket:
            message = websocket.receive_json()
            self.assertEqual(message["type"], "snapshot")
            self.assertIn("status", message)

    def test_websocket_rejects_untrusted_origin(self) -> None:
        with self.assertRaises(WebSocketDisconnect) as raised:
            with self.client.websocket_connect(
                "/ws/events", headers={"origin": "https://attacker.example"}
            ):
                pass
        self.assertEqual(raised.exception.code, 1008)

    def test_websocket_rejects_missing_origin(self) -> None:
        with self.assertRaises(WebSocketDisconnect) as raised:
            with self.client.websocket_connect("/ws/events"):
                pass
        self.assertEqual(raised.exception.code, 1008)


if __name__ == "__main__":
    unittest.main()
