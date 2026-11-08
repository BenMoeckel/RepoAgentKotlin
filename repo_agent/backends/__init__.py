"""Language-specific source analysis, shared by discovery and documentation."""

from pathlib import Path

from repo_agent.backends.base import LanguageBackend
from repo_agent.backends.python import PythonBackend


def get_backend(file_path, kotlin_lsp=None) -> LanguageBackend:
    suffix = Path(file_path).suffix
    if suffix == ".py":
        return PythonBackend()
    if suffix in {".kt", ".kts"}:
        from repo_agent.backends.kotlin import KotlinBackend

        return KotlinBackend(kotlin_lsp)
    raise ValueError(f"Unsupported source file: {file_path}")


def source_extensions():
    from repo_agent.settings import SettingsManager

    language = SettingsManager.get_setting().project.source_language
    return {
        "python": (".py",),
        "kotlin": (".kt", ".kts"),
        "auto": (".py", ".kt", ".kts"),
    }[language]


def is_source_file(file_path):
    return str(file_path).endswith(source_extensions())


def markdown_path(file_path, source_files=()):
    # Retain the traditional Python path, disambiguate Kotlin script/source pairs.
    path = Path(file_path)
    suffix = ".kts.md" if path.suffix == ".kts" else ".md"
    if path.suffix == ".kt" and path.with_suffix(".py").as_posix() in source_files:
        suffix = ".kt.md"
    return path.with_suffix(suffix)
