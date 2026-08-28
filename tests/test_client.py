"""El cliente: credenciales, cabeceras, el reintento del token y el token temporal.

Tres cosas que solo se pueden comprobar aqui, porque son del objeto y no de ningun recurso:

- **Las credenciales salen del entorno cuando no se pasan**, que es como se usa de verdad. Y sin
  ninguna de las dos vias, el fallo tiene que ser en la CONSTRUCCION y no en la primera llamada:
  un `PlanVortexConfigError` al arrancar el proceso se ve; un 401 tres pantallas mas adelante, no.
- **Un token muerto se reintenta UNA vez.** Un token puede morir antes de su `expires_in` —un
  despliegue de Keycloak, la app revocada— y ese caso se arregla pidiendo otro. Dos veces seria un
  bucle contra un servidor que esta diciendo que no.
- **Ese reintento respeta las reglas del cuerpo.** Con una subida en marcha, los bytes ya se fueron:
  repetir subiria cero y pareceria que funciono.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

import pytest
from pytest_httpx2 import HTTPXMock

from planvortex import AsyncPlanVortex, AuthError, PlanVortex, PlanVortexConfigError
from planvortex._core.transport import HttpRequest, RetryConfig
from planvortex._version import VERSION
from tests.conftest import BASE_URL, ClienteDePrueba, stub_token
from tests.contrato import peticiones, unica

ORG = f"{BASE_URL}/organizations/org1"
CUENTA = {"_id": "acc1"}


# -------------------------------------------------------------------------------- construccion


def test_las_credenciales_salen_del_entorno(
    nucleo: Any, httpx_mock: HTTPXMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLANVORTEX_CLIENT_ID", "del-entorno")
    monkeypatch.setenv("PLANVORTEX_CLIENT_SECRET", "secreto")
    monkeypatch.setenv("PLANVORTEX_BASE_URL", BASE_URL)
    stub_token(httpx_mock)
    httpx_mock.add_response(url=f"{ORG}/accounts", json={"accounts": [], "total": 0})

    pv = nucleo.plan_vortex()
    try:
        assert pv.base_url == BASE_URL
        nucleo.esperar(pv.accounts.list("org1"))
    finally:
        nucleo.cerrar(pv)

    token = next(p for p in httpx_mock.get_requests() if p.url.path.endswith("/oauth/token"))
    assert b"client_id=del-entorno" in token.content


def test_sin_credenciales_falla_al_construir_y_no_al_llamar(
    nucleo: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El fallo se ve al arrancar el proceso. Un 401 tres pantallas mas adelante, no."""
    for variable in ("PLANVORTEX_CLIENT_ID", "PLANVORTEX_CLIENT_SECRET"):
        monkeypatch.delenv(variable, raising=False)

    with pytest.raises(PlanVortexConfigError, match="client_id"):
        nucleo.plan_vortex(base_url=BASE_URL)


def test_la_barra_final_de_la_base_url_se_quita(nucleo: Any) -> None:
    """Una barra de mas convierte cada ruta en `//organizations`, que es un 404 raro."""
    pv = nucleo.plan_vortex(client_id="a", client_secret="b", base_url=f"{BASE_URL}///")
    try:
        assert pv.base_url == BASE_URL
    finally:
        nucleo.cerrar(pv)


def test_el_user_agent_lleva_la_version_y_la_de_python(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Las dos mitades se buscan en un log: cual de las nuestras falla, y en que fila de la matriz."""
    httpx_mock.add_response(url=f"{ORG}/accounts", json={"accounts": [], "total": 0})

    cliente.esperar(cliente.pv.accounts.list("org1"))

    agente = unica(httpx_mock).headers["user-agent"]
    assert agente.startswith(f"planvortex-python/{VERSION} python/")


def test_los_seis_recursos_estan_y_son_los_mismos_objetos(cliente: ClienteDePrueba) -> None:
    """De la fase 5. Y siempre el mismo objeto, que es de lo que depende la cache del catalogo."""
    nombres = ("catalog", "clients", "organizations", "accounts", "uploads", "publications")
    for nombre in nombres:
        assert getattr(cliente.pv, nombre) is getattr(cliente.pv, nombre)


RECURSOS = ("catalog", "clients", "organizations", "accounts", "uploads", "publications")


def _publicos(clase: type) -> set[str]:
    return {nombre for nombre in vars(clase) if not nombre.startswith("_")}


BASES = ("Resource", "AsyncResource")


def _clase_del_recurso(modulo: str, nombre: str, prefijo: str) -> type:
    """La clase `...Resource` de un modulo de recurso, sea la asincrona o la generada."""
    importado = import_module(f"{modulo}.{nombre}")
    clase: type = next(
        valor
        for clave, valor in vars(importado).items()
        if clave.endswith("Resource") and clave.startswith(prefijo) and clave not in BASES
    )
    return clase


def test_los_dos_clientes_tienen_la_misma_superficie() -> None:
    """El gemelo se genera, asi que esto no puede fallar... salvo que alguien lo edite a mano.

    `aclose` contra `close` es la unica diferencia del cliente, y es la que se anuncia.
    """
    asincronos = {nombre.replace("aclose", "close") for nombre in _publicos(AsyncPlanVortex)}
    assert asincronos == _publicos(PlanVortex)


@pytest.mark.parametrize("recurso", RECURSOS)
def test_cada_recurso_tiene_los_mismos_metodos_en_las_dos_variantes(recurso: str) -> None:
    """Un metodo que se pierda al traducir no rompe NADA del lado async: el cliente sincrono
    simplemente se queda sin el, y nadie se entera hasta que un integrador lo llama.
    """
    asincrono = _clase_del_recurso("planvortex.resources", recurso, "Async")
    sincrono = _clase_del_recurso("planvortex.resources_sync", recurso, "")

    traducidos = {metodo.replace("aiterate", "iterate") for metodo in _publicos(asincrono)}
    assert traducidos == _publicos(sincrono)


# ---------------------------------------------------------------------- el reintento del token


def test_un_token_muerto_se_reintenta_una_vez(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """El 501 llega dentro de un 400, como todo en esta API. Se pide otro token y se repite."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts", status_code=400, json={"code": 501, "message": "Token caducado"}
    )
    httpx_mock.add_response(url=f"{ORG}/accounts", json={"accounts": [CUENTA], "total": 1})

    pagina = cliente.esperar(cliente.pv.accounts.list("org1"))

    assert pagina.data == [CUENTA]
    assert len(peticiones(httpx_mock)) == 2


