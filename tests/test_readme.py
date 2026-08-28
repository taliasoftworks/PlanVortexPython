"""El README, contra el paquete que describe.

El README es lo primero que se lee y lo unico que mucha gente lee. Tiene dos trozos que no son prosa
sino DATOS copiados —la tabla de rangos de error y la lista de ejemplos—, y un dato copiado se queda
atras sin sintoma: nadie revisa un `git diff` de un `.md` buscando un rango que ya no existe.

Asi que se comparan, igual que el mapa camelCase de la § Trampa P2 y las formas de `_shapes.py`. Lo
que NO se comprueba aqui es la prosa: para eso esta el criterio de la fase 10, que es que alguien que
no conoce el producto publique su primer post siguiendo solo el README.
"""

from __future__ import annotations

import re
from pathlib import Path

from planvortex import PLANVORTEX_ERROR_RANGES
from planvortex._core.errors import error_class_for_code

RAIZ = Path(__file__).resolve().parent.parent
README = (RAIZ / "README.md").read_text(encoding="utf8")

# `| 500-544 | `auth` | `AuthError` |`, y tambien la fila doble de `plan_limit`.
FILA = re.compile(r"^\| (\d[\d\-, ]*) \| `(\w+)` \| `(\w+)` \|$", re.MULTILINE)


def _tabla_del_readme() -> list[tuple[str, str, str]]:
    return [(codigos, familia, clase) for codigos, familia, clase in FILA.findall(README)]


def test_la_tabla_de_errores_dice_los_rangos_que_publica_el_paquete() -> None:
    """Los numeros, en las dos direcciones.

    Un rango nuevo en el servidor que no llegue aqui es una familia que el README no menciona, y un
    rango que se quede en el README despues de desaparecer es peor: manda a capturar una excepcion
    que ya no llega nunca.
    """
    del_readme = {codigos for codigos, _, _ in _tabla_del_readme()}
    assert del_readme, "la tabla de errores del README no se encuentra: ha cambiado de formato"

    # `plan_limit` son DOS rangos en una sola fila, porque catalogar dos veces la misma familia con
    # la misma excepcion seria ruido. Se junta igual que en el README para poder compararlos.
    por_familia: dict[str, list[str]] = {}
    for rango in PLANVORTEX_ERROR_RANGES:
        por_familia.setdefault(rango.family, []).append(f"{rango.start}-{rango.end}")
    del_paquete = {", ".join(rangos) for rangos in por_familia.values()}

    assert del_readme == del_paquete


def test_cada_fila_nombra_la_excepcion_que_de_verdad_se_lanza() -> None:
    """La columna que se usa para escribir un `except`, comprobada contra el mapa real.

    Tres familias —`general`, `role` y `payment`— no tienen clase propia y salen como la base. Que
    el README lo diga es la mitad util de la tabla: quien busque un `RoleError` no lo encontraria.
    """
    for codigos, familia, clase in _tabla_del_readme():
        primero = int(codigos.split("-")[0])
        real = error_class_for_code(primero)
        assert real.__name__ == clase, f"{codigos} ({familia}) lanza {real.__name__}, no {clase}"
        assert real.__module__.startswith("planvortex"), clase


def test_los_ejemplos_de_la_tabla_existen_y_no_falta_ninguno() -> None:
    """La lista de ejemplos, contra `examples/`.

    En las dos direcciones a proposito: un enlace roto se ve al pulsarlo, pero un ejemplo NUEVO que
    nadie anade al README no se ve nunca — y la fase 10 anadio tres de golpe.
    """
    citados = set(re.findall(r"examples/(\w+\.py)", README))
    en_disco = {fichero.name for fichero in (RAIZ / "examples").glob("*.py")}

    assert citados == en_disco
