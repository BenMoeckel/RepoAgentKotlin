import subprocess
import sys
from pathlib import Path


def git(root, *args, check=True):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=check)


def install(root, executable, migrate=False):
    return subprocess.run(
        [sys.executable, "scripts/install_git_hooks.py", str(root),
         "--repoagent", str(executable), "--codex", "/usr/bin/true",
         *(["--migrate"] if migrate else [])],
        capture_output=True, text=True,
    )


def test_migration_disables_legacy_commit_hook(git_repo, settings):
    root = settings.project.target_repo
    legacy = root / ".githooks/pre-commit"
    legacy.parent.mkdir()
    legacy.write_bytes(Path("integrations/git-hooks/pre-commit").read_bytes())
    legacy.chmod(0o755)
    git(root, "config", "--local", "core.hooksPath", ".githooks")
    result = install(root, Path("/usr/bin/true"), migrate=True)
    assert result.returncode == 0, result.stderr
    assert not legacy.exists()
    assert legacy.with_name("pre-commit.disabled").is_file()
    assert (root / ".githooks/post-merge").is_file()
    assert (root / ".githooks/post-rewrite").is_file()
    assert list((root / ".git/repoagent-hook-backups").rglob("pre-commit"))
    # A normal commit succeeds without ever running the fake /usr/bin/true provider.
    # If generation ran, it would fail because no output folders exist to stage.
    git(root, "switch", "-c", "documentation")
    (root / "Example.kt").write_text("fun example() = 1\n")
    git(root, "add", "Example.kt")
    git(root, "commit", "-m", "Normal commits no longer generate documentation")
    assert not (root / "markdown_docs").exists()
    assert git(root, "config", "--get", "branch.documentation.merge").stdout.strip() == "refs/heads/develop"


def test_installer_preserves_existing_hook(git_repo, settings):
    root = settings.project.target_repo
    hook = root / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\necho existing\n")
    result = install(root, Path("/usr/bin/true"))
    assert result.returncode != 0
    assert "existing pre-commit hook" in result.stderr
    assert hook.read_text() == "#!/bin/sh\necho existing\n"
    assert not (root / ".githooks").exists()


def test_migration_refuses_a_modified_legacy_hook(git_repo, settings):
    root = settings.project.target_repo
    hook = root / ".githooks/pre-commit"
    hook.parent.mkdir()
    hook.write_text("#!/bin/sh\necho user-customized\n")
    git(root, "config", "--local", "core.hooksPath", ".githooks")
    result = install(root, Path("/usr/bin/true"), migrate=True)
    assert result.returncode != 0
    assert "differs from RepoAgent" in result.stderr
    assert hook.read_text() == "#!/bin/sh\necho user-customized\n"
    assert not (root / ".githooks/post-merge").exists()
