"""Integraciones (capa 2): Drive, RSS, y las dos formas de conectar.

Lo que se fija aqui:

- **El catalogo de proveedores viene envuelto en `{providers}`** y no lleva organizacion: es una
  constante del despliegue.
- **`connect_link` y `picker_config` son dos cosas distintas.** El primero devuelve una URL para
  mandar a la persona; el segundo, un token VIVO para abrir el selector de Google.
- **Reconectar es otra ruta**, no un `connect` repetido: no vuelve a ocupar cupo.
- **`config` es del RSS.** Al conectar, el formulario viaja PLANO; el `config` es lo que el servidor
  devuelve construido.
"""

from __future__ import annotations

from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, query, ruta, unica

ORG = f"{BASE_URL}/organizations/org1"
INTEGRACION = {
    "_id": "int1",
    "id_organization": "org1",
    "provider": "rss",
    "name": "Blog",
    "enabled": True,
    "connected": True,
    "error_code": 0,
    "config": {"url": "https://blog.example/feed", "id_accounts": ["acc1"]},
}


def test_el_catalogo_de_proveedores_sale_del_sobre(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    proveedor = {
        "provider": "rss",
        "requires_oauth": False,
        "file_import": False,
        "content_feed": True,
        "accepted_formats": [],
        "config_fields": [{"name": "url", "type": "string", "required": True}],
    }
    httpx_mock.add_response(url=f"{BASE_URL}/integration_providers", json={"providers": [proveedor]})

    proveedores = cliente.esperar(cliente.pv.integrations.providers())

    # `requires_oauth` es lo que decide como se conecta. No se adivina por el nombre.
    assert proveedores[0]["requires_oauth"] is False
    assert ruta(unica(httpx_mock)) == "/integration_providers"


def test_las_integraciones_se_listan_se_filtran_y_se_iteran(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url=f"{ORG}/integrations?limit=1&offset=0&provider=rss",
        json={"integrations": [INTEGRACION], "total": 1},
    )
    httpx_mock.add_response(
        url=f"{ORG}/integrations?limit=1&offset=1&provider=rss", json={"integrations": [], "total": 1}
    )

    todas = cliente.iterar(cliente.pv.integrations, "aiterate", "org1", limit=1, provider="rss")

    assert todas == [INTEGRACION]
    assert query(peticiones(httpx_mock)[0])["provider"] == ["rss"]


def test_el_enlace_de_autorizacion_devuelve_solo_la_url(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url=f"{ORG}/integrations/google_drive/connect_link?redirect_uri=https%3A%2F%2Fmio.test%2Fok",
        json={"url": "https://accounts.google.com/o/oauth2/auth?x=1"},
    )

    enlace = cliente.esperar(
        cliente.pv.integrations.connect_link("org1", "google_drive", redirect_uri="https://mio.test/ok")
    )

    assert enlace == "https://accounts.google.com/o/oauth2/auth?x=1"
    # El proveedor va en la RUTA, no en la query: es un segmento mas.
    assert ruta(unica(httpx_mock)) == "/organizations/org1/integrations/google_drive/connect_link"


def test_conectar_manda_el_formulario_plano_y_reconectar_va_a_otra_ruta(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(url=f"{ORG}/integrations", method="POST", json={"integration": INTEGRACION})
    httpx_mock.add_response(
        url=f"{ORG}/integrations/int1/reconnect", method="POST", json={"integration": INTEGRACION}
    )

    conectada = cliente.esperar(
        cliente.pv.integrations.connect(
            "org1", {"provider": "rss", "url": "https://blog.example/feed", "id_accounts": ["acc1"]}
        )
    )
    reconectada = cliente.esperar(
        cliente.pv.integrations.reconnect("org1", "int1", {"provider": "google_drive", "code": "4/abc"})
    )

    assert conectada == reconectada == INTEGRACION
    conectar, reconectar = peticiones(httpx_mock)
    # El formulario va PLANO, no dentro de un `config`: el `config` es lo que vuelve.
    assert cuerpo(conectar) == {
        "provider": "rss",
        "url": "https://blog.example/feed",
        "id_accounts": ["acc1"],
    }
    assert cuerpo(reconectar) == {"provider": "google_drive", "code": "4/abc"}
    assert ruta(reconectar) == "/organizations/org1/integrations/int1/reconnect"


def test_leer_apagar_y_borrar(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/integrations/int1", json={"integration": INTEGRACION})
    httpx_mock.add_response(
        url=f"{ORG}/integrations/int1",
        method="PUT",
        json={"integration": {**INTEGRACION, "enabled": False}},
    )
    httpx_mock.add_response(url=f"{ORG}/integrations/int1", method="DELETE", json={"success": True})

    leida = cliente.esperar(cliente.pv.integrations.get("org1", "int1"))
    apagada = cliente.esperar(cliente.pv.integrations.update("org1", "int1", {"enabled": False}))
    borrada = cliente.esperar(cliente.pv.integrations.remove("org1", "int1"))

    assert leida == INTEGRACION
    # Apagada sigue conectada, y deja de contar cupo. Es la forma de pausar un feed sin borrarlo.
    assert (apagada["enabled"], apagada["connected"]) == (False, True)
    assert borrada is None
    assert cuerpo(peticiones(httpx_mock)[1]) == {"enabled": False}


def test_el_enlace_de_una_tienda_lleva_su_url_y_el_id_para_reconectar(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """WooCommerce: el enlace que NO es OAuth apunta al WordPress de la tienda, asi que lleva su URL."""
    httpx_mock.add_response(
        url=f"{ORG}/integrations/woocommerce/connect_link?url=https%3A%2F%2Ftienda.example.com&id_integration=int1",
        json={"url": "https://tienda.example.com/wc-auth/v1/authorize?app_name=PlanVortex&scope=read"},
    )

    enlace = cliente.esperar(
        cliente.pv.integrations.connect_link(
            "org1", "woocommerce", url="https://tienda.example.com", id_integration="int1"
        )
    )

    assert "/wc-auth/v1/authorize" in enlace
    assert query(unica(httpx_mock)) == {"url": ["https://tienda.example.com"], "id_integration": ["int1"]}


def test_una_tienda_con_claves_manda_el_formulario_plano(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    tienda = {
        **INTEGRACION,
        "provider": "woocommerce",
        "config": {
            "url": "https://tienda.example.com",
            "api_base": "wp-json",
            "auth_mode": "basic",
            "key_ending": "3f9a2c1",
            "tax_location_missing": False,
        },
    }
    httpx_mock.add_response(url=f"{ORG}/integrations", method="POST", json={"integration": tienda})

    conectada = cliente.esperar(
        cliente.pv.integrations.connect(
            "org1",
            {
                "provider": "woocommerce",
                "url": "https://tienda.example.com",
                "consumer_key": "ck_1",
                "consumer_secret": "cs_1",
            },
        )
    )

    assert cuerpo(unica(httpx_mock)) == {
        "provider": "woocommerce",
        "url": "https://tienda.example.com",
        "consumer_key": "ck_1",
        "consumer_secret": "cs_1",
    }
    # Lo que hay que ENSENAR de una tienda: que clave borrar al desconectar, y si sus precios valen
    assert conectada["config"].get("key_ending") == "3f9a2c1"
    assert conectada["config"].get("tax_location_missing") is False


def test_los_productos_de_una_tienda_paginan_por_cursor_opaco(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    pagina = {
        "items": [
            {"external_id": "68", "name": "Taza", "price": "14,52 EUR IVA incluido", "available": True},
            {"external_id": "71", "name": "Zapatillas", "available": False},
        ],
        "next_cursor": "p3",
    }
    httpx_mock.add_response(
        url=f"{ORG}/integrations/int1/products?cursor=p2&search=taza&limit=20", json=pagina
    )

    leida = cliente.esperar(
        cliente.pv.integrations.products("org1", "int1", cursor="p2", search="taza", limit=20)
    )

    # Sin sobre: la pagina llega tal cual, con el cursor opaco para devolverlo sin tocarlo
    assert leida == pagina
    assert leida.get("next_cursor") == "p3"
    # Lo agotado viene, pero marcado: no se deja elegir
    assert leida["items"][1]["available"] is False
    assert ruta(unica(httpx_mock)) == "/organizations/org1/integrations/int1/products"


def test_los_productos_sin_cursor_piden_la_primera_pagina(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(url=f"{ORG}/integrations/int1/products", json={"items": []})

    leida = cliente.esperar(cliente.pv.integrations.products("org1", "int1"))

    assert leida == {"items": []}
    assert query(unica(httpx_mock)) == {}


def test_la_configuracion_del_selector_llega_en_crudo(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Sin sobre, y con un token vivo dentro: se pide justo antes de abrir el Picker."""
    configuracion = {
        "access_token": "ya29.vivo",
        "expires_in": "3599",
        "developer_key": "AIzaSy",
        "app_id": "123456789012",
    }
    httpx_mock.add_response(url=f"{ORG}/integrations/int1/picker_config", json=configuracion)

    assert cliente.esperar(cliente.pv.integrations.picker_config("org1", "int1")) == configuracion
