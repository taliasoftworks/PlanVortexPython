"""Planes de IA (capa 2).

Lo que se fija aqui:

- **Las rutas cuelgan del CLIENTE y de la organizacion**, las dos: son las unicas de la libreria con
  dos identificadores en el camino, y equivocarse de orden da un 404 que no dice cual.
- **Crear NO devuelve un plan envuelto**: devuelve `{ai_plan, estimate}`, porque lo que importa al
  encolar es el presupuesto.
- **Validar y reintentar SI vienen envueltos** en `{ai_plan}`.
- **Regenerar lleva `target` en el cuerpo** y devuelve la publicacion mas el gasto TOTAL del plan.

Y de las plantillas:

- **`template` y `source` son OPCIONALES**: un cuerpo sin ellos tiene que salir tal cual, porque es
  lo que manda quien integro con esta libreria antes de que existieran.
- **La fuente se valida al CREAR**, asi que sus errores (2112-2116) llegan en esa llamada.
- **`warnings` viaja DENTRO del plan generado**: el 2117 no es un error de la respuesta.
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


def test_sin_plantilla_el_cuerpo_sale_como_siempre(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """Es contrato, no una comodidad: el servidor tarifa como `standard` lo que llega sin `template`.

    Una libreria que rellenara el hueco con un `"template": "standard"` "por claridad" estaria
    cambiando lo que sale por el cable de todos los integradores que ya estaban.
    """
    httpx_mock.add_response(url=PLANES, method="POST", json={"ai_plan": PLAN, "estimate": {}})

    cliente.esperar(
        cliente.pv.ai_plans.create("cli1", "org1", {"prompt": "Pan de masa madre", "accounts": ["acc1"]})
    )

    assert cuerpo(unica(httpx_mock)) == {"prompt": "Pan de masa madre", "accounts": ["acc1"]}


def test_la_plantilla_y_su_fuente_viajan_con_las_fotos_en_orden(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """El ORDEN de las fotos es la historia.

    El orquestador se queda con la posicion de cada una como `source_index`, y es lo que deja que la
    foto 3 sea el "antes" y la 7 el "despues". Reordenarlas por el camino seria el copy del entrante
    con la foto del postre.
    """
    imagenes = [
        {"id_upload": "up1", "description": "Masa reposando en el banco"},
        {"id_upload": "up2", "description": "La hogaza saliendo del horno"},
    ]
    httpx_mock.add_response(
        url=PLANES,
        method="POST",
        json={
            "ai_plan": {**PLAN, "template": "from_images", "source": {"images": imagenes}},
            "estimate": {"base_cost": 48, "estimated_cost": 48, "images_target": 0},
        },
    )

    encolado = cliente.esperar(
        cliente.pv.ai_plans.create(
            "cli1",
            "org1",
            {
                "prompt": "Nuestra carta de otono",
                "accounts": ["acc1"],
                "template": "from_images",
                "source": {"images": imagenes},
            },
        )
    )

    enviado = cuerpo(unica(httpx_mock))
    assert enviado["template"] == "from_images"
    assert enviado["source"]["images"] == imagenes
    # Las fotos las pone la fuente, asi que el plan no financia ni una imagen: es de donde sale el
    # 519 -> 48 de la misma semana.
    assert encolado["estimate"]["images_target"] == 0
    assert encolado["ai_plan"]["source"]["images"][0]["description"] == "Masa reposando en el banco"


def test_la_fecha_de_campaign_viaja_como_dia_de_calendario(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Un `YYYY-MM-DD`, nunca un instante ISO.

    `2026-09-15T00:00:00Z` es medianoche UTC, o sea el 14 por la tarde en Nueva York: un dia entero
    de desfase en una cuenta atras, para media America y sin error en ninguna parte.
    """
    httpx_mock.add_response(url=PLANES, method="POST", json={"ai_plan": PLAN, "estimate": {}})

    cliente.esperar(
        cliente.pv.ai_plans.create(
            "cli1",
            "org1",
            {
                "prompt": "Abrimos tienda en el barrio",
                "accounts": ["acc1"],
                "template": "campaign",
                "source": {"event_name": "Apertura del local", "event_date": "2026-09-15"},
            },
        )
    )

    assert cuerpo(unica(httpx_mock))["source"]["event_date"] == "2026-09-15"


def test_el_2117_es_un_aviso_del_plan_y_no_un_error(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """El plan se genero perfectamente: lo que paso es que la fuente traia mas unidades que huecos.

    Va en `warnings` DENTRO del plan, junto a un `state` que dice `generated`, y no en el error de
    la respuesta — que es donde lo buscaria quien no lo sepa.
    """
    aviso = {
        "code": 2117,
        "message": "Some source items did not fit in the plan week",
        "data": {"source_items": 12, "capacity": 6},
    }
    httpx_mock.add_response(
        url=f"{PLANES}/plan1",
        json={"ai_plan": {**PLAN, "state": "generated", "template": "from_images", "warnings": [aviso]}},
    )

    plan = cliente.esperar(cliente.pv.ai_plans.get("cli1", "org1", "plan1"))

    assert plan["state"] == "generated"
    assert "error" not in plan
    assert plan["warnings"][0]["data"] == {"source_items": 12, "capacity": 6}


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
