from types import SimpleNamespace

import pytest

from repo_agent.doc_meta_info import DocItemStatus, MetaInfo, need_to_generate
from repo_agent.runner import Runner
from repo_agent.utils.meta_info_utils import delete_fake_files


@pytest.fixture
def fake_llm(monkeypatch):
    calls = []

    class FakeLLM:
        def __init__(self, **kwargs):
            pass

        def chat(self, messages):
            calls.append(messages)
            assert all("{project_structure}" not in m.content for m in messages)
            return SimpleNamespace(
                message=SimpleNamespace(
                    content="**Documentation**: Generated from code."
                ),
                raw=SimpleNamespace(
                    usage=SimpleNamespace(
                        prompt_tokens=1, completion_tokens=1, total_tokens=2
                    )
                ),
            )

    monkeypatch.setattr("repo_agent.chat_engine.OpenAILike", FakeLLM)
    return calls


def commit_sources(repo, root, files):
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    repo.index.add(list(files))
    repo.index.commit("Source fixtures")


def test_mixed_repository_generates_markdown_and_roundtrips_metadata(
    git_repo, settings, fake_llm
):
    root = settings.project.target_repo
    commit_sources(
        git_repo,
        root,
        {
            "src/App.kt": 'interface Api { fun load(id: Int): String }\nobject App { val name = "App"; fun run() = name }\n',
            "src/build.gradle.kts": 'fun configure() = "configured"\n',
            "src/helper.py": "async def helper(value):\n    return value\n",
            "build/Generated.kt": "fun generated() = 1\n",
        },
    )
    runner = Runner()
    runner.run()
    docs = root / settings.project.markdown_docs_name
    assert (docs / "src/App.md").exists()
    assert (docs / "src/build.gradle.kts.md").exists()
    assert (docs / "src/helper.md").exists()
    assert not (docs / "build/Generated.md").exists()
    assert "## Interface Api" in (docs / "src/App.md").read_text()
    assert "Property name" in (docs / "src/App.md").read_text()
    assert fake_llm
    assert any(
        "Source language: kotlin" in msg.content for call in fake_llm for msg in call
    )
    assert any(
        "Source language: python" in msg.content for call in fake_llm for msg in call
    )
    restored = MetaInfo.from_checkpoint_path(runner.absolute_project_hierarchy_path)
    assert restored.to_hierarchy_json() == runner.meta_info.to_hierarchy_json()
    assert all(
        not need_to_generate(i)
        for i in restored.target_repo_hierarchical_tree.get_travel_list()
    )


def test_incremental_updates_preserve_overload_docs_after_reordering(
    git_repo, settings, fake_llm
):
    root = settings.project.target_repo
    commit_sources(
        git_repo, root, {"App.kt": "fun parse(x: Int) = x\nfun parse(x: String) = x\n"}
    )
    runner = Runner()
    runner.run()
    before = len(fake_llm)
    (root / "App.kt").write_text(
        "fun parse(x: String) = x\nfun parse(x: Int) = x + 1\n", encoding="utf-8"
    )
    git_repo.index.add(["App.kt"])
    runner.run()
    assert len(fake_llm) == before + 1
    symbols = runner.meta_info.get_all_files()[0].children
    assert set(symbols) == {"parse(Int)", "parse(String)"}
    assert len(symbols["parse(Int)"].md_content) == 2
    assert len(symbols["parse(String)"].md_content) == 1
    assert all(s.item_status == DocItemStatus.doc_up_to_date for s in symbols.values())
    # Deleting a source removes its generated Markdown on the next refresh.
    git_repo.index.commit("Document changed overload")
    git_repo.index.remove(["App.kt"], working_tree=True)
    runner.run()
    assert not (root / settings.project.markdown_docs_name / "App.md").exists()


def test_failed_parse_restores_unstaged_work_through_cli(git_repo, settings, fake_llm):
    from click.testing import CliRunner

    from repo_agent.main import cli

    root = settings.project.target_repo
    path = root / "App.kt"
    path.write_text("fun broken( = {")
    git_repo.index.add(["App.kt"])
    path.write_text('fun userEdit() = "precious"\n')
    result = CliRunner().invoke(
        cli, ["run", "--target-repo-path", str(root), "--source-language", "kotlin"]
    )
    assert result.exit_code != 0
    assert path.read_text() == 'fun userEdit() = "precious"\n'
    assert not (root / ".repoagent-snapshots.json").exists()
    assert not fake_llm
    delete_fake_files()


def test_shared_stems_keep_both_documents_and_ignore_excluded_sources(
    git_repo, settings, fake_llm
):
    root = settings.project.target_repo
    commit_sources(
        git_repo,
        root,
        {
            "App.py": "def python_app(): return 1\n",
            "App.kt": "fun kotlinApp() = 1\n",
            "excluded/Invalid.kt": "fun broken( = {",
        },
    )
    settings.project.ignore_list = ["excluded"]
    runner = Runner()
    runner.run()
    docs = root / settings.project.markdown_docs_name
    assert (docs / "App.md").exists()
    assert (docs / "App.kt.md").exists()
    assert not (docs / "excluded").exists()
