"""La bandeja de comentarios, entera: el badge, la lista, la matriz de acciones, el hilo y la
respuesta.

Es la seccion que mas gente entiende mal, porque son DOS lecturas y no una:

    pv.comments.list()    la BANDEJA — sale de la base de datos de PlanVortex, es gratis, y es una
                          foto de la ultima vez que se leyo la red (`collected_date` dice de cuando)
    pv.comments.thread()  el HILO — pregunta a la red EN ESE MOMENTO, y en X cuesta un credito por
                          comentario devuelto

Pintar una lista con la segunda es como se hace una factura sin querer.

    PLANVORTEX_CLIENT_ID=... PLANVORTEX_CLIENT_SECRET=... \\
    PLANVORTEX_BASE_URL=http://localhost:3000/v1.0.0 \\
    uv run python examples/comments.py

RESPONDER ES PUBLICO E INMEDIATO: lo que se escriba aqui lo ve cualquiera que pase por el post, y le
llega a una persona. Por eso este ejemplo por defecto solo LEE y marca como leido. Para que ademas
responda, hay que pedirlo en voz alta:

    PLANVORTEX_ALLOW_REPLY=1 uv run python examples/comments.py

Todo esto exige plan de pago: con uno gratuito, la primera llamada contesta el error 516.
"""

from __future__ import annotations

import os
import sys

from planvortex import PlanVortex, PlanVortexError
from planvortex.types import Comment, CommentActions, CommentThread, account_id, publication_id

PERMITE_RESPONDER = os.environ.get("PLANVORTEX_ALLOW_REPLY") == "1"


def main() -> int:
    with PlanVortex() as pv:
        # 1. Cliente y organizacion, igual que en `publish.py`.
        clientes = pv.clients.list(limit=1)
        if not clientes.data:
            raise SystemExit("La app no ve ningun cliente: revisa las credenciales.")
        cliente = clientes.data[0]

        organizaciones = pv.clients.organizations(cliente["_id"], limit=1)
        if not organizaciones.data:
            raise SystemExit(f"El cliente {cliente['name']} no tiene ninguna organizacion.")
        organizacion = organizaciones.data[0]
        print(f"Organizacion: {organizacion['name']} ({organizacion['_id']})")

        # 2. EL BADGE. Es una llamada suya, no el `total` de la bandeja: lo NUESTRO no cuenta como
        #    pendiente de leer, asi que los dos numeros no coinciden y no es un fallo.
        print(f"Sin leer: {pv.comments.unread_count(organizacion['_id'])}")

        # 3. LA BANDEJA. No llama a ninguna red, no gasta creditos y no falla porque una cuenta este
        #    desconectada. `rating` es lo que la hace usable en una ficha de resenas —"ensename las
        #    de una y dos estrellas"— y no deja fuera nada en las redes sin estrellas, porque sus
        #    comentarios no traen ninguna.
        bandeja = pv.comments.list(organizacion["_id"], unread=True, limit=10)
        print(f"Bandeja: {len(bandeja.data)} de {bandeja.total} sin leer")
        for comentario in bandeja.data:
            print(f"  {_describir(comentario)}")

        if not bandeja.data:
            # Sin nada sin leer no hay ejemplo que ensenar, pero tampoco es un fallo.
            print("Nada pendiente. Prueba sin `unread=True` para ver la bandeja entera.")
            return 0
        objetivo = bandeja.data[0]

        # 4. QUE SE PUEDE HACER con los comentarios de ESA red, antes de pintar un boton. No se
        #    deduce de `social_capabilities`: que una red tenga comentarios no dice nada de lo que
        #    deja hacer con ellos. Instagram, X y Bluesky no dejan borrar el de otro, LinkedIn no
        #    tiene "ocultar", y Google Business solo deja borrar NUESTRA respuesta.
        acciones = pv.comments.actions_for(objetivo["social_network"])
        print(f"Acciones en {objetivo['social_network']}: {_describir_acciones(acciones)}")

        # 5. EL HILO, en vivo. La red manda: de lo guardado solo sobreviven `_id`, `read` y
        #    `replied`, y un comentario que la red ya no devuelve se marca borrado.
        hilo = _leer_hilo(pv, organizacion["_id"], objetivo)
        if hilo is None:
            print("Ese comentario no cuelga de ninguna publicacion nuestra: no hay hilo que leer.")
        else:
            # `credits_consumed` es dinero de verdad, y solo en X: en las demas es 0. `next_cursor`
            # es el token OPACO de la red, que se devuelve tal cual como `offset` en la llamada
            # siguiente — no es un numero de elementos, que es como pagina la bandeja.
            hay_mas = " · hay mas paginas" if hilo.get("next_cursor") else ""
            print(
                f"Hilo: {len(hilo['comments'])} de {hilo['total']} · "
                f"creditos gastados: {hilo['credits_consumed']}{hay_mas}"
            )
            for comentario in hilo["comments"]:
                propio = "(nuestro) " if comentario["author"].get("is_own") else ""
                print(f"  {propio}{_describir(comentario)}")

        # 6. Y lo que se hace con el. Marcar leido es NUESTRO: no toca la red, no gasta creditos y
        #    no puede fallar por lo que la red permita. Responder es lo otro.
        if not (PERMITE_RESPONDER and acciones is not None and acciones["reply"]):
            leido = pv.comments.mark_read(organizacion["_id"], objetivo["_id"])
            print(f"Marcado como leido: {leido['_id']}")
            if PERMITE_RESPONDER:
                print(f"{objetivo['social_network']} no deja responder desde la API.")
            else:
                print("Para responder de verdad: PLANVORTEX_ALLOW_REPLY=1")
            return 0

        _responder(pv, organizacion["_id"], objetivo)

    return 0


