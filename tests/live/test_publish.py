"""CAPA 3 — el camino de publicar, escribiendo de verdad.

TODO LO DE AQUI ESTA APAGADO por defecto y necesita `LIVE_ALLOW_PUBLISH=1`. Y aun encendido, lo que
crea **no sale a ninguna red**: la publicacion se programa a un dia vista y se borra al terminar.
Mandarla de verdad lleva un interruptor aparte, `LIVE_ALLOW_SOCIAL_PUBLISH=1`, porque eso ya es
publico, inmediato e irreversible.

Lo que solo se puede comprobar aqui:

 - **El `multipart` de verdad.** La capa 2 mira las partes que monta la libreria; que el servidor las
   acepte —y deduzca `file_type` y `file_format` del `content-type` de la parte, que es el error 805
   clasico— solo lo dice el servidor.
 - **`public_path` sirve.** Es una URL firmada que caduca. Que este bien formada no significa que se
   pueda descargar.
 - **Una publicacion invalida NO es un error HTTP**: llega un 200 en estado `withErrors` con el
   motivo dentro. Es la sorpresa que se lleva todo el que integra, y por eso la libreria no la
   convierte en una excepcion.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx2
import pytest

from planvortex import PlanVortexError
from planvortex.types import Account
from tests.live.conftest import LIVE, ContextoLive, escribe, marca, publica

pytestmark = LIVE


def _fichero_para(limites: Any, red: str, imagen: Path, video: Path | None) -> Path | None:
    """Que fichero acepta ESA red, segun el catalogo y no segun lo que nos parezca.

    `total_images: 0` es YouTube, que solo publica video: una imagen suya solo puede ser miniatura, y
    eso no es una publicacion (error 943).
    """
    admite_imagenes = ((limites.get("total_images") or {}).get(red) or 0) > 0
    return imagen if admite_imagenes else video


def _cuerpo(red: str, texto: str, limites: Any, **extra: Any) -> Any:
    """Una publicacion valida para la red que toque, con su titulo si lo pide.

    `title_characters > 0` es una red que EXIGE titulo: YouTube contesta 944 sin el. Todo lo que
    decide la forma de la publicacion sale del CATALOGO, que es exactamente lo que este paquete le
    pide a quien integra.
    """
    titulo = (limites.get("title_characters") or {}).get(red) or 0
    cuerpo: dict[str, Any] = {"social_network": red, "text": texto, "files": [], **extra}
    if titulo > 0:
        cuerpo["title"] = texto[:titulo]
    return cuerpo


@escribe
def test_sube_una_imagen_la_descarga_por_su_public_path_y_la_borra(live: ContextoLive, imagen: Path) -> None:
    fichero = live.pv.uploads.create(live.organization["_id"], imagen)

    try:
        assert fichero["_id"]
        # `file_type` y `file_format` los decide el servidor a partir del `content-type` de la
        # PARTE. Un `application/octet-stream` —lo que manda quien no deduce el tipo— se lleva un 805
        # con un PNG perfectamente valido dentro.
        assert fichero["file_type"] == "image"
        assert fichero["file_format"] == "png"
        assert fichero["file_properties"]["size_in_bytes"] > 0

        leido = live.pv.uploads.get(live.organization["_id"], fichero["_id"])
        assert leido["_id"] == fichero["_id"]
        assert leido["public_path"].startswith("http")

        # Si esto falla, o la firma esta mal o el stack contra el que pruebas no tiene quien sirva
        # los ficheros. Dentro de Docker el driver `local` no vale: no hay volumen ni servidor
        # estatico desde que se retiro `planvortex_cdn`.
        respuesta = httpx2.get(leido["public_path"], follow_redirects=True)
        assert respuesta.status_code == 200, f"public_path devolvio {respuesta.status_code}"
    finally:
        live.pv.uploads.remove(live.organization["_id"], fichero["_id"], force=True)

    # Y borrado es borrado: el fichero ya no esta.
    with pytest.raises(PlanVortexError):
        live.pv.uploads.get(live.organization["_id"], fichero["_id"])


@escribe
def test_programa_una_publicacion_la_encuentra_en_la_agenda_y_la_borra(
    live: ContextoLive, cuenta_que_publica: Account | None, imagen: Path, video: Path | None
) -> None:
    if cuenta_que_publica is None:
        pytest.skip("no hay ninguna cuenta conectada que publique")

    red = cuenta_que_publica["social_network"]
    limites = live.pv.catalog.social_limits()
    fuente = _fichero_para(limites, red, imagen, video)
    if fuente is None:
        pytest.skip(f"{red} no publica imagenes: hace falta LIVE_VIDEO_PATH")

    texto = marca()
    fichero = live.pv.uploads.create(live.organization["_id"], fuente)
    id_publicacion: str | None = None

    try:
        publicacion = live.pv.publications.create(
            live.organization["_id"],
            cuenta_que_publica["_id"],
            _cuerpo(
                red,
                texto,
                limites,
                files=[fichero["_id"]],
                # A un dia vista: queda `ready` y el robot no la toca mientras dura el test.
                publish_date=datetime.now(timezone.utc) + timedelta(days=1),
            ),
        )
        id_publicacion = publicacion["_id"]

        # Una publicacion invalida se guarda igual, en `withErrors` y con el motivo dentro. Que el
        # test lo diga con los codigos a la vista ahorra media tarde de mirar el panel.
        errores = publicacion.get("publication_errors") or []
        detalle = ", ".join(f"[{uno.get('code')}] {uno.get('message')}" for uno in errores)
        assert not errores, f"la publicacion quedo en {publicacion['state']}: {detalle}"
        assert publicacion["state"] == "ready"

        leida = live.pv.publications.get(live.organization["_id"], publicacion["_id"])
        assert leida["_id"] == publicacion["_id"]
        # `files` vuelve POBLADO: son `Upload` enteros, no identificadores. Es lo contrario de lo que
        # se manda, y la unica forma de verlo es preguntando.
        assert leida["files"][0]["_id"] == fichero["_id"]

        agenda = live.pv.publications.list(
            live.organization["_id"],
            state=["ready"],
            accounts=[cuenta_que_publica["_id"]],
            limit=50,
        )
        assert any(una["_id"] == publicacion["_id"] for una in agenda.data)

        live.pv.publications.remove(live.organization["_id"], publicacion["_id"])
        id_publicacion = None

        # Lo que de verdad importa: ya no esta en la agenda, que es de donde tira un panel.
        despues = live.pv.publications.list(
            live.organization["_id"],
            state=["ready"],
            accounts=[cuenta_que_publica["_id"]],
            limit=50,
        )
        assert not any(una["_id"] == publicacion["_id"] for una in despues.data)

        # Y tampoco se lee ya POR ID. Esto era un fallo del servidor —el borrado es blando y
        # `getPublicationById` era un `findById` pelado, asi que borrar y volver a leer por id
        # devolvia la publicacion como si nada— y se arreglo el 2026-08-25: ahora filtra `deleted` y
        # `checkIdPublication` contesta 917. Del listado ya desaparecia, que es por lo que el panel
        # nunca lo noto y quien integra si.
        with pytest.raises(PlanVortexError) as fallo:
            live.pv.publications.get(live.organization["_id"], publicacion["_id"])
        assert fallo.value.code == 917
    finally:
        # Limpiar SIEMPRE, aunque una comprobacion de arriba haya fallado: si no, cada ejecucion deja
        # una publicacion programada que un dia se publica sola.
        if id_publicacion is not None:
            _sin_ruido(live, "publicacion", id_publicacion)
        _sin_ruido(live, "fichero", fichero["_id"])


@publica
def test_publica_ahora_en_la_red_y_lo_borra(
    live: ContextoLive, cuenta_que_publica: Account | None, imagen: Path, video: Path | None
) -> None:
    if cuenta_que_publica is None:
        pytest.skip("no hay ninguna cuenta conectada que publique")

    red = cuenta_que_publica["social_network"]
    limites = live.pv.catalog.social_limits()
    fuente = _fichero_para(limites, red, imagen, video)
    if fuente is None:
        pytest.skip(f"{red} no publica imagenes: hace falta LIVE_VIDEO_PATH")

    fichero = live.pv.uploads.create(live.organization["_id"], fuente)
    id_publicacion: str | None = None

    try:
        # Sin `publish_date` se envia en esta misma peticion, y la respuesta ya dice si salio.
        publicacion = live.pv.publications.create(
            live.organization["_id"],
            cuenta_que_publica["_id"],
            _cuerpo(red, marca(), limites, files=[fichero["_id"]]),
        )
        id_publicacion = publicacion["_id"]

        errores = publicacion.get("publication_errors") or []
        detalle = ", ".join(f"[{uno.get('code')}] {uno.get('message')}" for uno in errores)
        assert not errores, detalle
        assert publicacion["state"] == "sended"
        # El identificador que devuelve la RED. Es lo que prueba que salio de verdad.
        assert publicacion["external_identifier"]
    finally:
        if id_publicacion is not None:
            _sin_ruido(live, "publicacion", id_publicacion)
        _sin_ruido(live, "fichero", fichero["_id"])


def _sin_ruido(live: ContextoLive, que: str, identificador: str) -> None:
    """Borra sin dejar que un fallo de limpieza tape el fallo de verdad del test."""
    try:
        if que == "publicacion":
            live.pv.publications.remove(live.organization["_id"], identificador)
        else:
            live.pv.uploads.remove(live.organization["_id"], identificador, force=True)
    except PlanVortexError:
        pass
