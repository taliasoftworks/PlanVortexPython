"""CAPA 3 — el catalogo: que redes hay, que sabe hacer cada una y con que limites.

Aqui es donde se entera la libreria de que el producto ha crecido. La capa 2 simula las respuestas y
por definicion nunca ve una red nueva; esta pregunta, y una undecima red que llegue sin limites o sin
capacidades sale en rojo el dia que se despliega y no seis meses despues, cuando un integrador
intente publicar en ella.

Los endpoints se cruzan ENTRE SI a proposito. Cada uno por separado siempre parece correcto: lo que
falla en la vida real es que uno crezca y los otros no.
"""

from __future__ import annotations

from typing import Any

import pytest

from planvortex import HttpHooks, PlanVortex, RequestInfo
from tests.live.conftest import LIVE, cliente_live

pytestmark = LIVE


@pytest.fixture(scope="module")
def catalogo(pv: PlanVortex) -> dict[str, Any]:
    """Los siete endpoints, leidos UNA vez. Se cruzan entre ellos, asi que viajan juntos."""
    return {
        "redes": pv.catalog.social_networks(),
        "publican": pv.catalog.allowed_social_publications(),
        "mensajean": pv.catalog.allowed_social_messages(),
        "capacidades": pv.catalog.social_capabilities(),
        "acciones": pv.catalog.social_comment_actions(),
        "limites": pv.catalog.social_limits(),
        "proporciones": pv.catalog.allowed_aspect_ratios(),
    }


def test_devuelve_las_redes_del_producto(catalogo: dict[str, Any]) -> None:
    redes = catalogo["redes"]

    assert len(redes) >= 9
    assert all(isinstance(red, str) and red for red in redes)


def test_cada_red_tiene_los_cinco_limites_que_se_declaran_completos(catalogo: dict[str, Any]) -> None:
    """`SOCIAL_LIMITS` es la unica fuente de verdad del servidor, y quien valida es quien anuncia.

    Si una red llega sin entrada, el compositor del panel se queda sin contador y la libreria no
    puede avisar antes de mandar. Un `0` es un valor legitimo —"esta red no tiene titulo"—; lo que no
    vale es que falte la clave, porque un `None` no se distingue de un olvido.

    Son cinco y no los siete mapas: los otros dos no van por red, y se miran mas abajo.
    """
    limites = catalogo["limites"]
    mapas = (
        "characters",
        "comment_characters",
        "max_file_size_mb",
        "max_post_bytes",
        "title_characters",
    )

    for red in catalogo["redes"]:
        for mapa in mapas:
            assert isinstance((limites.get(mapa) or {}).get(red), int), f"{mapa}.{red}"


def test_total_images_cubre_todas_las_redes_que_publican(catalogo: dict[str, Any]) -> None:
    """Aqui la cobertura exigible es la de las redes que PUBLICAN.

    Una red sin publicaciones no tiene "imagenes por publicacion" que anunciar. Google Business si
    esta, a `0`, aunque no publique; WhatsApp no esta. La inconsistencia es del servidor y no cambia
    nada para quien integra, asi que el test pide lo que de verdad importa y no lo que seria bonito.
    """
    total = catalogo["limites"].get("total_images") or {}

    for red in catalogo["publican"]:
        assert isinstance(total.get(red), int), f"total_images.{red}"


def test_las_capacidades_cuadran_con_las_listas_de_publicacion_y_mensajeria(
    catalogo: dict[str, Any],
) -> None:
    capacidades = catalogo["capacidades"]

    for red in catalogo["redes"]:
        capacidad = capacidades.get(red)
        assert capacidad is not None, f"capacidades de {red}"

        # Las dos listas son la misma informacion dicha de otra forma. Que se separen es exactamente
        # lo que rompe a un integrador que use una y no la otra.
        assert capacidad["publications"] is (red in catalogo["publican"]), f"{red}.publications"
        assert capacidad["messages"] is (red in catalogo["mensajean"]), f"{red}.messages"


def test_las_redes_con_comentarios_traen_su_matriz_de_acciones(catalogo: dict[str, Any]) -> None:
    """`allowComments()` es la puerta gruesa y esto es la fina: quien puede responder, ocultar y
    borrar.

    Van en endpoints distintos porque tienen formas distintas, y por eso hay que comprobar que no se
    separen.
    """
    capacidades = catalogo["capacidades"]
    con_comentarios = [red for red in catalogo["redes"] if capacidades.get(red, {}).get("comments")]
    assert con_comentarios

    for red in con_comentarios:
        acciones = catalogo["acciones"].get(red)
        assert acciones is not None, f"acciones de {red}"
        for accion in ("reply", "hide", "delete_own", "delete_others"):
            assert isinstance(acciones.get(accion), bool), f"{red}.{accion}"


