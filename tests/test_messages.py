"""Mensajeria (capa 2): conversaciones, hilos, envio y plantillas.

Lo que se fija aqui:

- **`conversations_total` son DOS rutas**, la de la organizacion y la de una cuenta, y por eso son
  dos metodos: un argumento opcional que cambia la URL en silencio es justo lo que devuelve el
  numero de otro.
- **`in_response_external_id` viaja en el cuerpo.** El servidor no lo copiaba hasta el 2026-08-24 y
  eso dejaba `comment_message` y `publication_message` inalcanzables desde la API publica.
- **Borrar una plantilla lleva las dos cosas en la QUERY**, identificador y nombre, no en el cuerpo:
  Meta borra por nombre y usa el `id` para desambiguar entre idiomas.
"""

from __future__ import annotations

from pytest_httpx2 import HTTPXMock

from tests.conftest import BASE_URL, ClienteDePrueba
from tests.contrato import cuerpo, peticiones, query, ruta, unica

ORG = f"{BASE_URL}/organizations/org1"
CUENTA = f"{ORG}/accounts/acc1"
CONTACTO = {"_id": "con1", "name": "Marta"}
MENSAJE = {
    "_id": "msg1",
    "text": "Abrimos de 9 a 14",
    "message_type": "simple_message",
    "message_options": {},
    "contact_id": CONTACTO,
}


def test_las_conversaciones_se_listan_y_se_iteran(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    conversacion = {"contact": CONTACTO, "last_message_date": "2026-08-27T10:00:00Z", "unread": 2}
    httpx_mock.add_response(
        url=f"{CUENTA}/conversations?limit=1&offset=0",
        json={"conversations": [conversacion], "total": 1},
        is_reusable=True,
    )
    httpx_mock.add_response(
        url=f"{CUENTA}/conversations?limit=1&offset=1", json={"conversations": [], "total": 1}
    )

    pagina = cliente.esperar(cliente.pv.messages.conversations("org1", "acc1", limit=1, offset=0))
    todas = cliente.iterar(cliente.pv.messages, "aiterate_conversations", "org1", "acc1", limit=1)

    # Una conversacion NO tiene `_id`: lo que abre el hilo es el `_id` del contacto.
    assert pagina.data == todas == [conversacion]
    assert todas[0]["contact"]["_id"] == "con1"


def test_los_totales_de_conversaciones_son_dos_rutas(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/conversations_total?group_by=day", json={"stats": [], "group": "day"})
    httpx_mock.add_response(url=f"{CUENTA}/conversations_total", json={"total": 12})

    organizacion = cliente.esperar(cliente.pv.messages.conversation_totals("org1", group_by="day"))
    cuenta = cliente.esperar(cliente.pv.messages.account_conversation_totals("org1", "acc1"))

    # Sin `group_by` es `{total}` y con el es `{stats, group}`: dos respuestas, no una con campos mas.
    assert organizacion == {"stats": [], "group": "day"}
    assert cuenta == {"total": 12}
    de_organizacion, de_cuenta = peticiones(httpx_mock)
    assert ruta(de_organizacion) == "/organizations/org1/conversations_total"
    assert ruta(de_cuenta) == "/organizations/org1/accounts/acc1/conversations_total"


def test_el_hilo_con_un_contacto_se_lista_y_se_itera(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url=f"{CUENTA}/messages/con1?limit=1&offset=0",
        json={"messages": [MENSAJE], "total": 1},
        is_reusable=True,
    )
    httpx_mock.add_response(url=f"{CUENTA}/messages/con1?limit=1&offset=1", json={"messages": [], "total": 1})

    pagina = cliente.esperar(cliente.pv.messages.list("org1", "acc1", "con1", limit=1, offset=0))
    todos = cliente.iterar(cliente.pv.messages, "aiterate", "org1", "acc1", "con1", limit=1)

    assert pagina.data == todos == [MENSAJE]


def test_enviar_un_mensaje_simple(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{CUENTA}/messages/con1", method="POST", json={"message": MENSAJE})

    enviado = cliente.esperar(
        cliente.pv.messages.send(
            "org1", "acc1", "con1", {"message_type": "simple_message", "text": "Abrimos de 9 a 14"}
        )
    )

    assert enviado == MENSAJE
    assert cuerpo(unica(httpx_mock)) == {
        "message_type": "simple_message",
        "text": "Abrimos de 9 a 14",
    }


def test_la_respuesta_privada_a_un_comentario_lleva_el_identificador_de_la_red(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """EL CAMPO QUE EL SERVIDOR NO LEIA. Sin el, el mensaje sale con el destinatario vacio."""
    httpx_mock.add_response(
        url=f"{CUENTA}/messages/con1",
        method="POST",
        json={"message": {**MENSAJE, "message_type": "comment_message"}},
    )

    cliente.esperar(
        cliente.pv.messages.send(
            "org1",
            "acc1",
            "con1",
            {
                "message_type": "comment_message",
                "text": "Te escribo por privado",
                "in_response_external_id": "ig_comment_9",
            },
        )
    )

    assert cuerpo(unica(httpx_mock))["in_response_external_id"] == "ig_comment_9"


def test_el_contador_de_mensajes_sin_leer(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{ORG}/unread_messages", json={"total": 3})

    assert cliente.esperar(cliente.pv.messages.unread_count("org1")) == 3


def test_borrar_los_mensajes_de_una_cuenta(cliente: ClienteDePrueba, httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=f"{CUENTA}/messages", method="DELETE", json={"success": True})

    assert cliente.esperar(cliente.pv.messages.remove_by_account("org1", "acc1")) is None
    assert ruta(unica(httpx_mock)) == "/organizations/org1/accounts/acc1/messages"


def test_las_plantillas_se_listan_se_crean_y_se_borran(
    cliente: ClienteDePrueba, httpx_mock: HTTPXMock
) -> None:
    """El formato es el de Meta y no se traduce: `name`, `status`, `components`, `language`."""
    plantilla = {"name": "horario", "status": "APPROVED", "language": "es", "components": []}
    httpx_mock.add_response(
        url=f"{CUENTA}/message_templates?limit=10", json={"templates": [plantilla], "total": 1}
    )
    httpx_mock.add_response(url=f"{CUENTA}/message_templates", method="POST", json={"template": plantilla})
    httpx_mock.add_response(
        url=f"{CUENTA}/message_templates?template_id=t1&template_name=horario",
        method="DELETE",
        json={"success": True},
    )

    pagina = cliente.esperar(cliente.pv.messages.templates("org1", "acc1", limit=10))
    creada = cliente.esperar(cliente.pv.messages.create_template("org1", "acc1", plantilla))
    borrada = cliente.esperar(cliente.pv.messages.delete_template("org1", "acc1", "t1", "horario"))

    assert pagina.data == [plantilla]
    assert creada == plantilla
    assert borrada is None
    _, crear, borrar = peticiones(httpx_mock)
    assert cuerpo(crear) == plantilla
    # Las dos claves en la QUERY, no en el cuerpo: es un DELETE.
    assert query(borrar) == {"template_id": ["t1"], "template_name": ["horario"]}
    assert cuerpo(borrar) is None
