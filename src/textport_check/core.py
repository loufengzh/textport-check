"""Pure byte analysis and deliberately narrow consumer contracts."""
from __future__ import annotations

SOURCES = {
    "powershell51-script": "https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_character_encoding?view=powershell-5.1",
    "posix-direct-script": "https://man7.org/linux/man-pages/man2/execve.2.html",
    "utf8-no-bom": "https://www.unicode.org/faq/utf_bom.html",
}
PROFILES = tuple(SOURCES)
BOMS = ((b"\xff\xfe\x00\x00", "utf-32-le"), (b"\x00\x00\xfe\xff", "utf-32-be"),
        (b"\xef\xbb\xbf", "utf-8"), (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"))


def inspect(data: bytes) -> dict:
    """Offsets always count bytes from zero, including any BOM."""
    bom, codec = b"", "utf-8"
    for marker, encoding in BOMS:
        if data.startswith(marker):
            bom, codec = marker, encoding
            break
    invalid = None
    try:
        decoded = data[len(bom):].decode(codec, errors="strict")
    except UnicodeDecodeError as exc:
        invalid = len(bom) + exc.start
        decoded = None
    first_lf = data.find(b"\n")
    first_line = data if first_lf < 0 else data[:first_lf]
    return {
        "size_bytes": len(data), "bom": codec if bom else None,
        "encoding": codec if bom else ("ascii" if data.isascii() else "utf-8") if invalid is None else "unknown",
        "valid_encoding": invalid is None, "invalid_byte_offset": invalid,
        "nul_byte_offset": data.find(b"\0") if b"\0" in data else None,
        "decoded_nul": decoded is not None and "\0" in decoded,
        "decoded_ascii": decoded is not None and decoded.isascii(),
        "ascii_only": data.isascii() and not bom,
        "shebang_at_zero": data.startswith(b"#!"),
        "first_line_ends_lf": first_lf >= 0,
        "first_line_has_cr": b"\r" in first_line,
        "first_line_ascii": first_line.isascii(),
        "shebang_has_interpreter": bool(first_line[2:].strip(b" \t")) if data.startswith(b"#!") else False,
    }


def evaluate(facts: dict, profile: str) -> dict:
    def result(status, code, message, remedy=None, offset=None):
        return {"profile": profile, "status": status, "diagnostic_id": code,
                "message": message, "remedy": remedy, "byte_offset": offset, "source": SOURCES[profile]}
    bom = facts["bom"]
    if profile == "utf8-no-bom":
        if bom:
            return result("incompatible", "TPC101", "The declared UTF-8/no-BOM contract forbids a BOM.", "Review a separate UTF-8/no-BOM copy for this consumer.", 0)
        if not facts["valid_encoding"]:
            return result("incompatible", "TPC102", "Bytes are not valid UTF-8.", "Determine the source encoding before manual conversion.", facts["invalid_byte_offset"])
        return result("compatible", "TPC100", "Valid UTF-8 without BOM, as explicitly required. NUL is permitted by this encoding-only contract.")
    if profile == "powershell51-script":
        if not facts["valid_encoding"]:
            return result("incompatible" if bom else "unknown", "TPC203", "Malformed declared Unicode encoding." if bom else "No recognized BOM and invalid UTF-8; legacy code-page interpretation is unknown.", "Confirm the source encoding and create a validated Unicode script copy.", facts["invalid_byte_offset"])
        if bom in ("utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be"):
            return result("unknown", "TPC205", "Recognized Unicode BOM, but this profile only certifies ASCII and UTF-8 BOM script decoding.", "Validate this Unicode variant with the actual Windows PowerShell 5.1 consumer.")
        if facts["decoded_nul"]:
            return result("unknown", "TPC204", "Decoded NUL requires parser review; encoding alone cannot establish script suitability.")
        if not bom and not facts["ascii_only"]:
            return result("incompatible", "TPC201", "Non-ASCII UTF-8 without BOM is not a portable Windows PowerShell 5.1 script encoding; the active legacy code page determines interpretation.", "Use a Unicode BOM-bearing copy for Windows PowerShell 5.1, or declare a different consumer.")
        return result("compatible", "TPC200", "ASCII or valid UTF-8 with BOM meets this Windows PowerShell 5.1 encoding check.")
    if profile == "posix-direct-script":
        if bom:
            return result("incompatible", "TPC301", "A BOM prevents #! from being the first two bytes for direct execution.", "Use a separate BOM-free script for direct execution.", 0)
        if not facts["shebang_at_zero"]:
            return result("incompatible", "TPC302", "Direct execution requires #! at byte zero in this profile.", "Review an appropriate interpreter line; explicit interpreter invocation is a different contract.", 0)
        if facts["first_line_has_cr"]:
            return result("incompatible", "TPC303", "CR in the interpreter line is not portable for direct execution.", "Use an LF-only interpreter line.")
        if not facts["first_line_ascii"] or not facts["shebang_has_interpreter"] or not facts["first_line_ends_lf"]:
            return result("unknown", "TPC304", "This profile requires a nonempty ASCII interpreter line terminated by LF.", "Review the interpreter line against the target operating system.")
        if facts["nul_byte_offset"] is not None:
            return result("unknown", "TPC305", "NUL bytes require interpreter-specific review.", offset=facts["nul_byte_offset"])
        if not facts["valid_encoding"]:
            return result("unknown", "TPC306", "The interpreter line is recognized, but body encoding is unknown.", "Check the explicitly selected interpreter's encoding contract.", facts["invalid_byte_offset"])
        return result("compatible", "TPC300", "BOM-free ASCII/UTF-8 bytes and an LF interpreter line meet this limited direct-execution check; interpreter existence, arguments, length limits, permissions and syntax are not checked.")
    raise ValueError("unknown profile")


def analyze(data: bytes, profiles: list[str]) -> dict:
    facts = inspect(data)
    results = [evaluate(facts, profile) for profile in sorted(set(profiles))]
    # Explicitly surface opposing remediation requirements, not every mixed outcome.
    conflict = ("powershell51-script" in profiles and
                any(p in profiles for p in ("posix-direct-script", "utf8-no-bom")) and
                facts["valid_encoding"] and not facts["decoded_ascii"])
    return {"facts": facts, "results": results, "conflicts": [{
        "diagnostic_id": "TPC400", "message": "Consumer requirements may oppose each other: PowerShell 5.1 needs BOM-signaled non-ASCII Unicode for portable interpretation, while another declared consumer forbids BOM. Consider separate artifacts or changing the consumer contract."
    }] if conflict else []}
