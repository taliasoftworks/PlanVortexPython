"""Lo que hace falta para afirmar sobre UNA peticion, sin repetirlo en seis ficheros.

El plugin ya vigila las dos ausencias —ninguna peticion sin simular, ningun mock sin usar—, asi que
aqui solo hacen falta las tres cosas que un test de contrato mira a mano: la ruta, la query y el
cuerpo. La query se devuelve como listas porque **un parametro repetido es lo normal en esta API**
(`?state=ready&state=withErrors`), y aplanarlo a un valor escondería justo lo que hay que
comprobar.

Las peticiones de token se filtran de `peticiones()`: son infraestructura y aparecerian en medio de
lo que se esta afirmando.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs

from tests.conftest import BASE_URL

PREFIJO = BASE_URL[BASE_URL.index("/v1.0.0") :]


def peticiones(httpx_mock: Any) -> list[Any]:
    """Todas las peticiones capturadas, en orden y sin las del token."""
    return [
        peticion for peticion in httpx_mock.get_requests() if not peticion.url.path.endswith("/oauth/token")
    ]


def unica(httpx_mock: Any) -> Any:
    """La unica peticion del test. Falla en voz alta si hubo mas de una o ninguna."""
    capturadas = peticiones(httpx_mock)
    assert len(capturadas) == 1, f"se esperaba una peticion y hubo {len(capturadas)}"
    return capturadas[0]


def ruta(peticion: Any) -> str:
    """La ruta sin la base ni el `/v1.0.0`, que es como se lee en el spec."""
    camino: str = peticion.url.path
    return camino[len(PREFIJO) :] if camino.startswith(PREFIJO) else camino


def query(peticion: Any) -> dict[str, list[str]]:
    """La query como pares clave -> lista de valores, con las claves repetidas juntas."""
    return parse_qs(peticion.url.query.decode(), keep_blank_values=True)


def cuerpo(peticion: Any) -> Any:
    """El cuerpo JSON, o ``None`` cuando no habia."""
    crudo = peticion.content
    return json.loads(crudo) if crudo else None


def partes_multipart(peticion: Any) -> dict[str, bytes]:
    """El multipart, troceado por nombre de campo. Solo para las subidas.

    No se usa una libreria: lo que un test quiere afirmar es que el campo se llama `file`, que
    lleva el nombre del fichero y el `content-type` que se dedujo, y que los bytes llegaron enteros.
    """
    tipo = peticion.headers["content-type"]
    assert tipo.startswith("multipart/form-data"), tipo
    frontera = tipo.split("boundary=", 1)[1].encode()
    trozos = peticion.content.split(b"--" + frontera)
    partes: dict[str, bytes] = {}
    for trozo in trozos:
        if b"\r\n\r\n" not in trozo:
            continue
        cabeceras, _, contenido = trozo.partition(b"\r\n\r\n")
        nombre = cabeceras.split(b'name="', 1)[1].split(b'"', 1)[0].decode()
        partes[nombre] = contenido.rstrip(b"\r\n")
        partes[f"{nombre}:headers"] = cabeceras
    return partes
