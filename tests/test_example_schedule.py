"""`examples/schedule.py`, recorrido entero contra un servidor de mentira.

Este ejemplo se sostiene sobre tres cosas que no fallan a la vista, y son exactamente las tres que
se fijan aqui:

  - `order_by_publish=True` viaja como `orderByPublish` (§ Trampa P2). Un parametro que el servidor
    no lee **no da error: devuelve la lista entera**, o sea un calendario silenciosamente equivocado.
  - Las dos fechas salen en ISO-8601 CON offset, porque sin el las leeria el servidor en su zona.
  - `withErrors` es un ESTADO y no una excepcion, asi que sale de la misma llamada cambiando el
    filtro. Un ejemplo que solo mirase los `try/except` no encontraria ni una.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, stub_token
from tests.contrato import cuerpo, peticiones, query, ruta

RAIZ = Path(__file__).resolve().parent.parent
ORG = f"{BASE_URL}/organizations/org1"

CLIENTE = {"_id": "cli1", "name": "Panaderia Vega"}
ORGANIZACION = {"_id": "org1", "name": "Central"}

PROGRAMADA = {
    "_id": "pub1",
    "state": "ready",
    "text": "Nuevo horno, nuevas hogazas",
    "publish_date": "2026-09-01T10:00:00.000Z",
}
FALLIDA = {
    "_id": "pub2",
    "state": "withErrors",
    "text": "Sin fecha y sin salir",
    "retries": 1,
    "publication_errors": [{"code": 943, "message": "YouTube needs exactly one video"}],
}


@pytest.fixture
def ejemplo(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """El modulo del ejemplo, cargado por su ruta: `examples/` no es un paquete a proposito."""
    monkeypatch.setenv("PLANVORTEX_CLIENT_ID", "app-1")
    monkeypatch.setenv("PLANVORTEX_CLIENT_SECRET", "s3cr3t")
    monkeypatch.setenv("PLANVORTEX_BASE_URL", BASE_URL)

    spec = importlib.util.spec_from_file_location("ejemplo_schedule", RAIZ / "examples" / "schedule.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["ejemplo_schedule"] = modulo
    try:
        spec.loader.exec_module(modulo)
        yield modulo
    finally:
        del sys.modules["ejemplo_schedule"]


def _camino(
    httpx_mock: HTTPXMock,
    *,
    programadas: list[dict[str, Any]] | None = None,
    fallidas: list[dict[str, Any]] | None = None,
) -> None:
    """Las cuatro respuestas fijas: cliente, organizacion, el calendario y lo que fallo."""
    stub_token(httpx_mock)
    httpx_mock.add_response(url=f"{BASE_URL}/clients?limit=1", json={"clients": [CLIENTE], "total": 1})
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations?limit=1",
        json={"organizations": [ORGANIZACION], "total": 1},
    )
    calendario = [PROGRAMADA] if programadas is None else programadas
    rotas = [FALLIDA] if fallidas is None else fallidas
    # Se casan por PREFIJO de ruta y no por URL completa: las fechas las pone el ejemplo con
    # `datetime.now`, asi que la query cambia en cada ejecucion. Lo que lleva dentro se comprueba
    # despues, sobre la peticion que de verdad salio.
    httpx_mock.add_response(
        url=re.compile(rf"{re.escape(ORG)}/publish\?.*orderByPublish.*"),
        json={"publications": calendario, "total": len(calendario)},
    )
    httpx_mock.add_response(
        url=re.compile(rf"{re.escape(ORG)}/publish\?.*state=withErrors.*"),
        json={"publications": rotas, "total": len(rotas)},
    )


def test_el_calendario_pide_orderbypublish_y_las_fechas_con_offset(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """La llamada que hace de esto un calendario, mirada por dentro.

    `orderByPublish` es el nombre del cable y `order_by_publish` el del argumento. Si el mapa de la
    § Trampa P2 se rompiera, esta peticion saldria sin el parametro, el servidor devolveria la lista
    ordenada por fecha de CREACION y no fallaria nada: por eso se afirma la query y no el resultado.
    """
    _camino(httpx_mock)
    httpx_mock.add_response(url=f"{ORG}/publish/pub1", method="PUT", json={"publication": PROGRAMADA})
    httpx_mock.add_response(url=f"{BASE_URL}/publication_limits", json={"max_retries": 3})
    httpx_mock.add_response(
        url=f"{ORG}/publish/pub2/retry",
        method="POST",
        json={"publication": {**FALLIDA, "state": "sended"}},
    )

    assert ejemplo.main() == 0

    calendario = peticiones(httpx_mock)[2]
    parametros = query(calendario)
    assert parametros["orderByPublish"] == ["true"]
    assert parametros["state"] == ["ready"]
    # Con offset, siempre. `+00:00` o `Z`, pero nunca una fecha desnuda.
    for clave in ("from_date", "to_date"):
        assert parametros[clave][0].endswith(("+00:00", "Z")), parametros[clave]

    salida = capsys.readouterr().out
    assert "Programadas para los proximos 7 dias: 1" in salida
    assert "Con errores: 1" in salida
    assert "[943] YouTube needs exactly one video" in salida


def test_mover_de_hora_manda_solo_la_fecha_y_como_texto_iso(
    ejemplo: ModuleType, httpx_mock: HTTPXMock
) -> None:
    """El `datetime` del cuerpo, que es el hueco de tipos que cerro la fase 8.

    En ejecucion lo serializa `_serialize`; lo que este test fija es que sale UNO y solo uno —lo que
    no se manda se queda como estaba— y que sale como texto con offset y no como un objeto que el
    serializador de JSON no sabria escribir.
    """
    _camino(httpx_mock)
    httpx_mock.add_response(url=f"{ORG}/publish/pub1", method="PUT", json={"publication": PROGRAMADA})
    httpx_mock.add_response(url=f"{BASE_URL}/publication_limits", json={"max_retries": 3})
    httpx_mock.add_response(
        url=f"{ORG}/publish/pub2/retry",
        method="POST",
        json={"publication": {**FALLIDA, "state": "sended"}},
    )

    assert ejemplo.main() == 0

    edicion = next(p for p in peticiones(httpx_mock) if p.method == "PUT")
    enviado = cuerpo(edicion)
    assert list(enviado) == ["publish_date"]
    assert isinstance(enviado["publish_date"], str)
    assert enviado["publish_date"].endswith(("+00:00", "Z"))


def test_sin_reintentos_disponibles_no_se_llama_a_reintentar(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """El tope sale de `publication_limits` y no de un 3 escrito a mano.

    Y lo que se fija de verdad es la AUSENCIA: no hay mock del `retry`, asi que si el ejemplo lo
    llamara, el plugin tumbaria el test por peticion no simulada. Gastar el ultimo intento en algo
    que va a fallar por el contenido es tirar la unica bala que quedaba.
    """
    agotada = {**FALLIDA, "retries": 3}
    _camino(httpx_mock, fallidas=[agotada])
    httpx_mock.add_response(url=f"{ORG}/publish/pub1", method="PUT", json={"publication": PROGRAMADA})
    httpx_mock.add_response(url=f"{BASE_URL}/publication_limits", json={"max_retries": 3})

    assert ejemplo.main() == 0

    assert "/organizations/org1/publish/pub2/retry" not in [
        ruta(peticion) for peticion in peticiones(httpx_mock)
    ]
    assert "Sin reintentos: 3 de 3 gastados" in capsys.readouterr().out


def test_un_reintento_que_vuelve_a_fallar_se_cuenta_y_se_explica(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """El reintento ocurre EN LA PETICION, asi que la respuesta ya dice si salio.

    Que vuelva a fallar es lo normal cuando el contenido no ha cambiado, y el ejemplo tiene que
    decirlo con el motivo delante en vez de dar el reintento por bueno.
    """
    _camino(httpx_mock)
    httpx_mock.add_response(url=f"{ORG}/publish/pub1", method="PUT", json={"publication": PROGRAMADA})
    httpx_mock.add_response(url=f"{BASE_URL}/publication_limits", json={"max_retries": 3})
    httpx_mock.add_response(url=f"{ORG}/publish/pub2/retry", method="POST", json={"publication": FALLIDA})

    assert ejemplo.main() == 0

    salida = capsys.readouterr().out
    assert "Reintentada y sigue fallando (withErrors)" in salida
    assert "[943] YouTube needs exactly one video" in salida


def test_sin_nada_programado_ni_roto_no_se_edita_ni_se_reintenta(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """La agenda vacia, que es la situacion buena y no un caso raro.

    Sin mocks de `PUT` ni de `retry`: cualquiera de las dos escrituras tumbaria el test.
    """
    _camino(httpx_mock, programadas=[], fallidas=[])

    assert ejemplo.main() == 0

    assert [ruta(peticion) for peticion in peticiones(httpx_mock)] == [
        "/clients",
        "/clients/cli1/organizations",
        "/organizations/org1/publish",
        "/organizations/org1/publish",
    ]
    assert "Nada que reintentar" in capsys.readouterr().out
