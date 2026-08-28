"""`examples/comments.py`, recorrido entero contra un servidor de mentira.

Por lo mismo que los otros dos: es lo que vende `/developers`, la gente lo copia y lo pega, y un
ejemplo roto es peor que ninguno.

Lo que se fija aqui son las tres cosas que este ejemplo existe para ensenar, y que un cambio
descuidado se lleva por delante sin que nada mas se entere:

  - Que la lista se pide con `comments.list` —la BANDEJA, gratis— y el hilo con `comments.thread`.
    Pintar la lista con el segundo es como se hace una factura sin querer, y desde fuera se ve igual.
  - Que una resena de Google Business pide el hilo POR LA CUENTA, porque cuelga de la ficha.
  - Que sin `PLANVORTEX_ALLOW_REPLY=1` no se escribe NADA en ninguna red. Responder es publico,
    inmediato, y le llega a una persona.
"""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, stub_token
from tests.contrato import cuerpo, peticiones, ruta

RAIZ = Path(__file__).resolve().parent.parent
ORG = f"{BASE_URL}/organizations/org1"

CLIENTE = {"_id": "cli1", "name": "Panaderia Vega"}
ORGANIZACION = {"_id": "org1", "name": "Central"}

ACCIONES = {
    "instagram": {"reply": True, "hide": True, "delete_own": True, "delete_others": False},
    "google_business": {"reply": True, "hide": False, "delete_own": True, "delete_others": False},
}

# Un comentario normal: cuelga de una publicacion nuestra, y en la BANDEJA `id_publication` viene
# POBLADO. En el hilo y en la respuesta llega como cadena, que es por lo que el ejemplo usa
# `publication_id` y no un `isinstance` a mano.
COMENTARIO = {
    "_id": "com1",
    "social_network": "instagram",
    "text": "Que horario teneis los domingos?",
    "author": {"name": "Marta", "is_own": False},
    "id_account": {"_id": "acc1", "name": "Panaderia", "social_network": "instagram"},
    "id_publication": {"_id": "pub1"},
    "read": False,
}

# Y una resena: cuelga de la FICHA y no de ninguna publicacion, puede venir SIN TEXTO, y trae
# estrellas. Las tres cosas juntas no las tiene ninguna otra red.
RESENA = {
    "_id": "com2",
    "social_network": "google_business",
    "text": "",
    "rating": 2,
    "author": {"name": None, "is_own": False},
    "id_account": {"_id": "acc9", "name": "La tienda", "social_network": "google_business"},
    "read": False,
}


