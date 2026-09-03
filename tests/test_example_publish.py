"""`examples/publish.py`, recorrido entero contra un servidor de mentira.

**Por que un ejemplo tiene test.** Es lo que vende `/developers`: quien llega a la libreria lo copia
y lo pega, asi que un ejemplo roto es peor que ninguno. Y no se puede probar de otra forma: publicar
de verdad exige una cuenta social conectada, y conectarla es un OAuth con una persona delante. La
prueba contra el stack real queda para la capa 3 de la fase 9.

Lo que aqui se fija son las OCHO llamadas del camino y su orden. El plugin exige que no sobre
ninguna simulada y que no falte ninguna real, asi que el test se pone rojo tanto si el ejemplo deja
de llamar a algo como si empieza a llamar a algo nuevo — que es exactamente lo que se quiere de un
ejemplo que la gente copia.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, stub_token
from tests.contrato import cuerpo, peticiones, ruta

RAIZ = Path(__file__).resolve().parent.parent
ORG = f"{BASE_URL}/organizations/org1"

CLIENTE = {"_id": "cli1", "name": "Panaderia Vega"}
ORGANIZACION = {"_id": "org1", "name": "Central"}
CUENTA_ROTA = {"_id": "acc0", "name": "Vieja", "social_network": "facebook", "error_code": 700}
CUENTA = {"_id": "acc1", "name": "Panaderia", "social_network": "instagram", "error_code": 0}
FICHERO = {
    "_id": "up1",
    "name": "hogaza.jpg",
    "file_properties": {
        "aspect_ratio": {"text": "1:1"},
        "size_in_bytes": 4096,
        "allowed_social_networks": ["instagram"],
    },
}
PUBLICACION = {
    "_id": "pub1",
    "state": "ready",
    "id_account": "acc1",
    "publish_date": "2026-09-01T10:00:00.000Z",
    "publication_errors": [],
}


@pytest.fixture
def ejemplo(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """El modulo del ejemplo, cargado por su ruta: `examples/` no es un paquete a proposito."""
    monkeypatch.setenv("PLANVORTEX_CLIENT_ID", "app-1")
    monkeypatch.setenv("PLANVORTEX_CLIENT_SECRET", "s3cr3t")
    monkeypatch.setenv("PLANVORTEX_BASE_URL", BASE_URL)

    spec = importlib.util.spec_from_file_location("ejemplo_publish", RAIZ / "examples" / "publish.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["ejemplo_publish"] = modulo
    try:
        spec.loader.exec_module(modulo)
        yield modulo
    finally:
        del sys.modules["ejemplo_publish"]


def _camino(httpx_mock: HTTPXMock, *, publicacion: dict[str, Any] | None = None) -> None:
    """Las ocho respuestas del camino, en el orden en que el ejemplo las pide."""
    stub_token(httpx_mock)
    httpx_mock.add_response(url=f"{BASE_URL}/clients?limit=1", json={"clients": [CLIENTE], "total": 1})
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations?limit=1",
        json={"organizations": [ORGANIZACION], "total": 1},
    )
    httpx_mock.add_response(url=f"{ORG}/limits", json={"accounts": 5, "users": 3})
    httpx_mock.add_response(
        url=f"{ORG}?getUse=true",
        json={"organization": {**ORGANIZACION, "actual_use": {"accounts": 1, "publications": 12}}},
    )
    httpx_mock.add_response(
        url=f"{ORG}/accounts?limit=10&capability=publications",
        json={"accounts": [CUENTA_ROTA, CUENTA], "total": 2},
    )
    httpx_mock.add_response(
        url=f"{BASE_URL}/social_limits",
        json={"characters": {"instagram": 2200}, "max_post_bytes": {"instagram": 0}},
    )
    httpx_mock.add_response(url=f"{ORG}/uploads", method="POST", json={"upload": FICHERO})
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/publish",
        method="POST",
        json={"publication": publicacion or PUBLICACION},
    )
    if publicacion is not None and publicacion["state"] == "withErrors":
        return
    httpx_mock.add_response(
        url=f"{ORG}/publish?limit=5&state=ready", json={"publications": [PUBLICACION], "total": 1}
    )
    httpx_mock.add_response(
        url=f"{ORG}/publish?limit=5&offset=0&state=ready",
        json={"publications": [PUBLICACION], "total": 1},
    )


def test_el_ejemplo_recorre_el_camino_entero(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """De credenciales a publicacion programada, y en el orden del guion."""
    _camino(httpx_mock)
    imagen = tmp_path / "hogaza.jpg"
    imagen.write_bytes(b"no es un jpeg de verdad")

    assert ejemplo.main(str(imagen)) == 0

    assert [ruta(peticion) for peticion in peticiones(httpx_mock)] == [
        "/clients",
        "/clients/cli1/organizations",
        "/organizations/org1/limits",
        "/organizations/org1",
        "/organizations/org1/accounts",
        "/social_limits",
        "/organizations/org1/uploads",
        "/organizations/org1/accounts/acc1/publish",
        "/organizations/org1/publish",
        "/organizations/org1/publish",
    ]

    salida = capsys.readouterr().out
    assert "Organizacion: Central (org1)" in salida
    assert "Cuenta: Panaderia en instagram" in salida
    assert "Programada pub1 (ready)" in salida
    assert "Pendientes: 1" in salida


def test_el_ejemplo_salta_la_cuenta_rota_y_programa_con_zona_horaria(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    """Las dos cosas que se le olvidan a quien copia y pega: `error_code` y el offset de la fecha."""
    _camino(httpx_mock)
    imagen = tmp_path / "hogaza.jpg"
    imagen.write_bytes(b"bytes")

    ejemplo.main(str(imagen))

    publicar = next(p for p in peticiones(httpx_mock) if p.method == "POST" and "publish" in str(p.url))
    enviado = cuerpo(publicar)
    assert enviado["files"] == ["up1"]
    # Con offset, siempre. Sin el, el servidor la leeria en SU zona horaria (§ Trampa P8).
    assert enviado["publish_date"].endswith("+00:00")


def test_una_publicacion_con_errores_se_cuenta_como_fallo(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """EL COMPORTAMIENTO QUE EL EJEMPLO EXISTE PARA ENSEÑAR. Un 200, y no va a salir nunca.

    El ejemplo devuelve 1 y escribe el motivo en `stderr`: un `try/except` no lo habria cazado.
    """
    _camino(
        httpx_mock,
        publicacion={
            **PUBLICACION,
            "state": "withErrors",
            "publication_errors": [{"code": 903, "message": "El texto es demasiado largo"}],
        },
    )
    imagen = tmp_path / "hogaza.jpg"
    imagen.write_bytes(b"bytes")

    assert ejemplo.main(str(imagen)) == 1
    assert "[903] El texto es demasiado largo" in capsys.readouterr().err


def test_el_contador_de_grafemas_del_ejemplo_no_usa_len(ejemplo: ModuleType) -> None:
    """Un emoji de familia es UN caracter para el servidor y once unidades para `len()`.

    El ejemplo cuenta lo que cuenta el servidor, que es lo unico util cuando el limite aprieta.
    """
    familia = "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466"

    assert ejemplo._grafemas(familia) == 1
    assert len(familia) == 7
    assert len(familia.encode("utf8")) == 25
