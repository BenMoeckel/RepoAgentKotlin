# Anweisungen für Agenten

## Verbindliches Arbeitsprotokoll

Dieses Projekt wird im Rahmen einer wissenschaftlichen Arbeit entwickelt. Alle
Agenten müssen Benutzerprompts und die daraufhin ausgeführten Arbeiten in
[`docs/ARBEITSPROTOKOLL.md`](docs/ARBEITSPROTOKOLL.md) nachvollziehbar dokumentieren.

- Lies vor Beginn einer Aufgabe das vorhandene Arbeitsprotokoll.
- Lege für jeden neuen Benutzerprompt einen fortlaufend nummerierten Eintrag an,
  auch bei reinen Erklärungen, Rückfragen, Korrekturen oder abgebrochenen Aufgaben.
  Ergänzende Prompts während einer Aufgabe erhalten ebenfalls einen eigenen Eintrag;
  zusammengehörige Einträge werden gegenseitig referenziert.
- Erfasse das Datum im Format `YYYY-MM-DD` mit Zeitzone `Europe/Berlin`. Wenn eine
  Uhrzeit erfasst wird, muss sie tatsächlich ermittelt worden sein.
- Übernimm den Benutzerprompt möglichst wortgetreu als Zitat. Geheimnisse wie
  API-Schlüssel, Passwörter und Tokens müssen durch `[REDAKTIERT]` ersetzt werden;
  kennzeichne sonstige notwendige Kürzungen oder Auslassungen ausdrücklich.
- Halte Ziel, tatsächlich ausgeführte Schritte, betroffene Dateien, Ergebnisse,
  Prüfungen und offene Punkte fest. Dokumentiere auch relevante Fehler,
  Einschränkungen und Entscheidungen mit ihrer Begründung.
- Unterscheide geplante Arbeiten von tatsächlich erledigten Arbeiten. Eine
  Erklärung oder vorgeschlagene Installation darf nicht als ausgeführte
  Einrichtung erscheinen. Testergebnisse dürfen nur als selbst geprüft gelten,
  wenn die Tests tatsächlich ausgeführt wurden; sonst die Quelle nennen.
- Erstelle oder beginne den Eintrag vor der Arbeit und vervollständige ihn vor der
  abschließenden Antwort. Bei Unterbrechungen bleibt der Status ausdrücklich offen.
- Protokolliere wesentliche Tätigkeiten während der Bearbeitung zeitnah. Verweise
  bei umfangreichen Ergebnissen auf Dateien und gegebenenfalls Commit-IDs.
- Ergänze frühere Ereignisse nur mit Quellenangabe und Kennzeichnung als
  nachträgliche Rekonstruktion. Unbekannte Prompts, Daten oder Abläufe dürfen
  nicht erfunden werden. Commit-Datum, Erfassungsdatum und tatsächliches
  Ereignisdatum sind bei Bedarf getrennt anzugeben.
- Führe das Protokoll chronologisch und ergänzend weiter. Frühere Einträge nicht
  stillschweigend überschreiben; sachliche Berichtigungen als datierten Nachtrag
  mit Bezug auf den ursprünglichen Eintrag dokumentieren.

Vorlage für neue Einträge:

```markdown
## NNN – Kurztitel

- Datum: YYYY-MM-DD (Europe/Berlin)
- Status: begonnen / abgeschlossen / unterbrochen
- Art: zeitnah protokolliert / nachträglich rekonstruiert

### Benutzerprompt

> Wortlaut des Prompts; notwendige Redaktionen ausdrücklich kennzeichnen.

### Ziel und ausgeführte Arbeiten

- ...

### Ergebnis und betroffene Dateien

- ...

### Prüfungen, Quellen und offene Punkte

- ...
```
