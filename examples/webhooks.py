"""Un receptor de webhooks de PlanVortex, entero y sin dependencias.

    PLANVORTEX_CLIENT_SECRET=... uv run python examples/webhooks.py

Levanta un servidor en el puerto 3210. Y si le pasas `--self-test` **se manda a si mismo** una
entrega firmada como la firma PlanVortex, para que veas el camino completo sin exponer tu maquina a
internet ni esperar a que llegue un comentario de verdad:

    uv run python examples/webhooks.py --self-test

Va con `http.server` A PROPOSITO, no con Flask ni con FastAPI: `handle_webhook_request` solo pide el
cuerpo CRUDO y algo con un `.get(nombre)` para las cabeceras, que es lo que tiene el servidor pelado
de la biblioteca estandar. En Flask son `request.get_data()` y `request.headers`; en FastAPI,
`await request.body()` y `request.headers`; en Django, `request.body` y `request.headers`. El cuerpo
de la funcion es el mismo en los tres.

LO QUE MAS SE HACE MAL AQUI ES EL CUERPO. La firma es un HMAC sobre los BYTES que llegaron: en
cuanto se pasa por un parser de JSON y se vuelve a serializar, un espacio de mas o una clave
reordenada cambian la firma y la verificacion falla. `request.json` no vale. Y en Django hace falta
`@csrf_exempt`, porque PlanVortex no manda el token de CSRF de nadie.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from planvortex.types import message_contact, message_direction
from planvortex.webhooks import (
    WEBHOOK_SIGNATURE_HEADERS,
    WebhookBodyError,
    WebhookChange,
    WebhookSignatureError,
    handle_webhook_request,
    is_account_state_change,
    is_comment_change,
    is_integration_error_change,
    is_message_change,
)

PUERTO = 3210
SECRETO = "secreto-de-ejemplo"


class Receptor(BaseHTTPRequestHandler):
    """El endpoint. Son ocho lineas de verdad; el resto es el servidor de juguete."""

    # El nombre en mayusculas no es un descuido: `BaseHTTPRequestHandler` despacha buscando
    # `do_` + el metodo HTTP.
    def do_POST(self) -> None:
        # EL CUERPO CRUDO, en bytes y sin tocar. Esto es lo unico que la firma cubre.
        cuerpo = self.rfile.read(int(self.headers.get("content-length") or 0))
        try:
            cambios = handle_webhook_request(cuerpo, self.headers, SECRETO)
        except WebhookSignatureError as error:
            # Una firma que no cuadra se contesta con 401 y NO se procesa. Es la unica linea que
            # separa tu endpoint de que cualquiera te invente comentarios.
            print(f"  x {error.message}")
            self._responder(401)
            return
        except WebhookBodyError as error:
            # Otra cosa: la firma valia y el cuerpo no es lo que dice ser. 400, y a mirar el proxy.
            print(f"  x {error.message}")
            self._responder(400)
            return

        # Se contesta ANTES de ponerse a trabajar. PlanVortex no reintenta una entrega que se cae,
        # asi que si lo tuyo tarda, se encola aqui y se vuelve.
        self._responder(200)
        _procesar(cambios)

    def _responder(self, estado: int) -> None:
        self.send_response(estado)
        self.send_header("content-length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # `format` lo nombra la clase base
        """El log de `http.server` a la basura: lo que interesa lo imprime el manejador."""


def _procesar(cambios: list[WebhookChange]) -> None:
    """Los cuatro tipos de evento, con los predicados y no con un `if change["field"] == ...`.

    Ese `if` NO estrecha: `UnknownWebhookChange` declara `field: str`, asi que ningun comprobador
    puede descartarlo de la rama y te quedas con la union. Los predicados si.

    Y hace falta el `else`, aunque hoy no lo dispare nada: la lista de eventos crece, y un `field`
    que esta version no conoce tiene que caer en un sitio en vez de ser un `KeyError`.
    """
    print(f"\n  {len(cambios)} cambio(s) en la entrega")
    for cambio in cambios:
        if is_comment_change(cambio):
            # META REPITE ENTREGAS. En produccion, deduplica por `external_id` antes de tocar nada.
            comentario = cambio.get("commentObj")
            if comentario is None:
                # Llega cuando el autor borro uno que nunca habiamos visto: hay aviso y no hay nada
                # que marcar. No es un error.
                print("  · un comentario que no teniamos guardado")
            else:
                autor = comentario["author"].get("name") or "anonimo"
                print(f"  · comentario de {autor}: {comentario.get('text') or '(sin texto)'}")

        elif is_message_change(cambio):
            # `messageObj` PUEDE faltar en `messaging_seen` y `messaging_error`: lo que se confirma
            # o lo que fallo no tiene por que ser un mensaje nuestro.
            mensaje = cambio.get("messageObj")
            if mensaje is None:
                print(f"  · {cambio['field']} sin mensaje asociado")
            else:
                contacto = message_contact(mensaje)
                con_quien = f" con {contacto['name']}" if contacto and contacto.get("name") else ""
                print(
                    f"  · {cambio['field']} ({message_direction(mensaje)}){con_quien}: "
                    f"{mensaje.get('text') or '—'}"
                )

        elif is_integration_error_change(cambio):
            # El unico evento que NO cuelga de una cuenta: una integracion es de la organizacion.
            print(f"  · la integracion {cambio['provider']} fallo con {cambio['error_code']}")

        elif is_account_state_change(cambio):
            print(f"  · la cuenta {cambio['id_account']} ({cambio['social_network']}): {cambio['field']}")

        else:
            # Un evento posterior a esta version del paquete. Se ignora, no se revienta.
            print(f"  · evento desconocido: {cambio['field']}")


def _autoprueba() -> None:
    """Una entrega firmada contra el servidor de arriba, para ver el camino sin salir de la maquina.

    Lo importante de estas lineas es lo que ensenan del otro lado: la firma va sobre EXACTAMENTE los
    bytes que se mandan —de ahi el `cuerpo` calculado una vez y reutilizado— y lleva el algoritmo
    delante (`sha256=<hex>`), que es la forma que espera `handle_webhook_request`.
    """
    entrega = [
        {
            "field": "comments",
            "id_account": "acc1",
            "id_organization": "org1",
            "social_network": "instagram",
            "commentObj": {
                "_id": "com1",
                "external_id": "ig-1",
                "text": "Que horario teneis los domingos?",
                "author": {"name": "Marta"},
                "social_network": "instagram",
            },
        },
        {
            "field": "integration_error",
            "id_integration": "int1",
            "id_organization": "org1",
            "provider": "google_drive",
            "error_code": 2201,
        },
        # Uno que esta version no conoce, para ver que cae en el `else` y no revienta nada.
        {"field": "un_evento_del_futuro"},
    ]
    cuerpo = json.dumps(entrega).encode("utf8")
    firma = hmac.new(SECRETO.encode("utf8"), cuerpo, hashlib.sha256).hexdigest()

    print(f"\n  El servidor contesto {_enviar(cuerpo, f'sha256={firma}')}")

    # Y la misma entrega con la firma estropeada, que es la mitad que de verdad hay que ver: tiene
    # que contestar 401 y no procesar nada.
    print(f"  Con la firma cambiada: {_enviar(cuerpo, 'sha256=0000')}")


def _enviar(cuerpo: bytes, firma: str) -> int:
    """Una entrega contra el propio servidor, devolviendo el estado. 401 tambien es un resultado."""
    peticion = urllib.request.Request(
        f"http://127.0.0.1:{PUERTO}/webhooks/planvortex",
        data=cuerpo,
        headers={
            "content-type": "application/json",
            WEBHOOK_SIGNATURE_HEADERS["sha256"]: firma,
        },
    )
    try:
        with urllib.request.urlopen(peticion) as respuesta:
            estado: int = respuesta.status
            return estado
    except urllib.error.HTTPError as error:
        # Se cierra, aunque sea un error: `HTTPError` es un fichero abierto, y dejarlo al recolector
        # suelta un `ResourceWarning` que en una suite con los avisos en modo error es un fallo.
        with error:
            return int(error.code)


def main(autoprueba: bool) -> int:
    servidor = HTTPServer(("127.0.0.1", PUERTO), Receptor)
    print(f"Escuchando en http://127.0.0.1:{PUERTO}/webhooks/planvortex")
    print("Esa es la URL que se registra con `pv.apps.update(id_app, webhook_url=...)`.")

    if not autoprueba:
        print("Ctrl-C para parar. Con `--self-test` se manda una entrega a si mismo.")
        try:
            servidor.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            servidor.server_close()
        return 0

    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        _autoprueba()
    finally:
        servidor.shutdown()
        hilo.join()
        servidor.server_close()
    return 0


if __name__ == "__main__":
    import os

    SECRETO = os.environ.get("PLANVORTEX_CLIENT_SECRET") or SECRETO
    raise SystemExit(main("--self-test" in sys.argv))