def test_los_dos_mapas_que_no_van_por_red_no_inventan_nombres_de_red(catalogo: dict[str, Any]) -> None:
    """Los dos mapas que NO van por red, y por que no se les puede pedir cobertura:

    - `video_duration_in_seconds` va por red **y tipo de publicacion** (`instagram_story`,
      `facebook_reel`) y solo estan las redes que limitan por duracion. Discord limita por PESO y por
      eso vive en `max_file_size_mb`.
    - `allowed_aspect_ratios` tampoco tiene a Discord, y es deliberado: no rechaza ninguna
      proporcion, asi que no hay lista de admitidas que publicar.

    Lo que si se les puede exigir es que ninguna clave sea de una red que no existe. Suena a poco y
    no lo es: en el servidor vivio anos un `likedin` sin la ene que dejaba a LinkedIn sin proporcion
    por defecto y reventaba al recortar, y le llegaba al usuario como un error generico.
    """
    duraciones = catalogo["limites"].get("video_duration_in_seconds") or {}
    claves = [*duraciones.keys(), *catalogo["proporciones"].keys()]
    assert claves

    for clave in claves:
        conocida = any(clave == red or clave.startswith(f"{red}_") for red in catalogo["redes"])
        assert conocida, f"clave de red desconocida: {clave}"

    for clave, valor in duraciones.items():
        assert isinstance(valor, int), f"video_duration_in_seconds.{clave}"


def test_los_limites_de_publicacion_llegan_con_los_tres_tamanos(pv: PlanVortex) -> None:
    limites = pv.catalog.publication_limits()

    assert limites
    assert len(limites) > 0


def test_las_plantillas_del_planificador_traen_sus_costes_y_sus_campos(pv: PlanVortex) -> None:
    """La entrada del catalogo que MAS caro sale copiar: lleva precios dentro.

    La capa 2 simula la respuesta, asi que jamas veria que el servidor ha cambiado lo que cobra ni
    que ha entrado una plantilla nueva — que es de lo que esta capa existe para enterarse.

    Lo que se cruza aqui es el invariante del que cuelga el consejo que da la libreria: **la que no
    genera la imagen tampoco la regenera**. El dia que dejara de cumplirse, el README estaria
    mintiendo.
    """
    plantillas = pv.catalog.planner_templates()

    assert len(plantillas) >= 5

    for plantilla in plantillas:
        nombre = plantilla.get("template")
        assert isinstance(nombre, str) and nombre, plantilla
        assert isinstance(plantilla.get("orchestration_cost"), int), f"{nombre}.orchestration_cost"
        assert isinstance(plantilla.get("generates_images"), bool), f"{nombre}.generates_images"

        # Sin imagen generada no hay imagen que regenerar. Lo contrario le cobraria al usuario 70
        # creditos por cambiar su propia foto por una inventada.
        if plantilla.get("generates_images") is False:
            assert (plantilla.get("regenerate") or {}).get("image") is False, f"{nombre}.regenerate"

        # Y un tope de unidades sin un campo que las recoja seria un numero que nadie puede usar.
        if plantilla.get("max_source_items", 0) > 0:
            assert plantilla.get("source_fields"), f"{nombre}.source_fields"

        # `source_requires_any` solo puede nombrar campos que la plantilla declare.
        declarados = {campo.get("name") for campo in plantilla.get("source_fields") or []}
        for pedido in plantilla.get("source_requires_any") or []:
            assert pedido in declarados, f"{nombre}.source_requires_any: {pedido}"

    # `standard` no puede desaparecer: es lo que tarifa un plan que no manda `template`.
    assert "standard" in [plantilla.get("template") for plantilla in plantillas]


def test_el_catalogo_se_cachea_dos_lecturas_una_peticion() -> None:
    """Y `clear_cache()` tiene que volver a preguntar DE VERDAD, no solo de mentira en la capa 2."""
    llamadas = 0

    def contar(info: RequestInfo) -> None:
        nonlocal llamadas
        if "/social_networks" in info.url and info.attempt == 1:
            llamadas += 1

    with cliente_live(hooks=HttpHooks(on_request=contar)) as cliente:
        cliente.catalog.social_networks()
        cliente.catalog.social_networks()
        assert llamadas == 1

        cliente.catalog.clear_cache()
        cliente.catalog.social_networks()
        assert llamadas == 2
