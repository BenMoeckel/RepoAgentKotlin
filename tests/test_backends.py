import pytest

from repo_agent.backends import get_backend
from repo_agent.backends.kotlin import KotlinBackend
from repo_agent.backends.python import PythonBackend

KOTLIN = """package demo
/** Represents a user. */
data class User(val name: String, var age: Int = 1) {
    companion object { val DEFAULT = User("Guest") }
    class Nested
    fun greet(value: String): String = value + name
    fun greet(value: Int): Int = value
}
interface Api { suspend fun load(id: Int): User? }
object Service { fun get() = 42 }
fun String.greet(prefix: String = "Hi"): String = prefix + this
val count: Int get() = 4
typealias Users = List<User>
fun outer() { val local = 1; fun inner() = local }
"""


def test_python_schema_and_async():
    source = "class A:\n    async def load(self, value):\n        return value\n"
    symbols = PythonBackend().parse(source)
    assert [s["type"] for s in symbols] == ["ClassDef", "AsyncFunctionDef"]
    assert symbols[1]["params"] == ["self", "value"]
    assert symbols[1]["code_content"] == source[source.index("    async") :]
    assert symbols[1]["have_return"] is True
    assert get_backend("x.py").language == "python"
    assert get_backend("x.kts").language == "kotlin"
    with pytest.raises(ValueError):
        get_backend("x.java")


def test_kotlin_declarations_and_exact_original_ranges():
    symbols = KotlinBackend().parse(KOTLIN)
    by_id = {s["symbol_id"]: s for s in symbols}
    assert {
        "User",
        "User/name",
        "User/age",
        "User/Companion",
        "User/Companion/DEFAULT",
        "User/Nested",
        "User/greet(String)",
        "User/greet(Int)",
        "Api/load(Int)",
        "Service/get()",
        "String.greet(String)",
        "count",
        "Users",
        "outer()/inner()",
    } <= by_id.keys()
    assert "outer()/local" not in by_id
    assert by_id["Api"]["kind"] == "Interface"
    assert by_id["Service"]["kind"] == "Object"
    assert by_id["count"]["type"] == "PropertyDef"
    assert by_id["Users"]["type"] == "TypeAliasDef"
    assert by_id["User"]["params"] == ["name", "age"]
    assert by_id["User"]["kdoc"] == "/** Represents a user. */"
    assert by_id["String.greet(String)"]["receiver"] == "String"
    for symbol in symbols:
        expected = KOTLIN.encode()[
            symbol["code_start_byte"] : symbol["code_end_byte"]
        ].decode()
        assert symbol["code_content"].endswith(expected)
        assert (
            symbol["code_start_line"]
            == KOTLIN[
                : len(KOTLIN.encode()[: symbol["code_start_byte"]].decode())
            ].count("\n")
            + 1
        )


def test_overload_ids_do_not_depend_on_declaration_order():
    backend = KotlinBackend()
    one = "fun parse(value: String) = value\n"
    two = "fun parse(value: Int) = value\n"
    assert (
        {s["symbol_id"] for s in backend.parse(one + two)}
        == {s["symbol_id"] for s in backend.parse(two + one)}
        == {"parse(String)", "parse(Int)"}
    )


def test_multiline_unicode_backticks_and_same_line_nesting():
    source = """/** Dokumentation */
class Grüße { companion object { fun `say hi`(
    value: String?
): String? = value } }
"""
    symbols = KotlinBackend().parse(source)
    method = next(s for s in symbols if s["name"] == "say hi")
    assert method["name_line"] == 2
    assert method["code_end_line"] == 4
    assert method["params"] == ["value"]
    assert method["have_return"]
    assert method["parent_id"].endswith("/Companion")
    assert source.splitlines()[method["name_line"] - 1][
        method["name_column"] :
    ].startswith("`say hi`")


def test_invalid_kotlin_fails_instead_of_silently_skipping_file():
    with pytest.raises(ValueError, match="Kotlin syntax"):
        KotlinBackend().parse("fun broken( = {")


def test_vararg_overloads_and_script_lambdas():
    source = """plugins { kotlin("jvm") version "2.1.0" }
fun parse(value: Int) = value
fun parse(vararg value: Int) = value.size
val task = { val local = 1; local }
"""
    symbols = KotlinBackend().parse(source)
    assert {s["symbol_key"] for s in symbols} == {
        "parse(Int)",
        "parse(vararg Int)",
        "task",
    }


def test_python_jedi_references(settings):
    root = settings.project.target_repo
    path = root / "helpers.py"
    source = "def callee():\n    return 1\n\ndef caller():\n    return callee()\n"
    path.write_text(source)
    backend = PythonBackend()
    callee = backend.parse(source)[0]
    assert (path.name, 5, 11) in backend.references(
        root, path.name, callee, in_file_only=True
    )


def test_python_does_not_require_optional_kotlin_dependencies(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "tree_sitter_language_pack", None)
    assert get_backend("helpers.py").parse("def helper(): pass")[0]["name"] == "helper"
    with pytest.raises(RuntimeError, match=r"repoagent\[kotlin\]"):
        get_backend("App.kt")
