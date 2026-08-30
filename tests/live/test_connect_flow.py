"""CAPA 3 — el flujo de conexion de cuentas, contra el servidor de verdad.

ESTO ES LO QUE LA FASE 8 DEJO A MEDIAS. Alli el flujo se verifico contra un servidor de mentira,
porque autorizar una red es un OAuth **con una persona delante** y eso no se automatiza. Lo que si se
puede comprobar sin nadie pulsando nada es todo lo de antes: que el token temporal se emite, que
sirve para pedir los enlaces, y —sobre todo— que **cada uno de los dos credenciales es rechazado
exactamente donde debe**.

Esa ultima parte es la que trae cuenta. El spec juraba que pedir los enlaces con credenciales de app
contesta 519 y que el token temporal contesta 519 al pedir un token: uno de los dos era 514, los dos
errores dicen casi lo mismo y estan a cinco numeros. Con esto pinchado, el dia que alguien cambie el
orden de un middleware se entera aqui y no en el foro de un integrador.

Lo que NO se prueba y no se puede: `accounts.connect()` completo. La URL de vuelta la construye la
red y apunta a un front nuestro; hace falta una persona autorizando.

OJO CON LOS CLIENTES INVITADOS: `as_temporal_token` devuelve OTRO `PlanVortex`, con su propia
conexion de `httpx2`. Van todos dentro de un `with` para que se cierre: la suite corre con
`filterwarnings = ["error"]` y un socket que se recoge solo acabaria fallando un test que no tiene
nada que ver.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from planvortex import PlanVortexError
from planvortex.types import (
    is_meta_embedded_signup,
    is_redirect_authorization,
    is_telegram_bot_authorization,
)
from tests.live.conftest import LIVE, ContextoLive

pytestmark = LIVE


def _cuando(momento: str) -> datetime:
    """`expires_at` viaja en ISO-8601 y a veces con la `Z`, que 3.10 todavia no sabe leer."""
    return datetime.fromisoformat(momento.replace("Z", "+00:00"))


@pytest.fixture(scope="module")
def token(live: ContextoLive) -> str:
    """Un token temporal sin red, o sea que abre todas. Se emite una vez para todo el fichero."""
    return live.pv.organizations.create_connect_token(live.organization["_id"])["token"]


def test_la_app_emite_un_token_temporal_con_su_url_y_su_caducidad(live: ContextoLive) -> None:
    """QUINCE MINUTOS.

    Era una hora, y la hora no compraba nada: quien recibe esto salta de la aplicacion del integrador
    al panel en el acto. Este numero solo lo puede confirmar la capa 3, porque lo fija el servidor y
    el paquete se limita a leer su `expires_at`.
    """
    conexion = live.pv.organizations.create_connect_token(
        live.organization["_id"], social_network="instagram"
    )

    assert conexion["token"]
    assert conexion["url"].startswith("http")

    queda = _cuando(conexion["expires_at"]) - datetime.now(timezone.utc)
    assert queda.total_seconds() > 0
    assert queda.total_seconds() <= 16 * 60


def test_un_token_emitido_para_una_red_solo_ensena_y_solo_conecta_esa_red(live: ContextoLive) -> None:
    """La red va DENTRO del token, no solo en la query de la URL.

    Antes viajaba unicamente ahi —o sea en la parte que cualquiera reescribe—, asi que un token
    pedido "para Instagram" conectaba igual de bien un Facebook de esa organizacion.

    Los enlaces son la mitad visible de lo mismo: con un token atado, solo sale esa red, para que el
    integrador no le pinte a su usuario botones que despues van a contestar 544.
    """
    conexion = live.pv.organizations.create_connect_token(
        live.organization["_id"], social_network="instagram"
    )

    with live.pv.as_temporal_token(conexion["token"]) as invitado:
        enlaces = invitado.accounts.connect_links(live.organization["_id"])
        assert [enlace["social_network"] for enlace in enlaces] == ["instagram"]

        # Y el rechazo de verdad: pedir la conexion de OTRA red con ese token. El guardia va delante
        # del handler, asi que esto no llega a hablar con Facebook.
        with pytest.raises(PlanVortexError) as fallo:
            invitado.accounts.connect(live.organization["_id"], "facebook", {"code": "no-llega-a-usarse"})

    assert fallo.value.code == 544
    assert fallo.value.status == 400


def test_con_el_token_temporal_se_piden_los_enlaces_de_autorizacion(live: ContextoLive, token: str) -> None:
    """LO QUE SE MIRA ES EL METODO, no si el enlace viene vacio.

    Esta era la excepcion escrita a mano para WhatsApp —que llega con `link: ""` porque su alta no es
    un OAuth sino el embedded signup de Meta— y que dejaba a cualquier integrador mandando a su
    usuario a su propia pagina. Ahora el servidor lo dice, y el que se salga de estos dos metodos
    rompe aqui en vez de en el navegador de alguien.
    """
    with live.pv.as_temporal_token(token) as invitado:
        enlaces = invitado.accounts.connect_links(live.organization["_id"])

    assert isinstance(enlaces, list)
    assert len(enlaces) > 0

    for enlace in enlaces:
        red = enlace["social_network"]
        assert isinstance(red, str)
        autorizacion = enlace["authorization"]

        if is_meta_embedded_signup(autorizacion):
            # No hay URL que dar, pero si todo lo que hace falta para levantar el popup.
            assert enlace["link"] == ""
            faltan = [
                campo
                for campo, valor in (
                    ("app_id", autorizacion["app_id"]),
                    ("config_id", autorizacion["config_id"]),
                    ("graph_version", autorizacion["graph_version"]),
                    ("feature_type", autorizacion["feature_type"]),
                    ("session_info_version", autorizacion["session_info_version"]),
                )
                if not valor
            ]
            assert not faltan, f"{red} no publica {', '.join(faltan)}"
            continue

        if is_telegram_bot_authorization(autorizacion):
            # Esta SI trae enlace, y aun asi no es una redireccion: abre un chat con el bot. Que el
            # servidor publique los dos campos es lo unico que la capa 3 puede confirmar; que la
            # cuenta aparezca despues exige a una persona metiendo el bot en su canal.
            assert autorizacion["bot_username"], "telegram no publica el @nombre del bot"
            assert "@" not in autorizacion["bot_username"], "el @nombre viaja SIN arroba"
            assert enlace["link"].startswith("http"), f"enlace de {red}"
            assert "startgroup" in autorizacion["add_to_group_link"], (
                "el segundo paso tiene que abrir la lista de GRUPOS, no la de canales"
            )
            continue

        assert is_redirect_authorization(autorizacion), f"metodo de autorizacion desconocido en {red}"
        # `link`, no `url`: es la URL de la RED, a la que se manda al usuario.
        assert enlace["link"].startswith("http"), f"enlace de {red}"


def test_whatsapp_publica_una_configuracion_de_embedded_signup_con_pinta_de_serlo(
    live: ContextoLive, token: str
) -> None:
    """Solo la capa 3 puede confirmar que la configuracion que publicamos es la que Meta acepta.

    En las capas 1 y 2 el `config_id` es el que le pongamos al banco de pruebas. Esto no abre el
    popup —hace falta una persona— pero si comprueba que el servidor de verdad tiene la variable
    puesta, que es donde estuvo el fallo: `WHATSAPP_ADJUST_ID` existia en el `.env` y no la leia
    nadie, mientras el valor bueno vivia a pelo en el front del panel.
    """
    with live.pv.as_temporal_token(token) as invitado:
        enlaces = invitado.accounts.connect_links(live.organization["_id"])

    whatsapp = next((uno for uno in enlaces if uno["social_network"] == "whatsapp"), None)
    if whatsapp is None:
        # Que no aparezca es legitimo: esa organizacion puede no tener WhatsApp disponible.
        pytest.skip("esta organizacion no ofrece WhatsApp")

    autorizacion = whatsapp["authorization"]
    assert is_meta_embedded_signup(autorizacion)
    # Los identificadores de Meta son numericos, y un "CAMBIAR" del .env de ejemplo no lo es.
    assert autorizacion["app_id"].isdigit()
    assert autorizacion["config_id"].isdigit()
    assert autorizacion["graph_version"].startswith("v")


def test_las_credenciales_de_app_no_sirven_para_pedir_enlaces(live: ContextoLive) -> None:
    """`requireTokenType(["current_user", "temporal_token"])`, o sea 519.

    Una app no puede conectar una cuenta ni aunque quiera, y esta es la trampa 2 del roadmap dicha
    por el servidor.
    """
    with pytest.raises(PlanVortexError) as fallo:
        live.pv.accounts.connect_links(live.organization["_id"])

    assert fallo.value.code == 519
    assert fallo.value.status == 400


def test_un_token_temporal_no_puede_emitir_otro_token_temporal(live: ContextoLive, token: str) -> None:
    """ESTO FUE UN FALLO DEL SERVIDOR, y es el que encontro esta capa en Node.

    Un token temporal podia emitir otro token temporal, y el nuevo duraba otra hora. Encadenandolos,
    el credencial no caducaba nunca — y ese credencial viaja en una URL, en el navegador del usuario
    final del integrador, cuyo unico modelo de seguridad era "muere pronto".

    El motivo estaba en `checkAuth`: cuando el token es temporal rellena `temporal_token` **y
    tambien** `current_app` —lo saca del `keycloak_client_idenfifier` que viaja dentro del propio
    token—, asi que el `requireCurrentApp` de la ruta lo daba por bueno. Arreglado el 2026-08-25: el
    guardia mira las dos cosas y un token temporal recibe el 514 que el spec ya anunciaba.

    O sea que este test dejo de afirmar lo que el servidor hacia para afirmar lo que debe hacer.
    """
    with live.pv.as_temporal_token(token) as invitado, pytest.raises(PlanVortexError) as fallo:
        invitado.organizations.create_connect_token(live.organization["_id"])

    assert fallo.value.code == 514
    # Como todo error de dominio: dentro de un 400, nunca en el status. § Trampa 1.
    assert fallo.value.status == 400


def test_el_token_temporal_esta_atado_a_una_organizacion(live: ContextoLive, token: str) -> None:
    organizaciones = live.pv.clients.organizations(live.client["_id"], limit=2)
    otra = next((una for una in organizaciones.data if una["_id"] != live.organization["_id"]), None)
    if otra is None:
        pytest.skip("hace falta una segunda organizacion en el cliente")

    with live.pv.as_temporal_token(token) as invitado, pytest.raises(PlanVortexError) as fallo:
        invitado.accounts.connect_links(otra["_id"])

    assert fallo.value.code == 1101
