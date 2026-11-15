"""Descarga inmutable de focos de calor mediante la API area de FIRMS."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from collections.abc import Callable, Sequence
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

from ingest.firms_schema import (
    API_AREA_URL_PLANTILLA,
    API_DAY_RANGE_MAX,
    API_LIMITE_TRANSACCIONES,
    COLUMNAS_REQUERIDAS,
    FUENTES_API,
    HUILA_BBOX,
    HUILA_BBOX_CONFIRMADO,
)
from ingest.manifest import append_entry, build_entry
from ingest.credenciales import leer_clave


BLOCKED_MESSAGE = (
    "BLOQUEO B-01: falta FIRMS_MAP_KEY en .env (ver .env.example); "
    "se continúa con datos sintéticos en data/sample"
)
PROVISIONAL_DAY_RANGE_MAX = 5
DEFAULT_SOURCES = tuple(
    source
    for source in (
        "MODIS_NRT",
        "MODIS_SP",
        "VIIRS_SNPP_SP",
        "VIIRS_NOAA20_NRT",
        "VIIRS_NOAA21_NRT",
        "VIIRS_NOAA20_SP",
    )
    if source in FUENTES_API
)
Fetch = Callable[[str], bytes]


def partition_windows(
    start: date, end: date, max_days: int
) -> list[tuple[date, date]]:
    """Parte un intervalo inclusivo en ventanas contiguas e inclusivas."""
    if start > end:
        raise ValueError("la fecha inicial no puede ser posterior a la final")
    if max_days < 1:
        raise ValueError("max_days debe ser positivo")

    windows: list[tuple[date, date]] = []
    current = start
    while current <= end:
        window_end = min(current + timedelta(days=max_days - 1), end)
        windows.append((current, window_end))
        current = window_end + timedelta(days=1)
    return windows


def _coordinate(value: float) -> str:
    return str(value)


def build_area_url(
    map_key: str,
    source: str,
    bbox: Sequence[float],
    start: date,
    end: date,
) -> str:
    """Construye una URL area usando literalmente la plantilla del esquema."""
    if source not in FUENTES_API:
        raise ValueError(f"fuente no incluida en FUENTES_API: {source}")
    if len(bbox) != 4:
        raise ValueError("bbox debe contener W,S,E,N")
    day_range = (end - start).days + 1
    if day_range < 1:
        raise ValueError("ventana de fechas inválida")

    # La plantilla documenta la fecha entre corchetes porque es opcional. Para
    # ventanas históricas siempre se incluye la fecha inicial.
    return (
        API_AREA_URL_PLANTILLA
        .replace("<MAP_KEY>", map_key)
        .replace("<FUENTE>", source)
        .replace("<W,S,E,N>", ",".join(_coordinate(value) for value in bbox))
        .replace("<DAY_RANGE>", str(day_range))
        .replace("[/<YYYY-MM-DD>]", f"/{start.isoformat()}")
    )


def _masked_url(url: str, map_key: str) -> str:
    return url.replace(map_key, "<MAP_KEY>")


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def read_map_key(env_path: Path) -> str | None:
    return leer_clave(env_path)


def _default_fetch(url: str) -> bytes:
    with urlopen(url, timeout=60) as response:  # noqa: S310 - URL fija de FIRMS
        return response.read()


def _fetch_with_retry(
    url: str,
    fetch: Fetch,
    *,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> bytes:
    for attempt in range(attempts):
        try:
            return fetch(url)
        except Exception:
            if attempt == attempts - 1:
                raise
            sleep(2**attempt)
    raise AssertionError("bucle de reintentos inalcanzable")


def _expected_header(source: str) -> str:
    metadata = FUENTES_API[source]
    variant = "api_nrt" if metadata["calidad"] == "NRT" else "api_sp"
    return ",".join(COLUMNAS_REQUERIDAS[(metadata["sensor"], variant)])


def _has_expected_header(payload: bytes, source: str) -> bool:
    """La primera línea debe contener todas las columnas requeridas.

    Se toleran columnas extra y otro orden, igual que el lector (ingest.reader).
    """
    first_line = payload.splitlines()[0] if payload.splitlines() else b""
    try:
        columns = {c.strip() for c in first_line.decode("utf-8-sig").split(",")}
    except UnicodeDecodeError:
        return False
    metadata = FUENTES_API[source]
    variant = "api_nrt" if metadata["calidad"] == "NRT" else "api_sp"
    return set(COLUMNAS_REQUERIDAS[(metadata["sensor"], variant)]) <= columns


def _log_invalid_response(
    out: Path,
    *,
    url: str,
    map_key: str,
    payload: bytes,
    downloaded_at: datetime,
) -> None:
    out.mkdir(parents=True, exist_ok=True)
    response = payload.decode("utf-8", errors="replace").replace(map_key, "<MAP_KEY>")
    response = response.replace("\r", " ").replace("\n", " ")[:1000]
    line = (
        f"{downloaded_at.strftime('%Y-%m-%dT%H:%M:%SZ')} "
        f"url={_masked_url(url, map_key)} respuesta={response}\n"
    )
    with (out / "_errores.log").open("a", encoding="utf-8") as target:
        target.write(line)


def _filename(
    source: str,
    bbox: Sequence[float],
    start: date,
    end: date,
    downloaded_at: datetime,
) -> str:
    coordinates = "_".join(_coordinate(value) for value in bbox)
    stamp = downloaded_at.strftime("%Y%m%dT%H%M%SZ")
    return f"{source}_{coordinates}_{start.isoformat()}_{end.isoformat()}__{stamp}.csv"


def _write_immutable(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"no se sobrescribe un archivo crudo existente: {path}")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        # El segundo chequeo reduce la ventana de carrera; data/raw se opera
        # con un solo proceso y jamás se reemplaza de forma intencional.
        if path.exists():
            raise FileExistsError(f"no se sobrescribe un archivo crudo existente: {path}")
        os.rename(temporary_name, path)
        temporary_name = None
        path.chmod(0o444)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _warn_unconfirmed(sources: Sequence[str]) -> None:
    unconfirmed = [source for source in sources if not FUENTES_API[source]["confirmado"]]
    if unconfirmed:
        print(
            "ADVERTENCIA: fuentes y metadatos por confirmar: " + ", ".join(unconfirmed),
            file=sys.stderr,
        )
    if not HUILA_BBOX_CONFIRMADO:
        print("ADVERTENCIA: HUILA_BBOX está por confirmar", file=sys.stderr)
    if API_DAY_RANGE_MAX is None:
        print(
            f"ADVERTENCIA: API_DAY_RANGE_MAX por confirmar; se usa {PROVISIONAL_DAY_RANGE_MAX} configurable",
            file=sys.stderr,
        )
    if API_LIMITE_TRANSACCIONES is None:
        print(
            "ADVERTENCIA: API_LIMITE_TRANSACCIONES por confirmar; configure --pause conservador",
            file=sys.stderr,
        )


def download(
    *,
    sources: Sequence[str],
    start: date,
    end: date,
    bbox: Sequence[float],
    out: Path,
    root: Path,
    map_key: str,
    fetch: Fetch = _default_fetch,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    pause: float = 1.0,
    max_days: int = PROVISIONAL_DAY_RANGE_MAX,
    sleep: Callable[[float], None] = time.sleep,
    rejected: list[str] | None = None,
    manifest: Path | None = None,
) -> list[Path]:
    """Descarga todas las ventanas válidas y devuelve los CSV guardados."""
    unknown = set(sources) - FUENTES_API.keys()
    if unknown:
        raise ValueError(f"fuentes desconocidas: {', '.join(sorted(unknown))}")
    # Por defecto, el manifiesto común de data/raw; un conjunto aparte (p. ej. global) lleva el suyo.
    manifest_path = manifest or root / "data" / "raw" / "manifest.jsonl"
    saved: list[Path] = []
    requests = [(source, first, last) for source in sources
                for first, last in partition_windows(start, end, max_days)]

    for index, (source, first, last) in enumerate(requests):
        if index and pause:
            sleep(pause)
        url = build_area_url(map_key, source, bbox, first, last)
        payload = _fetch_with_retry(url, fetch, sleep=sleep)
        downloaded_at = now().astimezone(timezone.utc)
        if not _has_expected_header(payload, source):
            _log_invalid_response(
                out, url=url, map_key=map_key, payload=payload,
                downloaded_at=downloaded_at,
            )
            if rejected is not None:
                rejected.append(_masked_url(url, map_key))
            continue

        path = out / source / _filename(source, bbox, first, last, downloaded_at)
        _write_immutable(path, payload)
        metadata = FUENTES_API[source]
        entry = build_entry(
            path,
            manifest_path.parent,
            fuente=source,
            sensor=metadata["sensor"],
            calidad=metadata["calidad"],
            coleccion=metadata["coleccion"],
            fecha_descarga=downloaded_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            url_sin_clave=_masked_url(url, map_key),
            bbox=list(bbox),
            fecha_inicio=first.isoformat(),
            fecha_fin=last.isoformat(),
            sintetico=False,
        )
        append_entry(manifest_path, entry)
        saved.append(path)
    return saved


def _parser(today: date) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", nargs="+", choices=tuple(FUENTES_API), default=DEFAULT_SOURCES)
    parser.add_argument("--start", type=date.fromisoformat, default=today - timedelta(days=365))
    parser.add_argument("--end", type=date.fromisoformat, default=today)
    parser.add_argument("--bbox", nargs=4, type=float, metavar=("W", "S", "E", "N"), default=HUILA_BBOX)
    parser.add_argument("--out", type=Path, default=Path("data/raw/firms_api"))
    parser.add_argument("--pause", type=float, default=1.0)
    parser.add_argument("--manifest", type=Path, default=None,
                        help="manifiesto destino (por defecto data/raw/manifest.jsonl); --out debe quedar debajo")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    root: Path | None = None,
    env_path: Path | None = None,
    fetch: Fetch = _default_fetch,
    now: datetime | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    root = (root or Path.cwd()).resolve()
    current = now or datetime.now(timezone.utc)
    args = _parser(current.date()).parse_args(argv)
    map_key = read_map_key(env_path or root / ".env")
    if map_key is None:
        print(BLOCKED_MESSAGE, file=sys.stderr)
        return 2

    max_days_text = os.environ.get("FIRMS_API_DAY_RANGE_MAX")
    max_days = int(max_days_text) if max_days_text else (API_DAY_RANGE_MAX or PROVISIONAL_DAY_RANGE_MAX)
    _warn_unconfirmed(args.sources)
    windows = partition_windows(args.start, args.end, max_days)
    if args.dry_run:
        for source in args.sources:
            for first, last in windows:
                url = build_area_url(map_key, source, args.bbox, first, last)
                print(_masked_url(url, map_key))
        return 0

    out = args.out if args.out.is_absolute() else root / args.out
    rejected: list[str] = []
    try:
        download(
            sources=args.sources,
            start=args.start,
            end=args.end,
            bbox=args.bbox,
            out=out,
            root=root,
            map_key=map_key,
            fetch=fetch,
            now=lambda: current if now is not None else datetime.now(timezone.utc),
            pause=args.pause,
            max_days=max_days,
            sleep=sleep,
            rejected=rejected,
            manifest=None if args.manifest is None else (
                args.manifest if args.manifest.is_absolute() else root / args.manifest),
        )
    except Exception as exc:
        # Frontera del CLI: incluso una excepción de urllib puede incluir la URL
        # solicitada; se oculta la credencial antes de informar el error.
        print(f"ERROR: {str(exc).replace(map_key, '<MAP_KEY>')}", file=sys.stderr)
        return 1
    if rejected:
        print(
            f"ADVERTENCIA: {len(rejected)} respuesta(s) rechazada(s) por cabecera inválida; "
            f"ver {out / '_errores.log'}",
            file=sys.stderr,
        )
        for url in rejected:
            print(f"  rechazada: {url}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
