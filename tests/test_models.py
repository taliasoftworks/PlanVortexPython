"""Los tipos generados contra el OpenAPI del que salen, y el guardia que los vigila.

Lo que la CI comprueba es otra cosa y es la principal: regenera y hace `git diff --exit-code`, o
sea que lo commiteado corresponde al spec commiteado. Aqui se comprueba lo que ese diff NO puede
ver, porque un fichero generado mal se regenera igual de mal y el diff sale vacio:

- **`_id` sigue llamandose `_id`** (§ Trampa P1). Es el unico fallo de esta fase que compila y
  miente: `datamodel-code-generator` sanea los nombres que no puede usar como atributo, y sin
  `--special-field-name-prefix ""` la clave primaria de todos los recursos sale como `field_id` —
  un campo que no existe en ninguna respuesta. mypy aprobaria `pub["field_id"]`, que revienta al
  ejecutarse, y rechazaria `pub["_id"]`, que es lo correcto;
- **el spec y los tipos tienen las mismas claves**, en las dos direcciones y con la misma
  obligatoriedad. Un campo que el servidor manda siempre y el tipo declara opcional obliga a
  comprobarlo en balde; al reves es peor;
- **la introspeccion en ejecucion no miente**. `__optional_keys__` vacio es el sintoma de dos
  fallos silenciosos distintos —el `from __future__ import annotations` y el `TypedDict` de
  `typing` con el `NotRequired` de `typing_extensions`— que mypy no ve, porque los comprobadores
  leen la PEP 655 directamente y aciertan igual;
- **los `Literal` escritos a mano en `types.py`** —los de las enumeraciones que el spec declara en
  linea y no como esquema— siguen diciendo lo que dice el bundle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, get_args

import pytest

from planvortex import types
from planvortex._generated import models

ROOT = Path(__file__).resolve().parent.parent
OPENAPI = ROOT / "openapi" / "planvortex.openapi.json"
MODELS_FILE = ROOT / "src" / "planvortex" / "_generated" / "models.py"

SPEC: dict[str, Any] = json.loads(OPENAPI.read_text(encoding="utf8"))
ESQUEMAS: dict[str, Any] = SPEC["components"]["schemas"]

# Los esquemas que se comparan campo a campo. Se dejan fuera los que combinan con `allOf`/`oneOf`,
# porque alli las propiedades no estan todas en el mismo sitio del documento y resolverlas seria
# reimplementar medio JSON Schema dentro de un test.
COMPARABLES = sorted(
    nombre
    for nombre, esquema in ESQUEMAS.items()
    if esquema.get("type") == "object"
    and isinstance(esquema.get("properties"), dict)
    and not (esquema.keys() & {"allOf", "oneOf", "anyOf"})
)

# Los recursos cuya clave primaria es `_id`. No es una lista de conveniencia: es la § Trampa P1
# escrita, y cada uno de estos es una respuesta que el integrador indexa por esa clave.
CON_ID = ("Publication", "Account", "Upload", "CommentsComment", "Message", "Contact", "ClientsClient")


def _es_typed_dict(nombre: str) -> bool:
    """No todo esquema es un TypedDict: `SocialNetwork` es un `Literal` y `AccountsMetricList` una
    lista. Los alias no tienen claves que comparar.
    """
    return hasattr(getattr(models, nombre, None), "__required_keys__")


def _claves(nombre: str) -> frozenset[str]:
    """Las claves de un TypedDict generado, incluidas las heredadas por un `allOf`."""
    tipo = getattr(models, nombre)
    claves: frozenset[str] = tipo.__required_keys__ | tipo.__optional_keys__
    return claves


# ------------------------------------------------------------------------------- § Trampa P1


@pytest.mark.parametrize("nombre", CON_ID)
def test_la_clave_primaria_sigue_llamandose_id(nombre: str) -> None:
    """`_id`, y no `id` ni `field_id`. El fallo que compila y miente.

    Si esto falla, lo que hay que mirar es `--special-field-name-prefix` en
    `scripts/generate_models.py`: el generador ha vuelto a sanear el nombre.
    """
    claves = _claves(nombre)

    assert "_id" in claves
    assert "field_id" not in claves
    assert "id" not in claves


def test_no_hay_un_solo_nombre_saneado_en_todo_el_modulo() -> None:
    """La version general de lo anterior, para los esquemas que nadie ha listado arriba."""
    saneados = sorted(
        f"{nombre}.{clave}"
        for nombre in ESQUEMAS
        if _es_typed_dict(nombre)
        for clave in _claves(nombre)
        if clave.startswith("field_")
    )

    assert saneados == []


def test_el_id_es_obligatorio_donde_el_spec_dice_que_lo_es() -> None:
    """Que la clave exista no basta: declararla opcional obligaria a comprobarla en cada acceso."""
    obligatorios = [nombre for nombre in CON_ID if "_id" in ESQUEMAS[nombre].get("required", [])]

    assert obligatorios, "el spec ha dejado de declarar `_id` obligatorio en TODOS: revisalo"
    for nombre in obligatorios:
        assert "_id" in getattr(models, nombre).__required_keys__


# --------------------------------------------------------------------- el spec y los tipos


def test_todos_los_esquemas_tienen_su_tipo_con_su_nombre() -> None:
    """Los 121 esquemas de `components/schemas`, uno a uno.

    Es lo que hace que `types.py` pueda mapear `Publication` al `Publication` publico sin
    comprobar nada: si un objeto declarado en linea le robara el nombre —lo evita
    `--naming-strategy primary-first`—, el alias publico apuntaria en silencio a otra forma.
    """
    faltan = sorted(nombre for nombre in ESQUEMAS if not hasattr(models, nombre))

    assert faltan == []


@pytest.mark.parametrize("nombre", COMPARABLES)
def test_las_claves_del_tipo_son_las_del_esquema(nombre: str) -> None:
    """En las dos direcciones: ni una clave de menos ni una de mas."""
    assert _claves(nombre) == frozenset(ESQUEMAS[nombre]["properties"])


@pytest.mark.parametrize("nombre", COMPARABLES)
def test_lo_obligatorio_del_tipo_es_lo_obligatorio_del_esquema(nombre: str) -> None:
    """Y con la misma obligatoriedad, que es la mitad que no se ve al leer el fichero generado."""
    esperado = frozenset(ESQUEMAS[nombre].get("required", []))

    assert getattr(models, nombre).__required_keys__ == esperado


def test_la_introspeccion_en_ejecucion_no_miente() -> None:
    """`__optional_keys__` vacio es el sintoma de los dos fallos silenciosos de esta fase.

    Uno es `from __future__ import annotations`, que deja las anotaciones en CADENAS y hace que
    `TypedDict` no pueda leer un `NotRequired` que es texto. El otro es coger `TypedDict` de
    `typing` y `NotRequired` de `typing_extensions`, que en 3.10 hace exactamente lo mismo. Los dos
    dan todas las claves por obligatorias, mypy sigue en verde en los dos casos, y el unico sitio
    donde se nota es aqui.
    """
    assert models.Publication.__optional_keys__
    assert "text" in models.Publication.__optional_keys__


def test_el_modulo_generado_no_exige_typing_extensions_en_las_versiones_que_no_lo_tienen() -> None:
    """La guarda de version, mirada en el texto porque es lo unico que se puede mirar desde aqui.

    Este proceso no puede comprobar las cinco versiones de la matriz, pero si que el fichero no
    tenga un `from typing_extensions import ...` suelto. Con uno, el paquete se instala y NO se
    importa en 3.13 ni en 3.14, donde `typing_extensions` no viene con nada — y aqui no se veria,
    porque mypy lo instala.
    """
    texto = MODELS_FILE.read_text(encoding="utf8")

    assert "if sys.version_info >= (3, 11):" in texto
    assert "\nfrom typing_extensions import" not in texto


def test_el_modulo_generado_avisa_de_que_es_generado() -> None:
    """La cabecera es lo unico que impide que alguien lo edite y pierda el cambio al regenerar."""
    assert MODELS_FILE.read_text(encoding="utf8").startswith('"""GENERADO POR `scripts/generate_models.py`')


