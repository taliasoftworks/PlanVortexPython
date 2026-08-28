"""CAPA 3 — leer todos los dominios contra el servidor de verdad.

ESTE ES EL FICHERO QUE JUSTIFICA LA CAPA 3. Cada lista del API llega envuelta con el nombre de su
recurso —`{publications, total}`, `{accounts, total}`, `{uploads, total}`— y la libreria la
desenvuelve por ese nombre EXACTO (`unwrap_list`). Si el servidor renombra un sobre, la capa 2 no se
entera: sus respuestas tienen el nombre viejo porque las escribimos nosotros. Aqui no.

En Python el sintoma es mejor que en Node, y conviene saberlo: `unwrap_list` LANZA cuando la clave no
esta, en vez de devolver una pagina con `data=None`. O sea que un sobre renombrado no llega a
parecer una lista vacia. Lo que no cambia es quien puede verlo: solo esta capa.

Por eso hay un test por dominio y todos comprueban lo mismo, que es lo aburrido y lo que importa:
`{data: [...], total: n}`, con `data` siendo una lista de verdad.

Lo que no esta aqui y es a proposito: `pv.apps`. Casi todo ese dominio exige token de USUARIO —una
app no se administra a si misma—, asi que contra credenciales de app solo se podria comprobar que
falla, y eso ya lo pincha `test_errors.py`.
"""

from __future__ import annotations

from typing import Any

import pytest

from planvortex import Page
from planvortex.types import Account
from tests.live.conftest import LIVE, ContextoLive, plan_de_pago

pytestmark = LIVE


def pagina_valida(pagina: Page[Any], nombre: str) -> None:
    """Lo que se le pide a cualquier listado: el sobre bien abierto."""
    assert isinstance(pagina.data, list), f"{nombre}.data no es una lista: cambio el nombre del sobre?"
    assert isinstance(pagina.total, int), f"{nombre}.total no es un numero"
    assert pagina.total >= 0


def test_clientes(live: ContextoLive) -> None:
    pagina = live.pv.clients.list(limit=5)

    pagina_valida(pagina, "clients")
    assert pagina.data[0]["_id"]


def test_cliente_con_plan_y_organizaciones(live: ContextoLive) -> None:
    cliente = live.pv.clients.get(live.client["_id"], get_use=True)

    assert cliente["_id"] == live.client["_id"]
    assert "actual_plan" in cliente

    pagina_valida(live.pv.clients.organizations(live.client["_id"], limit=5), "organizations")


def test_organizacion_sus_limites_y_su_consumo(live: ContextoLive) -> None:
    organizacion = live.pv.organizations.get(live.organization["_id"])
    assert organizacion["_id"] == live.organization["_id"]

    # `limits` es el plan que APLICA, ya resuelto por herencia; `use` es lo gastado. El panel ensena
    # los dos juntos, y un integrador que mire `organization["actual_plan"]` se encuentra un KeyError
    # en cuanto la organizacion hereda del padre.
    limites = live.pv.organizations.limits(live.organization["_id"])
    assert isinstance(limites.get("accounts"), int)
    assert isinstance(limites.get("publications"), int)

    uso = live.pv.organizations.use(live.organization["_id"])
    assert "actual_use" in uso

    pagina_valida(live.pv.organizations.children(live.organization["_id"], limit=5), "children")


def test_cuentas(live: ContextoLive) -> None:
    pagina = live.pv.accounts.list(live.organization["_id"], limit=10)
    pagina_valida(pagina, "accounts")

    for cuenta in pagina.data:
        assert isinstance(cuenta["social_network"], str)
        assert isinstance(cuenta["error_code"], int)


def test_ficheros(live: ContextoLive) -> None:
    pagina_valida(live.pv.uploads.list(live.organization["_id"], limit=5), "uploads")


def test_publicaciones(live: ContextoLive, cuenta_que_publica: Account | None) -> None:
    pagina_valida(live.pv.publications.list(live.organization["_id"], limit=5), "publications")

    if cuenta_que_publica is not None:
        pagina_valida(
            live.pv.publications.list_by_account(
                live.organization["_id"], cuenta_que_publica["_id"], limit=5
            ),
            "publications (por cuenta)",
        )


def test_comentarios(live: ContextoLive) -> None:
    with plan_de_pago():
        pagina_valida(live.pv.comments.list(live.organization["_id"], limit=5), "comments")
        assert isinstance(live.pv.comments.unread_count(live.organization["_id"]), int)


def test_buzon_privado(live: ContextoLive, cuenta_con_buzon: Account | None) -> None:
    with plan_de_pago():
        assert isinstance(live.pv.messages.unread_count(live.organization["_id"]), int)

        if cuenta_con_buzon is None:
            pytest.skip("no hay ninguna cuenta conectada de una red con mensajeria")

        pagina_valida(
            live.pv.messages.conversations(live.organization["_id"], cuenta_con_buzon["_id"], limit=5),
            "conversations",
        )


def test_contactos(live: ContextoLive) -> None:
    with plan_de_pago():
        pagina_valida(live.pv.contacts.list(live.organization["_id"], limit=5), "contacts")


def test_integraciones(live: ContextoLive) -> None:
    proveedores = live.pv.integrations.providers()
    assert isinstance(proveedores, list)
    # `describe()` de cada proveedor es lo que le ahorra al panel una copia del formulario de
    # configuracion. Si llega vacio, el panel se queda sin formulario y no lo dice.
    assert len(proveedores) > 0

    pagina_valida(live.pv.integrations.list(live.organization["_id"], limit=5), "integrations")


def test_planes_de_ia(live: ContextoLive) -> None:
    pagina_valida(live.pv.ai_plans.list(live.client["_id"], live.organization["_id"], limit=5), "ai plans")


def test_dashboard(live: ContextoLive) -> None:
    assert live.pv.dashboard.summary(live.organization["_id"]) is not None
    assert live.pv.dashboard.use(live.organization["_id"]) is not None


def test_catalogos_de_producto(live: ContextoLive) -> None:
    pagina = live.pv.accounts.list(live.organization["_id"], capability="products", limit=5)
    cuenta = next((una for una in pagina.data if una.get("error_code") == 0), None)
    if cuenta is None:
        pytest.skip("no hay ninguna cuenta de Facebook o Instagram conectada")

    pagina_valida(
        live.pv.products.catalogs(live.organization["_id"], cuenta["_id"], limit=5),
        "product catalogs",
    )


def test_el_servidor_respeta_el_offset(live: ContextoLive) -> None:
    """Dos paginas de una, dos elementos distintos.

    `iterate()` encadena paginas con `offset` y corta cuando una viene vacia. Un servidor que
    ignorase el `offset` devolveria la misma pagina para siempre: el `MAX_PAGES` de la libreria lo
    convierte en un error en vez de en un proceso colgado, pero el fallo de verdad es este, y solo se
    ve preguntando.
    """
    primera = live.pv.uploads.list(live.organization["_id"], limit=1, offset=0)
    if primera.total < 2:
        pytest.skip("hacen falta al menos dos ficheros en la organizacion")

    segunda = live.pv.uploads.list(live.organization["_id"], limit=1, offset=1)

    assert segunda.data[0]["_id"] != primera.data[0]["_id"]
