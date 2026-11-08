"""Tests for the shared core refactor (no network, microphone, or playback)."""
from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_STATE = tempfile.TemporaryDirectory()
os.environ["RUBBERDUCKY_STATE_DIR"] = _STATE.name

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError

import ducky
from core.config import load_config
from core.git_ops import (
    GitCommit,
    GitContext,
    collect_git_context,
    format_git_context,
)
from core.ignore import IgnoreManager
from core.llm_client import (
    LLMError,
    LLMErrorCode,
    build_client,
    complete_json,
    extract_json_object,
)
from core.parser import analyze_incident, validate_diagnosis
from core.pipeline import (
    DiagnosisOutcome,
    PipelineResult,
    TriageOutcome,
    run_debug_pipeline,
)
from core.repository import collect_candidate_paths
from server.git_service import build_git_context
from server.models import SessionRecord
from server.session_runner import SessionRunner


class RepositoryScanningTests(unittest.TestCase):
    def test_scans_once_with_shared_exclusions_and_limits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / "node_modules").mkdir()
            (root / "__pycache__").mkdir()
            (root / "dist").mkdir()
            (root / "keep.py").write_text("print('ok')", encoding="utf-8")
            (root / "src" / "app.py").write_text("x = 1", encoding="utf-8")
            (root / "node_modules" / "pkg.js").write_text("x", encoding="utf-8")
            (root / "__pycache__" / "x.pyc").write_text("x", encoding="utf-8")
            (root / "dist" / "bundle.js").write_text("x", encoding="utf-8")
            (root / ".env").write_text("SECRET=1", encoding="utf-8")
            (root / "ignored.log").write_text("log", encoding="utf-8")
            (root / ".rubberduckyignore").write_text("*.log\n", encoding="utf-8")

            manager = IgnoreManager(root)
            paths = collect_candidate_paths(root, manager)

            self.assertIn("keep.py", paths)
            self.assertIn("src/app.py", paths)
            self.assertNotIn(".env", paths)
            self.assertNotIn("ignored.log", paths)
            self.assertFalse(any(path.startswith(("node_modules/", "dist/", "__pycache__/")) for path in paths))
            self.assertEqual(len(collect_candidate_paths(root, manager, limit=2)), 2)
            self.assertEqual(manager.sensitive_findings([".env", "src/app.py"]), [".env"])


class GitContextTests(unittest.TestCase):
    def test_collects_each_git_operation_once_and_formats_without_git(self) -> None:
        calls: list[tuple[str, ...]] = []

        def fake_run(args, repo_path=None, *, config=None):
            calls.append(tuple(args))
            if args[0] == "status":
                return "## main...origin/main\n M safe.py\n!! ignored.log"
            if args[0] == "diff" and args[1] == "--name-only":
                return "conflict.py"
            if args[0] == "diff" and args[1] == "--cached":
                return "diff --git a/safe.py b/safe.py\n+staged"
            if args[0] == "diff":
                return ""
            if args[0] == "log":
                return "abc123 | 2026-01-01 | Subject"
            if args[0] == "rev-parse":
                return "main"
            return ""

        with tempfile.TemporaryDirectory() as directory, patch(
            "core.git_ops._run_git", side_effect=fake_run
        ):
            context = collect_git_context(directory)

            self.assertEqual(context.branch, "main")
            self.assertFalse(context.clean)
            self.assertEqual(context.ignored_paths, ["ignored.log"])
            self.assertEqual(context.conflicts, ["conflict.py"])
            self.assertTrue(context.has_conflicts)
            self.assertEqual(context.commits, [GitCommit("abc123", "2026-01-01", "Subject")])
            self.assertEqual(len([call for call in calls if call[0] == "status"]), 1)
            self.assertEqual(len([call for call in calls if call[0] == "diff"]), 3)
            self.assertEqual(len([call for call in calls if call[0] == "log"]), 1)
            self.assertEqual(len([call for call in calls if call[0] == "rev-parse"]), 1)

            before = len(calls)
            text = format_git_context(context)
            self.assertIn("GIT STATUS:", text)
            self.assertEqual(len(calls), before)


    def test_failed_git_status_is_not_reported_as_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch(
            "core.git_ops._run_git", return_value=""
        ), patch("core.git_ops.shutil.which", return_value="/usr/bin/git"):
            context = collect_git_context(directory)

        self.assertFalse(context.clean)
        self.assertTrue(context.status_lines)
        self.assertIn("Git context unavailable", context.status_lines[0])

    def test_frontend_projection_reuses_core_collection(self) -> None:
        context = GitContext(
            branch="main",
            clean=True,
            status_lines=["## main"],
            conflicts=[],
            has_conflicts=False,
            staged_diff="No staged changes.",
            unstaged_diff="No unstaged tracked changes.",
            commits=[],
            ignored_paths=[],
        )
        with patch("server.git_service.collect_git_context", return_value=context) as collect:
            payload = build_git_context("/tmp/example")
            collect.assert_called_once_with("/tmp/example")
            self.assertEqual(payload["branch"], "main")
            self.assertEqual(payload["commits"], [])


