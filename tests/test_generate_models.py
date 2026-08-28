"""El generador de los tipos, y los guardias que impiden que escriba uno roto.

Lo que la CI comprueba es que lo commiteado corresponda al spec (`git diff --exit-code`), y
`tests/test_models.py` comprueba que los tipos correspondan al bundle. Aqui se comprueba lo tercero:
que **los guardias del generador saltan**. Un guardia que nunca se ha visto fallar no es un guardia,
y estos dos existen para fallos que no rompen nada visiblemente:

- `_id` saneado a `field_id`, que produce un fichero perfecto que declara un campo inexistente;
- `typing_extensions` importado a pelo, que se instala bien y no se importa en 3.13 ni en 3.14.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import generate_models  # noqa: E402

CABECERA_DE_IMPORTS = """import sys
from typing import Any, Literal, TypeAlias

if sys.version_info >= (3, 11):
    from typing import NotRequired, TypedDict
else:
    from typing_extensions import NotRequired, TypedDict
"""


def test_el_guardia_salta_si_el_generador_vuelve_a_sanear_el_id() -> None:
    """§ Trampa P1, provocada a proposito.

    Es LA comprobacion de esta fase: sin ella, un cambio de opcion del generador dejaria
    `field_id` en los ~40 esquemas y todo —el linter, mypy, la CI— seguiria en verde.
    """
    roto = f"{CABECERA_DE_IMPORTS}\n\nclass Publication(TypedDict):\n    field_id: str\n"

    with pytest.raises(generate_models.GeneracionError, match="field_id"):
        generate_models.exigir_id_intacto(roto)


def test_el_guardia_salta_si_no_queda_ni_un_id() -> None:
    """La otra mitad: un fichero sin un solo `_id` no es un fichero limpio, es uno sin la clave
    primaria de todos los recursos de la API.
    """
    sin_id = f"{CABECERA_DE_IMPORTS}\n\nclass Publication(TypedDict):\n    text: str\n"

    with pytest.raises(generate_models.GeneracionError, match="_id"):
        generate_models.exigir_id_intacto(sin_id)


def test_el_guardia_tambien_rechaza_lo_que_ni_siquiera_compila() -> None:
    """Un nombre que no es un identificador valido produce esto, y `ast` es quien lo ve."""
    with pytest.raises(generate_models.GeneracionError, match="no es Python valido"):
        generate_models.exigir_id_intacto("class Publication(TypedDict):\n    2fa: str\n")


def test_el_id_de_verdad_pasa() -> None:
    """El caso bueno, para que los dos de arriba signifiquen algo."""
    generate_models.exigir_id_intacto(
        f"{CABECERA_DE_IMPORTS}\n\nclass Publication(TypedDict):\n    _id: str\n"
    )


def test_la_reescritura_deja_los_dos_nombres_detras_de_la_guarda() -> None:
    """`TypedDict` y `NotRequired` van los DOS o ninguno.

    Coger `NotRequired` de `typing_extensions` y dejar `TypedDict` en `typing` es exactamente la
    mezcla que en 3.10 da todas las claves por obligatorias: no falla, informa mal.
    """
    generado = (
        "from typing import Any, Literal, TypeAlias, TypedDict\n\nfrom typing_extensions import NotRequired\n"
    )

    reescrito = generate_models.reescribir_imports(generado)

    assert "from typing import Any, Literal, TypeAlias\n" in reescrito
    assert "if sys.version_info >= (3, 11):" in reescrito
    assert "    from typing import NotRequired, TypedDict" in reescrito
    assert "    from typing_extensions import NotRequired, TypedDict" in reescrito
    assert reescrito.startswith("import sys\n")


def test_la_reescritura_avisa_si_el_generador_cambia_de_donde_importa() -> None:
    """Callarse aqui seria publicar un paquete que no se importa en dos versiones de la matriz."""
    with pytest.raises(generate_models.GeneracionError, match="guarda de version"):
        generate_models.reescribir_imports("from typing import TypedDict\n")


def test_la_cabecera_dice_que_es_generado_y_como_rehacerlo() -> None:
    """Lo unico que impide que alguien lo edite a mano y pierda el cambio al regenerar."""
    assert "NO SE EDITA A MANO" in generate_models.CABECERA
    assert "scripts/generate_models.py" in generate_models.CABECERA


def test_el_generador_pide_el_prefijo_vacio_y_no_da_por_hecho_el_de_por_defecto() -> None:
    """La opcion de la que depende toda la § Trampa P1, fijada aqui para que quitarla se note.

    Va emparejada: `--special-field-name-prefix` seguido de la cadena vacia. Un dia alguien
    ordenara esta tupla y las dos se separaran.
    """
    opciones = list(generate_models.OPCIONES)
    posicion = opciones.index("--special-field-name-prefix")

    assert opciones[posicion + 1] == ""


def test_el_generador_no_pone_marca_de_tiempo_ni_deja_el_futuro_importado() -> None:
    """Las dos opciones que no son de estilo.

    `--disable-timestamp` porque lo que vigila la CI es que el diff este vacio, y una marca de
    tiempo lo mueve en cada ejecucion. `--disable-future-imports` porque con el `from __future__
    import annotations` las anotaciones se quedan en cadenas y `__optional_keys__` sale vacio en
    todas las versiones — mypy acierta igual y solo miente la introspeccion.
    """
    assert "--disable-timestamp" in generate_models.OPCIONES
    assert "--disable-future-imports" in generate_models.OPCIONES
