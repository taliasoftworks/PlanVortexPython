"""Comprueba que la wheel que se publicaria HOY sirve, y sobre todo que lleva sus tipos dentro.

    uv run python scripts/check_packaging.py

En Node esto lo hacian `publint` y `arethetypeswrong`: dos herramientas que abren el paquete y
avisan de un `exports` mal montado antes de que lo descubra alguien con un `require()`. **En Python
no existe el equivalente**, asi que el guardia hay que montarlo, y es este fichero.

Lo que vigila, en orden, es una cadena en la que cada eslabon tapa lo que el anterior no ve:

1. `uv build` construye wheel y sdist de verdad;
2. `twine check --strict` — lo unico que avisa de un README que PyPI no sabe renderizar. Ese fallo
   no rompe la instalacion: deja la ficha del paquete en blanco, no se ve hasta que esta publicada,
   y una version de PyPI no se puede reemplazar;
3. la wheel se ABRE y se comprueba que `planvortex/py.typed` esta dentro;
4. se instala en un venv limpio FUERA del repositorio y se importa;
5. mypy `--strict` contra ese venv, dos veces.

El paso 5 es el que no se puede saltar, y va doble a proposito (§ Trampa P4 del roadmap):

- un fragmento CORRECTO tiene que pasar. Es lo que de verdad detecta un `py.typed` que no llego:
  sin el, mypy no da "todo bien", da *"Skipping analyzing planvortex: module is installed, but
  missing library stubs or py.typed marker"*, que es un error;
- un fragmento con un error de tipo DELIBERADO tiene que fallar. Sin esta segunda mitad, la primera
  se podria aprobar con un mypy que no esta mirando nada.

Comprobar solo el fragmento malo seria peor que no comprobar: sin `py.typed` tambien falla —por el
motivo equivocado— y el guardia daria verde justo en el caso que existe para detectar.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"

# Un `str` donde va un `str`: tiene que pasar. Si esto falla, es que mypy no ve las anotaciones.
FRAGMENTO_CORRECTO = """
import planvortex

version: str = planvortex.__version__
print(version)
"""

# Un `str` donde va un `int`: tiene que fallar. Si esto pasa, es que mypy no esta analizando nada.
FRAGMENTO_ROTO = """
import planvortex

