"""El mapa camelCase contra el OpenAPI, en las dos direcciones.

§ Trampa P2. La API tiene cinco parametros que no van en snake_case, y en Python el argumento
publico tiene que ser `get_use` mientras que en el cable viaja `getUse`. El problema no es
traducirlos: es que **filtrar por un parametro que el servidor no lee devuelve la lista entera sin
avisar de nada**. Un `?account_type=facebook` que el backend ignora no da error; da todas las
cuentas, y el integrador se entera semanas despues. Ya paso en la libreria de Node.

Por eso este test no comprueba una lista escrita a mano: recorre el bundle del OpenAPI commiteado y
exige que **todo parametro camelCase del spec este en el mapa** y que **todo lo que hay en el mapa
siga existiendo en el spec**. La segunda mitad importa tanto como la primera: un parametro que el
servidor retira deja en la libreria una traduccion que ya no traduce nada.

El roadmap hablaba de CUATRO. Recorriendo el spec aparecieron CINCO: `forceDelete`, en
`DELETE /organizations/{id}/uploads/{id_upload}`, no estaba en la lista — comprobado ademas contra
`src/domain/services/uploads/index.ts` del servidor, que lo lee de `req.query`. Habra un sexto, y
por eso la comprobacion se hace asi y no repasando una tabla.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from planvortex._core.query import CAMEL_CASE_PARAMS, WIRE_TO_PYTHON, encode_query

OPENAPI = Path(__file__).resolve().parent.parent / "openapi" / "planvortex.openapi.json"
HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
ES_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


def _resolver(spec: dict[str, Any], parametro: dict[str, Any]) -> dict[str, Any]:
    """Un parametro puede venir por `$ref` a `components`. Se sigue una vez, que es lo que hay."""
    referencia = parametro.get("$ref")
    if not isinstance(referencia, str):
        return parametro
    _, _, seccion, nombre = referencia.split("/")
    resuelto = spec["components"][seccion][nombre]
    assert isinstance(resuelto, dict)
    return resuelto


def _parametros_del_spec() -> set[str]:
    """Todos los nombres de parametro que declara el bundle, sin repetir."""
    spec = json.loads(OPENAPI.read_text(encoding="utf8"))
    nombres: set[str] = set()

    for item in spec["paths"].values():
        candidatos: list[dict[str, Any]] = list(item.get("parameters", []))
        for metodo, operacion in item.items():
            if metodo in HTTP_METHODS:
                candidatos.extend(operacion.get("parameters", []))
        for parametro in candidatos:
            resuelto = _resolver(spec, parametro)
            nombre = resuelto.get("name")
            if isinstance(nombre, str):
                nombres.add(nombre)

    return nombres


def test_el_spec_no_ha_estrenado_un_camelcase_que_no_conocemos() -> None:
    """Cualquier parametro del spec que no sea snake_case tiene que estar traducido."""
    sin_traducir = sorted(
        nombre
        for nombre in _parametros_del_spec()
        if not ES_SNAKE_CASE.match(nombre) and nombre not in WIRE_TO_PYTHON
    )

    # Si esto falla: anade el parametro a CAMEL_CASE_PARAMS en `_core/query.py`. NO lo apanes en el
    # metodo que lo necesite — el siguiente que aparezca se olvidaria.
    assert sin_traducir == []


def test_el_mapa_no_traduce_parametros_que_ya_no_existen() -> None:
    """La direccion contraria: una traduccion huerfana es una promesa de algo que no esta."""
    declarados = _parametros_del_spec()
    huerfanos = sorted(wire for wire in WIRE_TO_PYTHON if wire not in declarados)

    assert huerfanos == []


def test_son_exactamente_los_cinco_que_hay_hoy() -> None:
    """La foto de hoy, para que un sexto se note como un cambio y no como un descuido.

    Este test SI se puede actualizar a mano — pero solo despues de que los dos de arriba pasen, que
    son los que dicen si el sexto es real.
    """
    assert sorted(CAMEL_CASE_PARAMS) == [
        "force_delete",
        "get_use",
        "limit_organizations",
        "offset_organizations",
        "order_by_publish",
    ]


def test_el_mapa_es_biyectivo() -> None:
    """Dos argumentos Python apuntando al mismo nombre del cable se pisarian en silencio."""
    assert len(WIRE_TO_PYTHON) == len(CAMEL_CASE_PARAMS)


def test_los_cinco_se_traducen_al_codificar() -> None:
    """El mapa no sirve de nada si el codificador no lo usa."""
    codificado = dict(encode_query(dict.fromkeys(CAMEL_CASE_PARAMS, "x")))
    assert sorted(codificado) == sorted(CAMEL_CASE_PARAMS.values())


def test_lo_que_ya_es_snake_case_no_se_toca() -> None:
    """La suerte de esta API: ninguno de sus snake_case choca con una palabra reservada de Python."""
    assert encode_query({"social_network": "instagram", "from_date": "2026-01-01"}) == [
        ("social_network", "instagram"),
        ("from_date", "2026-01-01"),
    ]
