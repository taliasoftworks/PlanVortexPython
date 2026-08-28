"""Productos y catalogos de Meta Commerce (capa 2).

Lo que se fija aqui:

- **El sobre se llama `items`**, no `products`, en las dos listas.
- **`product_id` YA llega a la red** (arreglado en el servidor el 2026-08-24), y la respuesta de
  pedir UNO tiene otra forma: `items` trae el objeto, no una lista. Por eso es un metodo aparte y
  no un argumento de `list`: con un objeto no se puede construir una `Page`.
- **Crear devuelve una CADENA**, el identificador en la red, y en el catalogo el campo se llama
  `product_catalog`.
- **`total` no sirve para paginar**: en productos vale siempre 0, asi que el iterador tiene que
  cortar por pagina corta.
"""

from __future__ import annotations

import pytest
from pytest_httpx2 import HTTPXMock

from planvortex import PlanVortexError
from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, query, ruta, unica

CUENTA = f"{BASE_URL}/organizations/org1/accounts/acc1"
PRODUCTO = {
    "id": "1122334455",
    "retailer_id": "HOGAZA-1",
    "name": "Hogaza de masa madre",
    "price": 450,
    "currency": "EUR",
    "image_url": "https://cdn.test/hogaza.jpg",
}


def test_los_productos_de_un_catalogo(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{CUENTA}/products?product_catalog_id=cat1&limit=50",
        json={"items": [PRODUCTO], "total": 0},
    )

    pagina = cliente.esperar(cliente.pv.products.list("org1", "acc1", "cat1", limit=50))

    assert pagina.data == [PRODUCTO]
    assert query(unica(httpx_mock)) == {"product_catalog_id": ["cat1"], "limit": ["50"]}


def test_el_iterador_corta_por_pagina_corta_y_no_por_total(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """`total` vale 0 siempre: un iterador que lo mirase no daria ni una vuelta."""
    httpx_mock.add_response(
        url=f"{CUENTA}/products?product_catalog_id=cat1&limit=2&offset=0",
        json={"items": [PRODUCTO, PRODUCTO], "total": 0},
    )
    httpx_mock.add_response(
        url=f"{CUENTA}/products?product_catalog_id=cat1&limit=2&offset=2",
        json={"items": [PRODUCTO], "total": 0},
    )

    todos = cliente.iterar(cliente.pv.products, "aiterate", "org1", "acc1", "cat1", limit=2)

    assert len(todos) == 3


def test_pedir_un_producto_suelto_admite_las_dos_formas(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Meta contesta con el producto, no con una lista, porque la peticion va a su nodo."""
    httpx_mock.add_response(
        url=f"{CUENTA}/products?product_id=1122334455", json={"items": PRODUCTO, "total": 0}
    )
    httpx_mock.add_response(
        url=f"{CUENTA}/products?product_id=1122334455", json={"items": [PRODUCTO], "total": 0}
    )

    objeto = cliente.esperar(cliente.pv.products.get("org1", "acc1", "1122334455"))
    lista = cliente.esperar(cliente.pv.products.get("org1", "acc1", "1122334455"))

    assert objeto == lista == PRODUCTO
    assert query(peticiones(httpx_mock)[0]) == {"product_id": ["1122334455"]}


def test_crear_un_producto_devuelve_su_identificador_en_la_red(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url=f"{CUENTA}/products?product_catalog_id=cat1",
        method="POST",
        json={"product_id": "1122334455"},
    )

    creado = cliente.esperar(cliente.pv.products.create("org1", "acc1", "cat1", PRODUCTO))

    assert creado == "1122334455"
    # El catalogo va en la QUERY aunque sea un POST, que es lo que el servidor lee.
    assert query(unica(httpx_mock)) == {"product_catalog_id": ["cat1"]}
    assert cuerpo(unica(httpx_mock))["retailer_id"] == "HOGAZA-1"


def test_los_catalogos_se_listan_se_iteran_y_se_crean(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    catalogo = {"id": "cat1", "name": "Panaderia"}
    httpx_mock.add_response(
        url=f"{CUENTA}/products_catalogs?limit=1&offset=0", json={"items": [catalogo], "total": 1}
    )
    httpx_mock.add_response(
        url=f"{CUENTA}/products_catalogs?limit=1&offset=1", json={"items": [], "total": 0}
    )
    httpx_mock.add_response(
        url=f"{CUENTA}/products_catalogs", method="POST", json={"product_catalog": "cat2"}
    )

    todos = cliente.iterar(cliente.pv.products, "aiterate_catalogs", "org1", "acc1", limit=1)
    creado = cliente.esperar(cliente.pv.products.create_catalog("org1", "acc1", {"name": "Nueva"}))

    assert todos == [catalogo]
    # Crear devuelve una CADENA en un campo que se llama `product_catalog`, no el catalogo entero.
    assert creado == "cat2"
    assert ruta(peticiones(httpx_mock)[-1]) == "/organizations/org1/accounts/acc1/products_catalogs"


def test_un_producto_que_no_existe_no_devuelve_none(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Una lista vacia es "no esta", y eso es un error, no un producto vacio colandose adelante."""
    httpx_mock.add_response(url=f"{CUENTA}/products?product_id=nope", json={"items": [], "total": 0})

    with pytest.raises(PlanVortexError) as fallo:
        cliente.esperar(cliente.pv.products.get("org1", "acc1", "nope"))

    assert fallo.value.data == {"product_id": "nope"}
