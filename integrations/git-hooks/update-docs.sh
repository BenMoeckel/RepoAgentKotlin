#!/bin/sh
# Run from any working directory; paths come from local Git configuration.
set -eu
repo_root=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)
cd "$repo_root"

repoagent_executable=$(git config --get repoagent.executable || true)
if [ -z "$repoagent_executable" ]; then
    repoagent_executable=$(command -v repoagent || true)
fi
if [ -z "$repoagent_executable" ] || [ ! -x "$repoagent_executable" ]; then
    echo "RepoAgent fehlt. Siehe .repoagent/README.md zur lokalen Einrichtung." >&2
    exit 1
fi
codex_executable=$(git config --get repoagent.codex || true)
if [ -z "$codex_executable" ]; then
    codex_executable=$(command -v codex || true)
fi
if [ -z "$codex_executable" ] || [ ! -x "$codex_executable" ]; then
    echo "Codex CLI fehlt. Installiere Codex und melde dich mit 'codex login' an." >&2
    exit 1
fi

lock_path=$(git rev-parse --path-format=absolute --git-path repoagent-run.lock)
if ! mkdir "$lock_path" 2>/dev/null; then
    echo "RepoAgent läuft bereits (Sperre: $lock_path)." >&2
    echo "Bei abgebrochenem Lauf zuerst den Prozess prüfen und dann die leere Sperre entfernen." >&2
    exit 1
fi
trap 'rmdir "$lock_path" 2>/dev/null || true' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

workers=$(git config --get repoagent.workers || true)
workers=${workers:-1}
timeout_seconds=$(git config --get repoagent.timeout || true)
timeout_seconds=${timeout_seconds:-300}
"$repoagent_executable" run \
    --target-repo-path "$repo_root" \
    --source-language kotlin \
    --language German \
    --llm-provider codex \
    --codex-command "$codex_executable" \
    --codex-timeout "$timeout_seconds" \
    --max-thread-count "$workers"

# Include both changed documents and deletions, but no unrelated working files.
git add -A -- markdown_docs .project_doc_record
