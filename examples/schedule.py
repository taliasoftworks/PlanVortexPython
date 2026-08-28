"""El calendario: lo que hay programado, moverlo de hora, y rescatar lo que fallo.

`publish.py` es la pantalla de componer — subir un fichero y crear la publicacion. Esta es la otra:
lo que se pinta DESPUES, cuando ya hay cosas en cola y algo no ha salido.

    PLANVORTEX_CLIENT_ID=... PLANVORTEX_CLIENT_SECRET=... \\
    PLANVORTEX_BASE_URL=http://localhost:3000/v1.0.0 \\
    uv run python examples/schedule.py

TRES COSAS QUE NO SE VEN VENIR, y que son el motivo de que este ejemplo exista aparte:

  - `order_by_publish=True` no es solo un orden: cambia POR QUE FECHA se filtra. Sin el,
    `from_date`/`to_date` miran la fecha de CREACION, que es lo que quiere un registro de actividad
    y nunca lo que quiere un calendario.
  - Una publicacion invalida NO llega como excepcion. Llega como un 200 en estado `withErrors` con
    el motivo dentro, porque validar contra la red no es un fallo de tu peticion. Un `try/except`
    no la ve.
  - EDITAR PONE EL CONTADOR DE REINTENTOS A CERO, y esa es la salida cuando se agotan los tres: el
    contador cuenta intentos de publicar ESE contenido, y al editarlo ya es otro.

Este ejemplo MUEVE una publicacion de hora y REINTENTA una fallida: las dos son escrituras, pero
ninguna sale a la red por si sola —mover solo cambia la cola y el reintento lo pide explicitamente—,
asi que no lleva interruptor como el de responder comentarios.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from planvortex import PlanVortex, PlanVortexError
from planvortex.types import Publication


def main() -> int:
    with PlanVortex() as pv:
        clientes = pv.clients.list(limit=1)
        if not clientes.data:
            raise SystemExit("La app no ve ningun cliente: revisa las credenciales.")
        organizaciones = pv.clients.organizations(clientes.data[0]["_id"], limit=1)
        if not organizaciones.data:
            raise SystemExit(f"El cliente {clientes.data[0]['name']} no tiene ninguna organizacion.")
        organizacion = organizaciones.data[0]
        print(f"Organizacion: {organizacion['name']} ({organizacion['_id']})")

        # 1. LA SEMANA QUE VIENE. `order_by_publish=True` es lo que hace de esto un calendario: sin
        #    el, las dos fechas filtran por `creation_date` y saldria lo que se CREO esta semana,
        #    que no es lo que va a salir esta semana.
        #
        #    Las dos fechas llevan zona horaria o la libreria lanza antes de mandar nada: sin
        #    offset, el servidor las leeria en la SUYA (§ Trampa P8 del roadmap).
        ahora = datetime.now(timezone.utc)
        semana = pv.publications.list(
            organizacion["_id"],
            from_date=ahora,
            to_date=ahora + timedelta(days=7),
            order_by_publish=True,
            state=["ready"],
            limit=50,
        )
        print(f"\nProgramadas para los proximos 7 dias: {semana.total}")
        for publicacion in semana.data:
            print(f"  {_describir(publicacion)}")

        # 2. LO QUE FALLO. Es un estado, no una excepcion: `withErrors` sale de la MISMA llamada,
        #    solo cambiando el filtro. Quien solo mire los `try/except` no se entera de ninguna.
        #
        #    `iterate` pagina solo, y tiene un tope duro de paginas para que un bucle no se coma la
        #    cuota si el servidor devolviera siempre la misma.
        fallidas = list(pv.publications.iterate(organizacion["_id"], state=["withErrors"], limit=25))
        print(f"\nCon errores: {len(fallidas)}")
        for publicacion in fallidas:
            print(f"  {_describir(publicacion)}")
            for fallo in publicacion.get("publication_errors") or []:
                # `code` es del catalogo de PlanVortex, NUNCA un status HTTP.
                print(f"      [{fallo['code']}] {fallo.get('message')}")

        # 3. MOVER UNA DE HORA. `update` acepta un `datetime` igual que `create`, y solo se manda el
        #    campo que cambia: lo que no va en el cuerpo se queda como estaba.
        if semana.data:
            movida = pv.publications.update(
                organizacion["_id"],
                semana.data[0]["_id"],
                {"publish_date": ahora + timedelta(days=1, hours=2)},
            )
            print(f"\nMovida: {_describir(movida)}")

        # 4. Y RESCATAR UNA FALLIDA. El reintento ocurre EN LA PETICION, asi que la respuesta ya
        #    dice si esta vez salio.
        if fallidas:
            _reintentar(pv, organizacion["_id"], fallidas[0])
        else:
            print("\nNada que reintentar, que es la situacion buena.")

    return 0


def _reintentar(pv: PlanVortex, id_organization: str, publicacion: Publication) -> None:
    """Un reintento, con las dos formas de que no valga la pena pedirlo.

    El tope de intentos NO es tres a fuerza de escribirlo: sale de `publication_limits`, que es
    quien lo publica. Y cada llamada gasta uno aunque vuelva a fallar por el contenido, asi que
    reintentar lo que fallo por el contenido es tirar los tres — lo que arregla eso es EDITAR, que
    ademas pone el contador a cero.
    """
    limites = pv.catalog.publication_limits()
    intentos = publicacion.get("retries", 0)
    if intentos >= limites["max_retries"]:
        print(f"\nSin reintentos: {intentos} de {limites['max_retries']} gastados. Editala y se resetea.")
        return

    resultado = pv.publications.retry(id_organization, publicacion["_id"])
    reintentada = resultado["publication"]
    if reintentada["state"] == "sended":
        print(f"\nReintentada y publicada: {reintentada['_id']}")
    else:
        # Ha vuelto a fallar, y por lo mismo casi siempre: el contenido no ha cambiado.
        print(f"\nReintentada y sigue fallando ({reintentada['state']}):")
        for fallo in reintentada.get("publication_errors") or []:
            print(f"  [{fallo['code']}] {fallo.get('message')}")


def _describir(publicacion: Publication) -> str:
    """Una linea por publicacion.

    `publish_date` puede faltar —una publicada al vuelo no se programo nunca— y `text` tambien: una
    publicacion puede ser solo un video. Ninguna de las dos ausencias es un error.
    """
    cuando = publicacion.get("publish_date") or "(sin fecha)"
    texto = (publicacion.get("text") or "(sin texto)").replace("\n", " ")
    recorte = texto if len(texto) <= 50 else f"{texto[:47]}..."
    return f"{cuando} · {publicacion['state']:<10} · {recorte}"


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PlanVortexError as error:
        # Los errores de la API se clasifican por `code`, NUNCA por el status: todos llegan con 400.
        print(f"[{error.family} {error.code}] {error.message}", error.data, file=sys.stderr)
        raise SystemExit(1) from error
