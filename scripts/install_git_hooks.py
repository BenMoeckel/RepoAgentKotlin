"""Install the reviewable local Codex documentation hooks in a target checkout."""

import argparse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def install(target, repoagent, codex, migrate=False):
    root = Path(subprocess.check_output(
        ["git", "-C", str(target), "rev-parse", "--show-toplevel"], text=True
    ).strip())
    for executable in (repoagent, codex):
        if not executable.is_file():
            raise RuntimeError(f"Executable missing: {executable}")
    configured = subprocess.run(
        ["git", "-C", str(root), "config", "--get", "core.hooksPath"],
        capture_output=True, text=True,
    )
    if configured.returncode == 0 and not (migrate and configured.stdout.strip() == ".githooks"):
        raise RuntimeError("Existing core.hooksPath found; integrate hooks manually.")
    for name in ("pre-commit", "post-merge", "post-rewrite"):
        hook_path = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-path", f"hooks/{name}"],
            text=True,
        ).strip()
        legacy_migration = (
            migrate and name == "pre-commit"
            and Path(hook_path).resolve() == (root / ".githooks/pre-commit").resolve()
        )
        if Path(hook_path).exists() and not legacy_migration:
            raise RuntimeError(f"An existing {name} hook must be preserved and integrated manually.")
    templates = Path(__file__).resolve().parents[1] / "integrations/git-hooks"
    files = {
        "post-merge": ".githooks/post-merge",
        "post-rewrite": ".githooks/post-rewrite",
        "after-sync.sh": ".repoagent/after-sync.sh",
        "update-docs.sh": ".repoagent/update-docs.sh",
        "README.md": ".repoagent/README.md",
    }
    legacy = root / ".githooks/pre-commit"
    disabled = legacy.with_name("pre-commit.disabled")
    if legacy.exists() and (
        not migrate or legacy.read_bytes() != (templates / "pre-commit").read_bytes()
    ):
        raise RuntimeError("Existing pre-commit differs from RepoAgent's legacy hook; refusing to replace it.")
    if migrate and disabled.exists():
        raise RuntimeError("A pre-commit.disabled backup already exists; refusing to overwrite it.")
    protected = files.values() if not migrate else (
        ".githooks/post-merge", ".githooks/post-rewrite", ".repoagent/after-sync.sh"
    )
    if any((root / destination).exists() for destination in protected):
        raise RuntimeError("Target hook files already exist; refusing to overwrite them.")
    if migrate:
        git_dir = Path(subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--absolute-git-dir"], text=True
        ).strip())
        backup = git_dir / "repoagent-hook-backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        for relative in (".githooks/pre-commit", ".repoagent/update-docs.sh", ".repoagent/README.md"):
            original = root / relative
            if original.exists():
                destination = backup / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(original, destination)
        if legacy.exists():
            legacy.rename(disabled)
    for source, destination in files.items():
        path = root / destination
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(templates / source, path)
        if source != "README.md":
            path.chmod(0o755)
    for name, value in {
        "repoagent.executable": str(repoagent.absolute()),
        "repoagent.codex": str(codex.absolute()),
        "core.hooksPath": ".githooks",
        "branch.documentation.remote": "origin",
        "branch.documentation.merge": "refs/heads/develop",
        "branch.documentation.rebase": "false",
    }.items():
        subprocess.run(["git", "-C", str(root), "config", "--local", name, value], check=True)
    print(f"Installed pull/merge/rebase documentation hooks in {root}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--repoagent", required=True, type=Path)
    parser.add_argument("--codex", required=True, type=Path)
    parser.add_argument("--generate", action="store_true", help="Generate documentation after installing hooks.")
    parser.add_argument("--migrate", action="store_true", help="Back up and disable RepoAgent's old pre-commit hook.")
    args = parser.parse_args()
    install(args.target, args.repoagent, args.codex, migrate=args.migrate)
    if args.generate:
        # Four workers for the initial full run; later commits use the default one.
        subprocess.run(["git", "-C", str(args.target), "config", "--local", "repoagent.workers", "4"], check=True)
        try:
            subprocess.run([str((args.target / ".repoagent/update-docs.sh").absolute())], check=True)
        finally:
            subprocess.run(["git", "-C", str(args.target), "config", "--local", "--unset", "repoagent.workers"], check=True)
