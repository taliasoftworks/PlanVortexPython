"""Que la copia del OpenAPI commiteada aqui siga siendo la que publica PlanVortexHome.

El spec vive en el repositorio hermano PlanVortexHome (`swagger/*.json`), que es quien lo sirve en
/documentation y quien lo une en `public/openapi.json` — el documento del que beben las dos
librerias oficiales. Aqui se guarda una copia commiteada, y esa copia es la fuente de los tipos: si
alguien toca el spec y no ejecuta `scripts/generate_models.py`, el paquete publica tipos de una API
que ya no existe y nadie se entera hasta que un integrador se come un 400.

Este test compara la copia byte a byte con el documento de Home. Como Home puede no estar —una CI
que solo clone este repositorio, o un `pip install` de alguien de fuera— **se salta entero** con un
aviso bien visible. En la maquina de desarrollo, donde los repositorios viven juntos, corre siempre.

Es el mismo montaje que `test/openapi_freshness.test.ts` en PlanVortexNode, y a proposito: las tres
copias del documento tienen que ser el mismo fichero, y con dos librerias es justo lo que puede
dejar de cumplirse en silencio.

Lo que este test NO cubre es que el spec corresponda al servidor: eso lo vigila
`openapi_parity.test.ts` en PlanVortexServer, que recorre `src/routes/*.ts` de verdad.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_models  # noqa: E402

ORIGEN = generate_models.origen_del_bundle()
# Una URL no se comprueba aqui: este test corre en cada `pytest` y no puede depender de la red.
DISPONIBLE = not generate_models.es_remoto(ORIGEN) and Path(ORIGEN).exists()

if not DISPONIBLE:
    # Sin este aviso el test se salta sin que nadie se entere, que es justo el fallo que existe
    # para evitar.
    print(
        f"[openapi_freshness] SALTADO: no encuentro el documento en {ORIGEN}. Clona "
        "PlanVortexHome al lado, o apunta PLANVORTEX_OPENAPI a su public/openapi.json.",
        file=sys.stderr,
    )


@pytest.mark.skipif(not DISPONIBLE, reason=f"PlanVortexHome no esta en {ORIGEN}")
def test_la_copia_es_el_documento_que_home_sirve_hoy() -> None:
    """Byte a byte. Si esto falla: `uv run python scripts/generate_models.py` y commitea los dos
    ficheros que salen. Y si lo que ha cambiado es el spec, en Home hace falta antes su
    `npm run openapi:bundle`.
    """
    upstream = Path(ORIGEN).read_bytes()
    commiteado = generate_models.BUNDLE.read_bytes()

    assert upstream == commiteado
