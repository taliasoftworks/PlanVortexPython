"""Las formas escritas a mano, contra el OpenAPI commiteado.

`src/planvortex/_shapes.py` existe porque el generador solo emite `components/schemas`, y una docena
de cuerpos y respuestas de esta API estan declarados EN LINEA dentro de su operacion. Esos tipos no
los vigila ningun `git diff --exit-code`: si el spec cambia un campo, el `TypedDict` se queda
diciendo lo de antes y mypy sigue en verde, porque lo unico que mypy compara es el codigo contra si
mismo.

Asi que se comparan contra el bundle, campo a campo y en las DOS direcciones —lo que declara el spec
tiene que estar, y lo que esta tiene que seguir declarandolo el spec—, igual que el mapa camelCase
de la § Trampa P2 y las seis enumeraciones escritas a mano de `types.py`.

Y hay una segunda cosa que este fichero caza gratis, que es la § Trampa P13: lee
`__optional_keys__`, y esa es exactamente la introspeccion que miente cuando el `TypedDict` y el
`NotRequired` no vienen del mismo sitio, o cuando alguien anade un `from __future__ import
annotations` al principio del fichero. En los dos casos TODAS las claves salen obligatorias y esto
se pone rojo, mientras que el comprobador de tipos no dice ni una palabra.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, get_args

import pytest

if sys.version_info >= (3, 11):
    from typing import NotRequired
else:  # pragma: no cover - la rama la elige el interprete, no un test
    from typing_extensions import NotRequired

from planvortex import _shapes
from planvortex._generated.models import (
    ClientsClient,
    DashboardPublicationsSummary,
    PublicationsPublicationInput,
)

OPENAPI = Path(__file__).resolve().parent.parent / "openapi" / "planvortex.openapi.json"

# TypedDict -> donde vive su forma en el spec. `ruta` es una secuencia de pasos desde el esquema de
# la operacion: el nombre de una propiedad, o `[]` para bajar a los elementos de un array.
#
# `ConnectResult`, `EnableResult` y `OrganizationUse` NO estan aqui y no es un olvido: son formas de
# la LIBRERIA, no del cable. Las dos primeras son lo que queda de una respuesta despues de quitarle
# lo que la libreria convierte en excepcion (`errorCode`) o en nada (`success: true`), y la tercera
# es un atajo de dos campos de la organizacion. La respuesta cruda del callback SI esta, que es la
# que importa que no se mueva.
TABLA: tuple[tuple[Any, str, str, str, tuple[str, ...]], ...] = (
    (_shapes.PublicationLimits, "/publication_limits", "get", "response", ()),
    (_shapes.ClientUpdate, "/clients/{id_client}", "put", "request", ()),
    (
        _shapes.AccountUpdate,
        "/organizations/{id_organization}/accounts/{id_account}",
        "put",
        "request",
        (),
    ),
    (
        _shapes.AccountConnectResponse,
        "/organizations/{id_organization}/account-connect/{social_network}",
        "get",
        "response",
        (),
    ),
    (
        _shapes.ConnectToken,
        "/organizations/{id_organization}/temporal_connect_token",
        "get",
        "response",
        (),
    ),
    (
        _shapes.UploadUpdate,
        "/organizations/{id_organization}/uploads/{id_upload}",
        "put",
        "request",
        (),
    ),
    (
        _shapes.ImportFile,
        "/organizations/{id_organization}/uploads/import",
        "post",
        "request",
        ("files", "[]"),
    ),
    (
        _shapes.ImportResult,
        "/organizations/{id_organization}/uploads/import",
        "post",
        "response",
        (),
    ),
    (
        _shapes.ImportFileError,
        "/organizations/{id_organization}/uploads/import",
        "post",
        "response",
        ("errors", "[]"),
    ),
    (
        _shapes.CommentUpdate,
        "/organizations/{id_organization}/comments/{id_comment}",
        "put",
        "request",
        (),
    ),
    (
        _shapes.CommentReplyResult,
        "/organizations/{id_organization}/comments/{id_comment}/reply",
        "post",
        "response",
        (),
    ),
    (
        _shapes.IntegrationUpdate,
        "/organizations/{id_organization}/integrations/{id_integration}",
        "put",
        "request",
        (),
    ),
    (
        _shapes.IntegrationPickerConfig,
        "/organizations/{id_organization}/integrations/{id_integration}/picker_config",
        "get",
        "response",
        (),
    ),
    (
        _shapes.AiPlanRegenerateResult,
        "/clients/{id_client}/organizations/{id_organization}/ai_plans/{id_ai_plan}"
        "/publications/{id_publication}/regenerate",
        "post",
        "response",
        (),
    ),
    (
        _shapes.MetricsResult,
        "/organizations/{id_organization}/metrics",
        "get",
        "response",
        (),
    ),
    (
        _shapes.TopPublicationsResult,
        "/organizations/{id_organization}/publications/top",
        "get",
        "response",
        (),
    ),
)


def _spec() -> dict[str, Any]:
    datos: dict[str, Any] = json.loads(OPENAPI.read_text(encoding="utf8"))
    return datos


def _esquema(path: str, metodo: str, clase: str, ruta: tuple[str, ...]) -> dict[str, Any]:
    """El esquema de una operacion, bajando por `ruta` hasta el objeto que toca."""
    operacion = _spec()["paths"][path][metodo]
    if clase == "request":
        esquema = operacion["requestBody"]["content"]["application/json"]["schema"]
    else:
        esquema = operacion["responses"]["200"]["content"]["application/json"]["schema"]

    for paso in ruta:
        esquema = esquema["items"] if paso == "[]" else esquema["properties"][paso]
    assert isinstance(esquema, dict)
    return esquema


def _claves(clase: Any) -> tuple[set[str], set[str]]:
    return set(clase.__required_keys__), set(clase.__optional_keys__)


# El reparto de `AccountsSocialAuthorizationMethod`, que el spec emite PLANO. Se enumera aqui y no
# dentro de cada test porque lo que se vigila es el conjunto: una forma nueva de autorizar que se
# escriba en `_shapes.py` y no se anada a esta lista deja los dos tests de abajo comprobando el
# reparto viejo, y en verde.
MITADES_DE_AUTORIZACION = (
    _shapes.RedirectAuthorization,
    _shapes.MetaEmbeddedSignupAuthorization,
    _shapes.TelegramBotAuthorization,
)


@pytest.mark.parametrize(
    ("clase", "path", "metodo", "tipo", "ruta"),
    TABLA,
    ids=[entrada[0].__name__ for entrada in TABLA],
)
def test_la_forma_escrita_a_mano_dice_lo_mismo_que_el_spec(
    clase: Any, path: str, metodo: str, tipo: str, ruta: tuple[str, ...]
) -> None:
    esquema = _esquema(path, metodo, tipo, ruta)
    del_spec = set(esquema["properties"])
    obligatorias_spec = set(esquema.get("required", []))

    obligatorias, opcionales = _claves(clase)

    assert obligatorias | opcionales == del_spec, "las propiedades no cuadran con el spec"
    assert obligatorias == obligatorias_spec, "no cuadra QUE es obligatorio"


def test_el_cliente_con_organizaciones_hereda_el_cliente_entero() -> None:
    """Es un `allOf` en el spec: el cliente de siempre, con dos campos mas dentro.

    Se comprueba por herencia y no campo a campo porque el cliente base SI lo vigila el generador;
    lo unico escrito a mano es lo que se le anade.
    """
    obligatorias, opcionales = _claves(_shapes.ClientWithOrganizations)
    base = set(ClientsClient.__required_keys__) | set(ClientsClient.__optional_keys__)

    assert base <= obligatorias | opcionales
    assert {"organizations", "total"} <= obligatorias

    esquema = _spec()["paths"]["/clients_organizations"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["properties"]["clients"]["items"]
    anadido = next(parte for parte in esquema["allOf"] if "properties" in parte)
    assert set(anadido["properties"]) == {"organizations", "total"}


def test_el_resumen_de_publicaciones_hereda_el_bloque_de_conteos() -> None:
    """Es un `allOf`, como `ClientWithOrganizations`: los conteos que ya vigila el generador, mas el
    rango. Lo unico escrito a mano es lo que se le anade.
    """
    obligatorias, opcionales = _claves(_shapes.PublicationsSummaryResult)
    base = set(DashboardPublicationsSummary.__required_keys__) | set(
        DashboardPublicationsSummary.__optional_keys__
    )

    assert base <= obligatorias | opcionales
    assert "range" in obligatorias

    esquema = _esquema("/organizations/{id_organization}/publications/summary", "get", "response", ())
    anadido = next(parte for parte in esquema["allOf"] if "properties" in parte)
    assert set(anadido["properties"]) == {"range"}


def test_la_introspeccion_de_los_typeddict_no_miente() -> None:
    """§ Trampa P13, en el fichero escrito a mano.

    Si alguien pone un `from __future__ import annotations` en `_shapes.py`, o coge el `TypedDict`
    de `typing` y el `NotRequired` de `typing_extensions`, TODAS las claves salen obligatorias. Los
    comprobadores de tipos siguen acertando —leen la PEP 655 directamente— y esto es lo unico que se
    entera.
    """
    assert _shapes.ImportFileError.__optional_keys__, "no hay ni una clave opcional: algo miente"
    assert set(_shapes.ImportFileError.__required_keys__) == {"code", "message"}
    assert set(_shapes.ConnectToken.__optional_keys__) == set()


def test_las_mitades_de_authorization_cubren_lo_que_declara_el_spec() -> None:
    """Las TRES mitades, contra el esquema del que salen.

    No son formas EN LINEA como el resto del fichero: el spec si declara
    `AccountsSocialAuthorizationMethod`, y el generador la emite. Lo que no puede emitir es que sea
    una UNION —OpenAPI no dice "estos cinco campos solo cuando `type` vale tal"—, asi que la emite
    plana y con todos opcionales. Estas clases son el reparto, y por eso hay que vigilarlo: un campo
    nuevo en el popup, o una forma nueva de autorizar, dejarian el reparto corto sin que nada se
    pusiera rojo. Que eran DOS hasta que llego Telegram, que autoriza de una tercera manera.
    """
    esquema = _spec()["components"]["schemas"]["AccountsSocialAuthorizationMethod"]
    del_spec = set(esquema["properties"])
    assert set(esquema.get("required", [])) == {"type"}, "el spec ya no obliga solo a `type`"

    obligatorias: set[str] = set()
    for mitad in MITADES_DE_AUTORIZACION:
        propias, opcionales = _claves(mitad)
        # Todas obligatorias en su mitad: es el reparto entero lo que se gana partiendo el tipo. Si
        # alguna sale opcional aqui, leerla vuelve a ser un `KeyError` que mypy no ve. Y ojo con
        # `add_to_group_link`, que el spec SI declara opcional: aqui no lo es, porque el servidor la
        # manda siempre en una entrada `telegram_bot` y quien ramifica ya sabe en cual esta.
        assert not opcionales, f"{mitad.__name__} deja claves opcionales"
        obligatorias |= propias

    # Entre las tres tienen que estar TODAS las propiedades, y ninguna que el spec no declare.
    assert obligatorias == del_spec

    # `redirect` no lleva nada mas que su discriminante. Es la mitad que aguanta las nueve redes.
    assert _claves(_shapes.RedirectAuthorization)[0] == {"type"}


def test_los_tipos_de_autorizacion_son_los_que_el_spec_enumera() -> None:
    """En las DOS direcciones, que es donde esto vale de verdad.

    El dia que una red se autorice de una forma nueva, el servidor la mete en el `enum` y aqui no
    hay ni mitad ni predicado que la reconozca: un integrador que recorra `connect_links` se la
    comeria como "ninguna de las conocidas" y no conectaria esa red. Este test es lo unico que se
    entera, porque el `Literal` generado si cambia solo y nadie mira un `git diff` de un fichero
    generado buscando un valor nuevo. Ya paso una vez: `telegram_bot` entro asi.
    """
    del_spec = set(
        _spec()["components"]["schemas"]["AccountsSocialAuthorizationMethod"]["properties"]["type"]["enum"]
    )
    de_las_mitades = {get_args(mitad.__annotations__["type"])[0] for mitad in MITADES_DE_AUTORIZACION}
    assert de_las_mitades == del_spec


# =================================================================================================
# `PublicationInput`, que es la unica forma escrita a mano ENCIMA de una generada
# =================================================================================================
#
# El resto del fichero existe porque el generador no emite esas formas. Esta si la emite, y se
# reescribe igualmente para ensanchar `publish_date` a `datetime | str`. Eso deja un tipo a mano que
# puede quedarse atras de dos maneras que nadie ve: que el spec cambie el cuerpo, y que la copia
# ensanche mas de lo que dijo que ensanchaba. Los tres tests siguientes son las dos cosas.

ESQUEMA_PUBLICATION_INPUT = "PublicationsPublicationInput"


def test_el_cuerpo_de_publicar_tiene_los_campos_que_declara_el_spec() -> None:
    esquema = _spec()["components"]["schemas"][ESQUEMA_PUBLICATION_INPUT]
    obligatorias, opcionales = _claves(_shapes.PublicationInput)

    assert obligatorias | opcionales == set(esquema["properties"])
    # El spec no obliga a NINGUNO, ni siquiera a `social_network`: crear sin el es un 702 del
    # servidor, no un fallo de forma, y `update` reutiliza el mismo cuerpo para tocar un campo.
    assert obligatorias == set(esquema.get("required", []))


def test_el_cuerpo_de_publicar_solo_ensancha_publish_date() -> None:
    """Lo escrito a mano, campo a campo contra lo generado.

    Es el test que importa de los tres: sin el, la copia se puede ir separando del spec un campo
    cada vez —un `title` que pasa a obligatorio, un `publication_type` con un valor nuevo— y el
    unico sintoma seria que la libreria acepta un cuerpo que el servidor rechaza. La UNICA
    diferencia permitida es la que motiva el fichero, y se nombra aqui para que anadir una segunda
    tenga que pasar por editar este test.
    """
    a_mano = _shapes.PublicationInput.__annotations__
    generado = PublicationsPublicationInput.__annotations__

    assert set(a_mano) == set(generado)
    for campo in generado:
        if campo == "publish_date":
            continue
        assert a_mano[campo] == generado[campo], f"`{campo}` ya no dice lo que dice el generado"

    # Y el ensanchado, explicito: lo del spec sigue valiendo, y ademas entra un `datetime`.
    assert _shapes.PublicationInput.__annotations__["publish_date"] == NotRequired[datetime | str]


def test_las_redes_que_publican_son_las_que_el_spec_enumera() -> None:
    """En las dos direcciones, y contra el enum EN LINEA del que sale.

    `/allowed_social_publications` no sirve de ancla: devuelve `SocialNetwork[]`, o sea las once.
    El unico sitio donde el spec dice cuales son las que publican es este enum dentro del cuerpo,
    asi que es contra el que se compara. El dia que una red nueva publique, esto se pone rojo y
    `PUBLISHABLE_NETWORKS` deja de decir que no a una red que si — que es exactamente lo que paso
    con `telegram`.
    """
    del_spec = set(
        _spec()["components"]["schemas"][ESQUEMA_PUBLICATION_INPUT]["properties"]["social_network"]["enum"]
    )
    assert set(get_args(_shapes.PublishableNetwork)) == del_spec

    # Y que sea de verdad mas estrecha que la lista entera, que es lo que la hace util.
    todas = set(_spec()["components"]["schemas"]["SocialNetwork"]["enum"])
    assert del_spec < todas
    assert todas - del_spec == {"google_business"}
