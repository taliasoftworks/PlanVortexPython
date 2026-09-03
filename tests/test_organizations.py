"""Organizaciones (capa 2), con los doce metodos del recurso.

Lo que se fija aqui y no se puede ver leyendo el codigo:

- **`limits` NO viene envuelto**: es el unico `GET` del recurso que devuelve el objeto pelado, sin
  `{organization: ...}` alrededor. Desenvolverlo daria un error de sobre que no dice nada.
- **`use` es un atajo de `get(get_use=True)`**, no una ruta propia. La ruta `/use` existe y es del
  dashboard: son dos numeros distintos y confundirlos es facil.
- **El token temporal es un `GET`** aunque cree algo, y devuelve los tres campos tal cual.
- **Borrar las credenciales de una red SI devuelve la organizacion envuelta**, que es la unica
  excepcion del `DELETE` en toda la libreria.
"""

from __future__ import annotations

from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, query, ruta, unica

ORG = f"{BASE_URL}/organizations/org1"
ORGANIZACION = {"_id": "org1", "name": "Central"}


def test_lee_una_organizacion_con_y_sin_consumo(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=ORG, json={"organization": ORGANIZACION})
    httpx_mock.add_response(url=f"{ORG}?getUse=true", json={"organization": ORGANIZACION})

    assert cliente.esperar(cliente.pv.organizations.get("org1")) == ORGANIZACION
    assert cliente.esperar(cliente.pv.organizations.get("org1", get_use=True)) == ORGANIZACION

    sin_uso, con_uso = (query(peticion) for peticion in peticiones(httpx_mock))
    assert sin_uso == {}
    assert con_uso == {"getUse": ["true"]}


def test_actualiza_y_borra(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=ORG, method="PUT", json={"organization": ORGANIZACION})
    httpx_mock.add_response(url=ORG, method="DELETE", json={"success": True})

    cambiada = cliente.esperar(cliente.pv.organizations.update("org1", {"actual_plan": {"accounts": 3}}))
    assert cliente.esperar(cliente.pv.organizations.remove("org1")) is None

    assert cambiada == ORGANIZACION
    editar, borrar = peticiones(httpx_mock)
    assert cuerpo(editar) == {"actual_plan": {"accounts": 3}}
    assert borrar.method == "DELETE"


def test_las_hijas_se_listan_se_iteran_y_se_crean(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{ORG}/organizations?limit=1&offset=0&name=Sur&getUse=true",
        json={"organizations": [ORGANIZACION], "total": 1},
    )
    httpx_mock.add_response(
        url=f"{ORG}/organizations?limit=1&offset=1", json={"organizations": [], "total": 1}
    )
    httpx_mock.add_response(
        url=f"{ORG}/organizations?limit=1&offset=0", json={"organizations": [ORGANIZACION], "total": 1}
    )
    httpx_mock.add_response(url=f"{ORG}/organizations", method="POST", json={"organization": ORGANIZACION})

    pagina = cliente.esperar(
        cliente.pv.organizations.children("org1", limit=1, offset=0, name="Sur", get_use=True)
    )
    hijas = cliente.iterar(cliente.pv.organizations, "aiterate_children", "org1", limit=1)
    creada = cliente.esperar(cliente.pv.organizations.create_child("org1", {"name": "Sur"}))

    assert pagina.data == hijas == [ORGANIZACION]
    assert creada == ORGANIZACION
    assert cuerpo(peticiones(httpx_mock)[-1]) == {"name": "Sur"}


