"""Publicaciones (capa 2), con los doce metodos del recurso.

Las tres cosas que se fijan aqui porque no se ven leyendo el codigo:

- **Una publicacion invalida NO es un error.** Llega con un 200, en estado `withErrors` y con el
  motivo dentro. Un `try/except` no basta, y un test que solo mirase que no hubo excepcion daria
  por buena una publicacion que no va a salir nunca.
- **`publish_date` se serializa con offset, o no sale.** Un `datetime` naive lanza en vez de suponer
  (§ Trampa P8): suponer UTC publica a la hora equivocada al que esta en Madrid y suponer la zona
  del proceso, al que esta en Docker.
- **`orderByPublish` va en camelCase y solo cuando es `True`.** Ordenar por fecha de publicacion en
  vez de por fecha de creacion es la diferencia entre un calendario y un registro de actividad, y
  un parametro que el servidor no lee no da error: devuelve el otro orden.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pytest_httpx2 import HTTPXMock

from planvortex import PlanVortexConfigError
from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, query, ruta, unica

ORG = f"{BASE_URL}/organizations/org1"
PUBLICACION = {"_id": "pub1", "state": "ready", "id_account": "acc1", "publication_errors": []}


def test_crea_una_publicacion_programada(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """La fecha sale en ISO-8601 con su offset, y la ruta es la de la CUENTA."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/publish", method="POST", json={"publication": PUBLICACION}
    )

    publicacion = cliente.esperar(
        cliente.pv.publications.create(
            "org1",
            "acc1",
            {
                "social_network": "instagram",
                "text": "Nuevo horno",
                "files": ["up1"],
                "publish_date": datetime(2026, 9, 1, 10, 0, tzinfo=timezone.utc),
            },
        )
    )

    assert publicacion == PUBLICACION
    peticion = unica(httpx_mock)
    assert ruta(peticion) == "/organizations/org1/accounts/acc1/publish"
    assert cuerpo(peticion) == {
        "social_network": "instagram",
        "text": "Nuevo horno",
        "files": ["up1"],
        "publish_date": "2026-09-01T10:00:00+00:00",
    }


def test_una_fecha_naive_lanza_y_no_sale_ninguna_peticion(cliente: ClienteDePrueba) -> None:
    """§ Trampa P8. Y sin peticion: el mock no declarado lo demostraria igualmente."""
    with pytest.raises(PlanVortexConfigError, match="naive"):
        cliente.esperar(
            cliente.pv.publications.create(
                "org1", "acc1", {"social_network": "instagram", "publish_date": datetime(2026, 9, 1, 10, 0)}
            )
        )


def test_una_cadena_ya_formada_se_deja_pasar(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Quien ya tiene la fecha en ISO no tiene que convertirla a `datetime` para volver a convertirla."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/publish", method="POST", json={"publication": PUBLICACION}
    )

    cliente.esperar(
        cliente.pv.publications.create(
            "org1", "acc1", {"social_network": "bluesky", "publish_date": "2026-09-01T10:00:00Z"}
        )
    )

    assert cuerpo(unica(httpx_mock))["publish_date"] == "2026-09-01T10:00:00Z"


