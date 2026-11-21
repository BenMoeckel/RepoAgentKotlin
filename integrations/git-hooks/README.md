# Develop übernehmen und Dokumentation nach dem Pull aktualisieren

Der Branch `documentation` übernimmt mit `git pull` die Änderungen aus
`origin/develop`. Danach wird die Kotlin-Dokumentation lokal über RepoAgent und
den vorhandenen ChatGPT-/Codex-Login aktualisiert. Normale Commits lösen keine
Generierung aus. Die Automatik ist auf den lokalen Branch `documentation` begrenzt.

## Einmalig auf diesem Rechner

Der Installer richtet diese lokalen Einstellungen ein:

```ini
[core]
    hooksPath = .githooks
[branch "documentation"]
    remote = origin
    merge = refs/heads/develop
    rebase = false
```

Persönliche Programmpfade und Timeouts liegen ebenfalls nur in `.git/config`.
Der lokale Branch `develop` wird durch diesen Ablauf nicht verändert: Die Quelle
ist der gefetchte Serverstand `origin/develop`. Neue Entwicklungen müssen deshalb
zuerst nach `origin/develop` gepusht worden sein.

## Regelmäßiger Ablauf

Nach Einrichtung zunächst die vorhandenen generierten Dokumente, Metadaten und
Hook-Dateien prüfen und committen. Für einen Pull benötigt Git einen geeigneten,
in diesem Workflow sauberen Arbeitsstand.

```sh
git switch documentation
git pull
# RepoAgent aktualisiert danach automatisch die betroffenen Dokumentationsabschnitte.
git diff --cached
# Bei passenden Ergebnissen separat committen:
git commit -m "docs: Dokumentation an develop anpassen"
git push origin HEAD:documentation
```

Der letzte Push-Befehl nennt das Ziel ausdrücklich, weil der Pull-Upstream
`origin/develop` heißt. Ein gewöhnliches `git push` kann bei Gits Standard
`push.default=simple` wegen der unterschiedlichen Branchnamen abgelehnt werden.
Es wird kein automatischer Push und kein automatischer Dokumentationscommit erzeugt.

## Welche Hooks laufen?

- `.githooks/post-merge` reagiert auf erfolgreiche Merge- und Fast-forward-
  Übernahmen, wie sie `git pull` mit der eingerichteten Einstellung ausführt.
- `.githooks/post-rewrite` reagiert zusätzlich auf einen Pull mit Rebase, wenn
  Commits tatsächlich umgeschrieben wurden. `commit --amend` wird ignoriert.
- Beide rufen `.repoagent/after-sync.sh` auf. Es führt ausschließlich auf
  `documentation` und bei sauberem Index/Arbeitsbaum das Update-Skript aus.
- `.repoagent/update-docs.sh` erzeugt die Dokumentation und nimmt ausschließlich
  generierte Markdown-Dateien und Metadaten in die Staging Area auf.

Git besitzt keinen eigenen `post-pull`-Hook. Bei einem bereits aktuellen Pull
ohne Übernahme wird nichts neu generiert. Änderungen allein auf GitHub starten
keinen lokalen Prozess; übernommen werden sie erst bei deinem Pull.
Bei Konflikten wird vor deren erfolgreicher Auflösung keine Doku erzeugt.
Ein fehlgeschlagener Dokumentationslauf kann einen bereits erfolgreichen Pull
nicht zurückrollen. Die Fehlermeldung zeigt dann die notwendige Wiederaufnahme an.

Manuell aktualisieren oder nach Anbieterfehlern erneut versuchen:

```sh
./.repoagent/update-docs.sh
```

Die Ausgaben stehen unter `markdown_docs/`, die Checkpoints unter
`.project_doc_record/`. Beide Verzeichnisse gemeinsam versionieren. Eigene
handgeschriebene Dokumente außerhalb des generierten Ausgabeordners pflegen.
Das Werkzeug analysiert den Git-Index und erhält weitere ungestagte Quelländerungen.
Bei Wiederaufnahme nach einem neuen Quellcommit werden gespeicherte Texte mit
aktuellem Code abgeglichen. Ungetrackte Quellen benötigen zuerst `git add`.

## Installation auf weiteren Rechnern

Diese Dateien zusammen mit dem Branch committen: `.githooks/post-merge`,
`.githooks/post-rewrite`, `.repoagent/after-sync.sh`, `.repoagent/update-docs.sh`
und diese Anleitung. Git aktiviert sie nach einem Clone nicht automatisch.
Jede Person benötigt RepoAgent mit Kotlin-Unterstützung, eine aktuelle Codex CLI
und einen eigenen ChatGPT-Login. Aktivierung und lokale Pfade:

```sh
codex login
git config --local repoagent.executable "/absoluter/pfad/zum/RepoAgent/.venv/bin/repoagent"
git config --local repoagent.codex "/absoluter/pfad/zu/codex"
git config --local core.hooksPath .githooks
git config --local branch.documentation.remote origin
git config --local branch.documentation.merge refs/heads/develop
git config --local branch.documentation.rebase false
```

Vorhandene Hooks vor der Einrichtung prüfen. Der Installer überschreibt fremde
Hooks nicht. Bei Migration des alten RepoAgent-Pre-commit-Hooks wird dieser als
`pre-commit.disabled` erhalten und eine Sicherung unter `.git/repoagent-hook-backups/`
angelegt. Er wird nicht mehr ausgeführt.

Standardmäßig läuft ein Codex-Prozess gleichzeitig. Anzahl und Wartezeit sind
mit `git config --local repoagent.workers 2` beziehungsweise
`git config --local repoagent.timeout 900` konfigurierbar (Timeout-Standard 300 s).
Eine Sperre unter `.git/repoagent-run.lock` verhindert parallele Generierungen.
Eine verwaiste Sperre erst entfernen, wenn kein Lauf mehr aktiv ist.

Codex-Limits des ChatGPT-Plans gelten weiterhin; es gibt keinen automatischen
API-Fallback. Java-Dateien werden nicht dokumentiert. Kotlin-LSP-Referenzen
stehen nur mit einem separat konfigurierten Language Server zur Verfügung.

Zum Deaktivieren `git config --local --unset core.hooksPath` ausführen, sofern
diese Einstellung ausschließlich für diese Automatik eingerichtet wurde.
