"""Comentarios y resenas (capa 2), con los doce metodos del recurso.

Lo que se fija aqui, que es lo que se rompe solo:

- **La bandeja y el hilo son DOS lecturas distintas**, con dos paginaciones distintas: la bandeja va
  con un `offset` numerico y el hilo con el `next_cursor` OPACO de la llamada anterior. Mandar el
  numero donde iba el cursor no da error: devuelve la primera pagina otra vez, para siempre.
- **`unread=False` no se manda.** El servidor enciende el filtro con la MERA PRESENCIA del
  parametro, asi que `unread=false` pediria justo lo contrario de lo que dice quien llama.
- **Responder devuelve TRES cosas** —el comentario, la respuesta y los creditos— y no un comentario
  envuelto, que es lo que parece por el nombre de la ruta.
- **`actions()` sale del catalogo y esta cacheado**: dos llamadas, una peticion.
"""

from __future__ import annotations

from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, query, ruta, unica

ORG = f"{BASE_URL}/organizations/org1"
COMENTARIO = {
    "_id": "com1",
    "id_organization": "org1",
    "text": "Que hogazas mas ricas",
    "read": False,
    "replied": False,
    "social_network": "instagram",
}


def test_la_bandeja_sale_del_sobre_y_manda_los_filtros(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """La lista repetida, el rating repetido, y `unread` como el literal que el servidor lee."""
    httpx_mock.add_response(
        url=(
            f"{ORG}/comments?limit=10&social_network=instagram&social_network=google_business"
            "&id_account=acc1&unread=true&search=hogaza&rating=1&rating=2"
        ),
        json={"comments": [COMENTARIO], "total": 1},
    )

    pagina = cliente.esperar(
        cliente.pv.comments.list(
            "org1",
            limit=10,
            social_network=["instagram", "google_business"],
            id_account="acc1",
            unread=True,
            search="hogaza",
            rating=[1, 2],
        )
    )

    assert (pagina.data, pagina.total) == ([COMENTARIO], 1)
    assert query(unica(httpx_mock)) == {
        "limit": ["10"],
        "social_network": ["instagram", "google_business"],
        "id_account": ["acc1"],
        "unread": ["true"],
        "search": ["hogaza"],
        "rating": ["1", "2"],
    }


def test_unread_false_no_viaja(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    """EL TEST QUE JUSTIFICA LA RAMA. Con `unread=false` el servidor filtraria igual."""
    httpx_mock.add_response(url=f"{ORG}/comments", json={"comments": [], "total": 0})

    cliente.esperar(cliente.pv.comments.list("org1", unread=False))

    assert query(unica(httpx_mock)) == {}


def test_la_bandeja_encadena_paginas(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{ORG}/comments?limit=1&offset=0", json={"comments": [COMENTARIO], "total": 2}
    )
    httpx_mock.add_response(url=f"{ORG}/comments?limit=1&offset=1", json={"comments": [], "total": 2})

    assert cliente.iterar(cliente.pv.comments, "aiterate", "org1", limit=1) == [COMENTARIO]


def test_el_contador_del_badge_devuelve_un_numero(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/unread_comments", json={"total": 7})

    assert cliente.esperar(cliente.pv.comments.unread_count("org1")) == 7
    assert ruta(unica(httpx_mock)) == "/organizations/org1/unread_comments"


def test_el_hilo_vive_en_la_publicacion_y_el_cursor_viaja_tal_cual(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """El `offset` del hilo es el `next_cursor` de la red, una cadena opaca, no un numero."""
    httpx_mock.add_response(
        url=f"{ORG}/publish/pub1/comments?limit=25&offset=QVFIUlo",
        json={"comments": [COMENTARIO], "total": 1, "credits_consumed": 0, "next_cursor": "QVFIUmM"},
    )

    hilo = cliente.esperar(cliente.pv.comments.thread("org1", "pub1", limit=25, offset="QVFIUlo"))

    assert hilo["next_cursor"] == "QVFIUmM"
    assert ruta(unica(httpx_mock)) == "/organizations/org1/publish/pub1/comments"


def test_el_hilo_por_cuenta_es_el_caso_de_google_business(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Una resena cuelga de la FICHA: esa cuenta no tiene ninguna publicacion con la que llamar."""
    httpx_mock.add_response(
        url=f"{ORG}/accounts/acc1/comments",
        json={"comments": [{**COMENTARIO, "rating": 2, "text": ""}], "total": 1, "credits_consumed": 0},
    )

    hilo = cliente.esperar(cliente.pv.comments.thread_by_account("org1", "acc1"))

    # Una resena de solo estrellas llega SIN texto, y eso no es una fila rota.
    assert hilo["comments"][0]["rating"] == 2
    assert hilo["comments"][0]["text"] == ""
    assert ruta(unica(httpx_mock)) == "/organizations/org1/accounts/acc1/comments"


def test_las_respuestas_de_un_comentario(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{ORG}/comments/com1/replies?limit=5",
        json={"comments": [], "total": 0, "credits_consumed": 15},
    )

    hilo = cliente.esperar(cliente.pv.comments.replies("org1", "com1", limit=5))

    # En X cada comentario devuelto es un credito, y por eso la respuesta lo dice.
    assert hilo["credits_consumed"] == 15


def test_responder_devuelve_el_comentario_la_respuesta_y_los_creditos(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """No es un `{comment}` envuelto: son tres campos, y `reply` puede llegar sin `_id`."""
    httpx_mock.add_response(
        url=f"{ORG}/comments/com1/reply",
        method="POST",
        json={
            "comment": {**COMENTARIO, "replied": True, "read": True, "our_reply_external_id": "ig_9"},
            "reply": {"text": "Gracias!", "author": {"is_own": True}},
            "credits_consumed": 200,
        },
    )

    resultado = cliente.esperar(cliente.pv.comments.reply("org1", "com1", "Gracias!"))

    assert resultado["credits_consumed"] == 200
    assert resultado["comment"]["our_reply_external_id"] == "ig_9"
    assert "_id" not in resultado["reply"]
    assert cuerpo(unica(httpx_mock)) == {"text": "Gracias!"}


def test_marcar_leido_y_ocultar_van_por_la_misma_llamada(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url=f"{ORG}/comments/com1",
        method="PUT",
        json={"comment": {**COMENTARIO, "read": True, "hidden": True}},
    )
    httpx_mock.add_response(
        url=f"{ORG}/comments/com1", method="PUT", json={"comment": {**COMENTARIO, "read": True}}
    )

    cambiado = cliente.esperar(cliente.pv.comments.update("org1", "com1", {"read": True, "hidden": True}))
    marcado = cliente.esperar(cliente.pv.comments.mark_read("org1", "com1"))

    assert cambiado["hidden"] is True
    assert marcado["read"] is True
    completo, atajo = peticiones(httpx_mock)
    assert cuerpo(completo) == {"read": True, "hidden": True}
    assert cuerpo(atajo) == {"read": True}


def test_borrar_va_a_la_red(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/comments/com1", method="DELETE", json={"success": True})

    assert cliente.esperar(cliente.pv.comments.remove("org1", "com1")) is None
    assert unica(httpx_mock).method == "DELETE"


def test_las_acciones_salen_del_catalogo_y_se_cachean(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """Dos llamadas, UNA peticion: la matriz es una constante del despliegue.

    Y `actions_for` de una red sin comentarios devuelve `None`, que no es lo mismo que un diccionario
    con las cuatro banderas en `False`: WhatsApp no tiene comentarios, no es que no deje hacer nada.
    """
    httpx_mock.add_response(
        url=f"{BASE_URL}/social_comment_actions",
        json={
            "instagram": {"reply": True, "hide": True, "delete_own": True, "delete_others": False},
            "linkedin": {"reply": True, "hide": False, "delete_own": True, "delete_others": False},
        },
    )

    matriz = cliente.esperar(cliente.pv.comments.actions())
    linkedin = cliente.esperar(cliente.pv.comments.actions_for("linkedin"))
    whatsapp = cliente.esperar(cliente.pv.comments.actions_for("whatsapp"))

    assert matriz["instagram"]["delete_others"] is False
    assert linkedin == {"reply": True, "hide": False, "delete_own": True, "delete_others": False}
    assert whatsapp is None
    assert len(peticiones(httpx_mock)) == 1
