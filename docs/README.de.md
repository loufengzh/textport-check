# textport-check

Dieselben Bytes, mehrere Verbraucher, unterschiedliche Ergebnisse. Das schreibgeschützte CLI prüft Kodierung gegen ausdrücklich gewählte Verbraucherprofile und zeigt widersprüchliche Anforderungen. Keine Änderungen, keine Vermutung alter Kodierungen, keine Quelltextvorschau, keine Ausführung geprüfter Skripte.

[English](../README.md) · [简体中文](README.zh-CN.md) · [Русский](README.ru.md)

Ein mehrsprachiges Windows-PowerShell-5.1-Skript benötigt für portable Interpretation unabhängig von alten Codepages ein UTF-8-BOM. Ein direkt gestartetes Unix-Skript benötigt `#!` ab Byte null. „Alle BOMs entfernen“ kann beide Anforderungen nicht ausdrücken. Reines ASCII benötigt kein BOM.

## Installation

Python 3.10+, keine Laufzeitabhängigkeiten. Installation aus diesem Repository; keine behauptete PyPI-Veröffentlichung:

```sh
python -m pip install .
textport-check --profile powershell51-script --profile utf8-no-bom examples/greeting.ps1
textport-check --config examples/textport.json --format json
```

Das erste Beispiel liefert absichtlich Exitcode 1 und Konflikt `TPC400`. Separate Artefakte oder ein anderer Verbrauchervertrag können helfen; automatische Konvertierung gibt es nicht.

## Profile und Grenzen

- `powershell51-script`: ASCII und gültiges UTF-8 mit BOM bestehen die Byteprüfung. Nicht-ASCII-UTF-8 ohne BOM ist unter üblichen alten ANSI-Codepages nicht portabel und deshalb inkompatibel mit diesem Vertrag. Auf Systemen mit UTF-8-Codepage kann das Verhalten anders sein. Ungültiges UTF-8 ohne BOM bleibt unbekannt. UTF-16/32-LE/BE-BOMs werden erkannt und streng validiert, ihre Skriptverarbeitung ist aber nicht zertifiziert: unbekannt. Dekodiertes NUL bleibt ebenfalls unbekannt.
- `posix-direct-script`: kein BOM, `#!` ab Byte null, nichtleere ASCII-Interpreterzeile mit LF, ASCII/UTF-8-Inhalt ohne NUL. BOM, fehlendes shebang oder CR in der ersten Zeile sind inkompatibel. Nicht-ASCII/fehlendes LF in der Interpreterzeile, NUL und Nicht-UTF-8-Inhalt bleiben unbekannt. Ein geeigneter Interpreter kann andere Inhaltskodierungen erlauben.
- `utf8-no-bom`: ein ausdrücklich gesetzter Projektvertrag für gültiges UTF-8 ohne BOM, einschließlich leerer Dateien und NUL. Keine Behauptung, dass jedes Textformat BOM verbietet.

Kompatibel bedeutet nur, dass diese Byteprüfungen bestanden wurden. Syntax, Sicherheit, Interpreterpfad, Ausführungsrechte, shebang-Argumente/Längen und Laufzeiterfolg werden nicht garantiert. Direkte Ausführung ist weder `sh file` noch Shell-Fallback. Das Profil ist ein konservativer Portabilitätsvertrag, keine Spezifikation jeder POSIX-Implementierung.

UTF-32-Signaturen werden vor überlappenden UTF-16-Signaturen geprüft; unvollständige Signaturen werden nicht erraten. Byteoffsets beginnen bei null und schließen das BOM ein. NUL-Bytes und dekodiertes NUL werden getrennt erfasst.

## Eingabe und Bericht

```json
{"version":1,"files":[{"path":"greeting.ps1","profiles":["powershell51-script","utf8-no-bom"]}]}
```

