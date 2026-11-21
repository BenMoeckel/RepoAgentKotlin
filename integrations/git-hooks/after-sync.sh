#!/bin/sh
set -eu
repo_root=$(git -C "$(dirname "$0")/.." rev-parse --show-toplevel)
cd "$repo_root"
branch=$(git symbolic-ref --quiet --short HEAD || true)
[ "$branch" = documentation ] || exit 0

# Do not overwrite or stage unrelated existing local changes after a pull.
if ! git diff --quiet || ! git diff --cached --quiet; then
    echo "RepoAgent: lokale Änderungen vorhanden; automatische Doku-Aktualisierung übersprungen." >&2
    echo "Prüfe/sichere die Änderungen und starte danach ./.repoagent/update-docs.sh." >&2
    exit 1
fi

echo "RepoAgent: documentation nach ${1:-Synchronisierung} über Codex aktualisieren ..."
if "$repo_root/.repoagent/update-docs.sh"; then
    echo "RepoAgent: Dokumentation aktualisiert. Änderungen prüfen und separat committen."
else
    echo "RepoAgent: Doku-Aktualisierung fehlgeschlagen; die Git-Übernahme ist bereits abgeschlossen." >&2
    echo "Nach Behebung erneut ./.repoagent/update-docs.sh ausführen." >&2
    exit 1
fi
