"""CAPA 3 — contra un PlanVortex de VERDAD. Las guardas, el descubrimiento y las fixturas.

Las capas 1 y 2 prueban lo que la libreria HACE; esta prueba que el servidor sigue contestando lo
que la libreria CREE. Son cosas distintas y solo esta capa ve la segunda: un sobre renombrado, un
codigo de error que cambio de numero o una decima red social pasan la capa 2 en verde, porque sus
respuestas las escribimos nosotros.

REGLAS DE SEGURIDAD, en orden:

 1. **Sin `.env.live`, todo se SALTA.** Nunca falla por falta de credenciales: `pytest` no se
    entera de que esto existe y la CI de un PR tampoco. Y ademas esta el marcador `live`, que la
    saca de la ejecucion por defecto: `addopts` lleva `-m "not live"` y esta suite se pide a
    proposito con `uv run pytest -m live`.
 2. **Las credenciales llevan prefijo `PLANVORTEX_LIVE_`** y no `PLANVORTEX_CLIENT_ID` a secas, que
    es lo que el cliente lee solo del entorno. Es a proposito: un `.env` con las credenciales de
    produccion —el que usan los `examples/`— no debe armar esta suite sin querer.
 3. **Nada escribe salvo con `LIVE_ALLOW_PUBLISH=1`**, y lo que escribe se programa a futuro y se
    borra al terminar: no sale a ninguna red social.
 4. **Publicar de verdad en la red lleva un interruptor propio**, `LIVE_ALLOW_SOCIAL_PUBLISH=1`. Es
    la misma decision que ya se tomo en el servidor con los comentarios: crear una publicacion
    programada es privado y reversible, y mandarla a Instagram es publico, inmediato e
    irreversible. No es el mismo riesgo, asi que no comparte interruptor.
 5. **Escribir contra produccion exige decirlo dos veces** (`LIVE_ALLOW_PRODUCTION=1`) y, si no,
    esto revienta en voz alta en vez de saltarse: una configuracion peligrosa no es lo mismo que una
    configuracion ausente.

POR QUE ESTA CAPA CORRE EN SINCRONO Y LAS OTRAS DOS EN LAS DOS VARIANTES. En las capas 1 y 2
parametrizar sale gratis y es lo unico que prueba el gemelo generado. Aqui cada vuelta es trafico
de verdad contra un servidor de verdad: duplicarla es duplicar las escrituras, y sobre todo
duplicar las peticiones a `POST /oauth/token`, que el servidor frena a 30 por minuto y `client_id`.
Asi que la suite entera va en sincrono y el gemelo asincrono lo cubre un unico test de humo en
`test_auth.py`, que es lo que hacia falta demostrar: que tambien habla con un servidor real.
"""

from __future__ import annotations

import os
import re
import struct
import zlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from planvortex import AsyncPlanVortex, PlanVortex, PlanVortexError, RetryConfig
from planvortex.types import Account, Client, Organization

# =================================================================================================
# El `.env.live`, sin dotenv
# =================================================================================================


def _cargar_env(fichero: Path) -> None:
    """Un `.env` minimo, escrito a mano.

    El paquete tiene UNA dependencia de runtime y no se le van a anadir mas a los tests por leer
    catorce lineas. Lo que ya venga del shell MANDA sobre el fichero, para poder lanzar una vez con
    otra configuracion sin editar nada.
    """
    if not fichero.is_file():
        return

    for linea in fichero.read_text(encoding="utf8").splitlines():
        # Un `#` al principio no casa: el nombre tiene que empezar por letra o guion bajo.
        casa = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", linea)
        if casa is None or casa.group(1) in os.environ:
            continue

        crudo = casa.group(2).strip()
        entrecomillado = len(crudo) > 1 and crudo[0] in "\"'" and crudo.endswith(crudo[0])
        os.environ[casa.group(1)] = crudo[1:-1] if entrecomillado else crudo


_cargar_env(Path.cwd() / os.environ.get("LIVE_ENV_FILE", ".env.live"))

