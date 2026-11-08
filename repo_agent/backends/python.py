"""Python AST extraction and Jedi reference analysis."""

import ast
import os

import jedi


class PythonBackend:
    language = "python"

    def parse(self, source):
        tree = ast.parse(source)
        lines = source.splitlines(keepends=True)
        symbols = []
        for node in ast.walk(tree):
            if not isinstance(
                node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                continue
            end = node.end_lineno or node.lineno
            code = "".join(lines[node.lineno - 1 : end])
            symbols.append(
                {
                    "type": type(node).__name__,
                    "name": node.name,
                    "code_start_line": node.lineno,
                    "code_end_line": end,
                    "params": [a.arg for a in node.args.args]
                    if hasattr(node, "args")
                    else [],
                    "md_content": [],
                    "code_content": code,
                    "name_column": lines[node.lineno - 1].find(node.name),
                    "have_return": "return" in code,
                }
            )
        return symbols

    def references(self, repo_path, file_path, symbol, in_file_only=False):
        script = jedi.Script(path=os.path.join(repo_path, file_path))
        kwargs = {"scope": "file"} if in_file_only else {}
        line, column = symbol["code_start_line"], symbol["name_column"]
        return [
            (os.path.relpath(ref.module_path, repo_path), ref.line, ref.column)
            for ref in script.get_references(line=line, column=column, **kwargs)
            if ref.module_path
            and ref.name == symbol["name"]
            and not (
                ref.line == line
                and ref.column == column
                and os.path.relpath(ref.module_path, repo_path) == file_path
            )
        ]
