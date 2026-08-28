"""El flujo de conexion de cuentas, y la frontera exacta de lo que esta libreria NO hace.

Conectar un Instagram es un OAuth con una PERSONA delante, asi que las credenciales de tu app no
sirven para eso y ningun script lo puede hacer solo. Lo que si se hace desde aqui es emitir el
credencial temporal que autoriza a esa persona, montar la URL a la que mandarla, y —si la interfaz
la pones tu— pedir la lista de como se autoriza cada red. El navegador es el que falta, y es la
parte que este ejemplo explica por escrito en vez de fingir.

    PLANVORTEX_CLIENT_ID=... PLANVORTEX_CLIENT_SECRET=... \\
    PLANVORTEX_BASE_URL=http://localhost:3000/v1.0.0 \\
    uv run python examples/connect.py https://tu-app.example/social/listo

Sin `PLANVORTEX_BASE_URL` va contra PRODUCCION. El argumento es opcional y es a donde vuelve TU
usuario cuando termina; tiene que estar en los `redirect_urls` de tu app o el servidor contesta 532.

Va en sincrono a proposito, que es como se escribe un script. El mismo codigo en asincrono cambia
tres cosas y ninguna mas: `AsyncPlanVortex`, un `await` delante de cada llamada, y `aiterate` donde
aqui pone `iterate`.
"""

from __future__ import annotations

import sys

from planvortex import PlanVortex, PlanVortexError
from planvortex.types import (
    ConnectLink,
    is_meta_embedded_signup,
    is_redirect_authorization,
)


def main(redirect_uri: str | None) -> int:
    # Credenciales de APP. Son las unicas que pueden emitir el token temporal, y las unicas que las
    # tres llamadas siguientes rechazan: el flujo entero es el reves del resto de la API.
    with PlanVortex() as pv:
        # 1. El cliente y su organizacion. Una cuenta social se conecta a UNA organizacion.
        clientes = pv.clients.list(limit=1)
        if not clientes.data:
            raise SystemExit("La app no ve ningun cliente: revisa las credenciales.")

        organizaciones = pv.clients.organizations(clientes.data[0]["_id"], limit=1)
        if not organizaciones.data:
            raise SystemExit(f"El cliente {clientes.data[0]['name']} no tiene ninguna organizacion.")
        organizacion = organizaciones.data[0]
        print(f"Organizacion: {organizacion['name']} ({organizacion['_id']})")

        # 2. Sitio en el plan, ANTES de mandar a nadie a ninguna parte. Quien consume la plaza es el
        #    `enable` del final, asi que sin sitio la persona hace todo el OAuth para comerse un 706
        #    en el ultimo paso — y la culpa parece suya. Ojo: en Discord una cuenta es un CANAL, o
        #    sea que publicar en #anuncios y en #novedades son dos plazas.
        limites = pv.organizations.limits(organizacion["_id"])
        # Ojo con el atajo `.get("actual_use") or {}`: `PlanData` tiene cinco claves OBLIGATORIAS,
        # asi que el diccionario vacio no es un `PlanData` y mypy lo rechaza — con razon, porque
        # leerle `accounts` despues seria un `KeyError`. `actual_use` puede no venir.
        uso = pv.organizations.use(organizacion["_id"]).get("actual_use")
        gastadas = uso["accounts"] if uso else 0
        libres = limites.get("accounts", 0) - gastadas
        print(f"Cuentas: {gastadas} de {limites.get('accounts', 0)} · quedan {libres}")
        if libres <= 0:
            raise SystemExit("No queda plaza de cuenta en el plan: `enable` contestaria 706.")

        # 3. El token temporal. Esto es lo que la libreria aporta al flujo, y lo unico.
        #
        #    Sin `social_network` vale para cualquier red y la persona elige; con ella queda atado a
        #    esa y no conecta otra (544). La red viaja DENTRO del token, firmada, asi que reescribir
        #    la query de la URL no la cambia.
        conexion = pv.organizations.create_connect_token(
            organizacion["_id"],
            redirect_uri=redirect_uri,
        )
        print(f"\nToken emitido, caduca a las {conexion['expires_at']}")

        _explicar_el_navegador(conexion["url"])

        # 4. Y la otra mitad: la lista de como se autoriza cada red, para quien sirve su propia
        #    interfaz. Se pide CON EL TOKEN TEMPORAL —con las credenciales de app es un 519—, que es
        #    para lo que existe `as_temporal_token`.
        #
        #    Leer no gasta el token: lo que se quema es la redencion, o sea el `accounts.connect`
        #    que termina bien. Este listado se puede pedir las veces que haga falta.
        with pv.as_temporal_token(conexion["token"]) as persona:
            enlaces = persona.accounts.connect_links(organizacion["_id"])

        print(f"\n{len(enlaces)} redes conectables ahora mismo:")
        for enlace in enlaces:
            _describir(enlace)

        _explicar_la_vuelta()

    return 0