def test_si_el_segundo_intento_tambien_falla_el_error_sale(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Dos veces y no mas: no es un bucle contra un servidor que esta diciendo que no."""
    for _ in range(2):
        httpx_mock.add_response(
            url=f"{ORG}/accounts", status_code=400, json={"code": 522, "message": "App revocada"}
        )

    with pytest.raises(AuthError) as fallo:
        cliente.esperar(cliente.pv.accounts.list("org1"))

    assert fallo.value.code == 522
    assert len(peticiones(httpx_mock)) == 2


def test_un_error_que_no_es_de_token_no_se_repite(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Repetir "el texto es demasiado largo" no lo arregla, y en esta API tambien llega con un 400."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts", status_code=400, json={"code": 1101, "message": "No existe"}
    )

    with pytest.raises(Exception, match="No existe"):
        cliente.esperar(cliente.pv.accounts.list("org1"))

    assert len(peticiones(httpx_mock)) == 1


def test_un_cuerpo_que_no_se_puede_repetir_no_se_repite_ni_por_el_token(
    nucleo: Any, httpx_mock: HTTPXMock
) -> None:
    """Los bytes de una subida ya se fueron: el segundo intento subiria cero y pareceria que fue bien.

    Se comprueba sobre `pv.request` y no sobre `uploads.create` porque lo que se esta fijando es la
    regla del CLIENTE, y montarla con un fichero de verdad la escondería detras del multipart.
    """
    stub_token(httpx_mock)
    httpx_mock.add_response(
        url=f"{ORG}/uploads", method="POST", status_code=400, json={"code": 501, "message": "Caducado"}
    )

    pv = nucleo.plan_vortex(
        client_id="a", client_secret="b", base_url=BASE_URL, retry=RetryConfig(max_retries=0)
    )
    try:
        with pytest.raises(AuthError):
            nucleo.esperar(
                pv.request(
                    HttpRequest(method="POST", path="/organizations/org1/uploads", files={}, repeatable=False)
                )
            )
    finally:
        nucleo.cerrar(pv)

    assert len(peticiones(httpx_mock)) == 1


# ------------------------------------------------------------------------------ token temporal


def test_as_temporal_token_conserva_la_configuracion_y_cambia_el_credencial(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """El invitado manda el token TAL CUAL, sin pedir ninguno: es lo que un token temporal es."""
    httpx_mock.add_response(url=f"{ORG}/connect_links", json={"links": []})

    invitado = cliente.pv.as_temporal_token("token-de-quince-minutos")
    try:
        assert invitado.base_url == cliente.pv.base_url
        assert cliente.esperar(invitado.accounts.connect_links("org1")) == []
    finally:
        cliente.nucleo.cerrar(invitado)

    peticion = unica(httpx_mock)
    assert peticion.headers["authorization"] == "Bearer token-de-quince-minutos"
    # Y NO pidio token: un token temporal no se renueva, y pedir otro contesta 514.
    assert not [p for p in httpx_mock.get_requests() if p.url.path.endswith("/oauth/token")]


def test_el_cliente_cierra_su_conexion(nucleo: Any) -> None:
    """Y el gestor de contexto es la forma que se anuncia en el README."""
    pv = nucleo.plan_vortex(client_id="a", client_secret="b", base_url=BASE_URL)
    nucleo.cerrar(pv)
    nucleo.cerrar(pv)  # cerrar dos veces no revienta
