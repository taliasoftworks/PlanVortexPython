"""CAPA 3 — la fachada de token, contra el servidor de verdad.

Es lo primero que se prueba porque es lo primero que se rompe: si `POST /oauth/token` deja de
contestar lo que la fase 3 dejo escrito, TODO lo demas de la libreria falla con un error que no dice
nada. Y es lo unico de todo el API cuyo error tiene forma de OAuth2 y status de verdad (401), en vez
del `{code, message, data}` con 400 del resto — eso tambien se comprueba aqui.

Y aqui esta el unico test de la capa 3 que corre en ASINCRONO. El resto de la suite va en sincrono a
proposito (§ el docstring de `conftest.py`), pero el gemelo asincrono es el original del que se
genera todo lo demas y no puede quedarse sin hablar nunca con un servidor real: la capa 2 le mide el
contrato contra un banco de pruebas, no contra TCP.
"""

from __future__ import annotations

import pytest

from planvortex import HttpHooks, PlanVortex, PlanVortexAuthenticationError, RequestInfo
from tests.live.conftest import (
    LIVE,
    ContextoLive,
    cliente_con_secreto_malo,
    cliente_live,
    cliente_live_async,
)

pytestmark = LIVE


def test_emite_un_token_y_sirve_para_llamar_al_api(pv: PlanVortex) -> None:
    """El camino feliz entero: credenciales, token, y una llamada que devuelve datos."""
    redes = pv.catalog.social_networks()

    assert isinstance(redes, list)
    assert len(redes) > 0


def test_una_sola_peticion_de_token_para_varias_llamadas() -> None:
    """La cache respeta el `expires_in` REAL del servidor, no el que le pongamos a un mock.

    Si esto sale a tres, el token se esta pidiendo en cada llamada: son 30 por minuto y `client_id`,
    o sea que un integrador con trafico se frena a si mismo.
    """
    tokens = 0

    def contar(info: RequestInfo) -> None:
        nonlocal tokens
        if info.url.endswith("/oauth/token") and info.attempt == 1:
            tokens += 1

    with cliente_live(hooks=HttpHooks(on_request=contar)) as cliente:
        # Tres llamadas seguidas, y la primera es la que arranca el token.
        clientes = cliente.clients.list(limit=1)
        cliente.catalog.social_networks()
        cliente.catalog.social_limits()

    assert len(clientes.data) > 0
    assert tokens == 1


def test_un_secreto_que_no_vale_contesta_401_invalid_client() -> None:
    """El endpoint de token es la UNICA ruta del servidor con forma de error OAuth2.

    Y con un status que significa algo. Si esto empieza a llegar como un 400 con `code`, es que
    alguien metio la fachada por el `errorHandler` global y el integrador dejo de poder distinguir
    "credenciales mal" de "publicacion invalida".
    """
    with cliente_con_secreto_malo() as cliente, pytest.raises(PlanVortexAuthenticationError) as fallo:
        cliente.catalog.social_networks()

    assert fallo.value.oauth_error == "invalid_client"
    assert fallo.value.status == 401
    assert fallo.value.family == "oauth"


def test_el_token_de_app_solo_ve_su_propio_cliente(live: ContextoLive) -> None:
    """Una app hereda los permisos de su cliente y no puede tocar otro (error 537).

    Que el listado devuelva exactamente uno es la forma barata de comprobarlo sin provocar un 537.
    """
    clientes = live.pv.clients.list(limit=50)

    assert [uno["_id"] for uno in clientes.data] == [live.client["_id"]]


@pytest.mark.asyncio
async def test_el_gemelo_asincrono_tambien_habla_con_un_servidor_de_verdad() -> None:
    """El original, contra TCP. Es la unica vuelta asincrona de toda la capa 3, y basta.

    Lo que se prueba aqui no es el contrato —de eso ya se encargan las capas 1 y 2 en las dos
    variantes— sino que `httpx2.AsyncClient` con estas credenciales y esta URL efectivamente
    conecta, autentica y devuelve datos. Es lo unico que un banco de pruebas no puede afirmar.
    """
    async with cliente_live_async() as pv:
        redes = await pv.catalog.social_networks()

    assert len(redes) > 0
