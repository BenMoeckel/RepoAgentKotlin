import pytest

from repo_agent.utils.meta_info_utils import delete_fake_files, make_fake_files


@pytest.mark.parametrize("suffix", ["py", "kt", "kts"])
@pytest.mark.parametrize("working", [b"unstaged changes\r\n", b"", None])
def test_index_snapshot_restores_exact_working_state(
    git_repo, settings, suffix, working
):
    root = settings.project.target_repo
    name = f"Source.{suffix}"
    path = root / name
    path.write_bytes(b"committed\n")
    git_repo.index.add([name])
    git_repo.index.commit("Source")
    path.write_bytes(b"staged\n")
    git_repo.index.add([name])
    if working is None:
        path.unlink()
    else:
        path.write_bytes(working)
    untracked = root / f"Untracked.{suffix}"
    untracked.write_bytes(b"untracked")
    reflections, skipped = make_fake_files()
    assert name in reflections
    assert untracked.name in skipped
    assert path.read_bytes() == b"staged\n"
    delete_fake_files()
    if working is None:
        assert not path.exists()
    else:
        assert path.read_bytes() == working
    assert git_repo.git.show(f":{name}") == "staged"
    assert untracked.read_bytes() == b"untracked"
    assert not (root / ".repoagent-snapshots.json").exists()
    delete_fake_files()  # Recovery is idempotent.


def test_existing_backup_is_never_overwritten(git_repo, settings):
    root = settings.project.target_repo
    path = root / "App.kt"
    path.write_text("original")
    git_repo.index.add([path.name])
    git_repo.index.commit("Source")
    path.write_text("user edit")
    backup = root / "App_latest_version.kt"
    backup.write_text("user backup")
    with pytest.raises(FileExistsError):
        make_fake_files()
    assert path.read_text() == "user edit"
    assert backup.read_text() == "user backup"
