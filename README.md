# textport-check

**One byte sequence, several consumers, different answers.** A read-only Python CLI that checks encoding compatibility against explicitly declared consumer profiles and makes conflicting requirements visible.

[简体中文](docs/README.zh-CN.md) · [Русский](docs/README.ru.md) · [Deutsch](docs/README.de.md)

A multilingual installer can need a UTF-8 BOM for portable Windows PowerShell 5.1 interpretation, while a directly executed Unix script needs `#!` at byte zero. A repository-wide “always remove BOM” policy cannot express both contracts. textport-check reports each consumer separately and flags opposing requirements. It never rewrites a file, guesses a legacy encoding, previews source, or executes an audited script.

## Install and try

Python 3.10+, no runtime dependencies. Install from this repository (no PyPI release is claimed):

```sh
python -m pip install .
textport-check --profile powershell51-script --profile utf8-no-bom examples/greeting.ps1
textport-check --config examples/textport.json --format json
```

The first example intentionally exits 1: the UTF-8/no-BOM file is compatible with that contract but not portable under Windows PowerShell 5.1's legacy ANSI default. `TPC400` explains the consumer conflict. ASCII does **not** require a BOM.

## Version 1 profiles

| Profile | Compatible byte checks | Incompatible / unknown boundaries |
|---|---|---|
| `powershell51-script` | ASCII; valid UTF-8 with BOM | Non-ASCII UTF-8 without BOM is incompatible with portable legacy-default interpretation; actual behavior depends on system code page. Invalid BOM-less UTF-8 is unknown. Recognized UTF-16/32 BOMs are identified but unknown, not certified. Decoded NUL is unknown. |
| `posix-direct-script` | No BOM; `#!` at byte zero; nonempty ASCII interpreter line terminated by LF; ASCII/UTF-8 body without NUL | BOM, absent shebang, or CR in the first line is incompatible with this portable profile. Non-ASCII/unterminated interpreter line, NUL, and non-UTF-8 body are unknown. |
| `utf8-no-bom` | Valid UTF-8 without a BOM, including empty content and NUL | An **explicit project contract**, not a claim that all text formats forbid BOM. BOM or invalid UTF-8 is incompatible. |

“Compatible” only means these byte checks passed. It does not promise valid script syntax, safe code, a working interpreter path, executable permission, supported shebang arguments/length, or successful execution. POSIX direct means direct kernel-style execution, not `sh file` or shell fallback. The profile is a conservative portability contract, not every POSIX implementation's specification. A non-UTF-8 body can work with an appropriate interpreter; we report unknown rather than guess.

The CLI recognizes UTF-8, UTF-16 LE/BE and UTF-32 LE/BE BOMs, validates the signaled encoding strictly, and reports invalid-byte offsets from zero including the BOM. UTF-32 signatures are checked before overlapping UTF-16 signatures. Partial signatures are not guessed. NUL byte evidence is separate from decoded NUL because UTF-16/32 naturally contain zero bytes.

## Inputs and output

CLI paths are relative to `--root` (current directory by default). Repeat `--profile` to compare consumers. Config paths are relative to the config's directory:

```json
{"version": 1, "files": [
  {"path": "greeting.ps1", "profiles": ["powershell51-script", "utf8-no-bom"]},
  {"path": "hello.sh", "profiles": ["posix-direct-script", "utf8-no-bom"]}
]}
```

Config and direct input modes cannot be mixed. Only explicit files: no globbing, recursion, exclusions, environment expansion or encoding autodetection. Duplicate normalized paths merge profile sets. Files and profiles sort deterministically. Config requires exact keys, rejects duplicate JSON keys, and is capped at 1 MiB / 10,000 entries. File reads default to 1 MiB each; `--max-bytes` accepts 1–67,108,864. Absolute paths, parent traversal, drive/root-qualified Windows paths, colon-containing paths, symlinks, reparse points and non-regular files are rejected. Spaces and multilingual relative names work. Use `--` before a filename beginning with `-`.

The relative-path restrictions apply to audited-file entries. `--root` and `--config` may use absolute paths or `..`, including `--root ..` and `--config ../textport.json`. Every original directory component is checked: a link, missing directory or regular file followed by `..` is rejected rather than erased to select a different target. Ordinary existing-directory parent traversal remains supported.

POSIX uses descriptor-relative traversal with no-follow at every component. Windows uses point-in-time link/reparse checks; **this is not a sandbox for directories concurrently modified by an adversary**. Concurrently changing files are not a consistent filesystem snapshot. Use a stable checkout. No file content or absolute root is included in reports; relative filenames and byte facts are still potentially private. Terminal paths are escaped.

`--format json` emits schema version 1 with `files`, per-file `facts`, `results`, `conflicts`, `error`, `summary` and `exit_code`. Machine keys and diagnostics stay English. Text and JSON contain no source previews. Incompatible and unknown findings coexist; summary counts consumer results plus one unknown per unreadable file.

Exit codes: **0** all compatible; **1** at least one incompatible and no unknown; **2** invalid arguments/configuration (stderr, no partial JSON); **3** at least one unknown or incomplete file read, even if other results are incompatible. Conflict messages do not independently change exit status. Stable IDs are documented in [diagnostics](docs/diagnostics.md).

## Why another tool?

[PSScriptAnalyzer's BOM rule](https://learn.microsoft.com/en-us/powershell/utility-modules/psscriptanalyzer/rules/usebomforunicodeencodedfile?view=ps-modules) already catches an important PowerShell issue. [pre-commit-hooks](https://github.com/pre-commit/pre-commit-hooks) can fix BOM/line endings, and [EditorConfig Checker](https://github.com/editorconfig-checker/editorconfig-checker) enforces style configuration. This project complements them with an explicit multi-consumer matrix and conflict explanation. It is not a formatter, language linter, encoding detector, converter, or general binary scanner.

## Evidence and development

- [Microsoft: character encoding in Windows PowerShell](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1): BOM-less script interpretation and cross-platform considerations.
- [Linux `execve(2)` interpreter scripts](https://man7.org/linux/man-pages/man2/execve.2.html): `#!` and direct execution. Linux evidence is not proof of every Unix implementation.
- [Unicode BOM FAQ](https://www.unicode.org/faq/utf_bom.html): encoding signatures and UTF-8 BOM considerations. The no-BOM requirement comes from your declared contract.

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python tests/runtime_fixtures.py
python -m pip install build
python -m build
```

Unit tests cover multilingual bytes, malformed/truncated encoding, BOM variants, shebangs, conflicts, boundaries, deterministic JSON and source immutability. Dedicated CI runs generated benign fixtures via native Windows PowerShell **5.1** and Linux direct execution (no shell fallback); audited user scripts are never run. Windows fixture observations record code-page-dependent BOM-less behavior rather than assuming universal failure. Separate Linux/Windows jobs test units and wheel installation. Local Linux execution is not evidence that hosted Windows CI passed; inspect the workflow for the published commit.

Contributions: keep consumer claims narrow and source-backed, add regression tests, preserve read-only behavior and update all four language guides. Report security issues privately through GitHub's repository security advisory feature if enabled; otherwise open an issue without sensitive file content. MIT license. No third-party source or fixtures are copied.
