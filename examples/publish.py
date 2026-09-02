"""El camino de publicar, entero: subir una imagen y programar una publicacion.

Es el ejemplo que cierra la fase 5 y lo que vende `/developers` — de credenciales a publicacion
programada, sin escribir un solo `httpx`.

    PLANVORTEX_CLIENT_ID=... PLANVORTEX_CLIENT_SECRET=... \\
    PLANVORTEX_BASE_URL=http://localhost:3000/v1.0.0 \\
    uv run python examples/publish.py ./hogaza.jpg

Sin `PLANVORTEX_BASE_URL` va contra PRODUCCION, que es exactamente lo que no quieres mientras
pruebas: pon el stack local (`docker compose up -d`) o una organizacion de juguete.

Va en sincrono a proposito, que es como se escribe un script. El mismo codigo en asincrono cambia
tres cosas y ninguna mas: `AsyncPlanVortex`, un `await` delante de cada llamada, y `aiterate` donde
aqui pone `iterate`.
"""

from __future__ import annotations

import sys
import unicodedata
from datetime import datetime, timedelta, timezone

from planvortex import HttpHooks, PlanVortex, PlanVortexError
from planvortex.types import account_id, is_publishable_network


def main(ruta_del_fichero: str) -> int:
    # Sin `client_id`/`client_secret`, salen de PLANVORTEX_CLIENT_ID y PLANVORTEX_CLIENT_SECRET.
    # El `with` cierra la conexion al salir, tambien si algo revienta por el camino.
    with PlanVortex(hooks=_registro()) as pv:
        # 1. El cliente y su organizacion. Con credenciales de app solo se ve el cliente de la app.
        clientes = pv.clients.list(limit=1)
        if not clientes.data:
            raise SystemExit("La app no ve ningun cliente: revisa las credenciales.")
        cliente = clientes.data[0]

        organizaciones = pv.clients.organizations(cliente["_id"], limit=1)
        if not organizaciones.data:
            raise SystemExit(f"El cliente {cliente['name']} no tiene ninguna organizacion.")
        organizacion = organizaciones.data[0]
        print(f"Organizacion: {organizacion['name']} ({organizacion['_id']})")

        # 2. Cuanto queda de plan. Se lee de `limits`, NO de `organization["actual_plan"]`, que
        #    falta cuando la organizacion no tiene plan propio y hereda el del padre.
        limites = pv.organizations.limits(organizacion["_id"])
        # `actual_use` puede no venir —una organizacion recien creada no ha gastado nada—, y ese es
        # el unico hueco: los cinco contadores de dentro son obligatorios, asi que una vez hay
        # bloque se leen con corchetes y no con `.get`.
        uso = pv.organizations.use(organizacion["_id"]).get("actual_use")
        print(
            f"Publicaciones: {uso['publications'] if uso else 0} de {limites['publications']} · "
            f"Cuentas: {uso['accounts'] if uso else 0} de {limites['accounts']}"
        )

        # 3. Una cuenta con la que se pueda publicar. El filtro `capability` lo resuelve el servidor
        #    con la misma matriz que publica `/social_capabilities`: ni WhatsApp ni Google Business
        #    aparecen aqui, porque no publican.
        cuentas = pv.accounts.list(organizacion["_id"], capability="publications", limit=10)
        cuenta = next((una for una in cuentas.data if una.get("error_code") == 0), None)
        if cuenta is None:
            raise SystemExit(
                "Todas las cuentas estan desconectadas (error_code != 0): hay que reconectarlas."
                if cuentas.data
                else "No hay ninguna cuenta que publique. Conectala primero (ver examples/connect.py)."
            )
        red = cuenta["social_network"]
        # El `capability` de arriba ya lo ha filtrado en el servidor, asi que esto no puede fallar
        # en ejecucion: lo que arregla es el TIPO. Una cuenta es una de las doce redes y una
        # publicacion es una de las once —`google_business` recibe resenas, no posts—, y sin este
        # puente pasar la una a la otra es un error de tipos. `red != "google_business"` no sirve:
        # comparar en negativo contra una union de once la deja en las once.
        if not is_publishable_network(red):
            raise SystemExit(f"{red} no publica: recibe resenas, no publicaciones.")
        print(f"Cuenta: {cuenta['name']} en {red}")

        # 4. Los limites de ESA red, tal y como los valida el servidor. Bluesky lleva dos cuentas
        #    del mismo texto y en unidades distintas, asi que se miran las dos.
        limites_sociales = pv.catalog.social_limits()
        max_caracteres = (limites_sociales.get("characters") or {}).get(red, 0)
        max_bytes = (limites_sociales.get("max_post_bytes") or {}).get(red, 0)

        texto = "Nuevo horno, nuevas hogazas 🥖"
        caracteres = _grafemas(texto)
        octetos = len(texto.encode("utf8"))
        if caracteres > max_caracteres or (max_bytes and octetos > max_bytes):
            raise SystemExit(
                f"El texto no cabe en {red}: {caracteres}/{max_caracteres} caracteres"
                + (f" y {octetos}/{max_bytes} bytes" if max_bytes else "")
            )

        # 5. La imagen. Una ruta en disco es la forma que NO pasa el fichero por memoria: la
        #    libreria lo abre, lo va mandando y lo cierra.
        fichero = pv.uploads.create(organizacion["_id"], ruta_del_fichero)
        # Un upload SIEMPRE trae `file_properties` y dentro siempre esta el recorte: el servidor los
        # calcula al ingerir. Por eso van con corchetes — un `.get(..., 0)` aqui no defiende de nada
        # y esconde que el dia que falten es un fallo, no un caso.
        propiedades = fichero["file_properties"]
        print(
            f"Subido {fichero['name']}: {propiedades['aspect_ratio']['text']} · "
            f"{propiedades['size_in_bytes'] // 1024} KB"
        )
        # `allowed_social_networks` es solo el RECORTE. La duracion y el peso los mira el servidor
        # al publicar, asi que esto es un aviso temprano y no una garantia.
        if red not in propiedades["allowed_social_networks"]:
            print(f"Aviso: el recorte no es de los que {red} recomienda.")

        # 6. La publicacion, programada para dentro de una hora. La fecha lleva zona horaria, o la
        #    libreria lanza: sin offset, el servidor la leeria en SU zona (§ Trampa P8).
        publicacion = pv.publications.create(
            organizacion["_id"],
            cuenta["_id"],
            {
                "social_network": red,
                "text": texto,
                "files": [fichero["_id"]],
                "publish_date": datetime.now(timezone.utc) + timedelta(hours=1),
            },
        )

        # 7. Y AQUI ESTA LO QUE HAY QUE MIRAR: una publicacion invalida no llega como error, llega
        #    como un 200 en estado `withErrors` con el motivo dentro. Un `try/except` no basta.
        if publicacion["state"] == "withErrors":
            print("La publicacion se guardo pero NO saldra:", file=sys.stderr)
            for fallo in publicacion["publication_errors"]:
                print(f"  [{fallo['code']}] {fallo['message']}", file=sys.stderr)
            return 1

        print(
            f"Programada {publicacion['_id']} ({publicacion['state']}) para "
            f"{publicacion.get('publish_date')} en la cuenta {account_id(publicacion)}"
        )

        # 8. Lo que hay en la agenda, para comprobar que esta. `iterate` encadena las paginas solo;
        #    `list` devuelve una y su `total`.
        pendientes = pv.publications.list(organizacion["_id"], state=["ready"], limit=5)
        print(f"Pendientes: {pendientes.total}")
        for programada in pv.publications.iterate(organizacion["_id"], state=["ready"], limit=5):
            print(f"  {programada['_id']} · {programada.get('publish_date')}")

    return 0


