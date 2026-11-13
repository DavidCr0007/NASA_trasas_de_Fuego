"""Manifiesto inmutable de archivos de entrada con verificación SHA-256."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


class ManifestError(Exception):
    """El manifiesto es inconsistente o un archivo no supera la verificación."""


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_entry(
    path: str | Path, manifest_dir: str | Path, **campos: Any
) -> dict[str, Any]:
    file_path = Path(path)
    base = Path(manifest_dir)
    try:
        relative = file_path.resolve().relative_to(base.resolve())
    except ValueError as exc:
        raise ManifestError(f"archivo fuera del directorio del manifiesto: {path}") from exc

    return {
        **campos,
        "archivo": relative.as_posix(),
        "sha256": sha256_file(file_path),
        "bytes": file_path.stat().st_size,
    }


def load_manifest(manifest_path: str | Path) -> dict[str, dict[str, Any]]:
    path = Path(manifest_path)
    if not path.exists():
        return {}

    entries: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
                filename = entry["archivo"]
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ManifestError(
                    f"entrada inválida en {path}:{line_number}"
                ) from exc
            previous = entries.get(filename)
            if previous is not None and previous.get("sha256") != entry.get("sha256"):
                raise ManifestError(f"{filename}: entradas con hash distinto")
            entries[filename] = entry
    return entries


def append_entry(manifest_path: str | Path, entry: dict[str, Any]) -> None:
    path = Path(manifest_path)
    entries = load_manifest(path)
    filename = entry["archivo"]
    previous = entries.get(filename)
    if previous is not None:
        if previous.get("sha256") != entry.get("sha256"):
            raise ManifestError(f"{filename}: ya existe con hash distinto")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(
        entry, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    with path.open("a", encoding="utf-8", newline="\n") as target:
        target.write(serialized + "\n")


def verify_file(path: str | Path, entry: dict[str, Any]) -> None:
    actual = sha256_file(path)
    expected = entry.get("sha256")
    if actual != expected:
        raise ManifestError(
            f"SHA-256 no coincide para {entry.get('archivo', path)}: "
            f"esperado {expected}, obtenido {actual}"
        )


def _verify_manifest(manifest_path: Path) -> None:
    entries = load_manifest(manifest_path)
    for entry in entries.values():
        verify_file(manifest_path.parent / entry["archivo"], entry)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify_parser = subparsers.add_parser("verify", help="verifica todos los archivos")
    verify_parser.add_argument("manifest", type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "verify":
            _verify_manifest(args.manifest)
    except (ManifestError, OSError) as exc:
        parser.exit(1, f"error: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
