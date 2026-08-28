"""Apps de cliente (capa 2): las credenciales con las que se integra un tercero.

Lo que se fija aqui:

- **El sobre es `client_apps` / `client_app`**, con guion bajo, y no `apps`.
- **El secreto es OTRA llamada** y llega en `{secret}`: no esta en la ficha porque no vive en
  PlanVortex, vive en Keycloak.
- **Actualizar REEMPLAZA los cinco campos**, asi que el test manda la app entera: es la forma de uso
  correcta, y lo contrario apaga el webhook sin decirlo.
"""

from __future__ import annotations

from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, ruta, unica

APPS = f"{BASE_URL}/clients/cli1/apps"
APP = {
    "_id": "app1",
    "id_client": "cli1",
    "name": "Mi integracion",
    "keycloak_client_idenfifier": "mi-integracion",
    "allowed_domains": ["https://mio.test"],
    "redirect_urls": ["https://mio.test/ok"],
    "webhook_url": "https://mio.test/planvortex",
}


def test_la_lista_trae_como_mucho_una(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Un cliente solo puede tener UNA app: crear la segunda contesta 536."""
    httpx_mock.add_response(url=f"{APPS}?limit=10", json={"client_apps": [APP], "total": 1})

    pagina = cliente.esperar(cliente.pv.apps.list("cli1", limit=10))

    assert (pagina.data, pagina.total) == ([APP], 1)
    assert ruta(unica(httpx_mock)) == "/clients/cli1/apps"


def test_leer_crear_y_actualizar(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{APPS}/app1", json={"client_app": APP})
    httpx_mock.add_response(url=APPS, method="POST", json={"client_app": APP})
    httpx_mock.add_response(url=f"{APPS}/app1", method="PUT", json={"client_app": {**APP, "name": "Otra"}})

    leida = cliente.esperar(cliente.pv.apps.get("cli1", "app1"))
    creada = cliente.esperar(
        cliente.pv.apps.create(
            "cli1", {"name": "Mi integracion", "keycloak_client_idenfifier": "mi-integracion"}
        )
    )
    cambiada = cliente.esperar(cliente.pv.apps.update("cli1", "app1", {**APP, "name": "Otra"}))

    assert leida == creada == APP
    assert cambiada["name"] == "Otra"
    _, crear, actualizar = peticiones(httpx_mock)
    assert cuerpo(crear)["keycloak_client_idenfifier"] == "mi-integracion"
    # Se manda entera: el PUT escribe los cinco campos con lo que llegue.
    assert cuerpo(actualizar)["webhook_url"] == "https://mio.test/planvortex"


def test_el_secreto_es_otra_llamada(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{APPS}/app1/secret", json={"secret": "s3cr3t-vivo"})

    assert cliente.esperar(cliente.pv.apps.secret("cli1", "app1")) == "s3cr3t-vivo"
    assert ruta(unica(httpx_mock)) == "/clients/cli1/apps/app1/secret"


def test_borrar(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{APPS}/app1", method="DELETE", json={"success": True})

    assert cliente.esperar(cliente.pv.apps.remove("cli1", "app1")) is None
    assert unica(httpx_mock).method == "DELETE"
