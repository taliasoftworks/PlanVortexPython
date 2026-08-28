"""CAPA 3 — los errores, tal y como los manda el servidor de verdad.

LA TRAMPA 1 DEL ROADMAP EN FORMA DE TEST: en este API **todo llega con HTTP 400**. No hay un 404 para
"no existe" ni un 403 para "no puedes": hay un `code` del catalogo dentro de un 400. Toda la
clasificacion de la libreria —que clase de error se lanza, que `family` tiene— cuelga de ese numero,
asi que si el servidor decidiera un dia devolver un 404 honrado, `error_family_for_code` dejaria de
encontrar nada y el integrador pasaria de capturar `OrganizationError` a capturar la clase base sin
enterarse.

La capa 2 no puede ver eso: sus respuestas de error las escribimos nosotros con el numero que
creemos. Estas vienen del catalogo real.
"""

from __future__ import annotations

import pytest

from planvortex import NO_ERROR_CODE, AuthError, HttpRequest, OrganizationError, PlanVortexError
from tests.live.conftest import LIVE, ContextoLive

pytestmark = LIVE

#: Un ObjectId con forma perfecta que no es de nadie.
ID_INEXISTENTE = "000000000000000000000000"


def test_una_organizacion_que_no_existe_es_un_400_con_codigo_1101(live: ContextoLive) -> None:
    with pytest.raises(OrganizationError) as fallo:
        live.pv.organizations.get(ID_INEXISTENTE)

    assert fallo.value.code == 1101
    assert fallo.value.family == "organization"
    # Lo importante de este test: el 400. Es lo que obliga a mirar `code` y nunca `status`.
    assert fallo.value.status == 400
    assert fallo.value.message


def test_un_identificador_con_forma_invalida_es_el_503_del_catalogo(live: ContextoLive) -> None:
    """503 vive en el rango 500-541, que es la familia `auth`.

    Sorprende —no tiene nada que ver con autenticarse— pero es donde esta, y la libreria lo clasifica
    por rango. Y es un 400, no un 500.
    """
    with pytest.raises(AuthError) as fallo:
        live.pv.organizations.get("no-soy-un-object-id")

    assert fallo.value.code == 503
    assert fallo.value.status == 400


def test_lo_que_exige_token_de_usuario_se_le_niega_a_una_app_con_el_512(live: ContextoLive) -> None:
    """`GET /clients/{id}/apps` lleva `requireCurrentUser`: una app no se administra a si misma.

    Es el limite del alcance de la libreria, y esta aqui para que se note el dia que cambie.
    """
    with pytest.raises(PlanVortexError) as fallo:
        live.pv.apps.list(live.client["_id"])

    assert fallo.value.code == 512
    assert fallo.value.family == "auth"
    assert fallo.value.status == 400


def test_una_ruta_que_no_existe_sale_como_error_http_sin_codigo_inventado(live: ContextoLive) -> None:
    """Aqui si hay un 404 de verdad, porque no lo genera el catalogo sino Express.

    El cuerpo ni siquiera es JSON. La libreria no debe fabricar un `code`: se distingue por `family`.
    """
    with pytest.raises(PlanVortexError) as fallo:
        live.pv.request(HttpRequest(method="GET", path="/esta-ruta-no-existe-jamas"))

    assert fallo.value.status == 404
    assert fallo.value.family == "http"
    assert fallo.value.code == NO_ERROR_CODE
