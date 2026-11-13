"""Busca posibles credenciales FIRMS en archivos versionados y no ignorados."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


FIRMS_VALUE = re.compile(r"^\s*FIRMS_MAP_KEY\s*=\s*(\S.*)$")
POSSIBLE_MAP_KEY = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{32}(?![0-9a-fA-F])")
AREA_URL = re.compile(r"/api/" + r"area/[^/\s?#]+/([^/\s?#]+)")


def scan_file(path: Path, *, versioned: bool = False) -> list[str]:
    if path.name == "uv.lock":
        return []
    if versioned and path.name == ".env":
        dotenv_issue = [f"{path}: archivo .env versionado"]
    else:
        dotenv_issue = []

    try:
        raw = path.read_bytes()
    except (OSError, FileNotFoundError):
        return dotenv_issue
    if b"\x00" in raw:
        return dotenv_issue
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return dotenv_issue

    issues = list(dotenv_issue)
    for number, line in enumerate(text.splitlines(), start=1):
        location = f"{path}:{number}"
        if FIRMS_VALUE.search(line):
            issues.append(f"{location}: FIRMS_MAP_KEY con valor no vacío")
        if POSSIBLE_MAP_KEY.search(line):
            issues.append(f"{location}: posible MAP_KEY")
        for match in AREA_URL.finditer(line):
            if match.group(1) != "<MAP_KEY>":
                issues.append(f"{location}: URL /api/area/ contiene una clave")
    return issues


def _git_files(*args: str) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z", *args],
        check=True,
        stdout=subprocess.PIPE,
    )
    return [Path(name.decode()) for name in result.stdout.split(b"\x00") if name]


def main() -> int:
    try:
        versioned = _git_files()
        untracked = _git_files("--others", "--exclude-standard")
    except (subprocess.CalledProcessError, UnicodeDecodeError) as exc:
        print(f"No se pudo enumerar los archivos Git: {exc}")
        return 1

    issues: list[str] = []
    for path in versioned:
        issues.extend(scan_file(path, versioned=True))
    for path in untracked:
        issues.extend(scan_file(path))

    if issues:
        print("\n".join(issues))
        return 1
    print("Escaneo de secretos: sin hallazgos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
