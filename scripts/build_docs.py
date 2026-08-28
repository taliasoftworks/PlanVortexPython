"""Genera la referencia de la API en `docs/`, que es lo que se publica en GitHub Pages.

    uv run python scripts/build_docs.py

`docs/` NO se commitea (esta en `.gitignore`, igual que en la libreria de Node): la referencia se
genera en cada push a `main` y lo que se sube como artefacto es lo que acaba de salir de aqui, asi
que no puede quedarse vieja.

POR QUE `pdoc` Y NO `mkdocs-material` + `mkdocstrings`: porque la documentacion de esta libreria
ESTA en los docstrings —el nucleo, los catorce recursos, los tipos y los webhooks—, la guia larga
vive en PlanVortexHome, y lo unico que falta aqui es la referencia. `pdoc` es una orden sin fichero
de configuracion; la otra pareja son un `mkdocs.yml` y un `nav` escrito a mano que se queda atras el
dia que se anade un recurso. Es la misma decision que TypeDoc en la libreria de Node.

ESTE FICHERO EXISTE POR LA LISTA DE MODULOS, que es lo unico que hay que mantener. Escrita en el
workflow, la CI publicaria una referencia distinta de la que ve quien la genera en su maquina.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Los dos gemelos van los DOS, y no es duplicar por duplicar: quien escribe un script usa el
# sincrono, y dejarlo fuera lo mandaria a leer la pagina de un cliente que no es el suyo. Que sean
# identicos no lo hace redundante — lo hace gratis, porque uno se genera del otro.
MODULOS = (
    "planvortex",
    "planvortex.types",
    "planvortex.webhooks",
    "planvortex.resources",
    "planvortex.resources_sync",
)

# `base` es la clase de la que heredan los catorce recursos: sus metodos son privados y lo que
# quedaria es una pagina vacia con un nombre que invita a leerla. Lo demas que empieza por `_`
# —`_core`, `_generated`, `_shapes`— lo salta `pdoc` por su cuenta.
EXCLUIDOS = (r"!planvortex\.resources(_sync)?\.base",)

# UN AVISO CONOCIDO Y QUE NO SE ARREGLA. `pdoc` saca cuatro "Error parsing type annotation
# list[ConnectLink] ... 'function' object is not subscriptable": resuelve la anotacion de un metodo
# en el espacio de nombres de SU CLASE, y esas clases tienen un metodo llamado `list`, asi que el
# `list` del `list[ConnectLink]` le sale la funcion. Lo unico que se pierde es el enlace en esas
# cuatro firmas, que salen como texto. La alternativa era renombrar `list` en catorce recursos.


def main() -> int:
    destino = RAIZ / "docs"
    orden = [
        sys.executable,
        "-m",
        "pdoc",
        *MODULOS,
        *EXCLUIDOS,
        "--output-directory",
        str(destino),
        # Los docstrings de esta libreria usan `:param:`, `:raises:` y `.. code-block:: python`,
        # que es reStructuredText. Es el valor por defecto de pdoc hoy, y se pasa explicito porque
        # el dia que cambie no habria ningun sintoma: se veria el marcado en crudo y ya.
        "--docformat",
        "restructuredtext",
        "--footer-text",
        f"planvortex {_version()}",
    ]
    print(" ".join(orden))
    resultado = subprocess.run(orden, cwd=RAIZ, check=False)
    if resultado.returncode == 0:
        print(f"Referencia en {destino}")
    return resultado.returncode


def _version() -> str:
    """La version del paquete instalado, para el pie. Sale de una sola fuente, como el resto."""
    from planvortex import VERSION

    version: str = VERSION
    return version


if __name__ == "__main__":
    raise SystemExit(main())
