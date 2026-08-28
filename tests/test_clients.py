"""Clientes y sus organizaciones raiz (capa 2), con los once metodos del recurso.

Lo que aqui importa mas que el resto: **`getUse` viaja en camelCase**. Es la § Trampa P2 vista desde
el otro lado — el mapa se comprueba contra el spec en `test_query_parity.py`, y aqui se comprueba
que los metodos lo USAN. Un `?get_use=true` que el servidor no lee no da error: devuelve la lista
entera sin `actual_use`, y quien llama se entera semanas despues pintando un cero.
"""

from __future__ import annotations

from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, query, ruta, unica

CLIENTE = {"_id": "cli1", "name": "Panaderia Vega"}
ORGANIZACION = {"_id": "org1", "name": "Central"}


def test_lista_los_clientes_y_desenvuelve_el_sobre(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """El sobre es `{clients, total}` y sale como `Page(data, total)`."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients?limit=2&offset=0", json={"clients": [CLIENTE], "total": 7}
    )

    pagina = cliente.esperar(cliente.pv.clients.list(limit=2, offset=0))

    assert pagina.data == [CLIENTE]
    assert pagina.total == 7
    assert len(pagina) == 1
    assert ruta(unica(httpx_mock)) == "/clients"


def test_get_use_sale_en_camelcase_y_solo_cuando_se_pide(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Los dos lados: `getUse=true` cuando se pide, y NADA cuando no.

    Un `getUse=false` en la query es ruido —el servidor lo compara contra la cadena "true"— y un
    `get_use` en snake_case no lo lee nadie.
    """
    httpx_mock.add_response(url=f"{BASE_URL}/clients?getUse=true", json={"clients": [], "total": 0})
    httpx_mock.add_response(url=f"{BASE_URL}/clients", json={"clients": [], "total": 0})

    cliente.esperar(cliente.pv.clients.list(get_use=True))
    cliente.esperar(cliente.pv.clients.list(get_use=False))

    primera, segunda = (query(peticion) for peticion in peticiones(httpx_mock))
    assert primera == {"getUse": ["true"]}
    assert segunda == {}


def test_lee_y_actualiza_un_cliente(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE_URL}/clients/cli1?getUse=true", json={"client": CLIENTE})
    httpx_mock.add_response(url=f"{BASE_URL}/clients/cli1", method="PUT", json={"client": CLIENTE})

    assert cliente.esperar(cliente.pv.clients.get("cli1", get_use=True)) == CLIENTE
    assert cliente.esperar(cliente.pv.clients.update("cli1", {"name": "Panaderia Vega"})) == CLIENTE

    lectura, escritura = peticiones(httpx_mock)
    assert ruta(lectura) == "/clients/cli1"
    assert escritura.method == "PUT"
    assert cuerpo(escritura) == {"name": "Panaderia Vega"}


def test_las_organizaciones_raiz_con_su_busqueda_por_nombre(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations?name=Central&limit=10",
        json={"organizations": [ORGANIZACION], "total": 1},
    )

    pagina = cliente.esperar(cliente.pv.clients.organizations("cli1", name="Central", limit=10))

    assert pagina.data == [ORGANIZACION]
    assert query(unica(httpx_mock)) == {"name": ["Central"], "limit": ["10"]}


def test_crea_actualiza_y_borra_una_organizacion_raiz(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """El borrado se lleva por delante todo lo de dentro, y no devuelve nada que desenvolver."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations", method="POST", json={"organization": ORGANIZACION}
    )
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations/org1",
        method="PUT",
        json={"organization": ORGANIZACION},
    )
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations/org1", method="DELETE", json={"success": True}
    )

    creada = cliente.esperar(cliente.pv.clients.create_organization("cli1", {"name": "Central"}))
    editada = cliente.esperar(
        cliente.pv.clients.update_organization("cli1", "org1", {"actual_plan": {"accounts": 5}})
    )
    assert cliente.esperar(cliente.pv.clients.delete_organization("cli1", "org1")) is None

    assert creada == editada == ORGANIZACION
    crear, editar, borrar = peticiones(httpx_mock)
    assert cuerpo(crear) == {"name": "Central"}
    assert cuerpo(editar) == {"actual_plan": {"accounts": 5}}
    assert borrar.method == "DELETE"


def test_los_ajustes_de_ia_se_mandan_y_no_vuelven(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """La clave viaja en el cuerpo; la respuesta es el cliente, sin secretos. Y un ambito a `None`
    borra su configuracion, asi que el `None` TIENE que llegar al servidor y no filtrarse.
    """
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/ai-settings", method="PUT", json={"client": CLIENTE}
    )

    ajustes = {"text": {"provider": "openai", "api_key": "sk-secreto"}, "image": None}
    assert cliente.esperar(cliente.pv.clients.update_ai_settings("cli1", ajustes)) == CLIENTE
    assert cuerpo(unica(httpx_mock)) == ajustes


def test_el_atajo_con_las_organizaciones_dentro(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Una llamada en vez de 1 + N, y con la paginacion del array interior en camelCase."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients_organizations?limitOrganizations=5&offsetOrganizations=0",
        json={"clients": [{**CLIENTE, "organizations": [ORGANIZACION], "total": 1}], "total": 1},
    )

    pagina = cliente.esperar(
        cliente.pv.clients.with_organizations(limit_organizations=5, offset_organizations=0)
    )

    assert pagina.data[0]["organizations"] == [ORGANIZACION]
    assert query(unica(httpx_mock)) == {"limitOrganizations": ["5"], "offsetOrganizations": ["0"]}


def test_iterate_encadena_paginas_de_clientes(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Dos paginas llenas y una corta: la corta corta el bucle sin pedir una cuarta."""
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients?limit=2&offset=0", json={"clients": [CLIENTE, CLIENTE], "total": 5}
    )
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients?limit=2&offset=2", json={"clients": [CLIENTE, CLIENTE], "total": 5}
    )
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients?limit=2&offset=4", json={"clients": [CLIENTE], "total": 5}
    )

    todos = cliente.iterar(cliente.pv.clients, "aiterate", limit=2)

    assert len(todos) == 5
    assert [query(peticion)["offset"] for peticion in peticiones(httpx_mock)] == [["0"], ["2"], ["4"]]


def test_iterate_organizations_encadena_las_raiz(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations?limit=1&offset=0",
        json={"organizations": [ORGANIZACION], "total": 2},
    )
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations?limit=1&offset=1",
        json={"organizations": [], "total": 2},
    )

    organizaciones = cliente.iterar(cliente.pv.clients, "aiterate_organizations", "cli1", limit=1)
    assert organizaciones == [ORGANIZACION]
