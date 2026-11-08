import json
import shlex
import sys
from pathlib import Path

import pytest

from repo_agent.backends.kotlin import KotlinBackend
from repo_agent.backends.lsp import KotlinLsp
from repo_agent.doc_meta_info import MetaInfo
from repo_agent.file_handler import FileHandler


@pytest.fixture
def server_command():
    fixture = Path(__file__).parent / "fixtures/kotlin_lsp_stub.py"

    def make(**config):
        return shlex.join([sys.executable, str(fixture), json.dumps(config)])

    return make


def test_stdio_protocol_and_utf16_positions(settings, server_command):
    root = settings.project.target_repo
    source = 'fun outer() { val face = "😀"; fun target() = 1 }\n'
    path = root / "Source with spaces.kt"
    path.write_text(source, encoding="utf-8")
    symbol = next(s for s in KotlinBackend().parse(source) if s["name"] == "target")
    prefix = source[: source.index("target")]
    utf16_column = len(prefix.encode("utf-16-le")) // 2
    command = server_command(
        expected_position={"line": 0, "character": utf16_column},
        locations=[
            {
                "uri": path.as_uri(),
                "range": {
                    "start": {"line": 0, "character": utf16_column},
                    "end": {"line": 0, "character": utf16_column + 6},
                },
            },
            {"uri": "jrt:/stdlib", "range": {}},
        ],
    )
    with KotlinLsp(command, root, timeout=2) as lsp:
        assert lsp.references(path.name, symbol) == [
            (path.name, 1, symbol["name_column"])
        ]
    assert lsp.process.poll() is not None


def test_lsp_references_build_bidirectional_graph(git_repo, settings, server_command):
    root = settings.project.target_repo
    path = root / "App.kt"
    path.write_text("fun callee() = 1\nfun caller() = callee()\n")
    git_repo.index.add([path.name])
    settings.project.kotlin_lsp_command = server_command()
    info = MetaInfo.init_meta_info({}, [])
    info.parse_reference()
    symbols = info.get_all_files()[0].children
    callee, caller = symbols["callee()"], symbols["caller()"]
    assert caller.reference_who == [callee]
    assert callee.who_reference_me == [caller]
    info.parse_reference()  # Rebuilding does not accumulate duplicate edges.
    assert caller.reference_who == [callee]
    payload = info.to_hierarchy_json(flash_reference_relation=True)
    restored = MetaInfo.from_project_hierarchy_json(payload)
    assert restored.get_all_files()[0].children[
        "callee()"
    ].who_reference_me_name_list == ["App.kt/caller()"]


@pytest.mark.parametrize(
    "configuration, exception",
    [
        ({"supports_references": False}, RuntimeError),
        ({"error": True}, RuntimeError),
        ({"ignore_references": True}, TimeoutError),
    ],
)
def test_lsp_failures_are_visible_and_processes_close(
    settings, server_command, configuration, exception
):
    root = settings.project.target_repo
    path = root / "App.kt"
    path.write_text("fun callee() = 1\n")
    lsp = KotlinLsp(server_command(**configuration), root, timeout=0.2)
    with pytest.raises(exception):
        with lsp:
            lsp.references(path.name, KotlinBackend().parse(path.read_text())[0])
    assert lsp.process.poll() is not None