version: int = planvortex.__version__
print(version)
"""


class EmpaquetadoError(Exception):
    """Algo del empaquetado no cumple. El mensaje dice que, y que hacer."""


def ejecutar(orden: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    print(f"  $ {' '.join(orden)}")
    return subprocess.run(orden, cwd=cwd, capture_output=True, text=True, check=False)


def exigir(resultado: subprocess.CompletedProcess[str], que: str) -> None:
    if resultado.returncode != 0:
        raise EmpaquetadoError(f"{que}\n\n{resultado.stdout}\n{resultado.stderr}")


def construir() -> tuple[Path, Path]:
    """`uv build` sobre un `dist/` vacio, para no colar el artefacto de una version anterior."""
    if DIST.exists():
        shutil.rmtree(DIST)
    exigir(ejecutar(["uv", "build"], cwd=ROOT), "`uv build` no ha podido construir el paquete.")

    wheels = sorted(DIST.glob("*.whl"))
    sdists = sorted(DIST.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise EmpaquetadoError(
            f"Esperaba una wheel y un sdist en {DIST}, y hay {len(wheels)} y {len(sdists)}."
        )
    return wheels[0], sdists[0]


def revisar_con_twine(wheel: Path, sdist: Path) -> None:
    exigir(
        ejecutar(["uv", "tool", "run", "twine", "check", "--strict", str(wheel), str(sdist)], cwd=ROOT),
        "`twine check --strict` ha rechazado los artefactos. Casi siempre es el README: PyPI no lo\n"
        "sabe renderizar y publicaria la ficha en blanco, sin posibilidad de reemplazarla.",
    )


def exigir_py_typed(wheel: Path) -> None:
    """El marcador de PEP 561, DENTRO del `.whl`.

    Que este en `src/` no significa que viaje: basta un `exclude` en la configuracion de hatchling,
    o cambiar de backend, para que se quede fuera. Y no lo nota nadie, porque el paquete se instala
    y se importa igual de bien.
    """
    with zipfile.ZipFile(wheel) as archivo:
        nombres = archivo.namelist()
        if "planvortex/py.typed" not in nombres:
            raise EmpaquetadoError(
                "La wheel no lleva `planvortex/py.typed`. Sin el, mypy y pyright ven el paquete\n"
                "como `Any` de arriba abajo y toda la fase de tipos no le llega al integrador.\n"
                f"Lo que si lleva: {sorted(nombres)}"
            )
        if archivo.getinfo("planvortex/py.typed").file_size != 0:
            raise EmpaquetadoError("`py.typed` tiene que estar vacio: nadie lee lo que lleve dentro.")


def python_del_venv(venv: Path) -> Path:
    ejecutable = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not ejecutable.exists():
        raise EmpaquetadoError(f"El venv de {venv} no ha dejado un interprete en {ejecutable}.")
    return ejecutable


def comprobar_instalacion(wheel: Path, taller: Path) -> Path:
    """Instala la wheel en un venv limpio y FUERA del repositorio, y la importa.

    Fuera del repositorio a proposito: desde dentro, `import planvortex` encontraria `src/` por el
    camino de busqueda y esto daria verde sin haber instalado nada.
    """
    venv = taller / "venv"
    exigir(ejecutar(["uv", "venv", str(venv)]), "No he podido crear el venv limpio.")
    interprete = python_del_venv(venv)

    exigir(
        ejecutar(["uv", "pip", "install", "--python", str(interprete), str(wheel)]),
        "La wheel no se ha podido instalar en un entorno limpio.",
    )
    exigir(
        ejecutar([str(interprete), "-c", "import planvortex; print(planvortex.__version__)"], cwd=taller),
        "La wheel se instala pero `import planvortex` no funciona.",
    )
    return interprete


def comprobar_tipos(interprete: Path, taller: Path) -> None:
    """mypy `--strict` contra el venv limpio: el correcto pasa, el roto falla."""
    # Config propia y minima: con la del repositorio, mypy heredaria su `files` y acabaria
    # analizando `src/` en vez del paquete instalado, que es justo lo que NO se quiere mirar aqui.
    config = taller / "mypy.ini"
    config.write_text("[mypy]\nstrict = True\n", encoding="utf8")

    correcto = taller / "usa_bien.py"
    correcto.write_text(FRAGMENTO_CORRECTO, encoding="utf8")
    roto = taller / "usa_mal.py"
    roto.write_text(FRAGMENTO_ROTO, encoding="utf8")

    orden = ["mypy", "--strict", "--config-file", str(config), "--python-executable", str(interprete)]

    bien = ejecutar([*orden, str(correcto)], cwd=taller)
    if bien.returncode != 0:
        raise EmpaquetadoError(
            "mypy rechaza un uso CORRECTO del paquete instalado. Casi siempre significa que\n"
            "`py.typed` no llego a la wheel y mypy se niega a analizarla:\n\n"
            f"{bien.stdout}\n{bien.stderr}"
        )

    mal = ejecutar([*orden, str(roto)], cwd=taller)
    if mal.returncode == 0:
        raise EmpaquetadoError(
            "mypy APRUEBA un error de tipo plantado a proposito (`int = planvortex.__version__`).\n"
            "Si esto pasa, no esta analizando el paquete y la comprobacion anterior no valia nada."
        )
    print("  mypy detecta el error plantado, como tiene que ser.")


def main() -> int:
    print("planvortex: comprobando el empaquetado\n")
    try:
        print("1/5  construyendo")
        wheel, sdist = construir()
        print(f"     {wheel.name}\n     {sdist.name}\n")

        print("2/5  twine check --strict")
        revisar_con_twine(wheel, sdist)
        print("     los artefactos son publicables\n")

        print("3/5  py.typed dentro de la wheel")
        exigir_py_typed(wheel)
        print("     esta, y vacio\n")

        with tempfile.TemporaryDirectory(prefix="planvortex-pkg-") as temporal:
            taller = Path(temporal)

            print("4/5  instalando en un venv limpio")
            interprete = comprobar_instalacion(wheel, taller)
            print("     instala e importa\n")

            print("5/5  mypy --strict contra el paquete instalado")
            comprobar_tipos(interprete, taller)
    except EmpaquetadoError as fallo:
        print(f"\nFALLA: {fallo}", file=sys.stderr)
        return 1

    print("\nTodo correcto: la wheel es publicable y lleva sus tipos dentro.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
