"""Planes de IA (capa 2).

Lo que se fija aqui:

- **Las rutas cuelgan del CLIENTE y de la organizacion**, las dos: son las unicas de la libreria con
  dos identificadores en el camino, y equivocarse de orden da un 404 que no dice cual.
- **Crear NO devuelve un plan envuelto**: devuelve `{ai_plan, estimate}`, porque lo que importa al
  encolar es el presupuesto.
- **Validar y reintentar SI vienen envueltos** en `{ai_plan}`.
- **Regenerar lleva `target` en el cuerpo** y devuelve la publicacion mas el gasto TOTAL del plan.
"""

from __future__ import annotations

from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, ruta, unica

PLANES = f"{BASE_URL}/clients/cli1/organizations/org1/ai_plans"
PLAN = {
    "_id": "plan1",
    "id_organization": "org1",
    "prompt": "Pan de masa madre",
    "state": "pending",
    "publications": [],
    "options": {"shared": False, "use_organization_context": True},
}


def test_encolar_devuelve_el_plan_y_el_presupuesto(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=PLANES,
        method="POST",
        json={"ai_plan": PLAN, "estimate": {"base_cost": 300, "estimated_cost": 1120}},
    )

    encolado = cliente.esperar(
        cliente.pv.ai_plans.create(
            "cli1",
            "org1",
            {
                "prompt": "Pan de masa madre",
                "accounts": ["acc1"],
                "options": {"publish_days": [1, 3, 5], "timezone": "Europe/Madrid"},
            },
        )
    )

    # El presupuesto lo calcula el SERVIDOR, y `base_cost` es lo que tiene que caber en los creditos.
    assert encolado["estimate"]["base_cost"] == 300
    assert encolado["ai_plan"]["state"] == "pending"
    assert ruta(unica(httpx_mock)) == "/clients/cli1/organizations/org1/ai_plans"
    assert cuerpo(unica(httpx_mock))["options"]["publish_days"] == [1, 3, 5]


def test_leer_listar_e_iterar(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{PLANES}/plan1", json={"ai_plan": PLAN})
    httpx_mock.add_response(url=f"{PLANES}?limit=1&offset=0", json={"ai_plans": [PLAN], "total": 1})
    httpx_mock.add_response(url=f"{PLANES}?limit=1&offset=1", json={"ai_plans": [], "total": 1})

    leido = cliente.esperar(cliente.pv.ai_plans.get("cli1", "org1", "plan1"))
    todos = cliente.iterar(cliente.pv.ai_plans, "aiterate", "cli1", "org1", limit=1)

    assert leido == PLAN
    assert todos == [PLAN]


def test_validar_y_reintentar_devuelven_el_plan(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{PLANES}/plan1/validate", method="POST", json={"ai_plan": {**PLAN, "state": "validated"}}
    )
    httpx_mock.add_response(
        url=f"{PLANES}/plan1/retry", method="POST", json={"ai_plan": {**PLAN, "state": "pending"}}
    )

    validado = cliente.esperar(cliente.pv.ai_plans.validate("cli1", "org1", "plan1"))
    reintentado = cliente.esperar(cliente.pv.ai_plans.retry("cli1", "org1", "plan1"))

    assert validado["state"] == "validated"
    assert reintentado["state"] == "pending"
    validar, reintentar = peticiones(httpx_mock)
    # Ninguno de los dos manda cuerpo: son POST vacios.
    assert cuerpo(validar) is None
    assert cuerpo(reintentar) is None


def test_regenerar_una_publicacion_del_plan(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{PLANES}/plan1/publications/pub1/regenerate",
        method="POST",
        json={"publication": {"_id": "pub1", "text": "Otra version"}, "credits_spent": 640},
    )

    resultado = cliente.esperar(cliente.pv.ai_plans.regenerate("cli1", "org1", "plan1", "pub1", "image"))

    # `credits_spent` es el total del PLAN, no lo que costo esta llamada.
    assert resultado["credits_spent"] == 640
    assert cuerpo(unica(httpx_mock)) == {"target": "image"}
    assert ruta(unica(httpx_mock)) == (
        "/clients/cli1/organizations/org1/ai_plans/plan1/publications/pub1/regenerate"
    )


def test_borrar_es_cancelar(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{PLANES}/plan1", method="DELETE", json={"success": True})

    assert cliente.esperar(cliente.pv.ai_plans.remove("cli1", "org1", "plan1")) is None
    assert unica(httpx_mock).method == "DELETE"