def test_una_publicacion_invalida_llega_como_dato_y_no_como_excepcion(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """EL COMPORTAMIENTO QUE SORPRENDE A TODO EL MUNDO. Se guarda, y no va a salir."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/publish",
        method="POST",
        json={
            "publication": {
                **PUBLICACION,
                "state": "withErrors",
                "publication_errors": [{"code": 903, "message": "El texto es demasiado largo"}],
            }
        },
    )

    publicacion = cliente.esperar(
        cliente.pv.publications.create("org1", "acc1", {"social_network": "linkedin", "text": "x" * 4000})
    )

    assert publicacion["state"] == "withErrors"
    assert publicacion["publication_errors"][0]["code"] == 903


def test_lista_con_todos_sus_filtros(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Los estados y las redes van como clave repetida, y `orderByPublish` en camelCase."""
    httpx_mock.add_response(
        url=f"{ORG}/publish?limit=5&state=ready&state=withErrors&social_network=instagram"
        "&accounts=acc1&search=horno&orderByPublish=true&from_date=2026-08-01T00%3A00%3A00%2B00%3A00",
        json={"publications": [PUBLICACION], "total": 1},
    )

    pagina = cliente.esperar(
        cliente.pv.publications.list(
            "org1",
            limit=5,
            state=["ready", "withErrors"],
            social_network=["instagram"],
            accounts=["acc1"],
            search="horno",
            order_by_publish=True,
            from_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
    )

    assert pagina.data == [PUBLICACION]
    parametros = query(unica(httpx_mock))
    assert parametros["state"] == ["ready", "withErrors"]
    assert parametros["orderByPublish"] == ["true"]
    assert parametros["from_date"] == ["2026-08-01T00:00:00+00:00"]


def test_order_by_publish_falso_no_viaja(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """El servidor lo compara contra el literal "true": un `false` es ruido en el log."""
    httpx_mock.add_response(url=f"{ORG}/publish", json={"publications": [], "total": 0})

    cliente.esperar(cliente.pv.publications.list("org1", order_by_publish=False))

    assert query(unica(httpx_mock)) == {}


def test_lee_itera_y_lista_por_cuenta(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/publish/pub1", json={"publication": PUBLICACION})
    httpx_mock.add_response(
        url=f"{ORG}/publish?limit=1&offset=0", json={"publications": [PUBLICACION], "total": 1}
    )
    httpx_mock.add_response(url=f"{ORG}/publish?limit=1&offset=1", json={"publications": [], "total": 1})
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/publish?state=ready", json={"publications": [PUBLICACION], "total": 1}
    )

    una = cliente.esperar(cliente.pv.publications.get("org1", "pub1"))
    todas = cliente.iterar(cliente.pv.publications, "aiterate", "org1", limit=1)
    de_la_cuenta = cliente.esperar(cliente.pv.publications.list_by_account("org1", "acc1", state=["ready"]))

    assert una == PUBLICACION
    assert todas == de_la_cuenta.data == [PUBLICACION]


def test_las_dos_rutas_de_actualizar_mandan_el_mismo_cuerpo(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """La API tiene las dos y las sirve el mismo handler. La segunda existe porque esta documentada."""
    httpx_mock.add_response(url=f"{ORG}/publish/pub1", method="PUT", json={"publication": PUBLICACION})
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/publish/pub1", method="PUT", json={"publication": PUBLICACION}
    )

    cuerpo_enviado = {"text": "Otro texto", "publish_date": datetime(2026, 9, 2, 9, 0, tzinfo=timezone.utc)}
    corta = cliente.esperar(cliente.pv.publications.update("org1", "pub1", dict(cuerpo_enviado)))
    larga = cliente.esperar(
        cliente.pv.publications.update_by_account("org1", "acc1", "pub1", dict(cuerpo_enviado))
    )

    assert corta == larga == PUBLICACION
    primera, segunda = peticiones(httpx_mock)
    assert cuerpo(primera) == cuerpo(segunda)
    assert cuerpo(primera)["publish_date"] == "2026-09-02T09:00:00+00:00"


def test_borra_reintenta_y_mide(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """`retry` devuelve la publicacion Y el tope, sin sobre. `metrics` pregunta a la red y `stats` no."""
    httpx_mock.add_response(url=f"{ORG}/publish/pub1", method="DELETE", json={"success": True})
    httpx_mock.add_response(
        url=f"{ORG}/publish/pub1/retry",
        method="POST",
        json={"publication": PUBLICACION, "max_retries": 3},
    )
    httpx_mock.add_response(url=f"{ORG}/publish/pub1/metrics", json={"likes": 12})
    httpx_mock.add_response(url=f"{ORG}/publish/pub1/stats", json={"series": [], "last": {}})

    assert cliente.esperar(cliente.pv.publications.remove("org1", "pub1")) is None
    reintento = cliente.esperar(cliente.pv.publications.retry("org1", "pub1"))
    metricas = cliente.esperar(cliente.pv.publications.metrics("org1", "pub1"))
    historico = cliente.esperar(cliente.pv.publications.stats("org1", "pub1"))

    assert reintento == {"publication": PUBLICACION, "max_retries": 3}
    assert metricas == {"likes": 12}
    # Una serie vacia es una respuesta valida: recien enviada, o una red sin estadisticas.
    assert historico["series"] == []


def test_lo_que_hay_en_el_muro_segun_la_red(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Incluye lo publicado por fuera de PlanVortex. En X, el `limit` es dinero."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/social_publications?limit=5",
        json={"publications": [PUBLICACION], "total": 1},
    )

    pagina = cliente.esperar(cliente.pv.publications.list_on_network("org1", "acc1", limit=5))

    assert pagina.data == [PUBLICACION]
    assert ruta(unica(httpx_mock)) == "/organizations/org1/accounts/acc1/social_publications"