def _describir(enlace: ConnectLink) -> None:
    """Como se autoriza UNA red, ramificando por `authorization` y nunca por el `link`.

    Aqui esta lo unico de este fichero que no es obvio. Nueve de las diez redes se autorizan con una
    URL; WhatsApp no tiene ninguna que dar —su alta es el popup del Embedded Signup de Meta, que
    contesta por `postMessage` con datos que no caben en una query string— y su `link` es la cadena
    vacia. Quien recorra la lista redirigiendo a `link` manda a su usuario a su propia pagina, sin
    error y sin nada roto que mirar: fue el fallo que la API arrastro un ano.

    Y los predicados no son adorno. El tipo que viaja por el cable es UNO y plano, con los cinco
    campos del popup opcionales, porque OpenAPI no sabe decir "estos cinco solo cuando `type` vale
    tal". O sea que `autorizacion["app_id"]` pasa `mypy --strict` y revienta con `KeyError` contra
    una entrada `redirect`. `is_meta_embedded_signup` es lo que estrecha de verdad.
    """
    red = enlace["social_network"]
    autorizacion = enlace["authorization"]

    if is_redirect_authorization(autorizacion):
        print(f"  {red}: manda a la persona a {enlace['link'][:60]}...")
        return

    if is_meta_embedded_signup(autorizacion):
        # Dentro de esta rama los cinco campos son obligatorios, asi que se leen sin `.get`.
        print(
            f"  {red}: NO hay URL. Abre el popup de Meta con el SDK de JavaScript de Facebook:\n"
            f"      FB.init(appId={autorizacion['app_id']}, version={autorizacion['graph_version']})\n"
            f"      FB.login(config_id={autorizacion['config_id']},\n"
            f"               extras.featureType={autorizacion['feature_type']},\n"
            f"               extras.sessionInfoVersion={autorizacion['session_info_version']})\n"
            "      El `waba_id` y el `phone_number_id` vuelven por `postMessage`, no en la URL."
        )
        return

    # El `else` que hoy no le toca a nadie, y que es justo por lo que se escribe. La lista de redes
    # crece y la de metodos puede crecer con ella; saltarse la red desconocida es una respuesta
    # honesta, y mandar a alguien a un `link` vacio porque el `if/elif` no cubria su caso, no.
    print(f"  {red}: metodo de autorizacion '{autorizacion['type']}', que esta version no conoce.")


def _explicar_el_navegador(url: str) -> None:
    """LA PARTE QUE LA LIBRERIA NO HACE, que es la mitad del flujo.

    No es una limitacion que se pueda levantar: lo que falta aqui es una persona pulsando "aceptar"
    en la pagina de Instagram. Ningun credencial de servidor sustituye eso.
    """
    print(
        "\n  --- y aqui empieza el navegador ---\n"
        f"  Manda a tu usuario a:\n    {url}\n\n"
        "  Ahi PlanVortex se encarga de todo: la eleccion de red, el OAuth, y la pantalla donde la\n"
        "  persona elige que cuentas se queda. Con esto la integracion esta hecha; los pasos que\n"
        "  siguen son solo para quien quiera servir esa interfaz por su cuenta.\n"
    )


def _explicar_la_vuelta() -> None:
    """Que pasa cuando la persona vuelve, y por que este ejemplo se para justo antes.

    `accounts.connect()` se completa con lo que la red PEGO a la URL de vuelta (`code`, `state`,
    y en X un `oauth_token`/`oauth_verifier`), y eso solo existe en un navegador que acaba de
    volver de la red social. Inventarlo aqui seria un ejemplo que no se parece a nada.
    """
    print(
        "\n  Cuando la persona vuelva, si la interfaz es tuya:\n"
        "    resultado = persona.accounts.connect(org_id, red, params_de_la_url_de_vuelta)\n"
        "    for cuenta in resultado['accounts']:\n"
        "        persona.accounts.enable(org_id, cuenta['_id'])\n\n"
        "  Tres cosas que no se ven venir:\n"
        "   - Las cuentas vuelven DESHABILITADAS. No ocupan plaza ni publican hasta el `enable`,\n"
        "     que es el paso donde de verdad se gasta el plan (706 si no cabe).\n"
        "   - Una autorizacion puede dejar VARIAS. Un Facebook con cuatro paginas son cuatro, y por\n"
        "     eso hay una pantalla para elegir en medio.\n"
        "   - El token se quema con el `connect`, no con la primera peticion: los `enable` que\n"
        "     terminan esa misma conexion siguen valiendo hasta que caduque. Un `connect` mas con\n"
        "     el mismo token contesta 543. Emite uno por conexion: son gratis e inmediatos.\n"
        "\n  Dura QUINCE MINUTOS, vale para UNA organizacion (1101 contra otra) y no puede pedir\n"
        "  otro token (514). Guardartelo para 'la proxima vez' no funciona de cuatro formas.\n"
    )


if __name__ == "__main__":
    destino = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        raise SystemExit(main(destino))
    except PlanVortexError as error:
        # Los errores de la API se clasifican por `code`, NUNCA por el status: todos llegan con 400.
        print(f"[{error.family} {error.code}] {error.message}", error.data, file=sys.stderr)
        raise SystemExit(1) from error