# ------------------------------------------------------- las enumeraciones escritas a mano


@pytest.mark.parametrize(
    ("tupla", "esquema", "campo"),
    [
        (types.PUBLICATION_STATES, "Publication", "state"),
        (types.PUBLICATION_TYPES, "Publication", "publication_type"),
        (types.AI_PLAN_STATES, "AiPlansAiPlan", "state"),
        (get_args(types.FileType), "Upload", "file_type"),
        (get_args(types.FileFormat), "Upload", "file_format"),
        (get_args(types.EngagementBase), "Publication", "engagement_base"),
        (types.PLANNER_TEMPLATES, "CatalogPlannerTemplate", "template"),
        (get_args(types.PlannerTemplateFieldType), "CatalogPlannerTemplateField", "type"),
    ],
    ids=[
        "states",
        "types",
        "ai_plan",
        "file_type",
        "file_format",
        "engagement",
        "planner_templates",
        "planner_field_types",
    ],
)
def test_los_literales_escritos_a_mano_dicen_lo_que_dice_el_spec(
    tupla: tuple[str, ...], esquema: str, campo: str
) -> None:
    """Estas ocho no tienen esquema propio: el spec las declara en linea, asi que el generador las
    emite como un `Literal` anonimo dentro del campo y no hay nada que importar.

    Son la unica parte de `types.py` que puede quedarse atras sola, y por eso se comparan con el
    bundle en vez de darlas por buenas.
    """
    assert list(tupla) == ESQUEMAS[esquema]["properties"][campo]["enum"]


