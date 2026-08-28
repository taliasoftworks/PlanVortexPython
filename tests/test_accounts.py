"""Cuentas conectadas (capa 2), con los doce metodos del recurso.

Aqui vive el fallo mas caro de toda la fase, y tiene su propio test: **el callback de conexion
contesta 200 con el error dentro**. Es un apaño deliberado del servidor —el navegador aterriza ahi
desde una redireccion y un 400 crudo seria una pagina rota—, asi que un cliente que solo mire el
status da por conectada una cuenta que no existe. La libreria lo deshace y lanza.

Y el segundo, que no da error de ninguna clase: **`connect_links` devuelve WhatsApp con `link: ""`**
porque su alta es el *embedded signup* de Meta. Quien recorra la lista redirigiendo a `link` manda a
su usuario a su propia pagina. Se ramifica por `authorization["type"]`.
"""

from __future__ import annotations

import pytest
from pytest_httpx2 import HTTPXMock

from planvortex import AccountError, PlanLimitError, PlanVortexError
from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, query, ruta, unica

ORG = f"{BASE_URL}/organizations/org1"
CUENTA = {"_id": "acc1", "name": "Panaderia", "social_network": "instagram", "error_code": 0}


# ------------------------------------------------------------------------ el flujo de conexion


def test_connect_links_trae_una_entrada_por_red_y_whatsapp_sin_url(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """El sobre es `{links}`, y la de WhatsApp llega con `link` vacio y su `authorization` dentro."""
    httpx_mock.add_response(
        url=f"{ORG}/connect_links?social_network=instagram&social_network=whatsapp",
        json={
            "links": [
                {
                    "social_network": "instagram",
                    "link": "https://api.instagram.com/oauth?x=1",
                    "authorization": {"type": "redirect"},
                },
                {
                    "social_network": "whatsapp",
                    "link": "",
                    "authorization": {"type": "meta_embedded_signup", "app_id": "123"},
                },
            ]
        },
    )

    enlaces = cliente.esperar(
        cliente.pv.accounts.connect_links("org1", social_network=["instagram", "whatsapp"])
    )

    assert [enlace["social_network"] for enlace in enlaces] == ["instagram", "whatsapp"]
    assert enlaces[1]["link"] == ""
    assert enlaces[1]["authorization"]["type"] == "meta_embedded_signup"
    # La lista repetida, no aplanada con comas: es lo que `getArrayParams` entiende.
    assert query(unica(httpx_mock)) == {"social_network": ["instagram", "whatsapp"]}


def test_connect_pasa_los_parametros_de_la_red_tal_cual(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Cada red pega lo suyo a la URL de vuelta y se reenvia sin filtrar."""
    httpx_mock.add_response(
        url=f"{ORG}/account-connect/instagram?code=abc&state=xyz",
        json={"accounts": [CUENTA], "errorCode": "", "errorMsg": "", "redirect_uri": "https://mio.test/ok"},
    )

    resultado = cliente.esperar(
        cliente.pv.accounts.connect("org1", "instagram", {"code": "abc", "state": "xyz"})
    )

    assert resultado == {"accounts": [CUENTA], "redirect_uri": "https://mio.test/ok"}
    assert ruta(unica(httpx_mock)) == "/organizations/org1/account-connect/instagram"


def test_un_200_con_errorcode_dentro_se_convierte_en_excepcion(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """EL TEST QUE JUSTIFICA EL METODO. Un 200 que en realidad es un fallo, y con la clase correcta.

    Y con LA clase, no con una generica: el codigo se reconstruye como si hubiera venido en un
    cuerpo de error normal, asi que cae en su rango del catalogo. `706` es de cuentas y `1301` es de
    plan, y para quien llama son dos cosas distintas — "reconecta" contra "sube de plan".
    """
    httpx_mock.add_response(
        url=f"{ORG}/account-connect/instagram",
        json={"accounts": [], "errorCode": "706", "errorMsg": "La cuenta ya no autoriza"},
    )
    httpx_mock.add_response(
        url=f"{ORG}/account-connect/facebook",
        json={"accounts": [], "errorCode": "1301", "errorMsg": "No quedan cuentas en el plan"},
    )

    with pytest.raises(AccountError) as cuenta:
        cliente.esperar(cliente.pv.accounts.connect("org1", "instagram"))
    with pytest.raises(PlanLimitError) as plan:
        cliente.esperar(cliente.pv.accounts.connect("org1", "facebook"))

    assert (cuenta.value.code, cuenta.value.status) == (706, 200)
    assert (plan.value.code, plan.value.family) == (1301, "plan_limit")


def test_un_errorcode_que_no_es_un_numero_no_revienta(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Sigue siendo un fallo, y sigue saliendo como excepcion: lo que no puede es ser un `ValueError`."""
    httpx_mock.add_response(
        url=f"{ORG}/account-connect/facebook", json={"errorCode": "algo_raro", "errorMsg": ""}
    )

    with pytest.raises(PlanVortexError) as fallo:
        cliente.esperar(cliente.pv.accounts.connect("org1", "facebook"))

    assert fallo.value.code == 0
    assert "algo_raro" in fallo.value.message


def test_enable_solo_devuelve_el_destino_cuando_lo_hay(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """`success: true` no se pasa: un fallo llega como excepcion, asi que no dice nada."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/enable", method="POST", json={"success": True, "redirect_uri": "https://x"}
    )
    httpx_mock.add_response(url=f"{ORG}/accounts/acc2/enable", method="POST", json={"success": True})

    assert cliente.esperar(cliente.pv.accounts.enable("org1", "acc1")) == {"redirect_uri": "https://x"}
    assert cliente.esperar(cliente.pv.accounts.enable("org1", "acc2")) == {}


# --------------------------------------------------------------------------- el resto del CRUD


def test_lista_y_filtra_por_capacidad(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """`capability` lo resuelve el servidor con la misma matriz que publica el catalogo."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts?limit=10&capability=publications&social_network=instagram"
        "&accounts=acc1&name=Pan",
        json={"accounts": [CUENTA], "total": 1},
    )

    pagina = cliente.esperar(
        cliente.pv.accounts.list(
            "org1",
            limit=10,
            capability="publications",
            social_network=["instagram"],
            accounts=["acc1"],
            name="Pan",
        )
    )

    assert pagina.data == [CUENTA]
    assert query(unica(httpx_mock))["capability"] == ["publications"]


def test_iterate_encadena_las_cuentas(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/accounts?limit=1&offset=0", json={"accounts": [CUENTA], "total": 2})
    httpx_mock.add_response(url=f"{ORG}/accounts?limit=1&offset=1", json={"accounts": [], "total": 2})

    assert cliente.iterar(cliente.pv.accounts, "aiterate", "org1", limit=1) == [CUENTA]


def test_lee_actualiza_y_borra_una_cuenta(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/accounts/acc1", json={"account": CUENTA})
    httpx_mock.add_response(url=f"{ORG}/accounts/acc1", method="PUT", json={"account": CUENTA})
    httpx_mock.add_response(url=f"{ORG}/accounts/acc1", method="DELETE", json={"success": True})

    assert cliente.esperar(cliente.pv.accounts.get("org1", "acc1")) == CUENTA
    assert cliente.esperar(cliente.pv.accounts.update("org1", "acc1", {"name": "Obrador"})) == CUENTA
    assert cliente.esperar(cliente.pv.accounts.remove("org1", "acc1")) is None

    assert cuerpo(peticiones(httpx_mock)[1]) == {"name": "Obrador"}


def test_las_metricas_y_sus_nombres_crudos(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """`names` va con los nombres CRUDOS de la red, repetidos, y `metric_list` es quien los da."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/metrics?names=page_impressions&names=page_fans",
        json={"group": "day", "metrics": []},
    )
    httpx_mock.add_response(url=f"{ORG}/accounts/acc1/metric_list", json=["page_impressions", "page_fans"])

    metricas = cliente.esperar(
        cliente.pv.accounts.metrics("org1", "acc1", names=["page_impressions", "page_fans"])
    )
    nombres = cliente.esperar(cliente.pv.accounts.metric_list("org1", "acc1"))

    assert metricas["group"] == "day"
    assert nombres == ["page_impressions", "page_fans"]
    assert query(peticiones(httpx_mock)[0])["names"] == ["page_impressions", "page_fans"]


def test_una_fecha_naive_en_las_metricas_no_llega_a_salir(cliente: ClienteDePrueba) -> None:
    """§ Trampa P8, en un filtro y no solo al publicar. Y sin peticion: falla antes de salir."""
    from datetime import datetime

    from planvortex import PlanVortexConfigError

    with pytest.raises(PlanVortexConfigError, match="naive"):
        cliente.esperar(cliente.pv.accounts.metrics("org1", "acc1", from_date=datetime(2026, 8, 1, 10, 0)))


def test_el_menu_persistente_se_lee_y_se_reemplaza(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Es un REEMPLAZO y viaja envuelto en `{persistent_menu: [...]}` en las dos direcciones."""
    menu = [{"locale": "default", "call_to_actions": []}]
    httpx_mock.add_response(url=f"{ORG}/accounts/acc1/persistent_menu", json={"persistent_menu": menu})
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/persistent_menu", method="POST", json={"persistent_menu": menu}
    )

    assert cliente.esperar(cliente.pv.accounts.get_persistent_menu("org1", "acc1")) == menu
    assert cliente.esperar(cliente.pv.accounts.set_persistent_menu("org1", "acc1", menu)) == menu
    assert cuerpo(peticiones(httpx_mock)[1]) == {"persistent_menu": menu}


def test_una_cuenta_rota_sigue_en_la_lista(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """`error_code` distinto de 0 no es un fallo de ESTA llamada: es una cuenta que hay que reconectar."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts", json={"accounts": [{**CUENTA, "error_code": 700}], "total": 1}
    )

    pagina = cliente.esperar(cliente.pv.accounts.list("org1"))

    assert pagina.data[0]["error_code"] == 700
    assert pagina.total == 1


def test_connect_sin_redirect_no_inventa_un_destino(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Solo viaja cuando el token temporal traia uno. Inventar una cadena vacia mandaria al usuario
    a la raiz del sitio de quien integra, que es peor que no mandarlo a ninguna parte.
    """
    httpx_mock.add_response(url=f"{ORG}/account-connect/instagram", json={"accounts": [CUENTA]})

    assert cliente.esperar(cliente.pv.accounts.connect("org1", "instagram")) == {"accounts": [CUENTA]}


def test_un_identificador_vacio_falla_antes_de_salir(cliente: ClienteDePrueba) -> None:
    """Un `""` interpolado en la ruta da un 404 de `/organizations//accounts`, y ese error no dice
    lo que paso — que a quien llama se le olvido un argumento.
    """
    with pytest.raises(TypeError, match="id_organization"):
        cliente.esperar(cliente.pv.accounts.list(""))

    with pytest.raises(TypeError, match="id_account"):
        cliente.esperar(cliente.pv.accounts.get("org1", "   "))
