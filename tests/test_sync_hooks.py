import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.test_git_hooks import git, install


@pytest.fixture
def sync_repo(git_repo, settings):
    root = settings.project.target_repo
    remote = root.parent / (root.name + "-remote.git")
    subprocess.run(["git", "init", "--bare", "--initial-branch=develop", str(remote)], check=True, capture_output=True)
    git(root, "branch", "develop")
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "origin", "HEAD:develop")
    git(root, "switch", "-c", "documentation")
    executable = root / "repoagent stub"
    executable.write_text(
        f"#!{Path(sys.executable).resolve()}\n"
        "import sys\nfrom pathlib import Path\n"
        "assert sys.argv[sys.argv.index('--llm-provider') + 1] == 'codex'\n"
        "root=Path(sys.argv[sys.argv.index('--target-repo-path') + 1])\n"
        "counter=root/'.git/stub_calls'\n"
        "calls=int(counter.read_text())+1 if counter.exists() else 1\n"
        "counter.write_text(str(calls))\n"
        "if (root/'.git/fail_generation').exists(): sys.exit(9)\n"
        "for folder in ['markdown_docs', '.project_doc_record']:\n"
        " (root/folder).mkdir(exist_ok=True)\n"
        " (root/folder/'generated.md').write_text('generated documentation '+str(calls))\n",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    result = install(root, executable)
    assert result.returncode == 0, result.stderr
    return root


def call_git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True,
        env={**os.environ, "GIT_EDITOR": "true", "GIT_MERGE_AUTOEDIT": "no"},
    )


def publish(root, contents):
    git(root, "switch", "develop")
    (root / "Example.kt").write_text(contents)
    git(root, "add", "Example.kt")
    git(root, "commit", "-m", "Upstream Kotlin change")
    git(root, "push", "origin", "develop")
    git(root, "switch", "documentation")


def count(root):
    path = root / ".git/stub_calls"
    return int(path.read_text()) if path.exists() else 0


def test_plain_pull_fast_forward_merge_and_rebase_update_documentation(sync_repo):
    root = sync_repo
    publish(root, "fun example() = 1\n")
    assert count(root) == 0  # Source commits are not triggers.
    result = call_git(root, "pull")
    assert result.returncode == 0, result.stderr
    assert count(root) == 1  # Fast-forward pull runs post-merge.
    staged = git(root, "diff", "--cached", "--name-only").stdout
    assert "markdown_docs/generated.md" in staged
    assert ".project_doc_record/generated.md" in staged
    git(root, "commit", "-m", "Document current source")
    assert count(root) == 1
    git(root, "commit", "--amend", "--no-edit")
    assert count(root) == 1  # post-rewrite amend is ignored.
    result = call_git(root, "pull")
    assert result.returncode == 0, result.stderr
    assert count(root) == 1  # No source integration on an up-to-date pull.

    publish(root, "fun example() = 2\n")
    result = call_git(root, "pull")
    assert result.returncode == 0, result.stderr
    assert count(root) == 2  # Diverging docs branch is merged, not reset.
    assert (root / "Example.kt").read_text() == "fun example() = 2\n"
    git(root, "commit", "-m", "Update generated docs")

    publish(root, "fun example() = 3\n")
    result = call_git(root, "pull", "--rebase")
    assert result.returncode == 0, result.stderr
    assert count(root) == 3  # Rebase pull is covered by post-rewrite.
    assert (root / "Example.kt").read_text() == "fun example() = 3\n"


def test_hooks_ignore_other_branches_and_preserve_local_changes(sync_repo):
    root = sync_repo
    git(root, "switch", "develop")
    result = subprocess.run([str(root / ".githooks/post-merge"), "0"], cwd=root, capture_output=True)
    assert result.returncode == 0
    assert count(root) == 0
    git(root, "switch", "documentation")
    (root / ".gitignore").write_text("local precious edit\n")
    result = subprocess.run([str(root / ".githooks/post-merge"), "0"], cwd=root, capture_output=True, text=True)
    assert result.returncode != 0
    assert "lokale Änderungen" in result.stderr
    assert count(root) == 0
    assert (root / ".gitignore").read_text() == "local precious edit\n"


def test_failed_pull_does_not_generate_and_generation_failure_does_not_undo_pull(sync_repo):
    root = sync_repo
    (root / "Example.kt").write_text("fun local() = 1\n")
    git(root, "add", "Example.kt")
    git(root, "commit", "-m", "Conflicting local source")
    publish(root, "fun upstream() = 2\n")
    result = call_git(root, "pull")
    assert result.returncode != 0
    assert count(root) == 0  # Conflict: no completed integration.
    git(root, "merge", "--abort")
    # Resolve through a fresh integration with an explicit merge strategy for this test.
    (root / ".git/fail_generation").write_text("fail")
    result = call_git(root, "pull", "--no-edit", "-s", "ours")
    assert result.returncode == 0, result.stderr  # Git ignores post-hook exit codes.
    assert count(root) == 1
    assert "Doku-Aktualisierung fehlgeschlagen" in result.stderr
    assert "Git-Übernahme ist bereits abgeschlossen" in result.stderr
    assert not (root / ".git/repoagent-run.lock").exists()
