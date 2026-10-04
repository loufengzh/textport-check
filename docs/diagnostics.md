# Schema 1 diagnostic IDs

IDs are stable within schema 1; human messages can improve. `byte_offset` is null when no single byte is appropriate. Errors do not include source bytes.

| ID | Meaning |
|---|---|
| TPC100 | Valid declared UTF-8/no-BOM contract |
| TPC101 | BOM forbidden by declared contract |
| TPC102 | Invalid UTF-8 for declared contract |
| TPC200 | ASCII or UTF-8 BOM meets PowerShell 5.1 byte check |
| TPC201 | Non-ASCII BOM-less UTF-8 is not portable under legacy ANSI defaults |
| TPC203 | Malformed BOM-signaled Unicode (incompatible), or unknown BOM-less legacy bytes |
| TPC204 | Decoded NUL requires parser review |
| TPC205 | Recognized UTF-16/32 format outside certified PowerShell profile |
| TPC300 | Limited direct-execution byte checks pass |
| TPC301 | BOM before direct-execution shebang |
| TPC302 | Missing byte-zero shebang |
| TPC303 | CR in interpreter line |
| TPC304 | Interpreter line outside supported ASCII/LF shape |
| TPC305 | NUL requires interpreter-specific review |
| TPC306 | Non-UTF-8 script body needs interpreter contract |
| TPC400 | Potentially opposing consumer requirements; informational |
| TPC900 | Read incomplete: missing/unreadable/unsafe/nonregular/over-limit input |

No TPC202 is allocated. Do not rely on contiguous numbering. Configuration errors return 2 and are outside the per-file report schema. Each successfully read file has one result per distinct declared profile; precedence within profiles reports the most immediate issue rather than every possible issue. A file error has no consumer results and adds one unknown to the summary. Conflicts suggest review/separate artifacts, never automatic conversion.
