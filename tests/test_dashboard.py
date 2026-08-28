"""Dashboard (capa 2): los numeros de la pantalla de inicio.

Lo que se fija aqui:

- **`summary` es UNA llamada** y sus bloques se omiten segun permisos: un bloque que falta no es un
  error, y `available_blocks` dice cuales se permitieron.
- **`summary=False` solo viaja cuando es False.** El servidor lo lee como el literal "false"; con
  cualquier otra cosa deja los agregados, asi que mandarlo siempre seria ruido y no mandarlo nunca
  serian tres agregaciones tiradas en cada pagina.
- **Una fila de `metrics` agrupada por `total` trae `group: null`**, que es el caso que no encajaba
  en su propio tipo hasta la fase 4.
- **`use` es la ruta `/use`**, la del dashboard, y no el atajo `organizations.use()`.
"""

from __future__ import annotations

from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import peticiones, query, ruta, unica

ORG = f"{BASE_URL}/organizations/org1"
RANGO = {
    "from_date": "2026-07-28",
    "to_date": "2026-08-27",
    "previous_from_date": "2026-06-28",
    "previous_to_date": "2026-07-28",
}


def test_la_pantalla_entera_en_una_llamada(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{ORG}/dashboard?from_date=2026-07-28&to_date=2026-08-27",
        json={
            "range": RANGO,
            "available_blocks": {"health": True, "publications": True, "messages": False},
            "health": {"accounts_with_error": []},
        },
    )

    pantalla = cliente.esperar(
        cliente.pv.dashboard.summary("org1", from_date="2026-07-28", to_date="2026-08-27")
    )

    # `publications` esta permitido y no viene: eso significa que no habia datos, no un fallo.
    assert pantalla["available_blocks"]["publications"] is True
    assert "publications" not in pantalla
    assert ruta(unica(httpx_mock)) == "/organizations/org1/dashboard"


def test_las_metricas_agregadas_por_total_traen_group_nulo(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url=f"{ORG}/metrics?group_by=total&names=followers&names=reach",
        json={
            "range": RANGO,
            "group_by": "total",
            "stats": [{"group": None, "metrics": {"followers": 1200, "reach": 8400}}],
        },
    )

    agregado = cliente.esperar(
        cliente.pv.dashboard.metrics("org1", group_by="total", names=["followers", "reach"])
    )

    assert agregado["stats"][0]["group"] is None
    assert query(unica(httpx_mock)) == {"group_by": ["total"], "names": ["followers", "reach"]}


def test_el_resumen_de_publicaciones_trae_las_dos_series(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """`by_day` cuenta lo CREADO y `published_by_day` lo que SALIO: dos preguntas distintas."""
    httpx_mock.add_response(
        url=f"{ORG}/publications/summary",
        json={
            "range": RANGO,
            "total": 12,
            "by_state": [{"state": "sended", "total": 9}],
            "by_network": [{"social_network": "instagram", "total": 7}],
            "by_day": [{"date": "2026-08-20", "total": 2}],
            "published_by_day": [{"date": "2026-08-21", "total": 1}],
        },
    )

    resumen = cliente.esperar(cliente.pv.dashboard.publications("org1"))

    assert resumen["by_day"] != resumen["published_by_day"]
    assert resumen["range"]["previous_from_date"] == "2026-06-28"


def test_el_ranking_no_tiene_forma_de_publicacion(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{ORG}/publications/top?metric=engagement&limit=3",
        json={
            "range": RANGO,
            "metric": "engagement",
            "publications": [
                {
                    "id_publication": "pub1",
                    "social_network": "instagram",
                    "metrics": {"engagement": 4.2},
                    "publication": {"text": "Hogazas"},
                }
            ],
        },
    )

    ranking = cliente.esperar(cliente.pv.dashboard.top_publications("org1", metric="engagement", limit=3))

    fila = ranking["publications"][0]
    # No hay `_id` y el contenido va anidado: es una agregacion, no la coleccion de publicaciones.
    assert "_id" not in fila
    assert fila["id_publication"] == "pub1"
    assert fila["publication"]["text"] == "Hogazas"


def test_el_listado_con_metricas_apaga_los_agregados_solo_si_se_pide(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """EL TEST DE LA RAMA: `summary=True` no viaja, `summary=False` si."""
    httpx_mock.add_response(
        url=f"{ORG}/publications/stats?social_network=instagram&limit=10&offset=10&summary=false",
        json={"range": RANGO, "publications": [], "total": 0},
    )
    httpx_mock.add_response(
        url=f"{ORG}/publications/stats?limit=10", json={"range": RANGO, "publications": [], "total": 0}
    )

    cliente.esperar(
        cliente.pv.dashboard.publication_stats(
            "org1", social_network=["instagram"], limit=10, offset=10, summary=False
        )
    )
    cliente.esperar(cliente.pv.dashboard.publication_stats("org1", limit=10, summary=True))

    apagado, encendido = peticiones(httpx_mock)
    assert query(apagado)["summary"] == ["false"]
    assert "summary" not in query(encendido)


def test_el_consumo_del_plan_es_su_propia_ruta(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """No es `organizations.use()`, que es un atajo sobre la ficha: esta trae ademas `limits`."""
    httpx_mock.add_response(
        url=f"{ORG}/use",
        json={
            "actual_use": {"accounts": 3},
            "actual_asigned": {"accounts": 1},
            "limits": {"accounts": 5},
        },
    )

    consumo = cliente.esperar(cliente.pv.dashboard.use("org1"))

    assert consumo["limits"]["accounts"] == 5
    assert ruta(unica(httpx_mock)) == "/organizations/org1/use"
