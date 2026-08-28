"""El catalogo (capa 2). Lo que se fija aqui, ademas del contrato de cada una de las nueve rutas:

- **Que se cachea.** Es la razon de existir del recurso: un compositor que valide mientras se
  escribe pediria `/social_limits` en cada tecla.
- **Que un fallo NO se cachea**, que es el error clasico de una cache escrita a la ligera: un 502 de
  un despliegue en marcha dejaria la instancia rota para siempre.
- **Que `allowed_social_messages` va en POST**, que es raro y es lo que hay. Escrito en GET, el
  servidor contesta 404 y el metodo devolveria una lista vacia sin que nadie se entere.
"""

from __future__ import annotations

from typing import Any

import pytest
from pytest_httpx2 import HTTPXMock

from planvortex import PlanVortexError
from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import peticiones, ruta, unica


def test_pide_las_redes_soportadas(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{BASE_URL}/social_networks", json=["instagram", "bluesky"])

    assert cliente.esperar(cliente.pv.catalog.social_networks()) == ["instagram", "bluesky"]
    assert ruta(unica(httpx_mock)) == "/social_networks"


def test_las_redes_que_publican_y_las_que_hablan_van_por_metodos_distintos(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """`allowed_social_messages` es un POST. No es un despiste del spec: es la ruta que hay."""
    httpx_mock.add_response(url=f"{BASE_URL}/allowed_social_publications", json=["instagram"])
    httpx_mock.add_response(url=f"{BASE_URL}/allowed_social_messages", method="POST", json=["whatsapp"])

    assert cliente.esperar(cliente.pv.catalog.allowed_social_publications()) == ["instagram"]
    assert cliente.esperar(cliente.pv.catalog.allowed_social_messages()) == ["whatsapp"]

    metodos = {ruta(peticion): peticion.method for peticion in peticiones(httpx_mock)}
    assert metodos == {"/allowed_social_publications": "GET", "/allowed_social_messages": "POST"}


def test_los_limites_y_las_dos_matrices_van_por_su_ruta(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Las capacidades y las acciones de comentario son DOS rutas y dos formas distintas."""
    httpx_mock.add_response(url=f"{BASE_URL}/social_limits", json={"characters": {"bluesky": 300}})
    httpx_mock.add_response(
        url=f"{BASE_URL}/social_capabilities",
        json={"whatsapp": {"publications": False, "messages": True, "comments": False}},
    )
    httpx_mock.add_response(
        url=f"{BASE_URL}/social_comment_actions",
        json={"instagram": {"reply": True, "hide": True, "delete_own": True, "delete_others": False}},
    )

    limites = cliente.esperar(cliente.pv.catalog.social_limits())
    capacidades = cliente.esperar(cliente.pv.catalog.social_capabilities())
    acciones = cliente.esperar(cliente.pv.catalog.social_comment_actions())

    assert limites["characters"]["bluesky"] == 300
    assert capacidades["whatsapp"]["publications"] is False
    assert acciones["instagram"]["delete_others"] is False


def test_los_recortes_y_el_tope_de_reintentos(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{BASE_URL}/allowed_aspect_ratios", json={"instagram": {"values": [1], "text": ["1:1"]}}
    )
    httpx_mock.add_response(url=f"{BASE_URL}/publication_limits", json={"max_retries": 3})

    recortes = cliente.esperar(cliente.pv.catalog.allowed_aspect_ratios())
    limites = cliente.esperar(cliente.pv.catalog.publication_limits())

    assert recortes["instagram"]["text"] == ["1:1"]
    assert limites["max_retries"] == 3


def test_se_cachea_y_una_sola_peticion_sirve_a_diez_llamadas(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """La razon de existir del recurso. El mock no es reutilizable: una segunda peticion fallaria."""
    httpx_mock.add_response(url=f"{BASE_URL}/social_limits", json={"characters": {"linkedin": 1300}})

    for _ in range(10):
        assert cliente.esperar(cliente.pv.catalog.social_limits())["characters"]["linkedin"] == 1300

    assert len(peticiones(httpx_mock)) == 1


def test_un_fallo_no_se_cachea(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Un 502 durante un despliegue no puede dejar la instancia rota para siempre.

    Es el fallo clasico de una cache escrita a la ligera, y aqui no puede pasar porque lo que se
    guarda es el VALOR y no la llamada: si la llamada revienta, no hay valor que guardar.
    """
    httpx_mock.add_response(url=f"{BASE_URL}/social_networks", status_code=502, json={})
    httpx_mock.add_response(url=f"{BASE_URL}/social_networks", json=["instagram"])

    with pytest.raises(PlanVortexError):
        cliente.esperar(cliente.pv.catalog.social_networks())

    assert cliente.esperar(cliente.pv.catalog.social_networks()) == ["instagram"]
    assert len(peticiones(httpx_mock)) == 2


def test_clear_cache_vuelve_a_preguntar(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Para un proceso de dias que quiera enterarse de una red nueva sin reiniciar."""
    httpx_mock.add_response(url=f"{BASE_URL}/social_networks", json=["instagram"])
    httpx_mock.add_response(url=f"{BASE_URL}/social_networks", json=["instagram", "bluesky"])

    assert cliente.esperar(cliente.pv.catalog.social_networks()) == ["instagram"]
    cliente.pv.catalog.clear_cache()
    assert cliente.esperar(cliente.pv.catalog.social_networks()) == ["instagram", "bluesky"]


def test_el_catalogo_es_el_mismo_objeto_en_toda_la_instancia(cliente: ClienteDePrueba) -> None:
    """Si fuera una propiedad que construye el recurso al vuelo, la cache no cachearia nada."""
    primero: Any = cliente.pv.catalog
    assert primero is cliente.pv.catalog