def _responder(pv: PlanVortex, id_organization: str, comentario: Comment) -> None:
    """La respuesta, con su limite propio comprobado antes de mandarla.

    El limite de un COMENTARIO no es el de una publicacion: Facebook admite 60.000 caracteres en un
    post y 8.000 en un comentario, y pasarse contesta el error 948. Sale de `social_limits`, que es
    quien lo valida, y nunca de una constante en casa.
    """
    limites = pv.catalog.social_limits()
    maximo = (limites.get("comment_characters") or {}).get(comentario["social_network"], 0)
    texto = "Gracias por escribir. Te contestamos por privado."
    if maximo and len(texto) > maximo:
        raise SystemExit(f"La respuesta no cabe: {len(texto)}/{maximo} caracteres.")

    resultado = pv.comments.reply(id_organization, comentario["_id"], texto)
    # `reply._id` puede faltar: la respuesta se publica primero en la red y se guarda despues, y esa
    # segunda escritura no puede tumbar una peticion que la red ya cumplio. Lo que SIEMPRE identifica
    # nuestra respuesta es `our_reply_external_id`.
    identificador = resultado["comment"].get("our_reply_external_id") or "(desconocido)"
    print(f"Respondido. Id en la red: {identificador} · creditos: {resultado['credits_consumed']}")


def _leer_hilo(pv: PlanVortex, id_organization: str, comentario: Comment) -> CommentThread | None:
    """El hilo, pedido por donde corresponda. `None` cuando no hay ninguno, que es un caso normal.

    Google Business es la unica red cuyas resenas cuelgan de la FICHA y no de una publicacion
    nuestra, asi que tiene su propia llamada. Y hay comentarios sin publicacion detras —un video
    subido a mano, un post anterior a PlanVortex—: no hay hilo que pedir, y tampoco es un error.
    """
    if comentario["social_network"] == "google_business":
        return pv.comments.thread_by_account(id_organization, account_id(comentario), limit=10)
    id_publicacion = publication_id(comentario)
    if id_publicacion is None:
        return None
    return pv.comments.thread(id_organization, id_publicacion, limit=10)


def _describir(comentario: Comment) -> str:
    """Una linea por comentario, con las dos cosas que sorprenden.

    El texto PUEDE venir vacio —una resena de solo estrellas no lleva ninguno—, y `rating` solo
    existe en las redes de resenas, asi que su ausencia significa "esta red no tiene eso" y nunca
    cero estrellas.
    """
    estrellas = comentario.get("rating")
    prefijo = "" if estrellas is None else f"{'*' * estrellas} "
    autor = comentario["author"].get("name") or "anonimo"
    return f"[{comentario['social_network']}] {prefijo}{autor}: {comentario.get('text') or '(sin texto)'}"


def _describir_acciones(acciones: CommentActions | None) -> str:
    """Las cuatro banderas, que son siempre cuatro: una ausente seria indistinguible de un descuido."""
    if acciones is None:
        return "ninguna (esa red no tiene comentarios)"
    permitidas = [nombre for nombre, vale in acciones.items() if vale]
    return ", ".join(permitidas) if permitidas else "ninguna"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PlanVortexError as error:
        # Los errores de la API se clasifican por `code`, NUNCA por el status: todos llegan con 400.
        if error.code == 516:
            print("Los comentarios son de plan de pago: con el gratuito no hay bandeja.", file=sys.stderr)
        print(f"[{error.family} {error.code}] {error.message}", error.data, file=sys.stderr)
        raise SystemExit(1) from error
