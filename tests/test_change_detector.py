from repo_agent.change_detector import ChangeDetector


def test_staged_sources_are_selected_by_backend(git_repo, settings):
    root = settings.project.target_repo
    for name in ("app.py", "App.kt", "build.gradle.kts", "README.md"):
        (root / name).write_text("", encoding="utf-8")
        git_repo.index.add([name])
    detector = ChangeDetector(root)
    assert set(detector.get_staged_pys()) == {"app.py", "App.kt", "build.gradle.kts"}
    settings.project.source_language = "kotlin"
    assert set(detector.get_staged_pys()) == {"App.kt", "build.gradle.kts"}
    settings.project.source_language = "python"
    assert set(detector.get_staged_pys()) == {"app.py"}


def test_only_generated_docs_are_staged(git_repo, settings):
    root = settings.project.target_repo
    docs = root / settings.project.markdown_docs_name
    docs.mkdir()
    (docs / "App.md").write_text("Documentation", encoding="utf-8")
    (root / "notes.md").write_text("User notes", encoding="utf-8")
    detector = ChangeDetector(root)
    assert detector.add_unstaged_files() == [f"{docs.name}/App.md"]
    assert "notes.md" in git_repo.untracked_files
    assert detector.get_to_be_staged_files() == []
