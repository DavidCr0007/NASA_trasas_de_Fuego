import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "tools" / "scan_secrets.py"
SPEC = importlib.util.spec_from_file_location("scan_secrets", SCRIPT)
assert SPEC and SPEC.loader
scan_secrets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scan_secrets)
scan_file = scan_secrets.scan_file


def test_detects_nonempty_firms_key(tmp_path):
    path = tmp_path / "config.txt"
    path.write_text("FIRMS_MAP_KEY=" + "secreto\n", encoding="utf-8")
    assert any("FIRMS_MAP_KEY" in issue for issue in scan_file(path))


def test_detects_exactly_32_hex_as_possible_map_key(tmp_path):
    path = tmp_path / "config.txt"
    token = "0123456789abcdef" + "0123456789ABCDEF"
    path.write_text("token=" + token + "\n", encoding="utf-8")
    assert any("posible MAP_KEY" in issue for issue in scan_file(path))


def test_allows_sha256_and_git_hash(tmp_path):
    path = tmp_path / "hashes.txt"
    path.write_text("a" * 64 + "\n" + "b" * 40 + "\n", encoding="utf-8")
    assert scan_file(path) == []


def test_detects_area_url_with_embedded_key(tmp_path):
    path = tmp_path / "url.txt"
    path.write_text(
        "https://firms.modaps.eosdis.nasa.gov/api/"
        + "area/csv/CLAVE/VIIRS/\n",
        encoding="utf-8",
    )
    assert any("URL /api/area/" in issue for issue in scan_file(path))


def test_allows_area_url_placeholder(tmp_path):
    path = tmp_path / "url.txt"
    path.write_text(
        "https://firms.modaps.eosdis.nasa.gov/api/"
        + "area/csv/<MAP_KEY>/VIIRS/\n",
        encoding="utf-8",
    )
    assert scan_file(path) == []


def test_flags_versioned_dotenv(tmp_path):
    path = tmp_path / ".env"
    path.write_text("FIRMS_MAP_KEY=\n", encoding="utf-8")
    assert any(".env versionado" in issue for issue in scan_file(path, versioned=True))


def test_ignores_binary_files(tmp_path):
    path = tmp_path / "imagen.bin"
    path.write_bytes(b"\x00FIRMS_MAP_KEY=secreto\n")
    assert scan_file(path) == []


def test_uv_lock_is_excluded(tmp_path):
    path = tmp_path / "uv.lock"
    path.write_text("FIRMS_MAP_KEY=" + "secreto\n", encoding="utf-8")
    assert scan_file(path) == []
