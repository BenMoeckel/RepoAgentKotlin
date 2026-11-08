# Python and Kotlin backends

For an illustrated German explanation of the architecture and workflow, see
[RepoAgent verstehen](ARCHITEKTUR_UND_ABLAUF_DE.md).

RepoAgent remains a Python application. It can document Python (`.py`), Kotlin
(`.kt`) and Kotlin scripts (`.kts`) through the same hierarchy, dependency
scheduler, LLM prompts, incremental update process and Markdown renderer.

## Installation and use

From this checkout, with Python 3.11 or newer:

```sh
python -m pip install -e '.[kotlin]'
repoagent run --target-repo-path /path/to/kotlin-repo \
  --source-language kotlin --language German
```

The existing LLM configuration still applies. The target must be a Git repository
with an initial commit. Add new/changed source files to its Git index before
running RepoAgent. Untracked sources are skipped, and analysis uses staged
contents when a file also has unstaged edits.

`--source-language auto` is the default and accepts both backends in a mixed
repository. `--source-language python` restricts discovery to Python and requires
no Kotlin dependencies. `--language` controls the prose language, independently
of the source language.

For PDM development, use `pdm install -G kotlin`.

## Semantic references with Kotlin LSP

Syntax extraction works without a JVM or a language server. To populate caller
and callee relationships, install a Kotlin LSP server separately and provide its
stdio command:

```sh
repoagent run --target-repo-path /path/to/kotlin-repo \
  --source-language kotlin --language German \
  --kotlin-lsp-command 'kotlin-lsp --stdio' \
  --kotlin-lsp-timeout 180
```

See the [official Kotlin LSP installation instructions](https://github.com/Kotlin/kotlin-lsp#install-kotlin-lsp-cli).
The server runs from the target repository root and receives workspace settings
and opened Kotlin source documents. It must advertise `textDocument/references`
and support UTF-16 positions. A supplied command is split into arguments without
running a shell; quote executable paths containing spaces inside the option.

Without the option, RepoAgent logs that Kotlin semantic references are unavailable
and produces documentation from declarations and source code. It does not invent
a call graph through name matching. With an explicitly configured server, startup,
protocol and timeout failures propagate instead of silently dropping references.

The LSP server performs its own project import/indexing. JVM, Gradle/Maven,
Android, multiplatform and compiler-version support depend on that server. The
official server currently describes itself as alpha; verify it against your
actual target project. The tests in this checkout use a deterministic stdio LSP
fixture, not a downloaded JetBrains server.

For commands using environment-based settings, such as `repoagent diff`, set
`TARGET_REPO`, `SOURCE_LANGUAGE`, `KOTLIN_LSP_COMMAND` and optionally
`KOTLIN_LSP_TIMEOUT` before invoking the command. `run` has the explicit options
shown above.

## Output compatibility

The default output locations remain:

- `markdown_docs/`: one Markdown document per source file containing nested
  declaration headings and generated explanations.
- `.project_doc_record/project_hierarchy.json`: the existing file-to-symbol-list
  schema, including code snippets, parameters, generated text and reference lists.
- `.project_doc_record/meta-info.json`: generation checkpoints and source version.

For example, `src/User.kt` generates `markdown_docs/src/User.md`.
`build.gradle.kts` generates `markdown_docs/build.gradle.kts.md`. If a mixed
repository contains both `App.py` and `App.kt` in the same directory, Kotlin uses
`App.kt.md` and Python keeps `App.md`, preserving both documents.

Kotlin symbols add `language`, `kind`, `signature`, `symbol_key`, `symbol_id`,
`parent_id`, exact source positions, receiver and KDoc metadata. Existing common
fields such as `type`, `name`, `params`, `code_content`, `md_content`,
`reference_who` and `who_reference_me` remain available. Interfaces and objects
use the common `ClassDef` category with a more precise `kind`; properties and
type aliases use `PropertyDef` and `TypeAliasDef`.

Overloads have stable signature-based identities, such as `parse(Int)` and
`parse(String)`, which are also shown in Markdown headings. Reordering overloads
does not reassign their documents. Parameter types, receivers and generic
parameters participate in identity. This is a syntax identity, not a
compiler-resolved fully qualified type signature.

## Kotlin coverage and boundaries

The backend extracts classes, interfaces, enum classes, objects, companion
objects, primary-constructor properties, secondary constructors, top-level and
nested functions, extension functions, properties and type aliases. It retains
modifiers such as `suspend` and nullability in the original source text. Existing
KDoc is included in the LLM context. Local variable declarations are excluded.
Enum entries and anonymous initializer blocks are described through their
containing declaration rather than as separate documents. Script statements
outside declarations do not get separate documents, matching the existing
Python declaration-oriented output.

Tree-sitter parses syntax; it does not type-check or execute Kotlin. The bundled
grammar may reject newer Kotlin syntax. A parse error stops generation with the
file path in the log rather than silently omitting a source file. Exclude
unsupported/generated paths using `--ignore-list` when appropriate. `.git`,
`.gradle`, `.kotlin`, `.venv` and `build` directories are excluded during discovery.

The bundled grammar has an implicit-semicolon limitation before some same-line
closing braces. The backend retries using whitespace at parsed brace-token
boundaries and maps every offset back to the unchanged original source. Tests
cover same-line nesting, Unicode, multiline signatures and exact snippets.

Git index snapshots are tracked in `.repoagent-snapshots.json`. Cleanup restores
unstaged files byte-for-byte, including empty files and unstaged deletions, and
runs after successful generation and errors. `repoagent clean` can recover an
interrupted run when configured with the same target repository. Reserved
`*_latest_version.py`, `*_latest_version.kt` and `*_latest_version.kts` backup
paths must remain available during a run.

## Architecture and verification

`repo_agent/backends/base.py` defines the backend protocol. `PythonBackend` uses
Python AST and Jedi. `KotlinBackend` uses the Kotlin grammar bundled in
`tree-sitter-language-pack==0.13.0`, optionally delegating reference lookup to
`KotlinLsp`. The Kotlin dependencies are installed only through the `kotlin`
extra. This pinned pack embeds the grammar, avoiding runtime downloads.

Run the tests without LLM network access:

```sh
python -m pip install -e '.[kotlin]' 'pytest>=7.4.4,<8' 'pytest-mock>=3.12,<4'
python -m pytest -q
```

The suite exercises both parsers, Python Jedi references, LSP framing and errors,
UTF-16 conversion, bidirectional reference graphs, checkpoint round trips, mixed
repositories, overload updates, deleted-source cleanup and snapshot recovery.
LLM requests are replaced by a local fake in pipeline tests.

## Tool research

The implementation was informed by these upstream sources:

- [Tree-sitter Kotlin](https://github.com/tree-sitter-grammars/tree-sitter-kotlin):
  dedicated Kotlin syntax parser, compared against declaration fixtures.
- [tree-sitter-language-pack 0.13.0](https://pypi.org/project/tree-sitter-language-pack/0.13.0/):
  bundled grammars and Python bindings, selected for reproducible offline parsing.
- [Official Kotlin LSP](https://github.com/Kotlin/kotlin-lsp): optional semantic
  analysis; [stdio setup](https://github.com/Kotlin/kotlin-lsp/blob/main/scripts/neovim.md).
- [fwcd Kotlin Language Server](https://github.com/fwcd/kotlin-language-server):
  its README now marks it deprecated in favor of the official server.