class SharedClientTests(unittest.TestCase):
    def test_client_uses_shared_base_url_timeout_and_retry_policy(self) -> None:
        cfg = replace(load_config(), llm=replace(load_config().llm, timeout=17))
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}), patch(
            "core.llm_client.OpenAI"
        ) as openai_cls:
            build_client(cfg)
        openai_cls.assert_called_once_with(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            timeout=17.0,
            max_retries=0,
        )

    def test_missing_key_is_structured_and_not_retryable(self) -> None:
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}):
            with self.assertRaises(LLMError) as raised:
                build_client(load_config())
        self.assertEqual(raised.exception.code, LLMErrorCode.MISSING_CREDENTIALS)
        self.assertFalse(raised.exception.retryable)


class StructuredLlmErrorTests(unittest.TestCase):
    def _response(self, content):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    def _client(self, *, response=None, error=None):
        def create(**_kwargs):
            if error is not None:
                raise error
            return response

        return SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

    def _complete(self, client):
        with patch("core.llm_client.log_event"):
            return complete_json("system", "user", client=client)

    def test_status_codes_map_to_structured_errors(self) -> None:
        cases = {
            401: (LLMErrorCode.AUTHENTICATION_ERROR, False),
            402: (LLMErrorCode.PAYMENT_REQUIRED, False),
            429: (LLMErrorCode.RATE_LIMITED, True),
            500: (LLMErrorCode.SERVER_ERROR, True),
        }
        for status, (code, retryable) in cases.items():
            request = httpx.Request("POST", "https://openrouter.ai/api/v1")
            error = APIStatusError(
                "failure",
                response=httpx.Response(status, request=request),
                body=None,
            )
            with self.assertRaises(LLMError) as raised:
                self._complete(self._client(error=error))
            self.assertEqual(raised.exception.code, code)
            self.assertEqual(raised.exception.retryable, retryable)
            self.assertEqual(raised.exception.status_code, status)

    def test_timeout_and_connection_errors_are_retryable(self) -> None:
        request = httpx.Request("POST", "https://openrouter.ai/api/v1")
        for error, code in (
            (APITimeoutError(request=request), LLMErrorCode.TIMEOUT),
            (APIConnectionError(request=request), LLMErrorCode.CONNECTION_ERROR),
        ):
            with self.assertRaises(LLMError) as raised:
                self._complete(self._client(error=error))
            self.assertEqual(raised.exception.code, code)
            self.assertTrue(raised.exception.retryable)

    def test_empty_response_invalid_json_and_schema_failures(self) -> None:
        with self.assertRaises(LLMError) as empty:
            self._complete(self._client(response=SimpleNamespace(choices=[])))
        self.assertEqual(empty.exception.code, LLMErrorCode.EMPTY_RESPONSE)

        with self.assertRaises(LLMError) as invalid:
            self._complete(self._client(response=self._response("not json")))
        self.assertEqual(invalid.exception.code, LLMErrorCode.INVALID_JSON)

        with self.assertRaises(LLMError) as schema:
            extract_json_object("[1, 2]")
        self.assertEqual(schema.exception.code, LLMErrorCode.SCHEMA_ERROR)

        with self.assertRaises(LLMError) as diagnosis_schema:
            validate_diagnosis({"diagnosis": "", "tts_response": "hello"})
        self.assertEqual(diagnosis_schema.exception.code, LLMErrorCode.SCHEMA_ERROR)

    def test_valid_json_is_returned(self) -> None:
        data = self._complete(
            self._client(
                response=self._response('{"diagnosis":"ok","tts_response":"theek hai"}')
            )
        )
        self.assertEqual(data["diagnosis"], "ok")
        self.assertEqual(validate_diagnosis(data)["tts_response"], "theek hai")

    def test_parser_preserves_diagnosis_contract(self) -> None:
        expected = {"diagnosis": "technical explanation", "tts_response": "Hinglish reply"}
        with patch("core.parser.build_client"), patch(
            "core.parser.complete_json", return_value=expected
        ) as complete:
            result = analyze_incident("bug", git_diff="", docker_logs="", category="logic_bug")
        self.assertEqual(result, expected)
        complete.assert_called_once()


