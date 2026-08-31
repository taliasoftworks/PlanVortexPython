"""La cobertura de rutas, que es la afirmacion que vende la libreria: la API publica ENTERA.

`scripts/route_coverage.py` recorre el bundle del OpenAPI y `src/planvortex/resources/*.py`, y
compara las dos en las dos direcciones. Aqui se ejecuta en cada `pytest` para que la afirmacion no
dependa de que alguien se acuerde de lanzar el script, y para que anadir un endpoint al spec sin
anadir el metodo se ponga rojo en el momento en que se actualiza la copia del spec.

Y hay una tercera cosa que se comprueba aqui y el script no puede: que el metodo exista **en los dos
clientes**. El script lee la fuente asincrona; que el gemelo se haya generado con esos metodos lo
dice el propio objeto.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from planvortex import AsyncPlanVortex, PlanVortex

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import route_coverage  # noqa: E402

# Los catorce recursos y como se llama cada uno en el cliente. Escrita a mano a proposito: es la
# lista de lo que la libreria PROMETE, y su parecido con `resources/*.py` es lo que se comprueba.
RECURSOS = (
    "accounts",
    "ai_plans",
    "apps",
    "catalog",
    "clients",
    "comments",
    "contacts",
    "dashboard",
    "integrations",
    "messages",
    "organizations",
    "products",
    "publications",
    "uploads",
)


def test_no_queda_ninguna_ruta_del_alcance_sin_metodo() -> None:
    """115 de 115. Si esto falla, el mensaje dice exactamente cual falta.

    Las dos ultimas son `archive` y `unarchive` de un plan de IA: son DOS rutas y no un cuerpo con
    un booleano, asi que el alcance crece de dos en dos cuando aparece una pareja de estas.
    """
    sin_cubrir, _, total = route_coverage.informe()

    assert total == 115, "el alcance ha cambiado de tamano: mira si el spec ha crecido"
    assert not sin_cubrir, "rutas del spec que ningun recurso construye:\n" + "\n".join(
        str(operacion) for operacion in sin_cubrir
    )


def test_ningun_recurso_construye_una_ruta_que_el_spec_no_declara() -> None:
    """La direccion que de verdad se paga: una ruta inventada da un 404 en produccion y verde aqui,
    porque el banco de pruebas contesta lo que se le diga.
    """
    _, inventadas, _ = route_coverage.informe()

    assert not inventadas, "rutas que la libreria construye y el spec no tiene:\n" + "\n".join(
        str(operacion) for operacion in inventadas
    )


@pytest.mark.parametrize("recurso", RECURSOS)
def test_los_dos_clientes_ofrecen_el_recurso(recurso: str) -> None:
    asincrono = AsyncPlanVortex(access_token="token")
    sincrono = PlanVortex(access_token="token")

    assert hasattr(asincrono, recurso), f"AsyncPlanVortex no tiene {recurso}"
    assert hasattr(sincrono, recurso), f"PlanVortex no tiene {recurso}"

    # Y los mismos metodos publicos en los dos, con `aiterate` -> `iterate` como unica diferencia.
    de_async = {
        nombre.replace("aiterate", "iterate", 1)
        for nombre in dir(getattr(asincrono, recurso))
        if not nombre.startswith("_")
    }
    de_sync = {nombre for nombre in dir(getattr(sincrono, recurso)) if not nombre.startswith("_")}
    assert de_async == de_sync


def test_los_recursos_del_cliente_son_los_modulos_de_resources() -> None:
    """Un modulo nuevo en `resources/` que nadie cuelga del cliente no lo cubre este test por
    casualidad: sus rutas contarian como cubiertas en el script y no existirian para el integrador.
    """
    modulos = {
        fichero.stem
        for fichero in route_coverage.RECURSOS.glob("*.py")
        if fichero.stem not in {"__init__", "base"}
    }

    assert modulos == set(RECURSOS)
