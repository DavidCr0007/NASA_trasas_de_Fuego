import hashlib
import json

import pytest

from ingest.manifest import (
    ManifestError,
    append_entry,
    build_entry,
    load_manifest,
    sha256_file,
    verify_file,
)


FIELDS = {
    "fuente": "MODIS_NRT",
    "sensor": "MODIS",
    "calidad": "NRT",
    "coleccion": "por confirmar",
    "fecha_descarga": "2026-11-13T17:00:00Z",
    "url_sin_clave": None,
    "bbox": [-76.0, 1.5, -74.0, 3.8],
    "fecha_inicio": "2026-11-12",
    "fecha_fin": "2026-11-13",
    "sintetico": False,
}


def test_sha256_file_known_value(tmp_path):
    path = tmp_path / "detecciones.csv"
    path.write_bytes(b"abc")
    assert sha256_file(path) == hashlib.sha256(b"abc").hexdigest()


def test_append_entry_is_idempotent(tmp_path):
    path = tmp_path / "detecciones.csv"
    path.write_text("dato", encoding="utf-8")
    manifest = tmp_path / "manifest.jsonl"
    entry = build_entry(path, tmp_path, **FIELDS)

    append_entry(manifest, entry)
    append_entry(manifest, entry)

    assert list(load_manifest(manifest)) == ["detecciones.csv"]
    assert len(manifest.read_text(encoding="utf-8").splitlines()) == 1


def test_append_entry_rejects_conflicting_hash(tmp_path):
    path = tmp_path / "detecciones.csv"
    path.write_text("primero", encoding="utf-8")
    manifest = tmp_path / "manifest.jsonl"
    append_entry(manifest, build_entry(path, tmp_path, **FIELDS))
    path.write_text("segundo", encoding="utf-8")

    with pytest.raises(ManifestError, match="hash distinto"):
        append_entry(manifest, build_entry(path, tmp_path, **FIELDS))


def test_verify_file_fails_after_file_changes(tmp_path):
    path = tmp_path / "detecciones.csv"
    path.write_text("original", encoding="utf-8")
    entry = build_entry(path, tmp_path, **FIELDS)
    path.write_text("alterado", encoding="utf-8")

    with pytest.raises(ManifestError, match="SHA-256"):
        verify_file(path, entry)


def test_manifest_uses_stable_sorted_compact_json(tmp_path):
    path = tmp_path / "subdir" / "detecciones.csv"
    path.parent.mkdir()
    path.write_text("dato", encoding="utf-8")
    manifest = tmp_path / "manifest.jsonl"
    entry = build_entry(path, tmp_path, **FIELDS)
    append_entry(manifest, entry)

    expected = json.dumps(
        entry, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    assert manifest.read_text(encoding="utf-8") == expected + "\n"
    assert entry["archivo"] == "subdir/detecciones.csv"
