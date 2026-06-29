"""
Tests for validate/run.py — focuses on the --claude-cli backend.
Run with:  python -m pytest validate/tests/ -v
"""
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make validate/ importable when running from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import run


# ---------------------------------------------------------------- call_model_cli
class TestCallModelCli:
    def test_returns_stdout_on_success(self, tmp_path):
        image = tmp_path / "map.jpg"
        image.write_bytes(b"fake")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"overall": 75}'
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            out = run.call_model_cli("claude-sonnet-4-6", "evaluate this", image)

        assert out == '{"overall": 75}'
        cmd = mock_run.call_args[0][0]
        assert cmd[0].lower().endswith("claude.exe") or cmd[0] == "claude"
        assert "-p" in cmd
        assert "--dangerously-skip-permissions" in cmd
        assert "--tools" in cmd
        assert "Read" in cmd
        prompt = cmd[5]
        assert str(image) in prompt
        assert "inspect" in prompt.lower()

    def test_uses_resolved_claude_executable_when_available(self, tmp_path):
        image = tmp_path / "map.jpg"
        image.write_bytes(b"fake")
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"overall": 75}'
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run, \
             patch("shutil.which", return_value=r"C:\\Program Files\\Claude\\claude.exe"):
            run.call_model_cli("claude-sonnet-4-6", "evaluate this", image)

        cmd = mock_run.call_args[0][0]
        assert cmd[0].replace('\\', '\\') == r"C:\\Program Files\\Claude\\claude.exe"

    def test_raises_on_nonzero_exit(self, tmp_path):
        image = tmp_path / "map.jpg"
        image.write_bytes(b"fake")
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "command not found"

        with patch("subprocess.run", return_value=mock_result):
            try:
                run.call_model_cli("claude-sonnet-4-6", "evaluate this", image)
                assert False, "should have raised"
            except RuntimeError as e:
                assert "1" in str(e)
                assert "command not found" in str(e)


# ---------------------------------------------------------------- describe_map_cli
class TestDescribeMapCli:
    def test_returns_stdout_on_success(self, tmp_path):
        image = tmp_path / "map.jpg"
        image.write_bytes(b"fake")
        ctx = {"name": "Alice", "role": "SC", "area": "opp", "topic": "deal", "language": "en"}
        template = "Describe this map for {{name}} about {{topic}}"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "## Map overview\nThis is a map."
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            out = run.describe_map_cli("claude-sonnet-4-6", template, ctx, image)

        assert out == "## Map overview\nThis is a map."
        called_prompt = mock_run.call_args[0][0][5]  # -p <prompt>
        assert "Alice" in called_prompt
        assert "deal" in called_prompt
        assert "inspect" in called_prompt.lower()

    def test_raises_on_nonzero_exit(self, tmp_path):
        image = tmp_path / "map.jpg"
        image.write_bytes(b"fake")
        ctx = {"name": "", "role": "", "area": "", "topic": "", "language": "en"}
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "auth error"

        with patch("subprocess.run", return_value=mock_result):
            try:
                run.describe_map_cli("claude-sonnet-4-6", "describe", ctx, image)
                assert False, "should have raised"
            except RuntimeError as e:
                assert "auth error" in str(e)


# ---------------------------------------------------------------- backend selection
class TestBackendSelection:
    def test_prefers_explicit_claude_cli_flag(self):
        args = type("Args", (), {"live": False, "claude_cli": True, "dry_run": False})()
        assert run.resolve_backend(args) == "claude_cli"

    def test_uses_claude_cli_when_available(self, monkeypatch):
        monkeypatch.setattr(run.shutil, "which", lambda name: "/usr/bin/claude")
        args = type("Args", (), {"live": False, "claude_cli": False, "dry_run": False})()
        assert run.resolve_backend(args) == "claude_cli"

    def test_falls_back_to_dry_run_without_backend(self, monkeypatch):
        monkeypatch.setattr(run.shutil, "which", lambda name: None)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "", prepend=False)
        args = type("Args", (), {"live": False, "claude_cli": False, "dry_run": False})()
        assert run.resolve_backend(args) == "dry_run"


# ---------------------------------------------------------------- prompt guidance
class TestPromptGuidance:
    def test_prompt_requires_specific_map_evidence(self):
        prompt = run.PROMPT_PATH.read_text(encoding="utf-8")
        assert "must cite specific evidence" in prompt.lower()
        assert "concrete note" in prompt.lower() or "visible evidence" in prompt.lower()


# ---------------------------------------------------------------- dry-run still works (no subprocess)
class TestDryRunNoSubprocess:
    def test_stub_result_shape(self):
        ctx = {"language": "en"}
        result = run.stub_result(ctx)
        assert result["overall"] == 74
        assert len(result["dimensions"]) == 5
        keys = {d["key"] for d in result["dimensions"]}
        assert keys == {"detail", "insight", "clarity", "innovation", "rigor"}

    def test_stub_description_contains_topic(self):
        ctx = {"topic": "pipeline review"}
        desc = run.stub_description(ctx)
        assert "pipeline review" in desc

    def test_stub_result_no_subprocess_called(self):
        with patch("subprocess.run") as mock_run:
            run.stub_result({"language": "en"})
            mock_run.assert_not_called()


# ---------------------------------------------------------------- extract_json
class TestExtractJson:
    def test_plain_json(self):
        text = '{"overall": 80, "confidence": "high"}'
        assert run.extract_json(text) == {"overall": 80, "confidence": "high"}

    def test_fenced_json(self):
        text = "```json\n{\"overall\": 70}\n```"
        assert run.extract_json(text) == {"overall": 70}

    def test_json_with_prose_around_it(self):
        text = "Here is the result:\n{\"overall\": 65}\nEnd."
        assert run.extract_json(text) == {"overall": 65}

    def test_raises_when_no_json(self):
        try:
            run.extract_json("no json here")
            assert False, "should have raised"
        except ValueError:
            pass


# ---------------------------------------------------------------- rag bands
class TestRag:
    def test_green_at_and_above_70(self):
        assert run.rag(70) == "green"
        assert run.rag(74) == "green"
        assert run.rag(100) == "green"

    def test_amber_60_to_69(self):
        assert run.rag(60) == "amber"
        assert run.rag(69) == "amber"

    def test_red_below_60(self):
        assert run.rag(59) == "red"
        assert run.rag(0) == "red"

    def test_handles_bad_input(self):
        assert run.rag(None) == "red"
        assert run.rag("x") == "red"
