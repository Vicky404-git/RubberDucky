"""BYOK provider tests: credentials, selection, clients and connection tests.

No network access and no real API keys are required. External provider APIs
are mocked. Tests never touch the real project .env or rubberducky.ini.
"""
from __future__ import annotations

import os
import stat
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_STATE = tempfile.TemporaryDirectory()
os.environ["RUBBERDUCKY_STATE_DIR"] = _STATE.name

import httpx
from fastapi.testclient import TestClient
from openai import APIStatusError

import core.config as config_module
import server.app as app_module
import server.credential_store as credential_store
from core.config import load_config, reset_config_cache
from core.llm_client import (
    LLMError,
    LLMErrorCode,
    build_client,
    complete_json,
)
from core.providers import PROVIDERS, llm_provider_ids
from server.connection_test import ConnectionTestError, run_connection_test
from server.credential_store import (
    CredentialError,
    all_provider_metadata,
    is_configured,
    remove_credential,
    save_credential,
)


class _TempEnv:
    """Patch the credential store to use a temporary .env file."""

    def __enter__(self):
        self._directory = tempfile.TemporaryDirectory()
        self._path = Path(self._directory.name) / ".env"
        self._previous = credential_store.ENV_FILE_OVERRIDE
        credential_store.ENV_FILE_OVERRIDE = self._path
        return self._path

    def __exit__(self, *_args):
        credential_store.ENV_FILE_OVERRIDE = self._previous
        self._directory.cleanup()
        return False


def _api_status_error(status_code: int, message: str = "request failed") -> APIStatusError:
    """Build a real OpenAI APIStatusError (as raised by the SDK)."""
    request = httpx.Request("POST", "https://provider.example/chat/completions")
    return APIStatusError(
        message, response=httpx.Response(status_code, request=request), body=None
    )


def _http_json_response(status_code: int, payload):
    request = httpx.Request("GET", "https://provider.example")
    return httpx.Response(status_code, request=request, json=payload)


def _fake_http_client(*responses: httpx.Response):
    """A drop-in replacement for httpx.Client in connection tests."""
    canned = list(responses)

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, _url, headers=None):
            return canned.pop(0)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    return _Client


