"""`examples/webhooks.py`, con su servidor levantado de verdad.

Este no se prueba contra un servidor de mentira, sino AL REVES: el ejemplo ES el servidor, y el test
le manda entregas. Es el unico de los cinco que puede recorrerse entero sin red y sin credenciales,
asi que se recorre entero — incluida la mitad que mas importa, que es la que RECHAZA.

Las tres cosas que se fijan:

  - Una entrega bien firmada se procesa y contesta 200.
  - Una con la firma cambiada contesta **401 y no procesa nada**. Esa linea es lo unico que separa
    un endpoint de webhooks de que cualquiera te invente comentarios, y quitarla no rompe ningun
    camino feliz.
  - Un `field` que esta version del paquete no conoce cae en el `else` en vez de reventar. La lista
    de eventos crece, y un receptor que se cae con un evento nuevo se cae en produccion un martes.
"""

from __future__ import annotations

import importlib.util
import socket
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parent.parent


def _puerto_libre() -> int:
    """Un puerto que ahora mismo no usa nadie. El ejemplo lo lleva fijo y aqui estorbaria."""
    with socket.socket() as sonda:
        sonda.bind(("127.0.0.1", 0))
        puerto: int = sonda.getsockname()[1]
        return puerto


@pytest.fixture
def ejemplo(monkeypatch: pytest.MonkeyPatch) -> Iterator[ModuleType]:
    """El modulo del ejemplo, cargado por su ruta: `examples/` no es un paquete a proposito."""
    spec = importlib.util.spec_from_file_location("ejemplo_webhooks", RAIZ / "examples" / "webhooks.py")
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["ejemplo_webhooks"] = modulo
    try:
        spec.loader.exec_module(modulo)
        monkeypatch.setattr(modulo, "PUERTO", _puerto_libre())
        yield modulo
    finally:
        del sys.modules["ejemplo_webhooks"]


def test_la_autoprueba_acepta_la_firma_buena_y_rechaza_la_mala(
    ejemplo: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """El camino entero, con HTTP de verdad contra el propio servidor del ejemplo.

    Las dos mitades en la misma prueba a proposito: un receptor que aceptara TODO pasaria la primera
    con nota. Lo que demuestra que la firma se comprueba es el 401 de la segunda.
    """
    assert ejemplo.main(True) == 0

    salida = capsys.readouterr().out
    assert "El servidor contesto 200" in salida
    assert "Con la firma cambiada: 401" in salida

    # Y lo de la entrega buena se ha procesado: los tres cambios, cada uno por su rama.
    assert "3 cambio(s) en la entrega" in salida
    assert "comentario de Marta" in salida
    assert "la integracion google_drive fallo con 2201" in salida
    assert "evento desconocido: un_evento_del_futuro" in salida

    # La entrega con la firma cambiada NO ha llegado a procesarse: si lo hubiera hecho, habria un
    # segundo bloque de tres cambios. Un `count` y no un `in`, que es lo que lo distingue.
    assert salida.count("3 cambio(s) en la entrega") == 1


def test_cada_rama_lee_lo_suyo_y_aguanta_lo_que_puede_faltar(
    ejemplo: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """Los cuatro tipos de evento por separado, con sus ausencias.

    Las tres ausencias son reales y ninguna es un error: un comentario borrado que nunca vimos llega
    sin `commentObj`, y un `messaging_seen` llega sin `messageObj` porque lo que se confirma no tiene
    por que ser un mensaje nuestro. Un receptor que las leyera a pelo se cae con un `KeyError`.
    """
    cambios: list[Any] = [
        {"field": "comments", "id_account": "acc1", "id_organization": "org1", "social_network": "instagram"},
        {
            "field": "messaging_seen",
            "id_account": "acc1",
            "id_organization": "org1",
            "social_network": "facebook",
        },
        {
            "field": "messages",
            "id_account": "acc1",
            "id_organization": "org1",
            "social_network": "facebook",
            "messageObj": {
                "_id": "msg1",
                "text": "Hola",
                "from_contact_id": {"_id": "con1", "name": "Marta"},
            },
        },
        {
            "field": "new_account",
            "id_account": "acc2",
            "id_organization": "org1",
            "social_network": "bluesky",
        },
    ]

    ejemplo._procesar(cambios)

    salida = capsys.readouterr().out
    assert "un comentario que no teniamos guardado" in salida
    assert "messaging_seen sin mensaje asociado" in salida
    assert "messages (incoming) con Marta: Hola" in salida
    assert "la cuenta acc2 (bluesky): new_account" in salida


def test_un_cuerpo_que_no_es_una_lista_se_contesta_con_400(ejemplo: ModuleType) -> None:
    """La otra forma de entrega mala, que NO es la firma.

    El error natural es tratar el cuerpo como un objeto, y no tiene sintoma hasta que se lee un
    campo que siempre falta. La libreria lo rechaza, y el ejemplo lo distingue del 401 porque la
    causa y lo que hay que mirar son distintas: aqui la firma valia.
    """
    import hashlib
    import hmac
    import json
    import threading
    from http.server import HTTPServer

    cuerpo = json.dumps({"field": "comments"}).encode("utf8")
    firma = hmac.new(ejemplo.SECRETO.encode("utf8"), cuerpo, hashlib.sha256).hexdigest()

    servidor = HTTPServer(("127.0.0.1", ejemplo.PUERTO), ejemplo.Receptor)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        assert ejemplo._enviar(cuerpo, f"sha256={firma}") == 400
    finally:
        servidor.shutdown()
        hilo.join()
        servidor.server_close()
