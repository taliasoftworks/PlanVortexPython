"""El catalogo (capa 2). Lo que se fija aqui, ademas del contrato de cada una de las diez rutas:

- **Que se cachea.** Es la razon de existir del recurso: un compositor que valide mientras se
  escribe pediria `/social_limits` en cada tecla.
- **Que un fallo NO se cachea**, que es el error clasico de una cache escrita a la ligera: un 502 de
  un despliegue en marcha dejaria la instancia rota para siempre.
- **Que `allowed_social_messages` va en POST**, que es raro y es lo que hay. Escrito en GET, el
  servidor contesta 404 y el metodo devolveria una lista vacia sin que nadie se entere.
- **Que `planner_templates` DESENVUELVE su sobre**, que es la unica ruta del catalogo que lo lleva.
  Sin desenvolver, el metodo devolveria `{"templates": [...]}` y recorrerlo daria las claves del
  `dict` —una cadena— en vez de las plantillas, sin error en ninguna parte.
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


def test_las_plantillas_del_planificador_salen_de_su_sobre(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """La ficha se fija ENTERA porque son precios: lo que el servidor cobra.

    Una tabla copiada a mano en la interfaz de un integrador ensenaria un coste que ya no es, y esa
    es exactamente la clase de copia que este catalogo existe para evitar.
    """
    httpx_mock.add_response(
        url=f"{BASE_URL}/planner_templates",
        json={
            "templates": [
                {
                    "template": "standard",
                    "allows_shared": True,
                    "allows_gallery": True,
                    "generates_images": True,
                    "regenerate": {"text": True, "image": True},
                    "orchestration_cost": 15,
                    "orchestration_cost_per_source_item": 0,
                    "max_source_items": 0,
                    "source_fields": [],
                },
                {
                    "template": "from_images",
                    "allows_shared": False,
                    "allows_gallery": False,
                    "generates_images": False,
                    "regenerate": {"text": True, "image": False},
                    "orchestration_cost": 20,
                    "orchestration_cost_per_source_item": 2,
                    "max_source_items": 20,
                    "source_fields": [
                        {"name": "images", "type": "uploads_with_description", "required": True, "max": 20}
                    ],
                },
            ]
        },
    )

    plantillas = cliente.esperar(cliente.pv.catalog.planner_templates())

    assert ruta(unica(httpx_mock)) == "/planner_templates"
    assert [plantilla["template"] for plantilla in plantillas] == ["standard", "from_images"]

    de_fotos = plantillas[1]
    # Lo que hace barata la plantilla, y lo que hay que decir ANTES de crear el plan: las fotos las
    # pone la fuente, asi que el plan no gasta un solo credito de imagen.
    assert de_fotos["generates_images"] is False
    # Y por eso mismo el boton de regenerar imagen no se pinta: serian 70 creditos por cambiar la
    # foto del usuario por una inventada.
    assert de_fotos["regenerate"]["image"] is False
    assert de_fotos["orchestration_cost_per_source_item"] == 2
    assert de_fotos["source_fields"][0]["type"] == "uploads_with_description"


def test_las_plantillas_publican_los_campos_de_los_que_hace_falta_uno(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """`source_requires_any` es lo que el `required` de un campo no sabe decir.

    En `from_text` hace falta la URL **o** el texto pegado, y ninguno de los dos por separado es
    obligatorio. Sin publicarlo, esa regla acabaria escrita a mano en cada interfaz. Y el `min`
    viaja por lo mismo que el `max`: si lo escribe la interfaz, el usuario se come un 2116 DESPUES
    de haber pegado el texto en vez de mientras lo pega.
    """
    httpx_mock.add_response(
        url=f"{BASE_URL}/planner_templates",
        json={
            "templates": [
                {
                    "template": "from_text",
                    "generates_images": True,
                    "orchestration_cost": 17,
                    "max_source_items": 0,
                    "source_fields": [
                        {"name": "url", "type": "url", "required": False},
                        {"name": "text", "type": "textarea", "required": False, "min": 200, "max": 12000},
                    ],
                    "source_requires_any": ["url", "text"],
                }
            ]
        },
    )

    de_texto = cliente.esperar(cliente.pv.catalog.planner_templates())[0]

    assert de_texto["source_requires_any"] == ["url", "text"]
    assert de_texto["source_fields"][1]["min"] == 200
    assert de_texto["source_fields"][1]["max"] == 12000


def test_las_plantillas_se_cachean_como_el_resto_del_catalogo(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Son constantes del despliegue: no dependen del cliente ni de la organizacion."""
    httpx_mock.add_response(url=f"{BASE_URL}/planner_templates", json={"templates": []})

    assert cliente.esperar(cliente.pv.catalog.planner_templates()) == []
    assert cliente.esperar(cliente.pv.catalog.planner_templates()) == []

    assert len(peticiones(httpx_mock)) == 1


def test_el_catalogo_es_el_mismo_objeto_en_toda_la_instancia(cliente: ClienteDePrueba) -> None:
    """Si fuera una propiedad que construye el recurso al vuelo, la cache no cachearia nada."""
    primero: Any = cliente.pv.catalog
    assert primero is cliente.pv.catalog
