"""From "a file" to the ``file`` part of a ``multipart/form-data`` the server accepts.

FOUR THINGS THAT CANNOT BE IMPROVISED (§ Trampa P5 of the roadmap):

1. **A video is not read into memory.** The server's cap is 200 MB per video; reading that into
   ``bytes`` works with a photo and takes the process down with a real video. An open binary file is
   handed to ``httpx2``, which streams it off the disk as it sends.
2. **AND THEREFORE THE POINTER ENDS UP AT THE END.** A retry over that same object uploads **zero
   bytes**, and the server answers a file error that says nothing about any of this. So every input
   declares how to put itself back (:attr:`UploadPart.rewind`) and, when it cannot, forbids the
   repeat outright (:attr:`UploadPart.repeatable`) — including the pre-flight failures that the
   transport would otherwise consider safe. A pipe, a socket and a generator have no second copy of
   those bytes anywhere.
3. **The part's ``content-type`` decides what the server stores.** ``file_type`` (image or video)
   and ``file_format`` come out of the MIME the client sends, not out of the content and not out of
   the name. An ``application/octet-stream`` — which is what an unnamed stream gets — earns an error
   805 ("this is neither an image nor a video") with a perfectly valid JPEG inside. That is why it
   is guessed from the extension and why it can be passed by hand.
4. **The REQUEST's ``content-type`` is not touched.** ``httpx2`` writes it, with its ``boundary``,
   the moment it is handed ``files=``. Writing it by hand breaks the whole multipart.

There is no synchronous twin here: opening a file is the same call in both clients, and ``httpx2``
reads a plain binary object in either. What changes between them is who awaits the request, and that
is the resource's business.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Union

from planvortex._core.errors import PlanVortexConfigError

# Las cuatro formas en las que un integrador tiene un fichero a mano. La ruta es la buena para lo
# grande: es la unica que ademas no obliga a acordarse del nombre ni de cerrar nada.
FileSource = Union[str, "os.PathLike[str]", bytes, bytearray, IO[bytes], Iterable[bytes]]

# El nombre del campo NO es negociable: el servidor lo lee con `uploadMulter.single("file")` y
# cualquier otro llega como "no se subio ningun fichero".
FIELD_NAME = "file"

# Extension -> MIME, solo de lo que el servidor acepta en la puerta (`ALLOWED_FILES_FORMATS`).
# `heic`/`heif` entran y se convierten a JPEG durante la ingesta, asi que se mandan tal cual: es el
# servidor quien los convierte, no la libreria.
MIME_BY_EXTENSION: dict[str, str] = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "heic": "image/heic",
    "heif": "image/heif",
    "mp4": "video/mp4",
}


@dataclass(frozen=True)
class UploadPart:
    """The multipart part, plus what the transport needs to know before repeating the request."""

    #: What goes into ``httpx2``'s ``files=``. Never build this by hand.
    files: dict[str, tuple[str, Any, str]]
    #: Puts the body back at its start. ``None`` when there is nothing to put back (``bytes``).
    rewind: Callable[[], None] | None
    #: ``False`` when the bytes cannot be sent a second time. The transport then refuses to repeat
    #: this request under any circumstance.
    repeatable: bool


def guess_content_type(filename: str) -> str | None:
    """The MIME an extension implies, or ``None`` when it is not one the server takes."""
    _, _, extension = filename.rpartition(".")
    return MIME_BY_EXTENSION.get(extension.lower()) if extension else None


@contextmanager
def upload_part(
    file: FileSource,
    *,
    filename: str | None = None,
    content_type: str | None = None,
) -> Iterator[UploadPart]:
    """Turn any of the four accepted forms into the part of the request, for as long as it lasts.

    With a path **the library opens and closes it**, which is what keeps a ``ResourceWarning:
    unclosed file`` out of the integrator's process. With anything else the handle is the caller's
    and is left exactly as it was found — open, and wherever the upload left the pointer.
    """
    if isinstance(file, (str, os.PathLike)):
        ruta = Path(file)
        nombre = filename or ruta.name
        tipo = content_type or _exigir_tipo(nombre)
        with ruta.open("rb") as fichero:
            yield UploadPart(
                files=_part(nombre, fichero, tipo),
                rewind=_rebobinar(fichero, 0),
                repeatable=True,
            )
        return

    if isinstance(file, (bytes, bytearray)):
        nombre = _exigir_nombre(filename, "bytes")
        tipo = content_type or _exigir_tipo(nombre)
        # Unos bytes se releen solos: no hay puntero que mover y el reintento es seguro.
        yield UploadPart(files=_part(nombre, bytes(file), tipo), rewind=None, repeatable=True)
        return

    if hasattr(file, "read"):
        abierto: IO[bytes] = file  # type: ignore[assignment]
        propuesto = filename or _nombre_del_fichero(abierto)
        nombre = _exigir_nombre(propuesto, "an open file with no name")
        tipo = content_type or _exigir_tipo(nombre)
        yield UploadPart(files=_part(nombre, abierto, tipo), **_rebobinado(abierto))
        return

    if isinstance(file, Iterable):
        nombre = _exigir_nombre(filename, "an iterable of bytes")
        tipo = content_type or _exigir_tipo(nombre)
        # Un iterable se consume al mandarlo y no hay forma de volver a empezar: se manda una vez o
        # no se manda. `repeatable=False` es lo que impide que el transporte suba cero bytes.
        yield UploadPart(files=_part(nombre, file, tipo), rewind=None, repeatable=False)
        return

    raise PlanVortexConfigError(
        f"A file has to be a path, bytes, an open binary file or an iterable of bytes, "
        f"and this is a {type(file).__name__}."
    )


def _part(filename: str, contenido: Any, content_type: str) -> dict[str, tuple[str, Any, str]]:
    return {FIELD_NAME: (filename, contenido, content_type)}


def _rebobinado(fichero: IO[bytes]) -> dict[str, Any]:
    """Whether this handle can go back, and to where.

    It rewinds to where the pointer WAS when we got it, not to byte zero. For a file just opened
    they are the same thing; for one the caller had already positioned, byte zero would send a
    different body on the second attempt than on the first, which is a worse bug than the one being
    fixed.
    """
    try:
        if not fichero.seekable():
            return {"rewind": None, "repeatable": False}
        inicio = fichero.tell()
    except (OSError, ValueError, AttributeError):
        # Un objeto que ni siquiera sabe decir donde esta no se puede rebobinar. Se manda una vez.
        return {"rewind": None, "repeatable": False}
    return {"rewind": _rebobinar(fichero, inicio), "repeatable": True}


def _rebobinar(fichero: IO[bytes], posicion: int) -> Callable[[], None]:
    """``seek`` returns the new offset, and a rewind returns nothing. It is only that."""

    def rebobinar() -> None:
        fichero.seek(posicion)

    return rebobinar


def _nombre_del_fichero(fichero: IO[bytes]) -> str | None:
    """The name an open file carries, when it has one. A ``BytesIO`` has none, and that is fine."""
    nombre = getattr(fichero, "name", None)
    if isinstance(nombre, str) and nombre:
        return Path(nombre).name
    return None


def _exigir_nombre(filename: str | None, que_es: str) -> str:
    if not filename:
        raise PlanVortexConfigError(
            f"{que_es} carries no name: pass filename alongside the file. The server stores it, "
            "and its extension is what the content type is guessed from."
        )
    return filename


def _exigir_tipo(filename: str) -> str:
    tipo = guess_content_type(filename)
    if tipo is None:
        raise PlanVortexConfigError(
            f'The type of "{filename}" cannot be guessed: pass content_type. PlanVortex decides '
            "whether this is an image or a video from the type you send, not from the bytes, so an "
            "unknown extension would be stored as neither (error 805). Accepted: "
            f"{', '.join(sorted(MIME_BY_EXTENSION))}."
        )
    return tipo
