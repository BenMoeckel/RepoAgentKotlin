# Dokumentation mit Codex und ChatGPT-Abonnement

RepoAgent kann die offizielle Codex CLI für seine Erklärungstexte verwenden.
Die Kotlin-/Python-Parser, Referenzanalyse und Markdown-Ausgabe bleiben dieselben.
Für `--llm-provider codex` ist kein `OPENAI_API_KEY` erforderlich.

## Voraussetzungen

- RepoAgent aus diesem Checkout installieren, für Kotlin mit
  `python -m pip install -e '.[kotlin]'`.
- Eine aktuelle [Codex CLI](https://developers.openai.com/codex/cli) installieren.
  Die Integration verwendet unter anderem `--ignore-user-config`, `--ephemeral`
  und `--output-last-message`. Lokal wurde Version `0.170.0` geprüft.
- `codex login` ausführen und mit ChatGPT anmelden. Mit `codex login status`
  prüfen: Die Ausgabe muss `Logged in using ChatGPT` enthalten.
- Das Zielprojekt muss ein Git-Repository mit einem ersten Commit sein.
  Neue/geänderte Quellen vor dem Lauf im Zielrepository gezielt mit `git add`
  vormerken. RepoAgent analysiert den Git-Index.

## Zuege-von-Hanoi dokumentieren

Aus dem RepoAgent-Verzeichnis, mit aktivierter Python-Umgebung und dem bereits
vorhandenen Nachbar-Checkout:

```sh
source .venv/bin/activate
repoagent run \
  --target-repo-path ../Zuege-von-Hanoi \
  --source-language kotlin \
  --language German \
  --llm-provider codex
```

Die Ergebnisse entstehen im Zielrepository unter `markdown_docs/` und
`.project_doc_record/`. Kotlin-Dateien unter `Client`, `Server` und `Twin` werden
unabhängig davon gefunden, ob sie in `src/main/kotlin` oder `src/main/java` liegen.
Java-Dateien werden von diesem Fork nicht dokumentiert. Freie Anweisungen in
Gradle-Kotlin-Skripten erhalten keine eigenen Dokumentationsabschnitte.

Der aufrufende Prozess benötigt Schreibzugriff auf das Zielrepository.
In einer eingeschränkten Codex-Sitzung kann dafür eine Schreibfreigabe nötig sein.
Die oben stehenden Befehle können auch direkt im eigenen Terminal ausgeführt werden.

## Einstellungen

| Option | Bedeutung |
|---|---|
| `--llm-provider codex` | Codex mit bestehendem ChatGPT-Login verwenden |
| `--codex-command /pfad/zu/codex` | Einzelner ausführbarer Pfad, ohne Shell-Argumente |
| `--codex-timeout 300` | Maximale Laufzeit je Erklärung in Sekunden, Standard 180 |
| `--model MODELLNAME` | Optionales Codex-Modell; sonst CLI-Standardmodell |
| `--max-thread-count 1` | Ein Symbol nach dem anderen; Standard für Codex |
| `--ignore-list Client,Server` | Beispielsweise nur den Bereich `Twin` dokumentieren |

`--temperature`, `--request-timeout` und `--base-url` konfigurieren den API-Anbieter
und werden für Codex nicht verwendet. `--kotlin-lsp-command` lässt sich unabhängig
vom Textanbieter ergänzen; siehe [Kotlin-Anleitung](KOTLIN_BACKEND.md).

Für Befehle mit Umgebungsvariablen, beispielsweise `repoagent diff`:

```sh
export LLM_PROVIDER=codex
export TARGET_REPO="/absoluter/pfad/zu/Zuege-von-Hanoi"
export SOURCE_LANGUAGE=kotlin
repoagent diff
```

`CODEX_COMMAND` und `CODEX_TIMEOUT` sind ebenfalls als Umgebungsvariablen nutzbar.

## Automatische Updates nach einem Pull aus develop

Mit `scripts/install_git_hooks.py` lassen sich lokale Git-Hooks installieren.
Sie konfigurieren `documentation` so, dass `git pull` Änderungen aus
`origin/develop` übernimmt. Nach erfolgreichen Merge-/Fast-forward-Übernahmen oder
einem Rebase mit umgeschriebenen Commits wird die Dokumentation auf `documentation`
inkrementell aktualisiert. Normale Commits und `amend` lösen keinen Lauf aus.
Bei einem bereits aktuellen Pull ohne Übernahme ist keine Generierung erforderlich.
Die erzeugten Dateien werden gestagt und anschließend separat geprüft und committed.
Konfiguration und manuelles Update-Skript
werden unter `.githooks/` und `.repoagent/` im Zielprojekt abgelegt; persönliche
Programmpfade bleiben in `.git/config`. Die Installation überschreibt keine
vorhandenen fremden Hooks. Mit `--migrate` kann der frühere RepoAgent-Commit-Hook
gesichert und deaktiviert werden. Details und Team-Einrichtung stehen in der
[Hook-Anleitung](../integrations/git-hooks/README.md).

## Ablauf und Fehlerbehandlung

RepoAgent prüft den ChatGPT-Login vor der Analyse. Für jedes zu dokumentierende
Symbol sendet es den vorhandenen Dokumentationsprompt über stdin an einen neuen
`codex exec`-Prozess. Dieser läuft in einem temporären Arbeitsverzeichnis mit
Read-only-Sandbox. Shell-Werkzeuge sind deaktiviert; der Prompt fordert reine
Textgenerierung. Der Prozess erhält keinen Schreibzugriff auf das Zielrepository.
RepoAgent liest nur die finale Antwort aus einer eigenen temporären Ausgabedatei.

Die Integration lädt nicht die persönliche Codex-Konfigurationsdatei; deren
Modellwahl, MCP-Server und Hooks werden daher nicht übernommen. Die vorhandene
Codex-Anmeldung bleibt verfügbar. Ein Modell kann explizit über `--model` gewählt
werden. Der ChatGPT-Login und der OpenAI-Modellanbieter werden für die Generierung
explizit vorgegeben. API-Schlüssel- und Access-Token-Overrides werden aus der
Prozessumgebung entfernt. Es gibt keinen automatischen Rückfall auf die API.

Fehlender Login, fehlende CLI, Timeout, Prozessfehler oder leere Antwort führen zu
einem Fehler. Nach einem Codex-Fehler werden keine weiteren Aufgaben gestartet;
bereits laufende Anfragen dürfen noch enden. Bei teilweise fehlgeschlagenen
Generierungen wird ein Wiederaufnahme-
Checkpoint gespeichert und der Befehl endet mit einem Fehlerstatus. Derselbe Aufruf
kann nach Behebung des Anbieterproblems wiederholt werden; dabei den zugrunde
liegenden Quellstand für die Wiederaufnahme beibehalten. Bereits generierte Texte
bleiben in den Metadaten gespeichert. Rohdiagnosen der CLI werden nicht als
Dokumentation gespeichert.

Die Nutzung unterliegt den Codex-Limits deines ChatGPT-Plans. Ein kompletter Lauf
über viele Symbole kann diese Limits beanspruchen; bei Limits wird kein anderer
Bezahlzugang verwendet. Diese Integration betrifft `repoagent run`; der separate
Chat-with-Repo-Prototyp und dessen Embeddings bleiben API-basiert.

## Quellen

- [Codex-Anmeldung](https://developers.openai.com/codex/auth)
- [Nichtinteraktive Codex-Aufrufe](https://developers.openai.com/codex/noninteractive)

Beide Quellen wurden am 2026-11-19 für die Integration geprüft.
