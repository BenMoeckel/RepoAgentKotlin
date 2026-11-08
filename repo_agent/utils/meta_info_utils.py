"""Temporarily expose Git index contents, preserving the working tree exactly."""

import json
import os
from pathlib import Path

import git

from repo_agent.backends import is_source_file
from repo_agent.settings import SettingsManager

# Kept for callers which exclude snapshot files from discovery.
latest_verison_substring = ("_latest_version.py", "_latest_version.kt", "_latest_version.kts")
_manifest_name = ".repoagent-snapshots.json"


def _save_manifest(path, entries):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(entries), encoding="utf-8")
    os.replace(temporary, path)


def make_fake_files():
    """Analyze staged source while retaining untracked and unstaged user edits.

    A recovery manifest distinguishes an absent file from a genuinely empty one.
    Existing backup paths are never overwritten.
    """
    delete_fake_files()
    root = Path(SettingsManager.get_setting().project.target_repo)
    repo = git.Repo(root)
    manifest = root / _manifest_name
    entries, reflections = [], {}
    jump_files = [name for name in repo.untracked_files if is_source_file(name)]
    try:
        for diff in repo.index.diff(None):
            name = diff.a_path
            if not name or not is_source_file(name):
                continue
            if diff.change_type == "A":
                jump_files.append(name)
                continue
            if diff.change_type not in {"M", "D"}:
                continue
            path = root / name
            backup = path.with_name(path.stem + "_latest_version" + path.suffix)
            if backup.exists():
                raise FileExistsError(f"Reserved RepoAgent backup already exists: {backup}")
            existed = path.exists()
            entry = {"source": name, "backup": backup.relative_to(root).as_posix(),
                     "existed": existed}
            entries.append(entry)
            _save_manifest(manifest, entries)
            if existed:
                os.replace(path, backup)
            path.write_bytes(diff.a_blob.data_stream.read())
            reflections[name] = entry["backup"]
    except BaseException:
        delete_fake_files()
        raise
    finally:
        repo.close()
    return reflections, jump_files


def delete_fake_files():
    """Recover only files owned by our manifest, including empty working files."""
    root = Path(SettingsManager.get_setting().project.target_repo)
    manifest = root / _manifest_name
    if not manifest.exists():
        return
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    for entry in reversed(entries):
        source = (root / entry["source"]).resolve()
        backup = (root / entry["backup"]).resolve()
        if not source.is_relative_to(root.resolve()) or not backup.is_relative_to(root.resolve()):
            raise ValueError("Invalid RepoAgent recovery path")
        if entry["existed"]:
            if backup.exists():
                os.replace(backup, source)
        else:
            source.unlink(missing_ok=True)
    manifest.unlink()