#: Contra que servidor. Sin barra final y CON el `/v1.0.0`, igual que el `base_url` del cliente.
BASE_URL = os.environ.get("PLANVORTEX_LIVE_BASE_URL", "")
_CLIENT_ID = os.environ.get("PLANVORTEX_LIVE_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("PLANVORTEX_LIVE_CLIENT_SECRET", "")

#: Lo que falta para poder ejecutar, con nombre y apellidos en el motivo del salto.
FALTA = [
    nombre
    for nombre, valor in (
        ("PLANVORTEX_LIVE_BASE_URL", BASE_URL),
        ("PLANVORTEX_LIVE_CLIENT_ID", _CLIENT_ID),
        ("PLANVORTEX_LIVE_CLIENT_SECRET", _CLIENT_SECRET),
    )
    if not valor
]

CONFIGURADA = not FALTA


def puede_escribir() -> bool:
    """Se puede subir, crear y borrar en esta ejecucion (§ regla 3)."""
    return os.environ.get("LIVE_ALLOW_PUBLISH") == "1"


def puede_publicar_en_la_red() -> bool:
    """Se puede mandar una publicacion a la RED, ya, de verdad. Interruptor propio (§ regla 4)."""
    return puede_escribir() and os.environ.get("LIVE_ALLOW_SOCIAL_PUBLISH") == "1"


def _es_produccion() -> bool:
    return "//api.planvortex.com" in BASE_URL


if CONFIGURADA and puede_escribir() and _es_produccion() and os.environ.get("LIVE_ALLOW_PRODUCTION") != "1":
    # Revienta, no se salta: esto es una configuracion peligrosa, no una ausente (§ regla 5).
    raise RuntimeError(
        "LIVE_ALLOW_PUBLISH=1 contra api.planvortex.com. Estos tests suben ficheros y crean "
        "publicaciones en una organizacion REAL. Si es lo que quieres, anade LIVE_ALLOW_PRODUCTION=1; "
        "si no, apunta PLANVORTEX_LIVE_BASE_URL a tu stack local."
    )


# =================================================================================================
# Los marcadores. Cada fichero de la capa 3 empieza con `pytestmark = LIVE`
# =================================================================================================
#
# Se ponen a mano —una linea por fichero— y no con un `pytest_collection_modifyitems`, porque el
# marcador tiene que estar puesto ANTES de que pytest evalue el `-m` de `addopts`. Un marcador
# anadido durante la coleccion depende del orden en que corran los hooks, y de eso depende que
# `pytest` a secas ejecute o no una suite que sale a la red.

LIVE = [
    pytest.mark.live,
    pytest.mark.skipif(not CONFIGURADA, reason=f"falta {', '.join(FALTA)} en .env.live"),
]

#: Lo que crea o borra. Se salta sin `LIVE_ALLOW_PUBLISH=1`.
escribe = pytest.mark.skipif(not puede_escribir(), reason="hace falta LIVE_ALLOW_PUBLISH=1")

#: Lo que sale a la red de verdad. Interruptor propio ademas del anterior.
publica = pytest.mark.skipif(
    not puede_publicar_en_la_red(), reason="hace falta LIVE_ALLOW_PUBLISH=1 y LIVE_ALLOW_SOCIAL_PUBLISH=1"
)


# =================================================================================================
# Los clientes y el contexto
# =================================================================================================


def cliente_live(**opciones: Any) -> PlanVortex:
    """Un cliente de la app, con las credenciales de `.env.live`."""
    return PlanVortex(client_id=_CLIENT_ID, client_secret=_CLIENT_SECRET, base_url=BASE_URL, **opciones)


def cliente_live_async(**opciones: Any) -> AsyncPlanVortex:
    """El gemelo asincrono, con las mismas credenciales. Solo lo usa el test de humo de `test_auth`."""
    return AsyncPlanVortex(client_id=_CLIENT_ID, client_secret=_CLIENT_SECRET, base_url=BASE_URL, **opciones)


def cliente_con_secreto_malo() -> PlanVortex:
    """Un cliente con un secreto que NO vale. Para comprobar el error, no para colarse."""
    return PlanVortex(
        client_id=_CLIENT_ID,
        client_secret=f"{_CLIENT_SECRET}-esto-no-es-el-secreto",
        base_url=BASE_URL,
        # Un secreto malo no mejora reintentandolo, y el servidor cuenta los fallos por `client_id`.
        retry=RetryConfig(max_retries=0),
    )


@dataclass(frozen=True)
class ContextoLive:
    """Con que se prueba: el cliente HTTP, el cliente de negocio y su organizacion."""

    pv: PlanVortex
    client: Client
    organization: Organization


@pytest.fixture(scope="session")
def pv() -> Iterator[PlanVortex]:
    """UN cliente para toda la sesion.

    De ahi el `scope="session"`: cada `PlanVortex` nuevo pide su propio token, y el servidor frena el
    endpoint a 30 por minuto y `client_id`. Una fixtura por test convertiria la suite en su propio
    ataque de fuerza bruta.
    """
    with cliente_live() as cliente:
        yield cliente


@pytest.fixture(scope="session")
def live(pv: PlanVortex) -> ContextoLive:
    """El cliente, su organizacion y el `PlanVortex` con el que se prueba, resueltos UNA vez.

    La organizacion se puede fijar con `LIVE_ORGANIZATION_ID`; si no, se coge la primera del
    cliente. Cliente no hay que elegir: con credenciales de app solo se ve el de la app (error 537).
    """
    clientes = pv.clients.list(limit=1)
    if not clientes.data:
        raise RuntimeError("La app no ve ningun cliente: revisa PLANVORTEX_LIVE_CLIENT_ID/SECRET.")
    cliente = clientes.data[0]

    preferida = os.environ.get("LIVE_ORGANIZATION_ID")
    if preferida:
        return ContextoLive(pv=pv, client=cliente, organization=pv.organizations.get(preferida))

    organizaciones = pv.clients.organizations(cliente["_id"], limit=1)
    if not organizaciones.data:
        raise RuntimeError(
            f"El cliente {cliente['name']} no tiene organizaciones. Crea una, o fija LIVE_ORGANIZATION_ID."
        )
    return ContextoLive(pv=pv, client=cliente, organization=organizaciones.data[0])


@pytest.fixture(scope="session")
def cuenta_que_publica(live: ContextoLive) -> Account | None:
    """Una cuenta conectada con la que se pueda publicar, o `None` si no hay ninguna.

    `None` es un resultado normal —conectar una cuenta es un OAuth con una persona delante, y eso no
    se automatiza—, asi que quien la use se salta su test en vez de fallarlo.
    """
    pagina = live.pv.accounts.list(live.organization["_id"], capability="publications", limit=50)
    # `error_code != 0` es una cuenta desconectada: existe, pero cualquier cosa que se le pida falla.
    utiles = [cuenta for cuenta in pagina.data if cuenta.get("error_code") == 0]

    preferida = os.environ.get("LIVE_ACCOUNT_ID")
    if preferida:
        return next((cuenta for cuenta in utiles if cuenta["_id"] == preferida), None)
    return utiles[0] if utiles else None


@pytest.fixture(scope="session")
def cuenta_con_buzon(live: ContextoLive) -> Account | None:
    """Una cuenta de una red con mensajeria, para las lecturas del buzon."""
    pagina = live.pv.accounts.list(live.organization["_id"], capability="messages", limit=50)
    return next((cuenta for cuenta in pagina.data if cuenta.get("error_code") == 0), None)


# =================================================================================================
# Los ficheros con los que se prueba
# =================================================================================================


def _png(ancho: int, alto: int) -> bytes:
    """Un PNG de verdad, generado aqui.

    NO hay un binario commiteado, y es a proposito: una libreria de cliente no lleva una foto dentro
    para sus tests. Se genera con `zlib` y `struct`, que son biblioteca estandar, y sale un
    degradado de 1080x1080 — cuadrado porque es la unica proporcion que aceptan las diez redes, y
    grande porque una imagen de 1x1 la rechaza la validacion de la publicacion y el fallo pareceria
    de la libreria.
    """

    def trozo(clase: bytes, carga: bytes) -> bytes:
        return (
            struct.pack(">I", len(carga))
            + clase
            + carga
            + struct.pack(">I", zlib.crc32(clase + carga) & 0xFFFFFFFF)
        )

    filas = bytearray()
    for y in range(alto):
        filas.append(0)  # El filtro de la fila: 0 = ninguno.
        filas += bytes((90, y * 255 // (alto - 1), 200)) * ancho

    return (
        b"\x89PNG\r\n\x1a\n"
        + trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0))
        + trozo(b"IDAT", zlib.compress(bytes(filas), 6))
        + trozo(b"IEND", b"")
    )


@pytest.fixture(scope="session")
def imagen(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """La imagen que se sube. `LIVE_IMAGE_PATH` la sustituye por una del disco."""
    puesta = os.environ.get("LIVE_IMAGE_PATH")
    if puesta:
        return Path(puesta).resolve()

    ruta = tmp_path_factory.mktemp("live") / "planvortex-live.png"
    ruta.write_bytes(_png(1080, 1080))
    return ruta


@pytest.fixture(scope="session")
def video() -> Path | None:
    """Un video, para las redes que no publican imagenes.

    No hay uno por defecto —un MP4 no se genera con `zlib`— asi que sin `LIVE_VIDEO_PATH` los tests
    de publicacion se saltan cuando la unica cuenta conectada es de YouTube o TikTok.
    """
    puesta = os.environ.get("LIVE_VIDEO_PATH")
    return Path(puesta).resolve() if puesta else None


# =================================================================================================
# Utilidades
# =================================================================================================

#: "Esta funcionalidad es de plan de pago". No es un fallo ni de la libreria ni del servidor.
CODIGO_DE_PLAN_DE_PAGO = 516


@contextmanager
def plan_de_pago() -> Iterator[None]:
    """Ejecuta el cuerpo, y si el API contesta 516 SALTA el test diciendo por que.

    Comentarios, buzon y contactos son de plan de pago, y un stack de pruebas suele tener el cliente
    en `free`. Se salta el dominio entero igual que se salta lo que necesita una cuenta conectada.
    """
    try:
        yield
    except PlanVortexError as error:
        if error.code == CODIGO_DE_PLAN_DE_PAGO:
            pytest.skip(f"el plan del cliente no incluye esto (error {CODIGO_DE_PLAN_DE_PAGO})")
        raise


def marca() -> str:
    """Texto unico por ejecucion: sirve para reconocer —y limpiar— lo que ha creado el test."""
    return f"PlanVortex live test {datetime.now(timezone.utc).isoformat()}"
