from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from ingest.firms_download import (
    build_area_url,
    download,
    main,
    partition_windows,
)
from ingest.firms_schema import COLUMNAS_REQUERIDAS, HUILA_BBOX


KEY = "clave-prueba-no-real"
NOW = datetime(2026, 11, 13, 17, 27, 52, tzinfo=timezone.utc)


def _header(source: str = "MODIS_NRT") -> bytes:
    sensor = "MODIS" if source.startswith("MODIS") else "VIIRS"
    variant = "api_nrt" if source.endswith("NRT") else "api_sp"
    return (",".join(COLUMNAS_REQUERIDAS[(sensor, variant)]) + "\n").encode()


def _manifest_entries(root: Path) -> list[dict[str, object]]:
    manifest = root / "data" / "raw" / "manifest.jsonl"
    return [json.loads(line) for line in manifest.read_text().splitlines()]


def test_partition_windows_is_contiguous_and_inclusive():
    assert partition_windows(date(2026, 1, 1), date(2026, 1, 12), 5) == [
        (date(2026, 1, 1), date(2026, 1, 5)),
        (date(2026, 1, 6), date(2026, 1, 10)),
        (date(2026, 1, 11), date(2026, 1, 12)),
    ]


def test_partition_windows_covers_a_full_year_exactly():
    start = date(2025, 11, 13)
    end = date(2026, 11, 13)
    windows = partition_windows(start, end, 5)

    assert len(windows) == 74
    assert windows[0] == (start, date(2025, 11, 17))
    assert windows[-1] == (date(2026, 11, 13), end)
    assert sum((last - first).days + 1 for first, last in windows) == 366
    assert all(
        windows[index][1].toordinal() + 1 == windows[index + 1][0].toordinal()
        for index in range(len(windows) - 1)
    )


def test_build_area_url_follows_schema_template():
    url = build_area_url(
        KEY,
        "MODIS_NRT",
        HUILA_BBOX,
        date(2026, 11, 1),
        date(2026, 11, 5),
    )

    assert url == (
        "https://firms.modaps.eosdis.nasa.gov/api/" + "area/csv/"
        f"{KEY}/MODIS_NRT/-76.7,1.4,-74.3,3.9/5/2026-11-01"
    )


def test_dry_run_never_exposes_key(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FIRMS_MAP_KEY", KEY)

    result = main(
        ["--sources", "MODIS_NRT", "--start", "2026-11-01", "--end", "2026-11-01", "--dry-run"],
        root=tmp_path,
        now=NOW,
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "<MAP_KEY>" in captured.out
    assert KEY not in captured.out + captured.err
    assert not (tmp_path / "data" / "raw" / "manifest.jsonl").exists()


def test_missing_key_returns_two(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("FIRMS_MAP_KEY", raising=False)

    result = main(["--dry-run"], root=tmp_path, env_path=tmp_path / "no-existe.env", now=NOW)

    assert result == 2
    assert capsys.readouterr().err.strip() == (
        "BLOQUEO B-01: falta FIRMS_MAP_KEY en .env (ver .env.example); "
        "se continúa con datos sintéticos en data/sample"
    )


def test_network_error_never_exposes_key(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FIRMS_MAP_KEY", KEY)

    def failing_fetch(_url):
        raise OSError(f"falló la petición con {KEY}")

    result = main(
        [
            "--sources", "MODIS_NRT", "--start", "2026-11-01",
            "--end", "2026-11-01", "--pause", "0",
        ],
        root=tmp_path,
        fetch=failing_fetch,
        now=NOW,
        sleep=lambda _: None,
    )

    captured = capsys.readouterr()
    assert result == 1
    assert KEY not in captured.out + captured.err
    assert "<MAP_KEY>" in captured.err


def test_download_writes_matching_manifest_hash_and_read_only_file(tmp_path):
    body = _header() + b"2.9,-75.3,300,1,1,2026-11-01,1200,T,MODIS,80,6.1NRT,290,10,D\n"

    paths = download(
        sources=["MODIS_NRT"],
        start=date(2026, 11, 1),
        end=date(2026, 11, 1),
        bbox=HUILA_BBOX,
        out=tmp_path / "data" / "raw" / "firms_api",
        root=tmp_path,
        map_key=KEY,
        fetch=lambda _: body,
        now=lambda: NOW,
        pause=0,
        max_days=5,
    )

    assert len(paths) == 1
    entry = _manifest_entries(tmp_path)[0]
    assert entry["sha256"] == hashlib.sha256(paths[0].read_bytes()).hexdigest()
    assert entry["archivo"] == paths[0].relative_to(tmp_path / "data" / "raw").as_posix()
    assert paths[0].stat().st_mode & 0o777 == 0o444
    serialized = json.dumps(entry)
    assert KEY not in serialized
    assert "<MAP_KEY>" in str(entry["url_sin_clave"])


def test_download_never_overwrites_existing_file(tmp_path):
    kwargs = dict(
        sources=["MODIS_NRT"], start=date(2026, 11, 1), end=date(2026, 11, 1),
        bbox=HUILA_BBOX, out=tmp_path / "data/raw/firms_api", root=tmp_path,
        map_key=KEY, fetch=lambda _: _header(), now=lambda: NOW, pause=0, max_days=5,
    )
    download(**kwargs)

    with pytest.raises(FileExistsError):
        download(**kwargs)


def test_error_response_is_logged_but_not_saved_as_data(tmp_path):
    response = f"Invalid MAP_KEY: {KEY}".encode()

    paths = download(
        sources=["MODIS_NRT"], start=date(2026, 11, 1), end=date(2026, 11, 1),
        bbox=HUILA_BBOX, out=tmp_path / "data/raw/firms_api", root=tmp_path,
        map_key=KEY, fetch=lambda _: response, now=lambda: NOW, pause=0, max_days=5,
    )

    error_log = tmp_path / "data/raw/firms_api/_errores.log"
    assert paths == []
    assert not list((tmp_path / "data/raw/firms_api/MODIS_NRT").glob("*.csv"))
    assert "Invalid MAP_KEY" in error_log.read_text()
    assert KEY not in error_log.read_text()
    assert not (tmp_path / "data/raw/manifest.jsonl").exists()


def test_header_only_response_is_valid(tmp_path):
    paths = download(
        sources=["MODIS_NRT"], start=date(2026, 11, 1), end=date(2026, 11, 1),
        bbox=HUILA_BBOX, out=tmp_path / "data/raw/firms_api", root=tmp_path,
        map_key=KEY, fetch=lambda _: _header(), now=lambda: NOW, pause=0, max_days=5,
    )

    assert len(paths) == 1
    assert paths[0].read_bytes() == _header()
    assert len(_manifest_entries(tmp_path)) == 1
