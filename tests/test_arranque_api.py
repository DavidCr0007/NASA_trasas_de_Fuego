"""Arranque local estable ante las desconexiones del navegador en Windows."""
import asyncio

import pytest
from uvicorn import Config

from api import __main__ as arranque


@pytest.mark.parametrize("plataforma,bucle", [
    ("win32", "api.__main__:crear_bucle_windows"), ("linux", "auto"),
])
def test_arranque_selecciona_bucle_solo_en_windows(monkeypatch, plataforma, bucle):
    aplicacion = object()
    llamadas = []
    monkeypatch.setattr(arranque.sys, "platform", plataforma)
    monkeypatch.setattr(arranque, "create_app", lambda *a, **k: aplicacion)
    monkeypatch.setattr(arranque.uvicorn, "run", lambda app, **k: llamadas.append((app, k)))
    arranque.main(["--datos", "data/processed/global_nrt", "--puerto", "8821"])
    assert llamadas == [(aplicacion, {"host": "127.0.0.1", "port": 8821, "loop": bucle})]


def test_uvicorn_resuelve_la_fabrica_del_bucle_selector():
    fabrica = Config(app=lambda: None, loop="api.__main__:crear_bucle_windows").get_loop_factory()
    bucle = fabrica()
    try:
        assert isinstance(bucle, asyncio.SelectorEventLoop)
        assert not bucle.is_closed()
    finally:
        bucle.close()
