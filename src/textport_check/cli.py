"""CLI contract: 0 compatible, 1 incompatible, 2 configuration, 3 incomplete/unknown."""
from __future__ import annotations
import argparse
import json
from pathlib import Path, PureWindowsPath
import sys
from . import __version__
from .core import PROFILES, analyze
from .io import InputError, safe_read


def _parser():
    parser = argparse.ArgumentParser(description="Read-only compatibility checks for explicitly declared text consumers.")
    parser.add_argument("files", nargs="*", help="relative files beneath --root")
    parser.add_argument("--profile", action="append", choices=PROFILES, help="repeat to compare consumers")
    parser.add_argument("--config", help="JSON config with explicit file/profile entries")
    parser.add_argument("--root", default=".", help="root for CLI file paths (default: current directory)")
    parser.add_argument("--max-bytes", type=int, default=1048576, help="per-file bound (default: 1048576; max: 67108864)")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def _entries(args):
    if not 1 <= args.max_bytes <= 67108864:
        raise ValueError("--max-bytes must be between 1 and 67108864")
    if args.config is not None:
        if args.config == "":
            raise ValueError("--config must not be empty")
        if args.files or args.profile or args.root != ".":
            raise ValueError("--config cannot be combined with files, --profile or --root")
        config = Path(args.config)
        # Config is also a bounded, regular, non-symlink file.
        data = safe_read(config.absolute().parent, config.name, 1048576)
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate JSON object key")
                result[key] = value
            return result
        try:
            doc = json.loads(data.decode("utf-8"), object_pairs_hook=unique_pairs)
        except RecursionError:
            raise ValueError("configuration nesting exceeds the supported limit") from None
        if not isinstance(doc, dict) or set(doc) != {"version", "files"} or type(doc["version"]) is not int or doc["version"] != 1:
            raise ValueError("config must contain exactly version: 1 and files")
        entries = doc["files"]
        root = config.absolute().parent
    else:
        if not args.files or not args.profile:
            raise ValueError("provide files and --profile, or --config")
        entries = [{"path": p, "profiles": args.profile} for p in args.files]
        root = Path(args.root)
    if not isinstance(entries, list) or not entries or len(entries) > 10000:
        raise ValueError("files must be a nonempty list of at most 10000 entries")
    merged = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"path", "profiles"}:
            raise ValueError("each file entry must contain exactly path and profiles")
        path, profiles = entry["path"], entry["profiles"]
        if not isinstance(path, str) or not path or "\x00" in path or Path(path).is_absolute() or PureWindowsPath(path).drive or PureWindowsPath(path).root or ":" in path or ".." in Path(path).parts or ".." in PureWindowsPath(path).parts:
            raise ValueError("paths must be nonempty relative paths without '..' or NUL")
        if not isinstance(profiles, list) or not profiles or any(not isinstance(p, str) or p not in PROFILES for p in profiles):
            raise ValueError("each entry needs a nonempty list of known profiles")
        merged.setdefault(Path(path).as_posix(), set()).update(profiles)
    return root, merged


def run(args) -> tuple[dict, int]:
    root, entries = _entries(args)
    reports = []
    statuses = []
    for path, profiles in sorted(entries.items()):
        try:
            report = analyze(safe_read(root, path, args.max_bytes), sorted(profiles))
            statuses.extend(result["status"] for result in report["results"])
            reports.append({"path": path, **report, "error": None})
        except (OSError, InputError) as exc:
            statuses.append("unknown")
            # Never expose exception text: OS errors can include absolute paths.
            reports.append({"path": path, "facts": None, "results": [], "conflicts": [],
                            "error": {"diagnostic_id": "TPC900", "message": str(exc) if isinstance(exc, InputError) else "File cannot be read safely as a regular file."}})
    exit_code = 3 if "unknown" in statuses else 1 if "incompatible" in statuses else 0
    return {"schema_version": 1, "tool_version": __version__, "files": reports,
            "summary": {"compatible": statuses.count("compatible"), "incompatible": statuses.count("incompatible"), "unknown": statuses.count("unknown")},
            "exit_code": exit_code}, exit_code


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        report, code = run(args)
    except (ValueError, OSError, InputError) as exc:
        # Configuration errors use stderr and no partial JSON report.
        print("textport-check: invalid configuration: " + (str(exc) if not isinstance(exc, OSError) else "configuration file cannot be read"), file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
    else:
        for file in report["files"]:
            # Escape controls in paths: filenames cannot inject terminal sequences.
            label = json.dumps(file["path"], ensure_ascii=True)
            if file["error"]:
                print(f'{label}: unknown TPC900 {file["error"]["message"]}')
            for result in file["results"]:
                print(f'{label} [{result["profile"]}]: {result["status"]} {result["diagnostic_id"]} {result["message"]}')
            for conflict in file["conflicts"]:
                print(f'{label}: {conflict["diagnostic_id"]} {conflict["message"]}')
        print("Summary: " + ", ".join(f"{key}={value}" for key, value in report["summary"].items()))
    return code