def test_limits_llega_sin_sobre(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """La cascada ya resuelta, y en crudo. Es lo que hay que mirar, no `actual_plan`."""
    httpx_mock.add_response(url=f"{ORG}/limits", json={"accounts": 5, "users": 3})

    assert cliente.esperar(cliente.pv.organizations.limits("org1")) == {"accounts": 5, "users": 3}
    assert ruta(unica(httpx_mock)) == "/organizations/org1/limits"


def test_use_es_un_atajo_de_get_con_get_use(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """UNA peticion, a `/organizations/org1` con `getUse`, y no a la ruta `/use` del dashboard."""
    httpx_mock.add_response(
        url=f"{ORG}?getUse=true",
        json={"organization": {**ORGANIZACION, "actual_use": {"accounts": 2}, "actual_asigned": {}}},
    )

    uso = cliente.esperar(cliente.pv.organizations.use("org1"))

    assert uso == {"actual_use": {"accounts": 2}, "actual_asigned": {}}
    assert ruta(unica(httpx_mock)) == "/organizations/org1"


def test_use_no_inventa_las_dos_cifras_cuando_no_vienen(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Ausente no es cero: un `{"actual_use": {}}` inventado se pintaria como "0 de 5" sin serlo."""
    httpx_mock.add_response(url=f"{ORG}?getUse=true", json={"organization": ORGANIZACION})

    assert cliente.esperar(cliente.pv.organizations.use("org1")) == {}


def test_el_token_temporal_va_en_get_y_devuelve_los_tres_campos(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """`url` para el camino alojado, `token` para `as_temporal_token`, y cuando caduca. Los tres."""
    httpx_mock.add_response(
        url=f"{ORG}/temporal_connect_token?social_network=instagram&redirect_uri=https%3A%2F%2Fmio.test%2Fok",
        json={
            "url": "https://app.planvortex.com/connect?token=abc",
            "token": "abc",
            "expires_at": "2026-08-27T10:15:00.000Z",
        },
    )

    token = cliente.esperar(
        cliente.pv.organizations.create_connect_token(
            "org1", social_network="instagram", redirect_uri="https://mio.test/ok"
        )
    )

    assert token["token"] == "abc"
    assert token["expires_at"].startswith("2026-08-27")
    peticion = unica(httpx_mock)
    assert peticion.method == "GET"
    assert query(peticion) == {
        "social_network": ["instagram"],
        "redirect_uri": ["https://mio.test/ok"],
    }


def test_el_contexto_de_ia_reemplaza_el_bloque(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/ai-context", method="PUT", json={"organization": ORGANIZACION})

    contexto = {"brand_voice": "cercana", "topics": ["pan", "horno"]}
    assert cliente.esperar(cliente.pv.organizations.update_ai_context("org1", contexto)) == ORGANIZACION
    assert cuerpo(unica(httpx_mock)) == contexto


def test_las_credenciales_propias_se_guardan_y_se_borran(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """El `DELETE` de aqui devuelve la organizacion ENVUELTA, que es la unica excepcion del paquete."""
    httpx_mock.add_response(
        url=f"{ORG}/social_credentials/discord", method="PUT", json={"organization": ORGANIZACION}
    )
    httpx_mock.add_response(
        url=f"{ORG}/social_credentials/discord", method="DELETE", json={"organization": ORGANIZACION}
    )

    credenciales = {"client_id": "1", "client_secret": "s", "bot_token": "t"}
    guardada = cliente.esperar(
        cliente.pv.organizations.update_social_credentials("org1", "discord", credenciales)
    )
    borrada = cliente.esperar(cliente.pv.organizations.delete_social_credentials("org1", "discord"))

    assert guardada == borrada == ORGANIZACION
    assert cuerpo(peticiones(httpx_mock)[0]) == credenciales


def test_los_usuarios_de_la_organizacion_salen_del_sobre(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """La unica ruta de la seccion de roles que la libreria cubre, porque es una LECTURA.

    Y su identificador es `id` —el de Keycloak—, no un `_id`: estas personas no viven en la base de
    datos de PlanVortex.
    """
    httpx_mock.add_response(
        url=f"{ORG}/users",
        json={"users": [{"id": "kc-1", "username": "marta", "email": "marta@panaderia.test"}], "total": 1},
    )

    usuarios = cliente.esperar(cliente.pv.organizations.users("org1"))

    assert usuarios[0]["id"] == "kc-1"
    assert ruta(unica(httpx_mock)) == "/organizations/org1/users"
