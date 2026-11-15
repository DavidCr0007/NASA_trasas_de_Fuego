"""Credenciales FIRMS exclusivamente en el servidor; nunca devolver sus valores en HTTP."""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken


class ErrorCredencial(ValueError):
    pass


def leer_entorno(path: Path) -> dict[str, str]:
    valores = {}
    if path.is_file():
        for linea in path.read_text(encoding="utf-8-sig").splitlines():
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            nombre, valor = linea.split("=", 1)
            valor = valor.strip()
            if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
                valor = valor[1:-1]
            valores[nombre.strip()] = valor
    return valores


def descifrar(cifrado: str, maestra: str) -> str:
    try:
        valor = Fernet(maestra.encode("ascii")).decrypt(cifrado.encode("ascii")).decode("utf-8").strip()
        if not valor or "\n" in valor or "\r" in valor:
            raise ValueError()
        return valor
    except (InvalidToken, ValueError, UnicodeError, TypeError):
        raise ErrorCredencial("La credencial FIRMS cifrada no se pudo abrir. Revise FIRMS_SECRET_KEY y FIRMS_MAP_KEY_ENCRYPTED en el servidor.") from None


def leer_clave(path: Path = Path(".env")) -> str | None:
    locales = leer_entorno(path)
    # La configuración del proceso prevalece sobre el archivo local. Un cifrado inválido
    # nunca se sustituye silenciosamente por otra clave en texto plano.
    cifrado = os.environ.get("FIRMS_MAP_KEY_ENCRYPTED")
    if cifrado:
        return descifrar(cifrado, os.environ.get("FIRMS_SECRET_KEY", ""))
    if os.environ.get("FIRMS_MAP_KEY"):
        return os.environ["FIRMS_MAP_KEY"].strip() or None
    if locales.get("FIRMS_MAP_KEY_ENCRYPTED"):
        return descifrar(locales["FIRMS_MAP_KEY_ENCRYPTED"], os.environ.get("FIRMS_SECRET_KEY") or locales.get("FIRMS_SECRET_KEY", ""))
    return locales.get("FIRMS_MAP_KEY", "").strip() or None


def estado_publico(path: Path = Path(".env")) -> dict:
    locales = leer_entorno(path)
    cifrada = bool(os.environ.get("FIRMS_MAP_KEY_ENCRYPTED") or (not os.environ.get("FIRMS_MAP_KEY") and locales.get("FIRMS_MAP_KEY_ENCRYPTED")))
    try:
        configurada = bool(leer_clave(path))
        return {"configurada": configurada, "cifrada": cifrada, "estado": "configurada" if configurada else "sin_configurar"}
    except ErrorCredencial:
        return {"configurada": False, "cifrada": cifrada, "estado": "cifrado_invalido"}
