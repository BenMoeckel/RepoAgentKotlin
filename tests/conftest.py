from pathlib import Path

import pytest
from git import Repo

from repo_agent.settings import SettingsManager


@pytest.fixture(autouse=True)
def settings(monkeypatch, tmp_path):
    # Dummy credentials are only used to construct settings. All LLMs are mocked.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-sent")
    monkeypatch.setenv("TARGET_REPO", str(tmp_path))
    monkeypatch.setenv("SOURCE_LANGUAGE", "auto")
    monkeypatch.setenv("KOTLIN_LSP_COMMAND", "")
    SettingsManager._setting_instance = None
    value = SettingsManager.get_setting()
    yield value
    SettingsManager._setting_instance = None


@pytest.fixture
def git_repo(settings):
    root = Path(settings.project.target_repo)
    repo = Repo.init(root)
    with repo.config_writer() as config:
        config.set_value("user", "name", "RepoAgent Tests")
        config.set_value("user", "email", "tests@example.invalid")
    (root / ".gitignore").write_text("build/\n.gradle/\n", encoding="utf-8")
    repo.index.add([".gitignore"])
    repo.index.commit("Initialize test repository")
    yield repo
    repo.close()