@pytest.fixture
def ejemplo(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """El modulo del ejemplo, cargado por su ruta: `examples/` no es un paquete a proposito."""
    monkeypatch.setenv("PLANVORTEX_CLIENT_ID", "app-1")
    monkeypatch.setenv("PLANVORTEX_CLIENT_SECRET", "s3cr3t")
    monkeypatch.setenv("PLANVORTEX_BASE_URL", BASE_URL)
    monkeypatch.delenv("PLANVORTEX_ALLOW_REPLY", raising=False)

    spec = importlib.util.spec_from_file_location("ejemplo_comments", RAIZ / "examples" / "comments.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["ejemplo_comments"] = modulo
    try:
        spec.loader.exec_module(modulo)
        yield modulo
    finally:
        del sys.modules["ejemplo_comments"]


def _camino(httpx_mock: HTTPXMock, *, bandeja: list[dict[str, Any]] | None = None) -> None:
    """Las cuatro primeras respuestas, que son iguales en todos los casos."""
    stub_token(httpx_mock)
    httpx_mock.add_response(url=f"{BASE_URL}/clients?limit=1", json={"clients": [CLIENTE], "total": 1})
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations?limit=1",
        json={"organizations": [ORGANIZACION], "total": 1},
    )
    httpx_mock.add_response(url=f"{ORG}/unread_comments", json={"total": 3})
    comentarios = [COMENTARIO] if bandeja is None else bandeja
    httpx_mock.add_response(
        url=f"{ORG}/comments?unread=true&limit=10",
        json={"comments": comentarios, "total": len(comentarios)},
    )
    if comentarios:
        httpx_mock.add_response(url=f"{BASE_URL}/social_comment_actions", json=ACCIONES)


def _hilo(comentarios: list[dict[str, Any]], *, creditos: int = 0) -> dict[str, Any]:
    return {"comments": comentarios, "total": len(comentarios), "credits_consumed": creditos}


def test_el_ejemplo_lee_la_bandeja_y_el_hilo_y_marca_leido(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """El camino entero, y en el orden del guion. La ultima escritura es la que NO toca la red."""
    _camino(httpx_mock)
    httpx_mock.add_response(url=f"{ORG}/publish/pub1/comments?limit=10", json=_hilo([COMENTARIO]))
    httpx_mock.add_response(url=f"{ORG}/comments/com1", method="PUT", json={"comment": COMENTARIO})

    assert ejemplo.main() == 0

    assert [ruta(peticion) for peticion in peticiones(httpx_mock)] == [
        "/clients",
        "/clients/cli1/organizations",
        "/organizations/org1/unread_comments",
        "/organizations/org1/comments",
        "/social_comment_actions",
        "/organizations/org1/publish/pub1/comments",
        "/organizations/org1/comments/com1",
    ]

    salida = capsys.readouterr().out
    assert "Sin leer: 3" in salida
    assert "Marta: Que horario teneis los domingos?" in salida
    assert "Marcado como leido: com1" in salida
    assert "Para responder de verdad: PLANVORTEX_ALLOW_REPLY=1" in salida


def test_la_resena_pide_el_hilo_por_la_cuenta_y_no_por_una_publicacion(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """La trampa de Google Business, que es la unica red donde la ruta del hilo es otra.

    Si alguien "simplifica" `_leer_hilo` a la llamada de siempre, esta red se queda sin hilo y el
    unico sintoma es un 404 en produccion — el mock sin usar lo caza aqui.
    """
    _camino(httpx_mock, bandeja=[RESENA])
    httpx_mock.add_response(url=f"{ORG}/accounts/acc9/comments?limit=10", json=_hilo([RESENA]))
    httpx_mock.add_response(url=f"{ORG}/comments/com2", method="PUT", json={"comment": RESENA})

    assert ejemplo.main() == 0

    assert "/organizations/org1/accounts/acc9/comments" in [
        ruta(peticion) for peticion in peticiones(httpx_mock)
    ]

    salida = capsys.readouterr().out
    # Sin texto y sin nombre: las dos ausencias se pintan, no revientan. Y dos estrellas se ven.
    assert "** anonimo: (sin texto)" in salida


def test_un_comentario_sin_publicacion_no_pide_ningun_hilo(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """Un video subido a mano, un post anterior a PlanVortex: no hay hilo, y no es un error.

    Lo que se fija es que NO se llame a la red. El plugin tumba el test ante una peticion no
    simulada, asi que un `thread(org, None)` se veria aqui.
    """
    huerfano = {**COMENTARIO, "_id": "com3", "id_publication": None}
    _camino(httpx_mock, bandeja=[huerfano])
    httpx_mock.add_response(url=f"{ORG}/comments/com3", method="PUT", json={"comment": huerfano})

    assert ejemplo.main() == 0

    assert "no cuelga de ninguna publicacion" in capsys.readouterr().out


def test_con_el_interruptor_puesto_responde_y_respeta_el_limite_de_la_red(
    ejemplo: ModuleType,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """La otra mitad: con `PLANVORTEX_ALLOW_REPLY=1` sí escribe, y antes pregunta el limite.

    El limite de un COMENTARIO no es el de una publicacion, y sale de `social_limits` y no de una
    constante en casa. El mock de `social_limits` sin usar es lo que caza que alguien lo hardcodee.
    """
    monkeypatch.setattr(ejemplo, "PERMITE_RESPONDER", True)
    _camino(httpx_mock)
    httpx_mock.add_response(url=f"{ORG}/publish/pub1/comments?limit=10", json=_hilo([COMENTARIO]))
    httpx_mock.add_response(url=f"{BASE_URL}/social_limits", json={"comment_characters": {"instagram": 2200}})
    httpx_mock.add_response(
        url=f"{ORG}/comments/com1/reply",
        method="POST",
        json={
            "comment": {**COMENTARIO, "our_reply_external_id": "ig-reply-9"},
            "credits_consumed": 0,
        },
    )

    assert ejemplo.main() == 0

    rutas = [ruta(peticion) for peticion in peticiones(httpx_mock)]
    assert "/organizations/org1/comments/com1/reply" in rutas
    # Y no se marca leido aparte: responder ya lo deja leido y respondido.
    assert "/organizations/org1/comments/com1" not in rutas

    respuesta = next(p for p in peticiones(httpx_mock) if ruta(p).endswith("/reply"))
    assert cuerpo(respuesta) == {"text": "Gracias por escribir. Te contestamos por privado."}
    assert "Id en la red: ig-reply-9" in capsys.readouterr().out


def test_en_una_red_que_no_deja_responder_no_se_responde_aunque_este_el_interruptor(
    ejemplo: ModuleType,
    httpx_mock: HTTPXMock,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """La matriz manda sobre el interruptor, que es el orden correcto.

    Es lo que separa un boton que no se pinta de un 400 en la cara del usuario: `reply` puede ser
    `false` aunque la red tenga comentarios.
    """
    monkeypatch.setattr(ejemplo, "PERMITE_RESPONDER", True)
    sin_respuesta = {**ACCIONES, "instagram": {**ACCIONES["instagram"], "reply": False}}
    stub_token(httpx_mock)
    httpx_mock.add_response(url=f"{BASE_URL}/clients?limit=1", json={"clients": [CLIENTE], "total": 1})
    httpx_mock.add_response(
        url=f"{BASE_URL}/clients/cli1/organizations?limit=1",
        json={"organizations": [ORGANIZACION], "total": 1},
    )
    httpx_mock.add_response(url=f"{ORG}/unread_comments", json={"total": 1})
    httpx_mock.add_response(
        url=f"{ORG}/comments?unread=true&limit=10", json={"comments": [COMENTARIO], "total": 1}
    )
    httpx_mock.add_response(url=f"{BASE_URL}/social_comment_actions", json=sin_respuesta)
    httpx_mock.add_response(url=f"{ORG}/publish/pub1/comments?limit=10", json=_hilo([COMENTARIO]))
    httpx_mock.add_response(url=f"{ORG}/comments/com1", method="PUT", json={"comment": COMENTARIO})

    assert ejemplo.main() == 0

    assert "no deja responder desde la API" in capsys.readouterr().out


def test_una_bandeja_vacia_no_es_un_fallo_y_no_pide_nada_mas(
    ejemplo: ModuleType, httpx_mock: HTTPXMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """Sin nada sin leer se para ahi, y ni pide acciones ni hilo. Es la situacion buena."""
    _camino(httpx_mock, bandeja=[])

    assert ejemplo.main() == 0

    assert [ruta(peticion) for peticion in peticiones(httpx_mock)] == [
        "/clients",
        "/clients/cli1/organizations",
        "/organizations/org1/unread_comments",
        "/organizations/org1/comments",
    ]
    assert "Nada pendiente" in capsys.readouterr().out
