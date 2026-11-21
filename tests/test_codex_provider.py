import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from llama_index.core.llms import ChatMessage
from pydantic import ValidationError

from repo_agent.codex_provider import CodexProvider
from repo_agent.main import cli
from repo_agent.settings import ChatCompletionSettings, SettingsManager


@pytest.fixture
def codex_stub(tmp_path):
    """A real subprocess, exercising stdin, argv, auth env, and output files."""
    path = tmp_path / "codex stub"
    path.write_text(
        f"#!{Path(sys.executable).resolve()}\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        "args = sys.argv[1:]\n"
        "assert not any(k in os.environ for k in "
        "['OPENAI_API_KEY', 'CODEX_API_KEY', 'OPENAI_BASE_URL', 'CODEX_ACCESS_TOKEN'])\n"
        "if args == ['login', 'status']:\n"
        "    print('Logged in using ChatGPT', file=sys.stderr)\n"
        "    sys.exit(0)\n"
        "assert args[0] == 'exec' and args[-1] == '-'\n"
        "assert '--ignore-user-config' in args and '--ephemeral' in args\n"
        "assert args[args.index('--sandbox') + 1] == 'read-only'\n"
        "assert 'forced_login_method=\"chatgpt\"' in args\n"
        "assert 'model_provider=\"openai\"' in args\n"
        "prompt = sys.stdin.read()\n"
        "assert 'SYSTEM:' in prompt and 'USER:' in prompt\n"
        "assert not Path('AGENTS.md').exists()\n"
        "if 'FAIL_GENERATION' in prompt:\n"
        "    print('private diagnostic that must not enter documentation', file=sys.stderr)\n"
        "    sys.exit(42)\n"
        "Path(args[args.index('--output-last-message') + 1]).write_text(\n"
        "    '**Erklärung**: Kotlin-Code über Codex dokumentiert.\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def test_settings_allow_codex_without_api_key_and_retain_openai_validation(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    value = ChatCompletionSettings(llm_provider="codex")
    assert value.openai_api_key is None
    assert value.model is None  # Never pass the API's default model to Codex.
    with pytest.raises(ValidationError, match="OPENAI_API_KEY is required"):
        ChatCompletionSettings(llm_provider="openai")
    assert ChatCompletionSettings(openai_api_key="fake").model == "gpt-4o-mini"


def test_codex_process_handles_concurrency_unicode_spaces_and_api_env(codex_stub, monkeypatch):
    for key in ["CODEX_API_KEY", "OPENAI_BASE_URL", "CODEX_ACCESS_TOKEN"]:
        monkeypatch.setenv(key, "must-not-be-used")
    monkeypatch.chdir(codex_stub.parent)
    provider = CodexProvider("./codex stub", model="example-model")
    messages = [ChatMessage(role="system", content="Erkläre äöü"), ChatMessage(content="fun x() = 1")]
    with ThreadPoolExecutor(max_workers=2) as executor:
        outputs = list(executor.map(lambda _: provider.generate(messages), range(3)))
    assert outputs == ["**Erklärung**: Kotlin-Code über Codex dokumentiert."] * 3


@pytest.mark.parametrize("status,code", [("Not logged in", 1), ("Logged in using an API key", 0)])
def test_codex_rejects_missing_or_api_auth(monkeypatch, status, code):
    monkeypatch.setattr("repo_agent.codex_provider.shutil.which", lambda _: "/codex")
    monkeypatch.setattr(
        "repo_agent.codex_provider.subprocess.run",
        lambda *a, **kw: SimpleNamespace(returncode=code, stdout="", stderr=status),
    )
    with pytest.raises(RuntimeError, match="requires a ChatGPT login"):
        CodexProvider()


def test_missing_cli_fails_with_install_hint(monkeypatch):
    monkeypatch.setattr("repo_agent.codex_provider.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError, match="Codex CLI not found"):
        CodexProvider()


@pytest.mark.parametrize("diagnostic,expected", [
    ("You've hit your usage limit. PRIVATE", "usage/rate limit reached"),
    ("HTTP 429 PRIVATE", "usage/rate limit reached"),
    ("401 Unauthorized PRIVATE", "authentication failed"),
    ("error sending request PRIVATE", "network connection failed"),
    ("unknown error PRIVATE", "Check 'codex login status'"),
])
def test_cli_errors_are_classified_without_exposing_diagnostics(diagnostic, expected):
    reason = CodexProvider.failure_reason(diagnostic)
    assert expected in reason
    assert "PRIVATE" not in reason


@pytest.mark.parametrize("outcome", ["timeout", "exit", "missing", "empty"])
def test_failed_generation_never_returns_diagnostics_as_docs(codex_stub, monkeypatch, outcome):
    provider = CodexProvider(str(codex_stub), timeout=2)

    def fail(args, **kwargs):
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(args, 2)
        output = Path(args[args.index("--output-last-message") + 1])
        if outcome == "empty":
            output.write_text(" \n", encoding="utf-8")
        return SimpleNamespace(returncode=42 if outcome == "exit" else 0, stderr="PRIVATE")

    monkeypatch.setattr("repo_agent.codex_provider.subprocess.run", fail)
    with pytest.raises(RuntimeError) as error:
        provider.generate([ChatMessage(content="Kotlin")])
    assert "PRIVATE" not in str(error.value)


def test_kotlin_cli_generates_and_retries_without_api_key(git_repo, settings, codex_stub, monkeypatch):
    root = settings.project.target_repo
    source = root / "Example.kt"
    source.write_text("fun FAIL_GENERATION() = 1\n", encoding="utf-8")
    git_repo.index.add([source.name])
    git_repo.index.commit("Kotlin example")
    monkeypatch.delenv("OPENAI_API_KEY")
    # Any accidental API provider construction is a test failure.
    def forbid_api(**kwargs):
        raise AssertionError("The API must not be used")

    monkeypatch.setattr("repo_agent.chat_engine.OpenAILike", forbid_api)
    args = [
        "run", "--target-repo-path", str(root), "--source-language", "kotlin",
        "--language", "German", "--llm-provider", "codex",
        "--codex-command", str(codex_stub),
    ]
    # Failed generation must be visible as a failing CLI exit, with a retry checkpoint.
    failed = CliRunner().invoke(cli, args)
    assert failed.exit_code != 0, failed.output
    assert "Documentation incomplete" in failed.output
    assert "Documentation task completed" not in failed.output
    assert SettingsManager.get_setting().project.max_thread_count == 1
    assert not (root / ".repoagent-snapshots.json").exists()
    # Retry unchanged source after the provider recovers, using the saved checkpoint.
    codex_stub.write_text(
        codex_stub.read_text().replace("if 'FAIL_GENERATION' in prompt:", "if False:"),
        encoding="utf-8",
    )
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    document = root / "markdown_docs/Example.md"
    assert "Kotlin-Code über Codex dokumentiert" in document.read_text()
    assert "PRIVATE" not in document.read_text()
    assert not (root / ".repoagent-snapshots.json").exists()