def test_la_plantilla_que_se_manda_es_la_misma_que_la_que_se_lee() -> None:
    """El spec declara el mismo enum en TRES sitios: la ficha del catalogo, el cuerpo de crear y el
    plan guardado. Son tres copias, y una copia que derive es una plantilla que se puede pedir y no
    se puede leer —o al reves— sin que nada lo diga.
    """
    del_catalogo = ESQUEMAS["CatalogPlannerTemplate"]["properties"]["template"]["enum"]
    de_crear = ESQUEMAS["AiPlansAiPlanCreateRequest"]["properties"]["template"]["enum"]
    del_plan = ESQUEMAS["AiPlansAiPlan"]["properties"]["template"]["enum"]

    assert de_crear == del_catalogo
    assert del_plan == del_catalogo
    assert list(types.PLANNER_TEMPLATES) == del_catalogo


def test_las_redes_de_la_tupla_son_las_del_spec() -> None:
    """`SOCIAL_NETWORKS` sale del `Literal` con `get_args`, asi que esto comprueba la cadena entera:
    spec -> tipo generado -> tupla de ejecucion.
    """
    assert list(types.SOCIAL_NETWORKS) == ESQUEMAS["SocialNetwork"]["enum"]
    assert list(types.COMMENT_NETWORKS) == ESQUEMAS["CommentsCommentNetworkName"]["enum"]
    assert list(types.CONTACT_CHANNELS) == ESQUEMAS["ContactChannel"]["enum"]
    assert list(types.MESSAGE_TYPES) == ESQUEMAS["MessageType"]["enum"]
    assert list(types.INTEGRATION_PROVIDERS) == ESQUEMAS["IntegrationsIntegrationProviderName"]["enum"]


def test_las_redes_de_comentarios_son_un_subconjunto_de_las_redes() -> None:
    """Una red con comentarios que no fuera una red seria una errata del spec, no una novedad."""
    assert set(types.COMMENT_NETWORKS) <= set(types.SOCIAL_NETWORKS)


def test_el_canal_de_un_contacto_es_una_red_o_el_correo() -> None:
    """`ContactChannel` es un SUBCONJUNTO de `SocialNetwork` mas `email`, y no la lista entera.

    Fue la lista entera hasta Telegram, y el dia que dejo de serlo es justo lo que habia que dejar
    escrito: un canal de contacto es una bandeja de chat, y esa red no tiene mensajes directos —un
    bot no puede empezar una conversacion con nadie—. Meterla ahi prometeria un buzon que no existe,
    asi que su ausencia es una decision y no un olvido del spec.

    Lo que si tiene que seguir cumpliendose es que no haya ningun canal que no sea una red (o el
    correo): eso si seria una errata.
    """
    assert set(types.CONTACT_CHANNELS) <= set(types.SOCIAL_NETWORKS) | {"email"}
    assert "email" in types.CONTACT_CHANNELS
    assert "telegram" in types.SOCIAL_NETWORKS
    assert "telegram" not in types.CONTACT_CHANNELS


# --------------------------------------------------------------- la superficie de `types.py`


def test_todo_lo_que_types_promete_existe() -> None:
    """Un nombre en `__all__` que no esta es un `ImportError` en el codigo del integrador."""
    faltan = sorted(nombre for nombre in types.__all__ if not hasattr(types, nombre))

    assert faltan == []


def test_types_no_publica_nada_a_medias() -> None:
    """La direccion contraria: nada definido en `types.py` se queda fuera de `__all__`.

    Un tipo que existe pero no se exporta es un tipo que nadie encuentra — y que un `from
    planvortex.types import *` no trae, aunque el editor lo autocomplete.
    """
    # Lo que `types.py` importa para escribirse a si mismo y no forma parte de su superficie.
    herramientas = {"Literal", "TypeAlias", "TypeGuard", "annotations", "cast", "get_args"}
    definidos = {
        nombre for nombre in vars(types) if not nombre.startswith("_") and nombre not in herramientas
    }

    assert definidos == set(types.__all__)


def test_el_all_de_types_no_repite_nada() -> None:
    """Un nombre dos veces es una linea que sobra, y casi siempre el rastro de un copiar y pegar.

    El ORDEN no se comprueba aqui: lo vigila `ruff` con la convencion de la casa —constantes
    primero, luego tipos, luego funciones—, que no es el `sorted()` de Python.
    """
    assert len(types.__all__) == len(set(types.__all__))


def test_los_alias_publicos_apuntan_al_tipo_generado_que_dicen() -> None:
    """La comprobacion que evita el peor fallo de este fichero: un alias bien escrito que apunta a
    otra forma.

    `AccountMetrics` y `PublicationMetrics` son el ejemplo real: en el modulo generado esos DOS
    nombres existen y son bloques del dashboard, no lo que la libreria de Node llama asi. Aqui se
    comprueba a que apunta cada uno de verdad.
    """
    assert types.AccountMetrics is models.AccountsMetricModel
    assert types.PublicationMetrics is models.NormalizedMetrics
    assert types.PublicationErrorDetail is models.PublicationError
    assert types.Publication is models.Publication
    assert types.Comment is models.CommentsComment
    assert types.Limit is models.OrganizationsLimit
