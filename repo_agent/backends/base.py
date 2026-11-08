"""Backend contract. Positions are one-based lines and zero-based characters."""

from typing import Protocol


class LanguageBackend(Protocol):
    language: str

    def parse(self, source: str) -> list[dict]:
        """Return JSON-serializable symbols in the common hierarchy schema."""
        ...

    def references(self, repo_path, file_path, symbol, in_file_only=False):
        """Return (relative source path, line, column) reference locations."""
        ...