class CredentialStoreTests(unittest.TestCase):
    def tearDown(self) -> None:
        for spec in PROVIDERS.values():
            os.environ.pop(spec.env_var, None)

    def test_save_openrouter_credential_persists_and_updates_runtime(self) -> None:
        with _TempEnv() as env_path:
            env_path.write_text(
                "# comment\nGNANI_API=keep-me\nOTHER=1\n", encoding="utf-8"
            )
            result = save_credential("openrouter", "  sk-or-test-123  ")
            text = env_path.read_text(encoding="utf-8")
        self.assertEqual(result, {"provider": "openrouter", "configured": True})
        self.assertIn("OPENROUTER_API_KEY=sk-or-test-123", text)
        self.assertIn("# comment", text)
        self.assertIn("GNANI_API=keep-me", text)
        self.assertIn("OTHER=1", text)
        self.assertEqual(os.environ["OPENROUTER_API_KEY"], "sk-or-test-123")

    def test_save_groq_credential(self) -> None:
        with _TempEnv() as env_path:
            save_credential("groq", "gsk_test-key")
            text = env_path.read_text(encoding="utf-8")
        self.assertIn("GROQ_API_KEY=gsk_test-key", text)
        self.assertEqual(os.environ["GROQ_API_KEY"], "gsk_test-key")
        self.assertTrue(is_configured("groq"))

    def test_save_gnani_credential(self) -> None:
        with _TempEnv() as env_path:
            save_credential("gnani", "gnani-key-1")
            text = env_path.read_text(encoding="utf-8")
        self.assertIn("GNANI_API=gnani-key-1", text)
        self.assertEqual(os.environ["GNANI_API"], "gnani-key-1")

    def test_save_replaces_existing_value_and_quotes_specials(self) -> None:
        with _TempEnv() as env_path:
            env_path.write_text(
                "OPENROUTER_API_KEY=old-value\nKEEP=2\n", encoding="utf-8"
            )
            save_credential("openrouter", 'weird "key" with spaces')
            text = env_path.read_text(encoding="utf-8")
        self.assertIn('OPENROUTER_API_KEY="weird \\"key\\" with spaces"', text)
        self.assertNotIn("old-value", text)
        self.assertIn("KEEP=2", text)
        self.assertEqual(os.environ["OPENROUTER_API_KEY"], 'weird "key" with spaces')

    def test_remove_credential_clears_file_and_runtime(self) -> None:
        with _TempEnv() as env_path:
            env_path.write_text(
                "OPENROUTER_API_KEY=abc\nGROQ_API_KEY=def\nNOTE=x\n",
                encoding="utf-8",
            )
            os.environ["OPENROUTER_API_KEY"] = "abc"
            result = remove_credential("openrouter")
            text = env_path.read_text(encoding="utf-8")
        self.assertEqual(result, {"provider": "openrouter", "configured": False})
        self.assertNotIn("OPENROUTER_API_KEY", text)
        self.assertIn("GROQ_API_KEY=def", text)
        self.assertIn("NOTE=x", text)
        self.assertNotIn("OPENROUTER_API_KEY", os.environ)
        self.assertFalse(is_configured("openrouter"))

    def test_remove_missing_credential_is_idempotent(self) -> None:
        with _TempEnv():
            os.environ["GROQ_API_KEY"] = "shell-value"
            result = remove_credential("groq")
        self.assertEqual(result, {"provider": "groq", "configured": False})
        self.assertNotIn("GROQ_API_KEY", os.environ)

    def test_invalid_provider_rejected(self) -> None:
        for bad in ("anthropic", "", "openrouter.exe", "unknown"):
            with self.assertRaises(CredentialError):
                save_credential(bad, "key")
            with self.assertRaises(CredentialError):
                remove_credential(bad)

    def test_provider_ids_are_normalized(self) -> None:
        with _TempEnv() as env_path:
            result = save_credential("  GROQ  ", "gsk-normalized")
            text = env_path.read_text(encoding="utf-8")
        self.assertEqual(result, {"provider": "groq", "configured": True})
        self.assertIn("GROQ_API_KEY=gsk-normalized", text)

    def test_missing_or_invalid_key_values_rejected(self) -> None:
        for bad in ("", "   ", "\n", "line1\nline2", "x" * 600):
            with self.assertRaises(CredentialError):
                save_credential("openrouter", bad)

    def test_env_file_permissions_are_restricted(self) -> None:
        with _TempEnv() as env_path:
            save_credential("openrouter", "perm-test")
            mode = stat.S_IMODE(env_path.stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_atomic_write_does_not_leave_temp_files(self) -> None:
        with _TempEnv() as env_path:
            save_credential("openrouter", "atomic-test")
            siblings = [
                entry for entry in env_path.parent.iterdir() if entry != env_path
            ]
        self.assertEqual(siblings, [])

    def test_provider_metadata_never_contains_keys(self) -> None:
        with _TempEnv():
            save_credential("groq", "gsk_super_secret_value")
            payload = all_provider_metadata(load_config())
        rendered = repr(payload)
        self.assertNotIn("gsk_super_secret_value", rendered)
        groq = next(item for item in payload if item["id"] == "groq")
        self.assertTrue(groq["configured"])
        self.assertIn("model", groq)
        self.assertIn("selected", groq)
        self.assertIsInstance(groq["connection_test_supported"], bool)


class ProviderConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        reset_config_cache()

    def _config_file(self, text: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "rubberducky.ini"
        path.write_text(text, encoding="utf-8")
        return path

    def test_groq_is_a_valid_llm_provider(self) -> None:
        path = self._config_file("[llm]\nprovider = groq\n")
        config = load_config(path, reload=True)
        self.assertEqual(config.llm.provider, "groq")
        self.assertEqual(config.llm.model, config.llm.model_for("groq"))

    def test_per_provider_models_with_openrouter_legacy_key(self) -> None:
        path = self._config_file(
            "[llm]\nprovider = openrouter\n"
            "model = vendor/model-x\n"
            "groq_model = llama-3.1-8b-instant\n"
        )
        config = load_config(path, reload=True)
        self.assertEqual(config.llm.models["openrouter"], "vendor/model-x")
        self.assertEqual(config.llm.models["groq"], "llama-3.1-8b-instant")
        self.assertEqual(config.llm.model, "vendor/model-x")

    def test_groq_provider_uses_groq_model_not_openrouter_model(self) -> None:
        path = self._config_file(
            "[llm]\nprovider = groq\nmodel = openrouter/only-model\n"
        )
        config = load_config(path, reload=True)
        self.assertEqual(config.llm.model, config.llm.model_for("groq"))
        self.assertNotEqual(config.llm.model, "openrouter/only-model")

    def test_unknown_provider_falls_back_to_openrouter(self) -> None:
        path = self._config_file("[llm]\nprovider = anthropic\n")
        config = load_config(path, reload=True)
        self.assertEqual(config.llm.provider, "openrouter")

    def test_provider_list_matches_registry(self) -> None:
        self.assertEqual(set(llm_provider_ids()), {"openrouter", "groq"})


class LlmClientProviderTests(unittest.TestCase):
    def tearDown(self) -> None:
        for spec in PROVIDERS.values():
            os.environ.pop(spec.env_var, None)
        reset_config_cache()

    def _config_file(self, text: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "rubberducky.ini"
        path.write_text(text, encoding="utf-8")
        return path

    def test_groq_client_construction(self) -> None:
        path = self._config_file("[llm]\nprovider = groq\n")
        config = load_config(path, reload=True)
        with patch.dict(os.environ, {"GROQ_API_KEY": "groq-key"}), patch(
            "core.llm_client.OpenAI"
        ) as openai_cls:
            build_client(config)
        openai_cls.assert_called_once_with(
            base_url="https://api.groq.com/openai/v1",
            api_key="groq-key",
            timeout=float(config.llm.timeout),
            max_retries=0,
        )

    def test_provider_switch_selects_credentials(self) -> None:
        groq_config = load_config(
            self._config_file("[llm]\nprovider = groq\n"), reload=True
        )
        openrouter_config = load_config(
            self._config_file("[llm]\nprovider = openrouter\n"), reload=True
        )
        with patch.dict(os.environ, {"GROQ_API_KEY": "g", "OPENROUTER_API_KEY": "o"}):
            self.assertEqual(build_client(groq_config).api_key, "g")
            self.assertEqual(build_client(openrouter_config).api_key, "o")

    def test_missing_groq_credentials_are_provider_specific(self) -> None:
        path = self._config_file("[llm]\nprovider = groq\n")
        config = load_config(path, reload=True)
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            with self.assertRaises(LLMError) as raised:
                build_client(config)
        self.assertEqual(raised.exception.code, LLMErrorCode.MISSING_CREDENTIALS)
        self.assertIn("GROQ_API_KEY", raised.exception.message)
        self.assertFalse(raised.exception.retryable)

    def test_unsupported_provider_is_structured(self) -> None:
        config = replace(load_config(), llm=replace(load_config().llm, provider="anthropic"))
        with self.assertRaises(LLMError) as raised:
            build_client(config)
        self.assertEqual(raised.exception.code, LLMErrorCode.UNSUPPORTED_PROVIDER)

    def _client(self, create):
        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

    def test_groq_authentication_error_names_the_provider(self) -> None:
        config = load_config(self._config_file("[llm]\nprovider = groq\n"), reload=True)

        def reject(**_kwargs):
            raise _api_status_error(401, "unauthorized")

        with patch("core.llm_client.log_event"):
            with self.assertRaises(LLMError) as raised:
                complete_json("s", "u", config=config, client=self._client(reject))
        self.assertEqual(raised.exception.code, LLMErrorCode.AUTHENTICATION_ERROR)
        self.assertIn("Groq", raised.exception.message)
        self.assertEqual(raised.exception.status_code, 401)

    def test_groq_json_mode_fallback_retries_without_response_format(self) -> None:
        config = load_config(self._config_file("[llm]\nprovider = groq\n"), reload=True)
        calls: list[dict] = []
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
        )

        def create(**kwargs):
            calls.append(kwargs)
            if "response_format" in kwargs:
                raise _api_status_error(400, "json mode unsupported")
            return response

        with patch("core.llm_client.log_event"):
            data = complete_json("s", "u", config=config, client=self._client(create))
        self.assertEqual(data, {"ok": True})
        self.assertEqual(len(calls), 2)
        self.assertIn("response_format", calls[0])
        self.assertNotIn("response_format", calls[1])

    def test_openrouter_400_still_raises_without_fallback(self) -> None:
        calls: list[dict] = []

        def create(**kwargs):
            calls.append(kwargs)
            raise _api_status_error(400, "bad request")

        with patch("core.llm_client.log_event"):
            with self.assertRaises(LLMError) as raised:
                complete_json("s", "u", client=self._client(create))
        self.assertEqual(raised.exception.code, LLMErrorCode.HTTP_ERROR)
        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(len(calls), 1)


class ConnectionTestTests(unittest.TestCase):
    def tearDown(self) -> None:
        for spec in PROVIDERS.values():
            os.environ.pop(spec.env_var, None)

    def test_openrouter_success_with_model(self) -> None:
        client = _fake_http_client(
            _http_json_response(200, {"data": {"usage": 1}}),
            _http_json_response(200, {"data": [{"id": "liquid/lfm-3-1.7b:free"}]}),
        )
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-key"}), patch(
            "server.connection_test.httpx.Client", client
        ):
            result = run_connection_test("openrouter", "liquid/lfm-3-1.7b:free")
        self.assertTrue(result["ok"])
        self.assertTrue(result["model_ok"])
        self.assertNotIn("or-key", repr(result))

    def test_openrouter_invalid_key_fails(self) -> None:
        client = _fake_http_client(_http_json_response(401, {"error": "denied"}))
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "bad-key"}), patch(
            "server.connection_test.httpx.Client", client
        ):
            result = run_connection_test("openrouter", "m")
        self.assertFalse(result["ok"])
        self.assertIn("HTTP 401", result["message"])

    def test_groq_model_not_in_list_reports_warning(self) -> None:
        client = _fake_http_client(
            _http_json_response(200, {"data": [{"id": "llama-3.3-70b-versatile"}]})
        )
        with patch.dict(os.environ, {"GROQ_API_KEY": "g-key"}), patch(
            "server.connection_test.httpx.Client", client
        ):
            result = run_connection_test("groq", "missing-model")
        self.assertTrue(result["ok"])
        self.assertFalse(result["model_ok"])
        self.assertIn("missing-model", result["message"])

    def test_groq_invalid_key_fails(self) -> None:
        client = _fake_http_client(_http_json_response(403, {"error": "forbidden"}))
        with patch.dict(os.environ, {"GROQ_API_KEY": "bad"}), patch(
            "server.connection_test.httpx.Client", client
        ):
            result = run_connection_test("groq", "m")
        self.assertFalse(result["ok"])
        self.assertIn("HTTP 403", result["message"])

    def test_network_error_is_reported_cleanly(self) -> None:
        class _Client:
            def __init__(self, *args, **kwargs):
                pass

            def get(self, _url, headers=None):
                raise httpx.ConnectError("boom")

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

        with patch.dict(os.environ, {"GROQ_API_KEY": "k"}), patch(
            "server.connection_test.httpx.Client", _Client
        ):
            result = run_connection_test("groq", "m")
        self.assertFalse(result["ok"])
        self.assertIn("network", result["message"].lower())

    def test_missing_credentials_fails_without_calling_provider(self) -> None:
        with patch.dict(os.environ, {"GROQ_API_KEY": ""}):
            result = run_connection_test("groq", "m")
        self.assertFalse(result["ok"])
        self.assertIn("not configured", result["message"])

    def test_gnani_has_no_fake_success(self) -> None:
        with patch.dict(os.environ, {"GNANI_API": "k"}):
            with self.assertRaises(ConnectionTestError):
                run_connection_test("gnani")

    def test_unknown_provider_rejected(self) -> None:
        with self.assertRaises(ConnectionTestError):
            run_connection_test("anthropic")


class BridgeProviderApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app_module.app)

    def setUp(self) -> None:
        for spec in PROVIDERS.values():
            os.environ.pop(spec.env_var, None)
        # Keep endpoint tests hermetic: no writes to the real debug.log.
        log_patcher = patch("server.app.log_event")
        log_patcher.start()
        self.addCleanup(log_patcher.stop)

    def test_providers_listing_returns_safe_metadata(self) -> None:
        with _TempEnv() as env_path:
            save_credential("groq", "gsk_secret_bridge_value")
            response = self.client.get("/api/settings/providers")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["selected_llm"], "openrouter")
        ids = {provider["id"] for provider in body["providers"]}
        self.assertEqual(ids, {"openrouter", "groq", "gnani"})
        self.assertNotIn("gsk_secret_bridge_value", response.text)
        groq = next(p for p in body["providers"] if p["id"] == "groq")
        self.assertTrue(groq["configured"])
        self.assertIsInstance(groq["connection_test_supported"], bool)

    def test_save_credential_endpoint_and_runtime_refresh(self) -> None:
        with _TempEnv() as env_path:
            response = self.client.post(
                "/api/settings/providers/credentials",
                json={"provider": "openrouter", "api_key": "sk-or-bridge-secret"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()["provider"]["configured"])
            self.assertIn(
                "OPENROUTER_API_KEY=sk-or-bridge-secret", env_path.read_text(encoding="utf-8")
            )
            self.assertEqual(os.environ.get("OPENROUTER_API_KEY"), "sk-or-bridge-secret")
            self.assertNotIn("sk-or-bridge-secret", response.text)
            status = self.client.get("/api/status").json()
            self.assertTrue(status["credentials"]["openrouter"])
            self.assertNotIn("sk-or-bridge-secret", repr(status))

    def test_remove_credential_endpoint(self) -> None:
        with _TempEnv() as env_path:
            env_path.write_text(
                "OPENROUTER_API_KEY=old\nGROQ_API_KEY=g\n", encoding="utf-8"
            )
            os.environ["OPENROUTER_API_KEY"] = "old"
            response = self.client.delete(
                "/api/settings/providers/credentials/openrouter"
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(response.json()["provider"]["configured"])
            self.assertNotIn("OPENROUTER_API_KEY", env_path.read_text(encoding="utf-8"))
            self.assertIn("GROQ_API_KEY=g", env_path.read_text(encoding="utf-8"))
            self.assertNotIn("OPENROUTER_API_KEY", os.environ)

    def test_delete_unknown_provider_is_404(self) -> None:
        with _TempEnv():
            response = self.client.delete(
                "/api/settings/providers/credentials/anthropic"
            )
        self.assertEqual(response.status_code, 404)

    def test_save_invalid_provider_is_rejected(self) -> None:
        with _TempEnv():
            response = self.client.post(
                "/api/settings/providers/credentials",
                json={"provider": "anthropic", "api_key": "x"},
            )
        self.assertEqual(response.status_code, 422)

    def test_save_empty_key_is_rejected(self) -> None:
        with _TempEnv():
            response = self.client.post(
                "/api/settings/providers/credentials",
                json={"provider": "openrouter", "api_key": "  "},
            )
        self.assertEqual(response.status_code, 422)

    def test_provider_test_endpoint_uses_backend_credential(self) -> None:
        with _TempEnv():
            save_credential("groq", "gsk-test-value")
            with patch(
                "server.app.run_connection_test",
                return_value={
                    "provider": "groq",
                    "ok": True,
                    "message": "Groq accepted the API key.",
                    "model": "llama-3.3-70b-versatile",
                    "model_ok": True,
                },
            ) as tested:
                response = self.client.post(
                    "/api/settings/providers/test", json={"provider": "groq"}
                )
        tested.assert_called_once()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertNotIn("gsk-test-value", response.text)

    def test_gnani_test_returns_structured_explanation(self) -> None:
        response = self.client.post(
            "/api/settings/providers/test", json={"provider": "gnani"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("speech pipeline", response.json()["detail"])

    def test_config_rejects_unknown_provider(self) -> None:
        response = self.client.put("/api/config", json={"llm_provider": "anthropic"})
        self.assertEqual(response.status_code, 422)

    def test_provider_switch_persists_to_ini_and_runtime(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        ini = Path(directory.name) / "rubberducky.ini"
        ini.write_text(
            "[llm]\nprovider = openrouter\nmodel = vendor/x\n", encoding="utf-8"
        )
        previous = config_module.DEFAULT_CONFIG_PATH
        config_module.DEFAULT_CONFIG_PATH = ini
        reset_config_cache()
        try:
            response = self.client.put("/api/config", json={"llm_provider": "groq"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["llm"]["provider"], "groq")
            self.assertIn("provider = groq", ini.read_text(encoding="utf-8"))
            # Takes effect immediately for newly built clients.
            self.assertEqual(load_config().llm.provider, "groq")
        finally:
            config_module.DEFAULT_CONFIG_PATH = previous
            reset_config_cache()
        self.assertEqual(load_config().llm.provider, "openrouter")

    def test_credential_endpoints_require_local_host(self) -> None:
        response = self.client.post(
            "/api/settings/providers/credentials",
            json={"provider": "openrouter", "api_key": "x"},
            headers={"host": "evil.example"},
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
