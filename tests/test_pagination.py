"""El sobre y el encadenado de paginas (capa 1: sin red).

Dos piezas y dos motivos.

**El sobre**, porque el fallo que tapa no da error: la API envuelve cada lista con el nombre de su
recurso —`{publications, total}`, `{accounts, total}`— y un metodo que desenvuelva el campo
equivocado devolveria `None` y el fallo apareceria tres capas mas arriba. Es literalmente lo que le
paso al spec de publicaciones, que anunciaba `{uploads, total}`.

**El tope de paginas**, porque el fallo que tapa es peor que un error: un servidor que ignorase el
`offset` devolveria la misma pagina para siempre y un `for` sin tope se lleva por delante el proceso
del integrador. `MAX_PAGES` no es un limite de uso — a 100 elementos por pagina es un millon.
"""

from __future__ import annotations

import re
from typing import Any

import pytest

from planvortex import MAX_PAGES, Page, PlanVortexError
from planvortex._core.pagination import PageParams, unwrap_list, unwrap_one
from planvortex.resources import base as base_async
from planvortex.resources_sync import base as base_sync
from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import peticiones, query

ORG = f"{BASE_URL}/organizations/org1"
CUENTA = {"_id": "acc1"}


# ------------------------------------------------------------------------------------ el sobre


def test_el_sobre_se_abre_por_su_nombre_exacto() -> None:
    pagina = unwrap_list({"accounts": [CUENTA], "total": 42}, "accounts")

    assert pagina.data == [CUENTA]
    assert pagina.total == 42


def test_un_sobre_con_otro_nombre_se_dice_en_voz_alta() -> None:
    """Y el error dice QUE se esperaba y QUE llego, que es lo unico util a las tres de la manana."""
    with pytest.raises(PlanVortexError) as fallo:
        unwrap_list({"uploads": [], "total": 0}, "publications")

    assert fallo.value.family == "http"
    assert fallo.value.data == {"expected": "publications", "received": ["total", "uploads"]}


def test_sin_total_la_longitud_de_la_pagina_es_mejor_que_un_none() -> None:
    """Un despliegue viejo que no lo mande no puede colar un `None` donde va un numero."""
    assert unwrap_list({"accounts": [CUENTA]}, "accounts").total == 1


def test_un_total_booleano_no_cuenta_como_numero() -> None:
    """En Python un `bool` ES un `int`, asi que un `total: true` se colaria como una pagina de uno."""
    assert unwrap_list({"accounts": [CUENTA, CUENTA], "total": True}, "accounts").total == 2


def test_un_recurso_suelto_tambien_sale_de_su_sobre() -> None:
    assert unwrap_one({"account": CUENTA}, "account") == CUENTA

    with pytest.raises(PlanVortexError, match="account"):
        unwrap_one({"cuenta": CUENTA}, "account")


def test_la_pagina_se_comporta_como_lo_que_es() -> None:
    """`len`, `for` y el `if` de "¿vino algo?", que es lo que se escribe de verdad."""
    pagina: Page[Any] = Page(data=[CUENTA, CUENTA], total=99)

    assert len(pagina) == 2
    assert list(pagina) == [CUENTA, CUENTA]
    assert pagina
    assert not Page(data=[], total=99)


def test_page_params_lleva_siempre_los_dos() -> None:
    assert tuple(PageParams(limit=50, offset=0)) == (50, 0)


# --------------------------------------------------------------------------------- el encadenado


def test_corta_en_la_pagina_corta_sin_pedir_una_mas(cliente: ClienteDePrueba, httpx_mock: Any) -> None:
    """Una pagina mas corta que el limite es la ultima: pedir la siguiente es una llamada que se
    sabe vacia, y con el `assert_all_requests_were_expected` del plugin, un test rojo.
    """
    httpx_mock.add_response(
        url=f"{ORG}/accounts?limit=3&offset=0", json={"accounts": [CUENTA] * 3, "total": 5}
    )
    httpx_mock.add_response(
        url=f"{ORG}/accounts?limit=3&offset=3", json={"accounts": [CUENTA] * 2, "total": 5}
    )

    assert len(cliente.iterar(cliente.pv.accounts, "aiterate", "org1", limit=3)) == 5
    assert len(peticiones(httpx_mock)) == 2


def test_corta_en_una_pagina_vacia_aunque_total_diga_otra_cosa(
    cliente: ClienteDePrueba, httpx_mock: Any
) -> None:
    """`total` se cuenta con una consulta aparte, asi que en una coleccion que se mueve no cuadra.

    Fiarse de el daria o un bucle infinito o una pagina perdida; lo que manda es que llegue vacia.
    """
    httpx_mock.add_response(
        url=f"{ORG}/accounts?limit=2&offset=0", json={"accounts": [CUENTA] * 2, "total": 1000}
    )
    httpx_mock.add_response(url=f"{ORG}/accounts?limit=2&offset=2", json={"accounts": [], "total": 1000})

    assert len(cliente.iterar(cliente.pv.accounts, "aiterate", "org1", limit=2)) == 2


def test_arranca_donde_se_le_diga(cliente: ClienteDePrueba, httpx_mock: Any) -> None:
    """El `offset` inicial es de quien llama; a partir de ahi lo lleva el iterador."""
    httpx_mock.add_response(url=f"{ORG}/accounts?limit=2&offset=10", json={"accounts": [CUENTA], "total": 11})

    assert len(cliente.iterar(cliente.pv.accounts, "aiterate", "org1", limit=2, offset=10)) == 1
    assert query(peticiones(httpx_mock)[0])["offset"] == ["10"]


def test_un_servidor_que_no_avanza_falla_en_vez_de_colgarse(
    cliente: ClienteDePrueba, httpx_mock: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El seguro de `MAX_PAGES`, provocado de verdad: la misma pagina llena, siempre.

    Sin el, esto es un `for` que no termina nunca dentro del proceso del integrador.

    El tope se baja a cinco para no hacer diez mil peticiones simuladas por una comprobacion que es
    la misma con cinco. Se parchea en las DOS variantes porque cada gemelo importa la constante en
    su propio espacio de nombres, y parchear solo una dejaria la mitad de la suite sin probar esto.
    """
    for modulo in (base_async, base_sync):
        monkeypatch.setattr(modulo, "MAX_PAGES", 5)
    httpx_mock.add_response(
        url=re.compile(rf"{re.escape(ORG)}/accounts.*"),
        json={"accounts": [CUENTA], "total": 1},
        is_reusable=True,
    )

    with pytest.raises(PlanVortexError, match="5 pages"):
        cliente.iterar(cliente.pv.accounts, "aiterate", "org1", limit=1)

    assert len(peticiones(httpx_mock)) == 5


def test_el_tope_de_paginas_no_es_un_limite_de_uso() -> None:
    """A cien elementos por pagina son un millon: es un fusible, no una politica."""
    assert MAX_PAGES >= 10_000
