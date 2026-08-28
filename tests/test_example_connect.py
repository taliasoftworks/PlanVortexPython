"""`examples/connect.py`, recorrido entero contra un servidor de mentira.

Por lo mismo que `test_example_publish.py`: es lo que vende `/developers`, la gente lo copia y lo
pega, y un ejemplo roto es peor que ninguno. Y aqui hay un motivo de mas, porque este ejemplo no se
puede probar de verdad ni con credenciales: lo que le falta al flujo es una PERSONA pulsando
"aceptar" en la pagina de Instagram, y eso no lo simula la capa 3 tampoco.

Lo que se fija son las cinco llamadas del camino, su orden, y las dos cosas que de verdad hay que
proteger: que la lista de redes se pide **con el token temporal** y no con el de la app, y que la
entrada de WhatsApp se cuenta por su `authorization` y nunca por su `link` vacio.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import quote

import pytest
from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, stub_token
from tests.contrato import peticiones, query, ruta

RAIZ = Path(__file__).resolve().parent.parent
ORG = f"{BASE_URL}/organizations/org1"

CLIENTE = {"_id": "cli1", "name": "Panaderia Vega"}
ORGANIZACION = {"_id": "org1", "name": "Central"}
TOKEN_TEMPORAL = "tok-temporal-15min"

CONEXION = {
    "url": "https://app.planvortex.com/organizations/org1/connect?token=tok-temporal-15min",
    "token": TOKEN_TEMPORAL,
    "expires_at": "2026-08-27T21:15:00.000Z",
}

# Las dos formas de autorizar que hay hoy, tal y como las manda el servidor: una red normal, y
# WhatsApp con el `link` vacio y los cinco campos del popup dentro de `authorization`.
INSTAGRAM = {
    "social_network": "instagram",
    "link": "https://api.instagram.com/oauth/authorize?client_id=1&redirect_uri=https%3A%2F%2Fx",
    "authorization": {"type": "redirect"},
}
WHATSAPP = {
    "social_network": "whatsapp",
    "link": "",
    "authorization": {
        "type": "meta_embedded_signup",
        "app_id": "111222333",
        "config_id": "444555666",
        "graph_version": "v23.0",
        "feature_type": "whatsapp_business_app_onboarding",
        "session_info_version": "3",
    },
}


@pytest.fixture
def ejemplo(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """El modulo del ejemplo, cargado por su ruta: `examples/` no es un paquete a proposito."""
    monkeypatch.setenv("PLANVORTEX_CLIENT_ID", "app-1")
    monkeypatch.setenv("PLANVORTEX_CLIENT_SECRET", "s3cr3t")
    monkeypatch.setenv("PLANVORTEX_BASE_URL", BASE_URL)

    spec = importlib.util.spec_from_file_location("ejemplo_connect", RAIZ / "examples" / "connect.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["ejemplo_connect"] = modulo
    try:
        spec.loader.exec_module(modulo)
        yield modulo
    finally:
        del sys.modules["ejemplo_connect"]


def _camino(
    httpx_mock: HTTPXMock,
    *,
    enlaces: list[dict[str, Any]] | None = None,
    cuentas_usadas: int = 1,
    redirect_uri: str | None = None,
) -> None:
    """Las cinco respuestas del camino, en el orden en que el ejemplo las pide."""
    stub_token(httpx_mock)
    httpx_mock.add_response(url=f"{BASE_URL}/clients?limit=1", json={"clients": [CLIENTE], "total": 1})
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations?limit=1",
        json={"organizations": [ORGANIZACION], "total": 1},
    )
    httpx_mock.add_response(url=f"{ORG}/limits", json={"accounts": 5, "publications": 100})
    httpx_mock.add_response(
        url=f"{ORG}?getUse=true",
        json={
            "organization": {
                **ORGANIZACION,
                "actual_use": {
                    "accounts": cuentas_usadas,
                    "publications": 12,
                    "users": 1,
                    "space": 0,
                    "integrations": 0,
                },
            }
        },
    )
    if cuentas_usadas >= 5:
        # Sin plaza el ejemplo se para antes de emitir el token, que es justo lo que se quiere.
        return
    consulta = f"?redirect_uri={quote(redirect_uri, safe='')}" if redirect_uri else ""
    httpx_mock.add_response(url=f"{ORG}/temporal_connect_token{consulta}", json=CONEXION)
    httpx_mock.add_response(
        url=f"{ORG}/connect_links",
        json={"links": enlaces if enlaces is not None else [INSTAGRAM, WHATSAPP]},
    )


def test_el_ejemplo_recorre_el_camino_entero(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """De credenciales de app a token temporal emitido, y en el orden del guion."""
    _camino(httpx_mock)

    assert ejemplo.main(None) == 0

    assert [ruta(peticion) for peticion in peticiones(httpx_mock)] == [
        "/clients",
        "/clients/cli1/organizations",
        "/organizations/org1/limits",
        "/organizations/org1",
        "/organizations/org1/temporal_connect_token",
        "/organizations/org1/connect_links",
    ]

    salida = capsys.readouterr().out
    assert "Organizacion: Central (org1)" in salida
    assert "quedan 4" in salida
    assert CONEXION["url"] in salida
    assert "2 redes conectables" in salida


def test_la_lista_de_redes_se_pide_con_el_token_temporal_y_no_con_el_de_la_app(
    ejemplo: ModuleType, httpx_mock: HTTPXMock
) -> None:
    """EL PASO QUE EL EJEMPLO EXISTE PARA ENSENAR, y el que no se ve al leerlo.

    `connect_links` con credenciales de app contesta 519. La unica pista de que `as_temporal_token`
    hizo algo es la cabecera, asi que se mira la cabecera: el resto del camino sigue yendo con el
    token de la app y solo esta llamada cambia de credencial.
    """
    _camino(httpx_mock)

    ejemplo.main(None)

    por_ruta = {ruta(peticion): peticion for peticion in peticiones(httpx_mock)}
    assert por_ruta["/organizations/org1/connect_links"].headers["authorization"] == (
        f"Bearer {TOKEN_TEMPORAL}"
    )
    # Y el de antes NO. Si `as_temporal_token` devolviera el mismo cliente, los dos serian iguales
    # y este test seguiria pasando con solo mirar el primero.
    assert por_ruta["/organizations/org1/temporal_connect_token"].headers["authorization"] == (
        "Bearer token-de-prueba"
    )


def test_whatsapp_no_se_anuncia_como_un_enlace_sino_como_el_popup(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """El fallo que la API arrastro un ano, y que un ejemplo copiado repetiria.

    Su `link` es la cadena vacia, asi que quien recorra la lista redirigiendo manda a su usuario a
    su propia pagina — sin error, sin excepcion y sin nada roto que mirar. El ejemplo ramifica por
    `authorization` y escribe los cinco parametros del popup, que hasta ahora solo estaban en el
    front de PlanVortex.
    """
    _camino(httpx_mock)

    ejemplo.main(None)

    salida = capsys.readouterr().out
    assert "whatsapp: NO hay URL" in salida
    assert "appId=111222333" in salida
    assert "config_id=444555666" in salida
    assert "postMessage" in salida
    # Y en ningun caso se le ofrece un sitio al que mandar a nadie.
    assert "whatsapp: manda a la persona" not in salida


def test_un_metodo_de_autorizacion_desconocido_se_salta_diciendolo(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """La rama que hoy no le toca a nadie, y por la que el ejemplo tiene `else` y no `elif` final.

    El dia que una red se autorice de una tercera forma, un `if/elif` sin salida la trataria como
    `redirect` o la ignoraria en silencio. Aqui sale por su nombre.
    """
    futura = {"social_network": "reddit", "link": "", "authorization": {"type": "device_code"}}
    _camino(httpx_mock, enlaces=[INSTAGRAM, futura])

    assert ejemplo.main(None) == 0

    salida = capsys.readouterr().out
    assert "reddit: metodo de autorizacion 'device_code'" in salida
    assert "reddit: manda a la persona" not in salida


def test_sin_plaza_en_el_plan_no_se_emite_ningun_token(ejemplo: ModuleType, httpx_mock: HTTPXMock) -> None:
    """Se comprueba ANTES, que es lo unico amable que se puede hacer aqui.

    Quien consume la plaza es el `enable` del final, o sea que sin sitio la persona haria el OAuth
    entero para comerse un 706 en el ultimo paso. El plugin exige que no sobre ningun mock, asi que
    este test tambien demuestra que las dos llamadas siguientes no llegan a hacerse.
    """
    _camino(httpx_mock, cuentas_usadas=5)

    with pytest.raises(SystemExit):
        ejemplo.main(None)

    assert [ruta(peticion) for peticion in peticiones(httpx_mock)] == [
        "/clients",
        "/clients/cli1/organizations",
        "/organizations/org1/limits",
        "/organizations/org1",
    ]


def test_el_redirect_uri_llega_al_token_y_no_a_la_lista_de_redes(
    ejemplo: ModuleType, httpx_mock: HTTPXMock
) -> None:
    """Los dos `redirect_uri` de este flujo son cosas distintas, y confundirlos es un 532.

    El del token es a donde vuelve TU usuario cuando termina; el de `connect_links` es a que front
    de PlanVortex devuelve la RED, y tiene que ser uno que el servidor tenga registrado. El ejemplo
    solo pasa el primero.
    """
    _camino(httpx_mock, redirect_uri="https://tu-app.example/social/listo")

    ejemplo.main("https://tu-app.example/social/listo")

    por_ruta = {ruta(peticion): peticion for peticion in peticiones(httpx_mock)}
    assert query(por_ruta["/organizations/org1/temporal_connect_token"]) == {
        "redirect_uri": ["https://tu-app.example/social/listo"]
    }
    assert query(por_ruta["/organizations/org1/connect_links"]) == {}