class ManageIgnoresTests(unittest.TestCase):
    def test_pattern_suggestions_use_shared_client(self) -> None:
        import manage_ignores

        with patch(
            "manage_ignores.complete_json",
            return_value={"patterns": ["*.log", "  ", 42]},
        ) as complete:
            patterns = manage_ignores.ask_ai_for_patterns(["a.log"])
        self.assertEqual(patterns, ["*.log"])
        self.assertEqual(complete.call_args.kwargs["temperature"], 0.0)


class PipelineTests(unittest.TestCase):
    def _context(self) -> GitContext:
        return GitContext(
            branch="main",
            clean=True,
            status_lines=["## main"],
            conflicts=[],
            has_conflicts=False,
            staged_diff="No staged changes.",
            unstaged_diff="No unstaged tracked changes.",
            commits=[],
            ignored_paths=[],
        )

    def test_pipeline_runs_shared_stages_in_order(self) -> None:
        events: list[str] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = replace(load_config(), project_root=root)
            triage = TriageOutcome("infrastructure", "keyword_router", True, 1.0)
            diagnosis = DiagnosisOutcome("diagnosis text", "Hinglish text")
            with patch("core.pipeline.collect_git_context", return_value=self._context()) as git, \
                 patch("core.pipeline.run_triage", return_value=triage), \
                 patch("core.pipeline.collect_docker_logs", return_value="log text") as logs, \
                 patch("core.pipeline.diagnose_incident", return_value=diagnosis), \
                 patch("core.pipeline.generate_tts", side_effect=lambda _s, path, _c: path), \
                 patch("core.pipeline.log_event"):
                result = run_debug_pipeline(
                    "bug",
                    config=cfg,
                    repo_path=root,
                    docker_container="api",
                    output_audio_path=root / "out.wav",
                    on_event=lambda event_type, _payload: events.append(event_type),
                )
        git.assert_called_once()
        logs.assert_called_once_with("api")
        self.assertEqual(result.diagnosis, diagnosis)
        self.assertEqual(result.docker_logs, "log text")
        self.assertEqual(result.audio_path, Path(directory) / "out.wav")
        self.assertIsNone(result.error)
        self.assertEqual(
            events,
            [
                "git_context_collected",
                "triage_started",
                "triage_completed",
                "docker_logs_started",
                "docker_logs_completed",
                "llm_started",
                "llm_completed",
                "tts_started",
                "tts_completed",
            ],
        )

    def test_pipeline_returns_structured_llm_failure_without_tts(self) -> None:
        events: list[str] = []
        failure = LLMError(
            LLMErrorCode.RATE_LIMITED,
            "rate limited",
            retryable=True,
            status_code=429,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = replace(load_config(), project_root=root)
            with patch("core.pipeline.collect_git_context", return_value=self._context()), \
                 patch("core.pipeline.run_triage", return_value=TriageOutcome("logic_bug", "laya", False, 0.0)), \
                 patch("core.pipeline.diagnose_incident", side_effect=failure), \
                 patch("core.pipeline.generate_tts") as tts, \
                 patch("core.pipeline.log_event"):
                result = run_debug_pipeline(
                    "bug",
                    config=cfg,
                    repo_path=root,
                    output_audio_path=root / "out.wav",
                    on_event=lambda event_type, _payload: events.append(event_type),
                )
        self.assertEqual(result.error, failure)
        self.assertIsNone(result.diagnosis)
        tts.assert_not_called()
        self.assertEqual(events[-1], "llm_failed")
        self.assertNotIn("tts_started", events)

    def test_cli_log_policy_skips_non_infrastructure_container(self) -> None:
        provider_calls: list[bool] = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = replace(load_config(), project_root=root)
            with patch("core.pipeline.collect_git_context", return_value=self._context()), \
                 patch("core.pipeline.run_triage", return_value=TriageOutcome("logic_bug", "laya", True, 0.9)), \
                 patch("core.pipeline.diagnose_incident", return_value=DiagnosisOutcome("d", "s")), \
                 patch("core.pipeline.generate_tts", side_effect=lambda _s, path, _c: path), \
                 patch("core.pipeline.log_event"):
                run_debug_pipeline(
                    "bug",
                    config=cfg,
                    repo_path=root,
                    docker_container_provider=lambda: provider_calls.append(True) or "api",
                    output_audio_path=root / "out.wav",
                    infrastructure_logs_only=True,
                )
        self.assertEqual(provider_calls, [])


class CliCompatibilityTests(unittest.TestCase):
    def test_cli_calls_shared_pipeline_and_aplay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cfg = replace(load_config(), project_root=root)
            result = PipelineResult(
                transcript="bug",
                diagnosis=DiagnosisOutcome("d", "s"),
                audio_path=Path("temp_output.wav"),
            )
            original_cwd = os.getcwd()
            try:
                with patch("ducky.load_dotenv"), \
                     patch("ducky.load_config", return_value=cfg), \
                     patch("ducky.record_audio", return_value=True), \
                     patch("ducky.transcribe_audio", return_value="bug"), \
                     patch("ducky.run_debug_pipeline", return_value=result) as pipeline, \
                     patch("ducky.log_event"), \
                     patch("ducky.subprocess.run") as run:
                    ducky.main()
            finally:
                os.chdir(original_cwd)
        pipeline.assert_called_once()
        self.assertEqual(pipeline.call_args.args[0], "bug")
        self.assertEqual(pipeline.call_args.kwargs["output_audio_path"], "temp_output.wav")
        run.assert_called_once_with(
            ["aplay", "temp_output.wav"],
            check=True,
            stderr=ducky.subprocess.DEVNULL,
        )


class FrontendSessionCompatibilityTests(unittest.TestCase):
    def test_pipeline_events_update_session_record(self) -> None:
        runner = SessionRunner()
        session = SessionRecord(
            id="test-session",
            started_at=1.0,
            updated_at=1.0,
            status="processing",
            stage="triage",
        )
        published: list[tuple[str, dict]] = []
        with patch("server.session_runner.session_store.upsert", return_value=session), \
             patch("server.session_runner.event_bus.publish", side_effect=lambda name, payload: published.append((name, payload))):
            runner._handle_pipeline_event(
                session,
                "triage_completed",
                {
                    "category": "infrastructure",
                    "category_source": "keyword_router",
                    "log_probability": 1.0,
                    "requires_logs": True,
                },
            )
        self.assertEqual(session.category, "infrastructure")
        self.assertTrue(session.requires_logs)
        self.assertEqual(published[-1][0], "triage_completed")
        self.assertEqual(published[-1][1]["stage"], "llm")


class IgnoreRedactionTests(unittest.TestCase):
    def test_secret_redaction_and_diff_filtering_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".rubberduckyignore").write_text("", encoding="utf-8")
            manager = IgnoreManager(root)
            redacted = manager.redact_secrets(
                "OPENROUTER_API_KEY=sk-abcdefghijklmnopqrstuvwxyz"
            )
            self.assertNotIn("sk-abcdefghijklmnopqrstuvwxyz", redacted)
            self.assertIn("[REDACTED]", redacted)

            diff = (
                "diff --git a/.env b/.env\n+SECRET=1\n"
                "diff --git a/app.py b/app.py\n+password = 'hunter2'\n"
            )
            safe = manager.filter_git_diff(diff)
            self.assertNotIn(".env", safe)
            self.assertIn("app.py", safe)
            self.assertNotIn("hunter2", safe)


if __name__ == "__main__":
    unittest.main()
