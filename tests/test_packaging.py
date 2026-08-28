"""Lo que el paquete promete de si mismo, comprobado contra los metadatos INSTALADOS.

No se lee `pyproject.toml`: se lee lo que `importlib.metadata` ve, que es lo que de verdad viaja en
la wheel y lo que un integrador tiene delante. Un pyproject correcto y una wheel mal construida se
parecen mucho hasta que alguien instala el paquete.

Lo que estos tests NO pueden ver es el interior del archivo `.whl` —si `py.typed` acabo dentro, si
`twine` lo aprueba—, porque aqui el paquete esta instalado en modo editable y apunta al arbol de
fuentes. Eso es cosa de `scripts/check_packaging.py`, que construye de verdad y abre la wheel.
"""

from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path

import planvortex

DISTRIBUTION = "planvortex"


def nombre_del_requisito(requisito: str) -> str:
    """El nombre de un requisito PEP 508, sin su especificador de version.

    Ojo con el atajo obvio, `rstrip("<>=0123456789.,")`: se lleva por delante el 2 de `httpx2` y
    deja `httpx`, que es precisamente el paquete que NO queremos. Costo un fallo desconcertante la
    primera vez que se ejecuto este fichero.
    """
    coincidencia = re.match(r"[A-Za-z0-9._-]+", requisito)
    if coincidencia is None:
        raise AssertionError(f"Requisito ilegible en los metadatos: {requisito!r}")
    return coincidencia.group(0)


def test_publica_la_misma_version_que_el_paquete() -> None:
    """`__version__` y la version de los metadatos son la misma.

    No es cosmetico: `__version__` acabara viajando en el `User-Agent` de cada peticion, asi que un
    numero viejo ahi es un numero viejo en nuestros logs justo el dia que haga falta saber que
    version esta fallando. Y el workflow de release compara el tag contra `pyproject.toml`, no
    contra el modulo: sin este test, las dos mitades pueden separarse sin que nadie lo note.
    """
    assert planvortex.__version__ == importlib.metadata.version(DISTRIBUTION)


def test_una_sola_dependencia_de_runtime_sin_condiciones() -> None:
    """`httpx2` en todas las versiones, y nada mas.

    Es la decision 1 del roadmap y la unica que se aparto de la libreria de Node, que no tiene
    ninguna. Una libreria de integracion que arrastra quince transitivas es una libreria que da
    problemas de auditoria en casa del cliente, asi que otra dependencia hay que justificarla en el
    roadmap ANTES de anadirla — y este test es lo que obliga a pasar por ahi.

    Las dependencias de desarrollo van en un `[dependency-groups]` (PEP 735) justamente para que no
    aparezcan aqui: un grupo no viaja en los metadatos, un `extra` si.
    """
    requires = importlib.metadata.requires(DISTRIBUTION) or []
    sin_marcador = [requisito for requisito in requires if ";" not in requisito]

    assert sorted(nombre_del_requisito(requisito) for requisito in sin_marcador) == ["httpx2"]


def test_typing_extensions_solo_donde_hace_falta() -> None:
    """La segunda entrada, que la decision 5 del roadmap ya anunciaba, y su marcador.

    Los TypedDict generados usan `NotRequired`, que no esta en `typing` hasta 3.11: sin esto, en
    3.10 el paquete se instala y NO se importa. De 3.11 en adelante no se instala nada, porque
    `_generated/models.py` elige la rama con `sys.version_info`.

    **El marcador es la mitad que importa.** Sin el seria una dependencia de verdad en las cinco
    versiones de la matriz, y eso es lo que la decision 1 no permite. Y declararla, en vez de
    heredarla de `httpx2` —que hoy la arrastra en `python_version < '3.13'`—, es lo que impide que
    el paquete deje de importarse en 3.10 el dia que `httpx2` cambie de opinion.
    """
    requires = importlib.metadata.requires(DISTRIBUTION) or []
    con_marcador = {
        nombre_del_requisito(requisito): requisito.split(";", 1)[1].strip()
        for requisito in requires
        if ";" in requisito
    }

    assert list(con_marcador) == ["typing-extensions"]
    # Las comillas del marcador las normaliza el backend de construccion, asi que se comparan sin
    # ellas: lo que importa es la condicion, no como acabo escrita en los metadatos.
    assert con_marcador["typing-extensions"].replace("'", '"') == 'python_version < "3.11"'


def test_el_suelo_es_python_310() -> None:
    """3.10 o superior, y esta escrito en los metadatos.

    Es el suelo de `httpx2` y de `datamodel-code-generator`, y es lo que trae Ubuntu 22.04 LTS. Sin
    esta linea, `pip` instalaria el paquete en un 3.9 y el fallo apareceria mas tarde y en otro
    sitio: un `X | Y` en una anotacion evaluada en runtime, con un `TypeError` sin contexto.
    """
    assert importlib.metadata.metadata(DISTRIBUTION)["Requires-Python"] == ">=3.10"


def test_py_typed_existe_y_esta_vacio() -> None:
    """El marcador de PEP 561, dentro del paquete y de cero bytes.

    Sin el, mypy y pyright tratan `planvortex` como `Any` de arriba abajo y toda la fase de tipos no
    le llega al integrador. No es una comprobacion de forma: el fichero tiene que estar VACIO —lo que
    lleva dentro no lo lee nadie— y tiene que estar dentro del paquete, no al lado.

    Que ademas acabe dentro de la wheel lo comprueba `scripts/check_packaging.py`; aqui solo se
    vigila que no desaparezca del arbol de fuentes, que es la forma barata de perderlo.
    """
    marcador = Path(planvortex.__file__).parent / "py.typed"
    assert marcador.is_file()
    assert marcador.stat().st_size == 0