CLI-Dateien sind relativ zu `--root` (standardmäßig aktuelles Verzeichnis), Konfigurationspfade relativ zum Konfigurationsverzeichnis. Die Eingabemodi dürfen nicht gemischt werden. Nur explizite Dateien, keine Globs, Rekursion, Ausschlüsse oder Umgebungsvariablen-Erweiterung. Doppelte normalisierte Pfade führen Profile zusammen; Ausgabe wird deterministisch sortiert. Exakte Konfigurationsschlüssel sind Pflicht; doppelte JSON-Schlüssel werden abgelehnt. Konfiguration maximal 1 MiB/10.000 Einträge. Datei maximal 1 MiB standardmäßig; `--max-bytes`: 1–67.108.864.

Absolute Pfade, Elternverzeichniswechsel, Windows-Laufwerks-/Wurzelpfade, Doppelpunkte, Symlinks, Reparse Points und nichtreguläre Dateien werden abgelehnt. Leerzeichen und mehrsprachige Namen funktionieren. Vor Namen mit `-` steht `--`. POSIX durchläuft jede Komponente über Deskriptoren ohne Linkverfolgung. Windows prüft punktuell: kein Sandbox-Schutz gegen bösartige gleichzeitige Verzeichnisänderungen. Eine stabile Arbeitskopie verwenden; gleichzeitige Dateiänderungen ergeben keinen konsistenten Snapshot.

Die Einschränkungen für relative Pfade gelten für die Einträge der geprüften Dateien. `--root` und `--config` dürfen absolute Pfade oder `..` enthalten, etwa `--root ..` und `--config ../textport.json`. Jede ursprüngliche Verzeichniskomponente wird geprüft: Ein Link, ein fehlendes Verzeichnis oder eine reguläre Datei vor `..` wird abgelehnt, statt durch Normalisierung ein anderes Ziel auszuwählen. Der Wechsel zum Elternverzeichnis eines vorhandenen normalen Verzeichnisses bleibt unterstützt.

JSON-Schema 1 enthält `files`, `facts`, `results`, `conflicts`, `error`, `summary`, `exit_code`. Maschinenschlüssel und Diagnosen bleiben englisch. Keine Quelltextvorschau und keine absolute Wurzel, aber relative Namen und Byteinformationen können vertraulich sein. Steuerzeichen in Dateinamen werden maskiert. Die Zusammenfassung zählt Verbraucherergebnisse plus ein unbekanntes Ergebnis je nicht lesbarer Datei.

Exitcodes: 0 alles kompatibel; 1 inkompatibel ohne unbekannte Ergebnisse; 2 Argument-/Konfigurationsfehler (stderr, kein Teil-JSON); 3 unbekannt oder unvollständig gelesen, auch bei gleichzeitiger Inkompatibilität. Konflikthinweise ändern den Code nicht eigenständig. [Stabile Diagnose-IDs](diagnostics.md).

## Quellen und Entwicklung

[Microsoft](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1), [Linux execve](https://man7.org/linux/man-pages/man2/execve.2.html), [Unicode BOM FAQ](https://www.unicode.org/faq/utf_bom.html). Linux belegt nicht jedes Unix. Die Verbrauchermatrix ergänzt PSScriptAnalyzer-BOM-Regel, pre-commit-hooks und EditorConfig Checker; kein Formatierer, Sprach-Linter oder Kodierungsdetektor.

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python tests/runtime_fixtures.py
python -m pip install build
python -m build
```

Tests prüfen mehrsprachige Bytes, UTF-16/32, ungültige/abgeschnittene Sequenzen, NUL, shebangs, Konflikte, Pfade/Limits, deterministisches JSON und unveränderte Quelldateien. Eigene harmlose Laufzeitbeispiele werden in CI unter Linux direkt und unter echtem Windows PowerShell 5.1 (ASCII und UTF-8 BOM) ausgeführt. Verhalten ohne BOM wird codepageabhängig protokolliert. Das normale CLI führt niemals Nutzerskripte aus. Separate Linux/Windows-Jobs testen Units und Wheel-Installation. Lokaler Linux-Erfolg beweist keinen Windows-CI-Erfolg; den veröffentlichten Commit prüfen.

Beiträge: enge, belegte Verträge, Regressionstests und Pflege aller vier Sprachen. Sicherheitsprobleme privat über GitHub melden, falls verfügbar, sonst Issue ohne vertrauliche Inhalte. MIT; keine kopierten Drittanbieterquellen oder Testbeispiele.