def _grafemas(texto: str) -> int:
    """Cuantos caracteres cuenta el servidor, que no es `len()`.

    Un emoji de familia son once unidades de UTF-16, UN grafema y veinticinco bytes. Python no trae
    segmentacion de grafemas en la biblioteca estandar, asi que se aproxima juntando las marcas
    combinantes, el selector de variacion y el unidor de ancho cero; para contar de verdad hay un
    `regex` en PyPI, pero una dependencia por un ejemplo no sale a cuenta.
    """
    selector_de_variacion = "\ufe0f"
    unidor = "\u200d"

    total = 0
    tras_unidor = False
    for caracter in texto:
        # El unidor no cuenta, y lo que viene detras tampoco: los cuatro monigotes de un emoji de
        # familia y los tres unidores que los pegan son UN grafema, no siete.
        pegado = (
            unicodedata.combining(caracter) != 0 or caracter in (selector_de_variacion, unidor) or tras_unidor
        )
        if not pegado:
            total += 1
        tras_unidor = caracter == unidor
    return total


def _registro() -> HttpHooks:
    """Los hooks, que es donde se enchufa el logger de casa. Aqui, un `print`."""
    return HttpHooks(on_request=lambda info: print(f"  -> {info.method} {info.url}"))


if __name__ == "__main__":
    ruta = sys.argv[1] if len(sys.argv) > 1 else "./ejemplo.jpg"
    try:
        raise SystemExit(main(ruta))
    except PlanVortexError as error:
        # Los errores de la API se clasifican por `code`, NUNCA por el status: todos llegan con 400.
        print(f"[{error.family} {error.code}] {error.message}", error.data, file=sys.stderr)
        raise SystemExit(1) from error
