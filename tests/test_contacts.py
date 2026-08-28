"""Contactos (capa 2): la agenda, y el agujero de `extra_data`.

Lo que se fija aqui:

- **El filtro por red YA FUNCIONA.** Comparaba el array de objetos contra la cadena de la red y
  devolvia siempre vacio; se arreglo en el servidor el 2026-08-24. Esta libreria lo expone y la de
  Node todavia lo documenta como roto.
- **`extra_data` viaja indexado** (`extra_data[0][key]`), que es como Express lo vuelve a montar en
  un array de objetos.
- **Actualizar NO devuelve el contacto**: la API contesta `{success: true}`.
- **`merge` son dos peticiones**, y existe porque un `update` sin `extra_data` BORRA los campos
  propios del contacto.
"""

from __future__ import annotations

from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, query, ruta, unica

ORG = f"{BASE_URL}/organizations/org1"
CONTACTO = {
    "_id": "con1",
    "id_organization": "org1",
    "name": "Marta",
    "social_identifiers": [{"_id": "si1", "social_network": "whatsapp", "external_identifier": "34600"}],
    "extra_data": {"city": "Madrid", "custom_1": "clienta desde 2024"},
}


def test_la_agenda_filtra_por_red_y_por_campos_propios(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url=(
            f"{ORG}/contacts?limit=10&search=Marta&social_network=whatsapp"
            "&extra_data%5B0%5D%5Bkey%5D=city&extra_data%5B0%5D%5Bvalue%5D=Madrid"
            "&extra_data%5B0%5D%5Bvalue%5D=Toledo"
        ),
        json={"contacts": [CONTACTO], "total": 1},
    )

    pagina = cliente.esperar(
        cliente.pv.contacts.list(
            "org1",
            limit=10,
            search="Marta",
            social_network="whatsapp",
            extra_data=[{"key": "city", "value": ["Madrid", "Toledo"]}],
        )
    )

    assert pagina.data == [CONTACTO]
    assert query(unica(httpx_mock)) == {
        "limit": ["10"],
        "search": ["Marta"],
        "social_network": ["whatsapp"],
        "extra_data[0][key]": ["city"],
        # Una lista de valores se lee como "cualquiera de", y viaja repetida como las demas.
        "extra_data[0][value]": ["Madrid", "Toledo"],
    }


def test_la_agenda_encadena_paginas(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/contacts?limit=1&offset=0", json={"contacts": [CONTACTO], "total": 2})
    httpx_mock.add_response(url=f"{ORG}/contacts?limit=1&offset=1", json={"contacts": [], "total": 2})

    assert cliente.iterar(cliente.pv.contacts, "aiterate", "org1", limit=1) == [CONTACTO]


def test_leer_y_crear(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Crear es idempotente sobre el primer identificador: puede devolver el que ya habia."""
    httpx_mock.add_response(url=f"{ORG}/contacts/con1", json={"contact": CONTACTO})
    httpx_mock.add_response(url=f"{ORG}/contacts", method="POST", json={"contact": CONTACTO})

    leido = cliente.esperar(cliente.pv.contacts.get("org1", "con1"))
    creado = cliente.esperar(
        cliente.pv.contacts.create(
            "org1",
            {
                "name": "Marta",
                "social_identifiers": [{"social_network": "whatsapp", "external_identifier": "34600"}],
            },
        )
    )

    assert leido == creado == CONTACTO
    assert cuerpo(peticiones(httpx_mock)[-1])["social_identifiers"][0]["external_identifier"] == "34600"


def test_actualizar_no_devuelve_el_contacto(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/contacts/con1", method="PUT", json={"success": True})

    assert cliente.esperar(cliente.pv.contacts.update("org1", "con1", {"name": "Marta G."})) is None
    assert cuerpo(unica(httpx_mock)) == {"name": "Marta G."}


def test_merge_lee_antes_para_no_borrar_los_campos_propios(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """EL TEST QUE JUSTIFICA EL METODO. `extra_data` es el unico campo que el servidor PISA."""
    httpx_mock.add_response(url=f"{ORG}/contacts/con1", json={"contact": CONTACTO})
    httpx_mock.add_response(url=f"{ORG}/contacts/con1", method="PUT", json={"success": True})

    cliente.esperar(
        cliente.pv.contacts.merge("org1", "con1", {"name": "Marta G.", "extra_data": {"city": "Toledo"}})
    )

    leer, escribir = peticiones(httpx_mock)
    assert leer.method == "GET"
    assert cuerpo(escribir) == {
        "name": "Marta G.",
        # `city` cambia y `custom_1` SOBREVIVE, que es justo lo que un `update` pelado se llevaria.
        "extra_data": {"city": "Toledo", "custom_1": "clienta desde 2024"},
    }


def test_borrar_uno_y_borrarlos_todos(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/contacts/con1", method="DELETE", json={"success": True})
    httpx_mock.add_response(url=f"{ORG}/contacts", method="DELETE", json={"success": True})

    assert cliente.esperar(cliente.pv.contacts.remove("org1", "con1")) is None
    assert cliente.esperar(cliente.pv.contacts.remove_all("org1")) is None

    uno, todos = peticiones(httpx_mock)
    assert ruta(uno) == "/organizations/org1/contacts/con1"
    assert ruta(todos) == "/organizations/org1/contacts"
